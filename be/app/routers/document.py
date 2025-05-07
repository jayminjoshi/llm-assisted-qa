from services import DocumentService, VectorSearchService
from utils import GCPStorageClient, Database
from pydantic import BaseModel
from typing import List, Dict
from loguru import logger
from tqdm import tqdm

class DocumentRequest(BaseModel):
    project_id: int
    user_id: int
    timestamp: str
    gcp_files: List[Dict[str, str]]

class DeleteRequest(BaseModel):
    file_id: int
    user_id: int

class DeleteProjectRequest(BaseModel):
    project_id: int
    user_id: int


class DocumentRouter:

    def __init__(self):
        self.document_service = DocumentService()
        self.vector_search_service = VectorSearchService()
        self.gcp_client = GCPStorageClient()
        self.db = Database.get_instance()

    def process_document(
        self,
        request: DocumentRequest
    ):
        logger.debug(f"Recieved request: {request}")
        
        try:
            project_id = request['project_id']
            user_id = request['user_id']
            
            for gcp_file in request['gcp_files']:
                
                bucket = gcp_file['bucket']
                gcp_file_path = gcp_file['path']
                type = gcp_file['type']

                success = self.document_service.process_document(
                    bucket=bucket,
                    gcp_file_path=gcp_file_path,
                    file_type=type,
                    project_id=project_id,
                    user_id=user_id
                )

            if not success:
                raise 

            return {"message": "Document processed and inserted successfully"}
        
        except Exception as e:
            logger.exception("Error processing document")
            raise

    def delete_document(
        self,
        request: DeleteRequest
    ):
        logger.debug(f"Recieved request: {request}")

        try:

            logger.info("Deleting file from GCP")
            bucket, gcp_file_path = self.db.get_file_gcp_details(
                file_id=request['file_id'],
                user_id=request['user_id']
            )
            self.gcp_client.delete_file(
                bucket=bucket,
                gcp_file_path=gcp_file_path
            )

            logger.info("Deleting file from Vector Search and vector metadata from DB")
            self.vector_search_service.delete(
                file_id=request['file_id'],
                user_id=request['user_id']
            )

            logger.info("Removing file from database")
            self.db.delete_file(
                file_id=request['file_id'],
                user_id=request['user_id']
            )
        
        except Exception as e:

            logger.exception("Error deleting file")
            raise

    def delete_project(
        self,
        request: DeleteProjectRequest
    ):
        logger.debug(f"Recieved request: {request}")

        try:

            logger.debug("Getting all files for project")
            files = self.db.get_project_files(request['project_id'], request['user_id'])
            project = self.db.get_project_by_id(request['project_id'])

            logger.info(f"Deleting all file/s from GCP for project {project['name']}")
            for file in tqdm(files):
                bucket, gcp_file_path = self.db.get_file_gcp_details(
                    file_id=file['id'],
                    user_id=request['user_id']
                )
                self.gcp_client.delete_file(
                    bucket=bucket,
                    gcp_file_path=gcp_file_path
                )

                logger.info("Deleting file from Vector Search and vector metadata from DB")
                self.vector_search_service.delete(
                    file_id=file['id'],
                    user_id=request['user_id']
                )
                
                logger.info("Removing file from database")
                self.db.delete_file(
                    file_id=file['id'],
                    user_id=request['user_id']
                )

            logger.info(f"Deleting project {project['name']}")
            self.db.delete_project(request['project_id'], request['user_id'])
        
        except Exception as e:

            logger.exception("Error deleting project")
            raise