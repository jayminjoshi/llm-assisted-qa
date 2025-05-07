from typing import Dict, List, Any
from .base_extractor import BaseExtractor

import uuid
import re

class WebsiteExtractor(BaseExtractor):
    def __init__(self):
        """Initialize the Website extractor"""
        super().__init__()
        self.supported_formats = ['html', 'htm', 'website']
        self.chunk_size = 3500  # Characters per chunk (max embedding model token limit is 2048)

    def validate_content(self, content: str) -> bool:
        """
        Validate if the content is not empty
        
        Args:
            content: Raw markdown content
        Returns:
            Boolean indicating if content is valid
        """
        if not content or not content.strip():
            raise ValueError("Empty content provided")
        return True

    def chunk_content(self, text: str) -> List[str]:
        """
        Split content into chunks of reasonable size
        
        Args:
            text: Text content to chunk
        Returns:
            List of text chunks
        """
        text = text.strip()
        chunks = []
        
        # Process the text in chunks of exactly 1000 characters
        for i in range(0, len(text), self.chunk_size):
            chunk = text[i:i + self.chunk_size].strip()
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)
        
        return chunks

    def extract_content(self, raw_markdown: str) -> List[Dict[str, Any]]:
        """
        Extract and chunk content from markdown
        
        Args:
            raw_markdown: Raw markdown content from crawler
        Returns:
            List of dictionaries containing chunk information
        """
        self.validate_content(raw_markdown)
        chunks = self.chunk_content(raw_markdown)
        
        return [
            {
                'content': chunk,
                'chunk_number': i,
                'total_chunks': len(chunks)
            }
            for i, chunk in enumerate(chunks, 1)
        ]

    def extract_documents(
        self,
        file_path: str,  # In this case, this will be the URL
        project_id: int,
        user_id: int,
        file_id: int,
        raw_markdown: str = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Extract content from website in Qdrant format
        
        Args:
            file_path: URL of the website
            project_id: Project identifier
            user_id: User identifier
            file_id: File identifier
            raw_markdown: Raw markdown content from crawler
            
        Returns:
            List of documents with page_content and metadata
        """
        content = self.extract_content(raw_markdown)
        documents = []
        
        for item in content:
            document = {
                "vector_id": str(uuid.uuid4()),
                "page_content": item['content'],
                "metadata": {
                    "project_id": project_id,
                    "user_id": user_id,
                    "file_id": file_id,
                    "file_type": "website",
                    "url": file_path,
                    "chunk_number": item['chunk_number'],
                    "total_chunks": item['total_chunks']
                }
            }
            
            self.insert_vector(document)
            documents.append(document)
        
        return documents     