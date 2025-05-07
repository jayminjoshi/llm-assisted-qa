from google.cloud import pubsub_v1
from processing import Database
from config import config
from loguru import logger

import streamlit as st
import json
import time
import os

class ProjectHomePage:
    def __init__(self, db: Database):
        self.db = db
        self.env = os.environ['ENV']

    def show(self):
        # Get project details
        project = self.db.get_project_by_id(st.session_state['current_project_id'])
        if not project:
            st.error("Project not found")
            return
        
        # Title and refresh button in the same row
        col1, col2 = st.columns([6, 1])
        with col1:
            st.title(f"{project['name']}")
            st.caption("All times are in UTC")
        with col2:
            if st.button("🔄 Refresh", key="refresh_project_home"):
                st.rerun()
        
        # Add spacing after title
        st.write("")
            
        # Get user_id from session state
        user = self.db.get_user_by_username(st.session_state['username'])
        if not user:
            st.error("User not found")
            return
            
        # Get files for this project
        files = self.db.get_project_files(project['id'], user['id'])
        
        if files:
            # Create table header
            col1, col2, col3, col4, col5, col6 = st.columns([1, 3, 2, 2, 2, 1])
            with col1:
                st.write("**Sr. No.**")
            with col2:
                st.write("**File Name**")
            with col3:
                st.write("**Type**")
            with col4:
                st.write("**Created At**")
            with col5:
                st.write("**Status**")
            with col6:
                st.write("**Actions**")
            
            # Add spacing after header
            st.write("")
            
            # Display file rows
            for idx, file in enumerate(files, 1):
                col1, col2, col3, col4, col5, col6 = st.columns([1, 3, 2, 2, 2, 1])
                with col1:
                    st.write(idx)
                with col2:
                    if file['type'] == 'website':
                        st.write(file['link'])
                    else:
                        st.write(file['name'])
                with col3:
                    st.write(file['type'])
                with col4:
                    st.write(file['index_started_at'].strftime("%Y-%m-%d %H:%M"))
                with col5:
                    if file['is_indexed']:
                        st.markdown("✅", unsafe_allow_html=True)
                    elif file['index_failed_at']:
                        st.markdown("❌", unsafe_allow_html=True)
                    else:
                        st.markdown("⏳", unsafe_allow_html=True)
                with col6:
                    if st.button("Delete", key=f"delete_{file['id']}"):
                        try:
                            # Initialize Pub/Sub client
                            publisher = pubsub_v1.PublisherClient()
                            topic_path = publisher.topic_path(
                                config['env'][self.env]['GCP_PROJECT'], 
                                config['env'][self.env]['GCP_PUBSUB_TOPIC']
                            )

                            # Prepare payload
                            payload = {
                                "user_id": user['id'],
                                "file_id": file['id'],
                                "request_type": "document_delete"
                            }

                            # Publish message
                            future = publisher.publish(
                                topic_path,
                                json.dumps(payload).encode("utf-8")
                            )
                            
                            try:
                                future.result()  # Wait for message to be published
                                logger.info(f"File deletion message published successfully for file {file['id']}")
                                # Immediately refresh the page to remove the row
                                st.rerun()
                            except Exception as e:
                                st.error("Error deleting file")
                                logger.error(f"Failed to publish file deletion message: {str(e)}")
                                
                        except Exception as e:
                            logger.exception(f"Error deleting file {file['id']}")
                            st.error(f"Error: {str(e)}")
        else:
            st.info("No files uploaded yet, additional documents help in generating accurate and relevant RFP responses.")
