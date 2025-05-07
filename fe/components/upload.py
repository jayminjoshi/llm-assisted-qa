from google.cloud import storage, pubsub_v1
from processing import Database
from datetime import datetime
from loguru import logger
from config import config
from pathlib import Path

import streamlit as st
import pandas as pd
import io
import os
import json

class UploadPage:

    def __init__(self, db: Database):
        self.db = db
        # self.llm = llm
        # self.search = search
        self.urls = []
        self.env = os.environ['ENV']

    def show(self):
        col1, col2 = st.columns([6, 1])
        with col1:
            st.title("Historic RFPs and Supporting Documents")
        with col2:
            if st.button("🔄 Refresh"):
                st.rerun()
        
        # File uploader
        uploaded_files = st.file_uploader("Choose file/s", accept_multiple_files=True, 
                                          type=['xlsx', 'xls', 'csv', 'txt', 'pdf', 'pptx', 'docx', 'doc'])
        
        # URL input section
        col1, col2 = st.columns([3, 1])
        with col1:
            url = st.text_input("Enter URL")
        with col2:
            if st.button("Add Link"):
                if url:
                    if url not in self.urls:
                        self.urls.append(url)
                        st.success("URL added successfully!")
                    else:
                        st.warning("URL already exists!")
                else:
                    st.warning("Please enter a URL first")
        
        # Display added URLs with remove buttons
        if self.urls:
            st.write("Added URLs:")
            for i, url in enumerate(self.urls):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"- {url}")
                with col2:
                    if st.button("Remove", key=f"remove_{i}"):
                        self.urls.remove(url)
                        st.rerun()

        # Show total count of files to be processed
        total_files = len(uploaded_files or []) + len(self.urls)
        if total_files > 0:
            st.markdown(f"<p style='color: #ffd700;'>Total files to be processed: {total_files}</p>", unsafe_allow_html=True)
        
        # Process button
        process_button = st.button("Process")
        
        if process_button:
            if not uploaded_files and not self.urls:
                st.error("Please upload a file or enter a link")
                return
            
            try:
                # Upload files to GCP
                gcp_paths = []
                for file in uploaded_files:
                    bucket, gcp_path = self._upload_to_gcp(file)
                    gcp_paths.append({
                        "bucket": bucket,
                        "path": gcp_path,
                        "type": Path(uploaded_files[0].name).suffix[1:]
                    })
                
                # Send to processing API
                self._send_to_processing_api(self.urls, gcp_paths)
                
            except Exception as e:
                st.error(f"Error during processing: {str(e)}")

    def _upload_to_gcp(self, file):
        """
        Uploads a file to the bucket.
        
        Args:
            file (file): The file to upload.
        
        Returns:
            str: The path to the uploaded file in the bucket.
        """
        
        logger.info(f"Uploading file {file.name} to {config['env'][self.env]['GCP_BUCKET']}.")
        storage_client = storage.Client()
        bucket = storage_client.bucket(config['env'][self.env]['GCP_BUCKET'])
        project_name = self.db.get_project_by_id(st.session_state['current_project_id'])['name']
        gcp_path = f"{st.session_state['username']}/{project_name}/{file.name}" # Path to be stored at
        blob = bucket.blob(gcp_path)
        
        blob.upload_from_file(file)

        logger.info(f"File {file.name} uploaded to {config['env'][self.env]['GCP_BUCKET']}.")

        return config['env'][self.env]['GCP_BUCKET'], gcp_path
    
    def _send_to_processing_api(self, urls, gcp_files):
        """Send URLs and GCP paths to processing via Pub/Sub"""
        
        user = self.db.get_user_by_username(st.session_state['username'])
        user_id = user['id']
        
        # Initialize Pub/Sub client
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(
            config['env'][self.env]['GCP_PROJECT'], 
            config['env'][self.env]['GCP_PUBSUB_TOPIC']
        )
        
        try:
            if gcp_files:
                payload = {
                    "gcp_files": gcp_files,
                    "project_id": st.session_state['current_project_id'],
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                    "request_type": "document_process"  # Add request type
                }

                logger.info(f"Publishing payload to Pub/Sub: {payload}")

                future = publisher.publish(
                    topic_path,
                    json.dumps(payload).encode("utf-8")
                )
                
                try:
                    message_id = future.result()  # Wait for message to be published
                    logger.info(f"Sent message to Pub/Sub with ID: {message_id}")
                    st.success(f"File/s sent for processing, you can check status in the home page.")
                except Exception as e:
                    st.error("Unable to process file, please try again later.")
                    logger.exception(f"Failed to publish message: {str(e)}")
            
            if urls:
                payload = {
                    "urls": urls,
                    "project_id": st.session_state['current_project_id'],
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                    "request_type": "crawl"  # Add request type
                }

                future = publisher.publish(
                    topic_path,
                    json.dumps(payload).encode("utf-8")
                )

                try:
                    future.result()  # Wait for message to be published
                    st.success("Link/s sent for processing, you can check status in the home page")
                except Exception as e:
                    st.error("Unable to process links, please try again later")
                    logger.exception(f"Failed to publish message: {str(e)}")

        except Exception as e:
            st.error("Unable to process files/links, please try again later")
            logger.exception("Pub/Sub publishing error")