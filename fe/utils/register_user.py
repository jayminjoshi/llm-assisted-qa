import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processing import Database

import streamlit_authenticator as stauth
from auth import Authenticator
import os

def register_user(env: str, username: str, password: str, first_name: str, last_name: str, email: str):
    # Set environment variable
    os.environ['ENV'] = env
    
    try:
        # Initialize database
        db = Database.get_instance()
        
        # Generate hashed password
        hashed_password = stauth.Hasher.hash(password)
        
        # Insert user into database
        user_id = db.insert_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=hashed_password
        )
        
        print(f"User registered successfully with ID: {user_id}")
        return user_id
        
    except Exception as e:
        print(f"Error registering user: {str(e)}")
        return None

if __name__ == "__main__":
    # Get user inputs
    env = input("Enter environment (e.g., dev, prod): ")
    username = input("Enter username: ")
    password = input("Enter password: ")
    first_name = input("Enter first name: ")
    last_name = input("Enter last name: ")
    email = input("Enter email: ")
    
    # Register user
    register_user(env, username, password, first_name, last_name, email)