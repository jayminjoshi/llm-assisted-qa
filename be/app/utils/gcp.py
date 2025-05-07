# app/utils/gcp.py

from google.api_core.exceptions import NotFound
from google.cloud import storage

from typing import Optional
from loguru import logger
from pathlib import Path
from config import config

import os


class GCPStorageClient:
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize GCP Storage client
        
        Args:
            credentials_path (str, optional): Path to GCP credentials JSON file.
                If None, will use default credentials.
        """
        self.env = os.environ['ENV']
        if credentials_path:
            self.client = storage.Client.from_service_account_json(credentials_path)
        else:
            self.client = storage.Client(
                project=config['env'][self.env]['GCP_PROJECT_ID'],
            )

    def download_blob_to_temp(
        self,
        bucket: str,
        gcp_file_path: str,
    ) -> str:
        """
        Downloads a file from GCP Storage to a temporary file
        
        Args:
            gcp_file_path (str): Path to the file in the bucket. Eg gs://dev/user_id/project_id/file_name.pptx
            prefix (str): Prefix for the temporary file name
            
        Returns:
            str: Path to the temporary file
            
        Raises:
            Exception: If download fails
        """
        
        try:
            # Get bucket and blob
            bucket = self.client.bucket(bucket)
            blob = bucket.blob(gcp_file_path)
            
            # Convert to Path object and split parts
            parts = Path(gcp_file_path).parts
            
            # For meaningful filenames, so we don't end up with empty folders.
            user_id = parts[0]
            project_name = parts[1]
            file_name = parts[-1]

            # Download to temporary file
            temp_file_path = os.path.join("/tmp", f"{user_id}_{project_name}_{file_name}")
            blob.download_to_filename(temp_file_path)
            
            return temp_file_path
            
        except Exception as e:
            raise Exception(f"Failed to download file: {str(e)}")
    
    def cleanup_temp_file(self, temp_file_path: str) -> None:
        """
        Removes the temporary file
        
        Args:
            temp_file_path (str): Path to the temporary file to remove
        """
        try:
            logger.info(f"Removing temporary file: {temp_file_path}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.info(f"Temporary file removed: {temp_file_path}")
            else:
                logger.info(f"Temporary file not found: {temp_file_path}")
        
        except Exception as e:
            logger.exception(f"Warning: Failed to remove temporary file {temp_file_path}: {str(e)}")
    
    def _upload_to_gcp(self, filename, bucket, username, project_name):
        
        """
        Uploads a file to the bucket.
        
        Args:
            file (file): The file to upload.
        
        Returns:
            str: The path to the uploaded file in the bucket.
        """
        
        logger.info(f"Uploading file {filename} to {bucket}.")
        
        bucket = self.client.bucket(bucket)
        gcp_path = f"{username}/{project_name}/rfp_processed/{filename}" # Path to be stored at
        blob = bucket.blob(gcp_path)
        
        blob.upload_from_filename(f"/tmp/{filename}")

        logger.info(f"File {filename} uploaded to {bucket}.")

        return gcp_path
    
    def delete_file(self, bucket: str, gcp_file_path: str) -> None:
        """
        Deletes a file from the bucket.
        
        Args:
            bucket (str): Name of the GCP bucket
            gcp_file_path (str): Path to the file in the bucket
            
        Returns:
            None
            
        Raises:
            Exception: If deletion fails for reasons other than file not found
        """
        if gcp_file_path is None or bucket is None:
            logger.warning(f"GCP file path or bucket is None. Skipping this step... File path: {gcp_file_path} Bucket: {bucket}")
            return
        
        try:
            bucket = self.client.bucket(bucket)
            blob = bucket.blob(gcp_file_path)
            blob.delete()
            logger.info(f"Successfully deleted file: {gcp_file_path} from bucket: {bucket}")
            
        except NotFound:
            logger.warning(f"File not found: {gcp_file_path} in bucket: {bucket}. Skipping this step...")
            # Don't raise an error since the end goal (file not existing) is achieved
            
        except Exception as e:
            logger.error(f"Error deleting file: {gcp_file_path} from bucket: {bucket}")
            raise Exception(f"Failed to delete file: {str(e)}")
