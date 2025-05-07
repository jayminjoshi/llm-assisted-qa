from google.cloud import pubsub_v1
from processing import Database
from config import config
from loguru import logger

import streamlit as st
import time
import json
import os

class HomePage:
    def __init__(self, db: Database):
        self.db = db
        self.env = os.environ['ENV']

    def show(self):
        # Title and refresh button in the same row
        col1, col2 = st.columns([6, 1])
        with col1:
            st.title('Welcome to LLM Assisted Q&A')
        with col2:
            if st.button("🔄 Refresh", key="refresh_home"):
                st.rerun()
                
        # Add spacing after title
        st.write("")
        
        # Get user_id from session state
        user = self.db.get_user_by_username(st.session_state['username'])
        if not user:
            st.error("User not found. Please log in again.")
            return
            
        # Create New Project button
        if st.button("Create New Project"):
            st.session_state['show_project_form'] = True
            
        # Show project creation form OR projects list
        if st.session_state.get('show_project_form', False):
            # Add Back button
            if st.button("Back"):
                st.session_state['show_project_form'] = False
                st.rerun()
                
            with st.form("new_project_form"):
                project_name = st.text_input("Name")  
                project_domain = st.selectbox(
                    "Domain",
                    options=[
                        "Construction",
                        "IT Services",
                        "Healthcare",
                        "Education",
                        "Transportation",
                        "Energy",
                        "Other"
                    ]
                )
                st.markdown("*This will be used while generating LLM Responses*")

                # Add spacing before submit button
                st.write("")
                st.write("")
                submitted = st.form_submit_button("Submit")
                
                if submitted and project_name:
                    try:
                        self.db.create_project(user['id'], project_name, project_domain)
                        st.success("Project created successfully!")
                        st.session_state['show_project_form'] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating project: {str(e)}")
        else:
            # Display existing projects
            projects = self.db.get_user_projects(user['id'])
            
            if projects:
                # Create a table header
                col1, col2, col3 = st.columns([1, 3, 2])
                with col1:
                    st.write("**Sr. No.**")
                with col2:
                    st.write("**Project Name**")
                with col3:
                    st.markdown("**Actions**")
                
                # Display project rows
                for idx, project in enumerate(projects, 1):
                    col1, col2, col3 = st.columns([1, 3, 2])
                    with col1:
                        st.write(idx)
                    with col2:
                        st.write(project['name'])
                    with col3:
                        # Create two buttons side by side in the Actions column
                        button_col1, button_col2 = st.columns(2)
                        with button_col1:
                            if st.button("Go To Project", key=f"view_{project['id']}"):
                                st.session_state['current_project_id'] = project['id']
                                st.session_state['current_page'] = 'Project'
                        with button_col2:
                            if st.button("Delete", key=f"delete_{project['id']}", type="secondary"):
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
                                        "project_id": project['id'],
                                        "request_type": "project_delete"
                                    }

                                    # Publish message
                                    future = publisher.publish(
                                        topic_path,
                                        json.dumps(payload).encode("utf-8")
                                    )
                                    
                                    try:
                                        message_id = future.result()  # Wait for message to be published
                                        logger.info(f"Project deletion message published successfully for project {project['id']}. Message ID: {message_id}")
                                        time.sleep(5)
                                        st.rerun()
                                    except Exception as e:
                                        st.error("Failed to delete project. Please try again.")
                                        logger.error(f"Failed to publish project deletion message: {str(e)}")
                                        
                                except Exception as e:
                                    st.error(f"Error deleting project: {str(e)}")
                                    logger.exception("Error in project deletion")
            else:
                st.info("No projects found. Create a new project to get started!")