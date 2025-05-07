from google.cloud import storage
from processing import Database
from loguru import logger

import streamlit as st
import os

class ProcessedRFPsPage:
    def __init__(self, db: Database):
        self.db = db
        self.env = os.environ['ENV']

    def download_file(self, bucket_name, file_path):
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(file_path)
            
            # Create a temporary file and download
            temp_path = f"/tmp/{os.path.basename(file_path)}"
            blob.download_to_filename(temp_path)
            
            with open(temp_path, "rb") as file:
                content = file.read()
            
            # Clean up temp file
            os.remove(temp_path)
            return content
            
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            return None

    def show(self):
        # Create title and refresh button in the same row
        col1, col2 = st.columns([6, 1])
        with col1:
            st.title('Processed RFPs')
            st.caption("All times are in UTC")
        with col2:
            if st.button("🔄 Refresh", key="refresh_rfps"):
                st.rerun()
        
        # Add spacing after title
        st.write("")
        
        # Get user_id and project_id from session state
        user = self.db.get_user_by_username(st.session_state['username'])
        project_id = st.session_state.get('current_project_id')
        
        if not user or not project_id:
            st.error("User or project not found. Please return to home page.")
            return
            
        # Get RFPs for the current project and user
        rfps = self.db.get_rfps_by_project_and_user(project_id, user['id'])
        
        if rfps:
            # Create table header
            col1, col2, col3 = st.columns([2, 2, 2])
            with col1:
                st.write("**RFP Name**")
            with col2:
                st.write("**Status**")
            with col3:
                st.write("**Preview**")
            
            # Add spacing after header
            st.write("")
            
            # Display RFP rows
            for rfp in rfps:
                col1, col2, col3 = st.columns([2, 2, 2])
                
                with col1:
                    st.write(rfp['name'])
                with col2:
                    status = rfp['status'].capitalize()
                    if status == 'Processing':
                        st.markdown(f"<span style='color: #FFA500'>{status}</span>", unsafe_allow_html=True)
                    elif status == 'Failed':
                        st.markdown(f"<span style='color: #FF0000'>{status}</span>", unsafe_allow_html=True)
                    elif status == 'Completed':
                        st.markdown(f"<span style='color: #008000'>{status}</span>", unsafe_allow_html=True)
                    else:
                        st.write(status)
                with col3:
                    if rfp['status'] == 'completed' and rfp['processed_file_path']:
                        if st.button("Download Excel", key=f"download_{rfp['id']}"):
                            file_content = self.download_file(rfp['bucket'], rfp['processed_file_path'])
                            if file_content:
                                st.download_button(
                                    label="Save Excel",
                                    data=file_content,
                                    file_name=os.path.basename(rfp['processed_file_path']),
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key=f"save_{rfp['id']}"
                                )
                            else:
                                st.error("Error downloading file")
                    else:
                        st.write("NA")
        else:
            st.info("No RFPs found for this project.") 