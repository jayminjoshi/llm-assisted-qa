from processing import Database

import streamlit_authenticator as stauth
import os

class Authenticator:
    def __init__(self, db: Database):
        self.db = db
        self.config = self._load_config_from_db()
        
        self.authenticator = stauth.Authenticate(
            self.config['credentials'],
            self.config['cookie']['name'],
            self.config['cookie']['key'],
            self.config['cookie']['expiry_days']
        )
    
    def _load_config_from_db(self):
        """
        Load authentication configuration from database.
        
        Returns:
            dict: Configuration dictionary compatible with streamlit_authenticator
        """
        # Get all users from database
        users = self.db.get_all_users()
        
        # Transform users into the format expected by streamlit_authenticator
        credentials = {
            "usernames": {
                user['username']: {
                    "email": user['email'],
                    "name": f"{user['first_name']} {user['last_name']}",
                    "password": user['password']
                } for user in users
            }
        }
        
        # Cookie settings could be stored in a settings table, 
        # but for now we'll use constants
        cookie_config = {
            "name": "llm-assisted-qa",
            "key": os.environ['COOKIE_KEY'],
            "expiry_days": 30
        }
        
        return {
            "credentials": credentials,
            "cookie": cookie_config
        }