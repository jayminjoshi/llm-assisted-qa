from processing import Database
from auth import Authenticator

import streamlit as st

class RegisterPage:
    def __init__(self, authenticator: Authenticator, db: Database):
        self.authenticator = authenticator
        self.db = db

    def show(self):
        st.header("Register")
        email, username, name = self.authenticator.authenticator.register_user()
        
        if email and username and name:
            # Split the full name into first and last name
            name_parts = name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Get the hashed password from the config
            user_config = self.authenticator.config['credentials']['usernames'].get(username, {})
            hashed_password = user_config.get('password', '')
            
            # Insert into database
            self.db.insert_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=hashed_password
            )
            
            st.success('User registered successfully')