from utils.extractor_factory import ExtractorFactory
from services import VectorSearchService

from datetime import datetime, timezone
from utils.gcp import GCPStorageClient
from utils.database import Database

import os

class DocumentService:
    def __init__(self):
        self.vector_search_service = VectorSearchService()
        self.gcp_client = GCPStorageClient()
        self.db = Database.get_instance()
    
    def process_document(
        self,
        bucket: str,
        gcp_file_path: str,
        file_type: str,
        project_id: int,
        user_id: int,
    ) -> bool:
        extractor = ExtractorFactory.get_extractor(file_type)
        
        try:
            # Insert into DB
            file_id = self.db.insert_file(
                project_id=project_id,
                user_id=user_id,
                type=file_type,
                filename=os.path.basename(gcp_file_path),
                gcp_path=gcp_file_path,
                bucket=bucket
            )

            # Download file to temp
            tmp_file_path = self.gcp_client.download_blob_to_temp(bucket, gcp_file_path)

            documents = extractor.extract_documents(
                file_path=tmp_file_path,
                project_id=project_id,
                user_id=user_id,
                file_id=file_id,
            )
            
            # Update vectors in Vector Search and vector metadata in DB
            is_indexed = self.vector_search_service.insert(
                documents=documents
            )
            
            # Update DB
            self.db.update_file_indexing_status(
                file_id=file_id,
                is_indexed=is_indexed,
                completed_at=datetime.now(timezone.utc)
            )

            # Cleanup temp file
            self.gcp_client.cleanup_temp_file(tmp_file_path)
            
            # Insert into Qdrant
            return is_indexed
        
        except Exception as e:
            # Update DB
            self.db.update_file_indexing_status(
                file_id=file_id,
                is_indexed=False,
                completed_at=datetime.now(timezone.utc)
            )
            raise