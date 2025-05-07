from typing import List, Dict, Any
from abc import ABC, abstractmethod

from utils.database import Database


class BaseExtractor(ABC):

    def __init__(self):
        self.db = Database.get_instance()
    
    @abstractmethod
    def extract_documents(
        self, 
        file_path: str, 
        project_id: int, 
        user_id: int,
        file_id: int,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Extract content and format for Vector Search insertion"""
        pass
    
    def insert_vector(self, document: Dict[str, Any]):
        """
        Insert chunk into the database

        Args:
            documents (Dict[str, Any]): List of documents with page_content and metadata
        Returns:
            None
        """
        vector_id = document['vector_id']
        file_id = document['metadata']['file_id']
        user_id = document['metadata']['user_id']
        project_id = document['metadata']['project_id']
        text = document['page_content']
        chunk_number = document['metadata']['chunk_number']
        file_type = document['metadata']['file_type']
        sheet_name = document['metadata'].get('sheet_name', None)

        self.db.insert_vector(
            vector_id=vector_id,
            file_id=file_id,
            user_id=user_id,
            project_id=project_id,
            text=text,
            chunk_number=chunk_number,
            file_type=file_type,
            sheet_name=sheet_name
        )
        