# from sentence_transformers import SentenceTransformer

# from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchText, MatchValue
# from qdrant_client import QdrantClient

from typing import List, Dict
from loguru import logger
from config import config

import uuid
import os

class QdrantService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QdrantService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.env = os.environ['ENV']
        self.model = SentenceTransformer(config['env'][self.env]['MODEL_NAME'])
        self.client = QdrantClient(config['env'][self.env]['QDRANT_HOST'], 
                                 port=config['env'][self.env]['QDRANT_PORT'])
        self.collection_name = config['env'][self.env]['QDRANT_COLLECTION_NAME']
        self._initialized = True
    
    def search(self, query: str, user_id: int, project_id: int, limit: int = 1) -> str:
        """
        Search for the most relevant documents in the collection
        
        Args:
            query (str): The query to search for
            limit (int): The number of results to return
            
        Returns:
            str: The most relevant document
        """
        query = f"query: {query}"
        vector = self.model.encode(query, normalize_embeddings=True)
        
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            query_filter={
                "must": [
                    {
                        "key": "metadata.user_id",
                        "match": {"value": user_id}
                    },
                    {
                        "key": "metadata.project_id",
                        "match": {"value": project_id}
                    }
                ]
            },
            limit=limit
        )
        
        return search_results[0].payload["page_content"]
    
    def insert(self, payloads: List[Dict]):
        """
        Insert a list of payloads into the collection
        
        Args:
            payloads (list): List of dicts with page_content and metadata.

        Returns:
            bool: True if the insertion was successful, False otherwise
        """

        try:
            vector_ids=[str(uuid.uuid4()) for _ in range(len(payloads))]

            self.client.upload_points(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=vector_ids[idx],
                        vector= self.model.encode(point['page_content'], normalize_embeddings=True),
                        payload={"page_content": point['page_content'], "metadata": point['metadata']}
                    )
                    for idx, point in enumerate(payloads)
                ]
            )

            return True
    
        except Exception as e:
            logger.exception(f"Error inserting payloads : {e}")
           
            return False
    
    def delete(self, file_id: int, user_id: int):

        self.client.delete(collection_name=self.collection_name,
                           points_selector=Filter(
                                    must=[
                                        FieldCondition(
                                            key='metadata.user_id',
                                            match=MatchValue(value=int(user_id))
                                        ),
                                        FieldCondition(
                                            key='metadata.file_id',
                                            match=MatchValue(value=int(file_id))
                                        )
                                    ]
                                )
                            )