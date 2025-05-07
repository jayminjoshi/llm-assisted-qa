from mysql.connector import pooling
from datetime import datetime
from config import config

import mysql.connector
import os

class Database:
    _instance = None
    _pool = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Database()
        return cls._instance
    
    def __init__(self):
        env = os.getenv('ENV')
        if Database._pool is None:
            dbconfig = {
                "host": config['env'][env]["MYSQL_HOST"],
                "user": config['env'][env]["MYSQL_USER"],
                "password": config['env'][env]["MYSQL_PASSWORD"],
                "database": config['env'][env]["MYSQL_DB"],
                "pool_name": "mypool",
                "pool_size": 5
            }
            Database._pool = mysql.connector.pooling.MySQLConnectionPool(**dbconfig)
    
    def get_connection(self):
        """
        Get a connection from the MySQL connection pool.
        
        Returns:
            MySQLConnection: A connection object from the pool
        """
        return self._pool.get_connection()
    
    def execute_query(self, query, params=None):
        """
        Execute a SQL query and commit the changes.

        Args:
            query (str): The SQL query to execute
            params (tuple, optional): Parameters to safely inject into the query
            
        Returns:
            int: The last row id of the inserted/updated record
            
        Raises:
            Exception: If the query execution fails
        """
        connection = self.get_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            connection.commit()
            return cursor.lastrowid
        except Exception as e:
            connection.rollback()
            raise e
        finally:
            cursor.close()
            connection.close()
    
    def fetch_one(self, query, params=None):
        """
        Execute a SQL query and fetch a single result.
        
        Args:
            query (str): The SQL query to execute
            params (tuple, optional): Parameters to safely inject into the query
            
        Returns:
            dict: A single row from the query result as a dictionary,
                 or None if no results found
        """
        connection = self.get_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            cursor.close()
            connection.close()
    
    def fetch_all(self, query, params=None):
        """
        Execute a SQL query and fetch all results.
        
        Args:
            query (str): The SQL query to execute
            params (tuple, optional): Parameters to safely inject into the query
            
        Returns:
            list[dict]: List of all matching rows as dictionaries
        """
        connection = self.get_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            cursor.close()
            connection.close()
    
    def get_user_by_username(self, username):
        """
        Retrieve a user by their username.
        
        Args:
            username (str): The username to search for
            
        Returns:
            dict: User data if found, None otherwise
        """
        query = "SELECT * FROM users WHERE username = %s"
        return self.fetch_one(query, (username,))
    
    def insert_file(self, user_id, filename, file_type, storage_location="local_storage"):
        """
        Insert a new file record into the database.
        
        Args:
            user_id (int): ID of the user who uploaded the file
            filename (str): Name of the uploaded file
            file_type (str): Type/extension of the file
            storage_location (str, optional): Where the file is stored. Defaults to "local_storage"
            
        Returns:
            int: ID of the newly inserted file record
        """
        query = """
            INSERT INTO files 
            (user_id, name, type, storage_location, is_indexed, index_started_at) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (
            user_id,
            filename,
            file_type,
            storage_location,
            False,
            datetime.now()
        )
        return self.execute_query(query, values)
    
    def update_file_indexing_status(self, file_id, is_indexed, completed_at=None):
        """
        Update the indexing status of a file.
        
        Args:
            file_id (int): ID of the file to update
            is_indexed (bool): Whether indexing was successful
            completed_at (datetime, optional): When indexing completed. 
                                            If None, current time is used
            
        Returns:
            int: ID of the updated file record
        """
        if is_indexed:
            query = """
                UPDATE files 
                SET is_indexed = %s, 
                    index_completed_at = %s,
                    index_failed_at = NULL
                WHERE id = %s
            """
            values = (is_indexed, completed_at or datetime.now(), file_id)
        else:
            query = """
                UPDATE files 
                SET is_indexed = %s, 
                    index_completed_at = NULL,
                    index_failed_at = %s
                WHERE id = %s
            """
            values = (is_indexed, datetime.now(), file_id)
        return self.execute_query(query, values)
    
    def get_user_files(self, user_id):
        """
        Get all files belonging to a specific user.
        
        Args:
            user_id (int): ID of the user whose files to retrieve
            
        Returns:
            list[dict]: List of file records ordered by index start time descending
        """
        query = "SELECT * FROM files WHERE user_id = %s ORDER BY index_started_at DESC"
        return self.fetch_all(query, (user_id,))

    def insert_user(self, username, email, first_name, last_name, password):
        """
        Insert a new user into the database.
        
        Args:
            username (str): User's username
            email (str): User's email address
            first_name (str): User's first name
            last_name (str): User's last name
            password (str): User's hashed password
            
        Returns:
            int: ID of the newly inserted user record
            
        Raises:
            Exception: If insertion fails (e.g., duplicate username/email)
        """
        query = """
            INSERT INTO users 
            (username, email, first_name, last_name, password) 
            VALUES (%s, %s, %s, %s, %s)
        """
        values = (username, email, first_name, last_name, password)
        return self.execute_query(query, values)
    
    
    def get_all_users(self):
        """
        Retrieve all users from the database.
        
        Returns:
            list[dict]: List of all users with their credentials
        """
        query = """
            SELECT id, username, email, first_name, last_name, password
            FROM users
        """
        return self.fetch_all(query)
    
    def get_user_by_credentials(self, username, password):
        """
        Retrieve a user by their username and password.
        
        Args:
            username (str): The username to check
            password (str): The hashed password to verify
            
        Returns:
            dict: User data if credentials match, None otherwise
        """
        query = """
            SELECT id, username, email, first_name, last_name
            FROM users
            WHERE username = %s AND password = %s
        """
        return self.fetch_one(query, (username, password))
    
    def get_user_projects(self, user_id):
        """
        Get all projects belonging to a user.
        
        Args:
            user_id (int): ID of the user whose projects to retrieve
            
        Returns:
            list[dict]: List of project records
        """
        query = "SELECT * FROM projects WHERE user_id = %s ORDER BY created_at DESC"
        return self.fetch_all(query, (user_id,))

    def create_project(self, user_id, project_name, project_domain):
        """
        Create a new project for a user.
        
        Args:
            user_id (int): ID of the user creating the project
            project_name (str): Name of the project
            project_domain (str): Domain of the project

        Returns:
            int: ID of the newly created project
        """
        query = """
            INSERT INTO projects 
            (user_id, name, domain, created_at) 
            VALUES (%s, %s, %s, NOW())
        """
        return self.execute_query(query, (user_id, project_name, project_domain))

    def get_project_by_id(self, project_id):
        """ 
        Get project details by ID.
        
        Args:
            project_id (int): ID of the project to retrieve
            
        Returns:
            dict: Project details if found, None otherwise
        """
        query = "SELECT * FROM projects WHERE id = %s"
        return self.fetch_one(query, (project_id,))

    def get_project_files(self, project_id, user_id):
        """
        Get all files associated with a project and user.
        
        Args:
            project_id (int): ID of the project
            user_id (int): ID of the user
            
        Returns:
            list[dict]: List of file records
        """
        query = """
            SELECT * FROM files 
            WHERE project_id = %s 
            AND user_id = %s 
            AND soft_delete = 0
            ORDER BY index_started_at DESC
        """
        return self.fetch_all(query, (project_id, user_id))

    def get_rfps_by_project_and_user(self, project_id: int, user_id: int):
        query = """
            SELECT id, name, status, original_file_path, processed_file_path, 
                   project_id, user_id, bucket, created_at, completed_at
            FROM rfps 
            WHERE project_id = %s AND user_id = %s
            ORDER BY created_at DESC
        """
        return self.fetch_all(query, (project_id, user_id))