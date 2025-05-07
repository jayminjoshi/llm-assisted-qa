from google.cloud import storage, pubsub_v1
from processing import Database
from datetime import datetime
from loguru import logger
from config import config

import streamlit as st
import pandas as pd
import json
import os


class RFPPage:
    def __init__(self, db: Database):
        self.db = db
        self.env = os.environ['ENV']

    def show(self):
        st.title("RFP Processing")

        # File uploader specifically for Excel files
        uploaded_file = st.file_uploader(
            "Upload RFP Excel File", 
            type=['xlsx', 'xls'],
            help="Please upload an Excel file containing RFP requirements",
            accept_multiple_files=False
        )

        if uploaded_file:
            # Show preview of the Excel file
            try:
                df = pd.read_excel(uploaded_file)
                st.write("Preview of uploaded RFP:")
                st.dataframe(df.head())

                # Additional input fields
                rfp_name = st.text_input("RFP Name", value=uploaded_file.name.split('.')[0])

                if st.button("Process RFP"):
                    self._process_rfp(uploaded_file, rfp_name)

            except Exception as e:
                st.error(f"Error reading Excel file: {str(e)}")

    def _process_rfp(self, file, rfp_name):
        
        try:
            
            # Get user details
            user = self.db.get_user_by_username(st.session_state['username'])
            project = self.db.get_project_by_id(st.session_state['current_project_id'])

            # Reset file pointer to beginning before upload
            file.seek(0)
            
            bucket, gcp_path = self._upload_to_gcp(file, project['name'])
            
            if not user:
                st.error("User not found. Please log in again.")
                return

            # Prepare payload
            payload = {
                "rfp_name": rfp_name,
                "bucket": bucket,
                "gcp_path": gcp_path,
                "project_id": st.session_state['current_project_id'],
                "project_name": project['name'],
                "user_id": user['id'],
                "username": st.session_state['username'],
                "timestamp": datetime.now().isoformat(),
                "request_type": "rfp"
            }

            # Initialize Pub/Sub client
            publisher = pubsub_v1.PublisherClient()
            topic_path = publisher.topic_path(
                config['env'][self.env]['GCP_PROJECT'], 
                config['env'][self.env]['GCP_PUBSUB_TOPIC']
            )

            # Publish message
            future = publisher.publish(
                topic_path,
                json.dumps(payload).encode("utf-8")
            )
            
            try:
                future.result()  # Wait for message to be published
                logger.info(f"RFP {rfp_name} sent for processing")
                st.success("RFP sent for processing. You can check the status in the project home page.")
                
            except Exception as e:
                st.error("Failed to send RFP for processing. Please try again.")
                logger.error(f"Failed to publish message: {str(e)}")

        except Exception as e:
            st.error(f"Error processing RFP: {str(e)}")
            logger.exception("Error in RFP processing") 
        

    def _upload_to_gcp(self, file, project_name: str):
        """
        Uploads a file to the bucket.
        
        Args:
            file (file): The file to upload.
            project_name (str): The name of the project.
            
        Returns:
            str: The path to the uploaded file in the bucket.
        """
        
        logger.info(f"Uploading file {file.name} to {config['env'][self.env]['GCP_BUCKET']}.")
        storage_client = storage.Client()
        bucket = storage_client.bucket(config['env'][self.env]['GCP_BUCKET'])
        gcp_path = f"{st.session_state['username']}/{project_name}/rfp_to_process/{file.name}" # Path to be stored at
        blob = bucket.blob(gcp_path)
        
        blob.upload_from_file(file)

        logger.info(f"File {file.name} uploaded to {config['env'][self.env]['GCP_BUCKET']}.")

        return config['env'][self.env]['GCP_BUCKET'], gcp_path