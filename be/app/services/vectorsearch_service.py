from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import MatchNeighbor
from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import Namespace
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel, TextEmbedding
from google.cloud.aiplatform.compat.types import (  # type: ignore[attr-defined, unused-ignore]
    matching_engine_index as meidx_types,
)
from google.cloud import aiplatform

from utils.database import Database
from typing import List, Dict, Any
from loguru import logger
from config import config

import math
import os
import time

class VectorSearchService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorSearchService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.env = os.environ['ENV']

        # Initialize Vertex AI
        aiplatform.init(
            project=config['env'][self.env]['GCP_PROJECT_ID'],
            location=config['env'][self.env]['GCP_LOCATION']
        )
        
        self.model = TextEmbeddingModel.from_pretrained(config['env'][self.env]['GCP_EMBEDDING_MODEL_NAME'])
        
        # Get the index instance
        self.index = aiplatform.MatchingEngineIndex(
            index_name=config['env'][self.env]['GCP_VECTOR_SEARCH_INDEX_NAME']
        )
        self.index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=config['env'][self.env]['GCP_VECTOR_SEARCH_INDEX_ENDPOINT_NAME']
        )
        self.deployed_index_id = config['env'][self.env]['GCP_VECTOR_SEARCH_DEPLOYED_INDEX_ID']

        # Database
        self.db = Database.get_instance()
        
        self._initialized = True
    
    def prepare_vector_search_datapoints(
        self,
        embeddings: List[TextEmbedding],
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Prepare datapoints for Vector Search insertion
        
        Args:
            documents (List[Dict]): List of documents with metadata
            embeddings (List[List[float]]): List of embeddings for each document
            
        Returns:
            DicSequence[IndexDatapoint]: Formatted datapoints for Vector Search
        """
        
        datapoints = []
        
        for doc, embedding in zip(documents, embeddings):
            # Prepare restricts for filtering
            restricts = [
                meidx_types.IndexDatapoint.Restriction(
                    namespace="file_type",
                    allow_list=[doc['metadata']['file_type']]
                ),
                meidx_types.IndexDatapoint.Restriction(
                    namespace="project_id",
                    allow_list=[str(doc['metadata']['project_id'])]
                ),
                meidx_types.IndexDatapoint.Restriction(
                    namespace="user_id",
                    allow_list=[str(doc['metadata']['user_id'])]
                ),
                meidx_types.IndexDatapoint.Restriction(
                    namespace="file_id",
                    allow_list=[str(doc['metadata']['file_id'])]
                ),
                meidx_types.IndexDatapoint.Restriction(
                    namespace="chunk_number",
                    allow_list=[str(doc['metadata']['chunk_number'])]
                )
            ]

            # Add optional sheet_name restrict if present
            if 'sheet_name' in doc['metadata']:
                restricts.append(
                    meidx_types.IndexDatapoint.Restriction(
                        namespace="sheet_name",
                        allow_list=[doc['metadata']['sheet_name']]
                    )
                )
            

            datapoint = meidx_types.IndexDatapoint(
                datapoint_id=doc['vector_id'],
                feature_vector=embedding.values,
                restricts=restricts
            )

            datapoints.append(datapoint)
            
        return datapoints
    
    def search(self, query: str, user_id: int, project_id: int, limit: int = 5) -> List[MatchNeighbor]:
        """
        Search for the most relevant documents in the index
        
        Args:
            query (str): The query to search for
            user_id (int): User ID for filtering
            project_id (int): Project ID for filtering
            limit (int): Number of results to return
            
        Returns:
            List[Dict]: List of matched documents with scores
        """
        try:
            # Encode query
            input = [TextEmbeddingInput(query, "QUESTION_ANSWERING")]
            
            # Add retry mechanism with exponential backoff for embedding generation
            max_retries = 5
            base_sleep_time = 20  # seconds
            for retry in range(max_retries):
                try:
                    embedding = self.model.get_embeddings(input, output_dimensionality=768)
                    query_vector = embedding[0].values
                    break
                except Exception as e:
                    if retry == max_retries - 1:  # Last retry
                        raise e
                    
                    sleep_time = base_sleep_time * (2 ** retry)  # Exponential backoff
                    logger.warning(f"Rate limit hit while generating embeddings, retrying in {sleep_time} seconds... (Attempt {retry + 1}/{max_retries})")
                    time.sleep(sleep_time)
            
            # Prepare restrictions for filtering
            filter = [
                Namespace(
                    name="project_id",
                    allow_tokens=[str(project_id)],
                    deny_tokens=[]
                ),
                Namespace(
                    name="user_id",
                    allow_tokens=[str(user_id)],
                    deny_tokens=[]
                )
            ]
            
            # Add retry mechanism with exponential backoff for search
            for retry in range(max_retries):
                try:
                    response = self.index_endpoint.find_neighbors(
                        deployed_index_id=self.deployed_index_id,
                        queries=[query_vector],
                        num_neighbors=limit,
                        filter=filter,
                        return_full_datapoint=True
                    )
                    return response[0]
                except Exception as e:
                    if retry == max_retries - 1:  # Last retry
                        raise e
                    
                    sleep_time = base_sleep_time * (2 ** retry)  # Exponential backoff
                    logger.warning(f"Rate limit hit while searching, retrying in {sleep_time} seconds... (Attempt {retry + 1}/{max_retries})")
                    time.sleep(sleep_time)
            
        except Exception as e:
            logger.exception(f"Error searching vector index: {e}")
            return []

    def insert(self, documents: Dict[str, Any]) -> bool:
        """
        Insert documents into the vector index
        
        Args:
            documents (List[Dict]): List of documents with page_content and metadata
            
        Returns:
            bool: True if insertion was successful, False otherwise
        """
        try:
            # Generate embeddings for all documents
            embeddings = []
            batch_size = 2
            texts = [doc['page_content'] for doc in documents]
            number_of_batches = math.ceil(len(texts) / batch_size)
            batch_number = 0
            
            # Generate embeddings in batches
            for i in range(0, len(texts), batch_size):
                batch_number += 1
                logger.debug(f"Generating embeddings for batch {batch_number} out of {number_of_batches}")

                batch_texts = texts[i:i + batch_size]
                batch_inputs = [TextEmbeddingInput(text, "RETRIEVAL_DOCUMENT") for text in batch_texts]
                
                # Add retry mechanism with exponential backoff
                max_retries = 3
                base_sleep_time = 20  # seconds
                for retry in range(max_retries):
                    try:
                        batch_embeddings = self.model.get_embeddings(
                            batch_inputs, 
                            output_dimensionality=768, 
                            auto_truncate=False
                        )
                        embeddings.extend(batch_embeddings)
                        break
                    except Exception as e:
                        if retry == max_retries - 1:  # Last retry
                            raise e
                        
                        sleep_time = base_sleep_time * (2 ** retry)  # Exponential backoff
                        logger.warning(f"Rate limit hit, retrying in {sleep_time} seconds... (Attempt {retry + 1}/{max_retries})")
                        time.sleep(sleep_time)

            # Prepare datapoints
            datapoints = self.prepare_vector_search_datapoints(embeddings, documents)

            # Upsert datapoints to the index
            self.index.upsert_datapoints(datapoints=datapoints)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error inserting documents: {e}")
            return False
    
    def delete(self, file_id: int, user_id: int) -> bool:
        """
        Delete documents from the vector index
        
        Args:
            file_id (int): ID of the file whose vectors to delete
            user_id (int): ID of the user who owns the file
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            # Get vector IDs from database
            vector_records = self.db.get_vectors_by_file(file_id, user_id)
            if not vector_records:
                return True  # No vectors to delete
                
            # Delete from Vector Search
            vector_ids = [record['vector_id'] for record in vector_records]
            self.index.remove_datapoints(datapoint_ids=vector_ids)
            
            # Delete from database
            self.db.delete_vectors_by_file(file_id, user_id)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error deleting documents: {e}")
            return False