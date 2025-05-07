from typing import Dict, List, Union, Any
from .base_extractor import BaseExtractor

import pandas as pd
import uuid
import os

class ExcelExtractor(BaseExtractor):
    def __init__(self):
        """Initialize the Excel/CSV extractor"""
        super().__init__()
        self.supported_formats = ['.xlsx', '.xls', '.csv']
        self.chunk_size = 1000  # Number of cells to include in each chunk

    def validate_file(self, file_path: str) -> bool:
        """
        Validate if the file is an Excel/CSV file
        
        Args:
            file_path: Path to the Excel/CSV file
        Returns:
            Boolean indicating if file is valid
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported file format. Supported formats: {self.supported_formats}")
        
        return True

    def read_file(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """
        Read Excel/CSV file into pandas DataFrames
        
        Args:
            file_path: Path to the file
        Returns:
            Dictionary of sheet names and their corresponding DataFrames
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.csv':
            # For CSV, create a single sheet dictionary
            return {'Sheet1': pd.read_csv(file_path)}
        else:
            # For Excel, read all sheets
            return pd.read_excel(file_path, sheet_name=None)

    def process_dataframe(self, df: pd.DataFrame):
        """
        Process a DataFrame into chunks of text, with each row as a separate chunk
        including its own header
        
        Args:
            df: Pandas DataFrame to process
        Returns:
            List of text chunks, one per row
        """
        chunks = []

        # Process each row as a separate chunk
        for idx, row in df.iterrows():
            
            row_text = ""
            for header, row in row.items():
                if not pd.isna(row):
                    row_text += f"{header}: \n{row}\n\n"
                else:
                    row_text += f"{header}: \nNone\n\n"
            chunks.append(row_text)
        
        return chunks

    def extract_content(self, file_path: str) -> List[Dict[str, Union[int, str]]]:
        """
        Extract content from Excel/CSV file
        
        Args:
            file_path: Path to the Excel/CSV file
        Returns:
            List of dictionaries containing sheet information and content
        """
        self.validate_file(file_path)
        sheets_data = self.read_file(file_path)
        content = []
        
        for sheet_name, df in sheets_data.items():
            chunks = self.process_dataframe(df)
            
            for chunk_number, chunk_content in enumerate(chunks, 1):
                content.append({
                    'sheet_name': sheet_name,
                    'chunk_number': chunk_number,
                    'total_chunks': len(chunks),
                    'content': chunk_content
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
        Extract content from Excel/CSV file in Qdrant format
        
        Args:
            file_path: Path to the Excel/CSV file
            project_id: Project identifier
            user_id: User identifier
            file_id: File identifier
            
        Returns:
            List of documents with page_content and metadata
        """
        content = self.extract_content(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
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
                    "file_type": file_ext[1:],  # Remove the dot from extension
                    "sheet_name": item['sheet_name'],
                    "chunk_number": item['chunk_number'],
                    "total_chunks": item['total_chunks']
                }
            }

            self.insert_vector(document)
            documents.append(document)
        
        return documents