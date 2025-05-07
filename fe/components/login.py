from auth.authenticator import Authenticator

import streamlit as st
import os

class LoginPage:
    def __init__(self, authenticator: Authenticator):
        self.authenticator = authenticator

    def show(self):

        # Display the image
        image_path = os.path.join('assets', 'Logo.jpg')
        if os.path.exists(image_path):
            # Create a container with custom width
            col1, col2, col3 = st.columns([3,1,3])  # This creates 3 columns in ratio 2:1:2
            with col2:  # Use the middle column
                st.image(image_path, use_column_width="auto")
        else:
            st.error("Image not found: assets/Logo.jpg")

        self.authenticator.authenticator.login(
            # single_session=True, 
            location='main'
        )
        
        if st.session_state['authentication_status']:
            st.session_state['current_page'] = 'Home'
            # st.rerun()
        elif st.session_state['authentication_status'] is False:
            st.error('Username/Password is incorrect')