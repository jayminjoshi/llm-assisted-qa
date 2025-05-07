from typing import Dict, List, Union, Any
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
from pathlib import Path

from .base_extractor import BaseExtractor

import pytesseract
import uuid
import os

class PDFExtractor(BaseExtractor):
    def __init__(self):
        """Initialize the PDF extractor"""
        super().__init__()
        self.supported_formats = ['.pdf']
    
    def validate_file(self, file_path: str) -> bool:
        """
        Validate if the file is a PDF
        :param file_path: Path to the PDF file
        :return: Boolean indicating if file is valid
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported file format. Supported formats: {self.supported_formats}")
        
        return True

    def extract_text_with_ocr(self, file_path: str) -> str:
        """Extract text using OCR when regular extraction fails"""
        pages = convert_from_path(file_path, dpi=200)
        text_data = ''
        for page in pages:
            text = pytesseract.image_to_string(page)
            text_data += text + '\n'
        return text_data.strip()

    def extract_content(self, file_path: str) -> List[Dict[str, Union[int, str]]]:
        """
        Extract content from PDF file
        :param file_path: Path to the PDF file
        :return: List of dictionaries containing page numbers and content
        """
        self.validate_file(file_path)
        reader = PdfReader(file_path)
        content = []

        for page_number, page in enumerate(reader.pages, 1):
            # Try regular text extraction first
            text = page.extract_text().strip()
            
            # If no text was extracted, try OCR
            if not text:
                text = self.extract_text_with_ocr(file_path)
            
            content.append({
                'content': text,
                'chunk_number': page_number,
            })

        return content

    def extract_documents(
        self, 
        file_path: str, 
        project_id: int, 
        user_id: int,
        file_id: int
    ) -> List[Dict[str, Any]]:
        """
        Extract content from PDF file in Qdrant format
        
        Args:
            file_path (str): Path to the PDF file
            project_id (int): Project identifier
            user_id (int): User identifier
            file_id (int): File identifier
            
        Returns:
            List[Dict]: List of documents with page_content and metadata
        """
        content = self.extract_content(file_path)
        documents = []
        
        for item in content:
            vector_id = str(uuid.uuid4())
            document = {
                "page_content": item['content'],
                "vector_id": vector_id,
                "metadata": {
                    "project_id": project_id,
                    "user_id": user_id,
                    "file_id": file_id,
                    "file_type": "pdf",
                    "chunk_number": item['chunk_number'],
                    "total_chunks": len(content)
                },
            }

            self.insert_vector(document)
            documents.append(document)
        
        return documents 