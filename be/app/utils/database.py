from datetime import datetime, timezone
from typing import Optional, List, Dict
from config import config
from loguru import logger

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
    
    def insert_file(
        self,
        project_id: str,
        user_id: str,
        type: str,
        filename: Optional[str] = None,
        link: Optional[str] = None,
        gcp_path: Optional[str] = None,
        bucket: Optional[str] = None
    ) -> int:
        """
        Insert a new file record into the database.
        
        Args:
            project_id (str): ID of the project
            user_id (str): ID of the user who uploaded the file
            document_type (str): Type of document ('file' or 'link')
            filename (str, optional): Name of the uploaded file
            file_type (str, optional): Type/extension of the file
            link (str, optional): Public link to access the file
            gcp_path (str, optional): Path in Google Cloud Storage
            bucket (str, optional): GCP bucket name
            
        Returns:
            int: ID of the newly inserted file record
        """
        
        # Websites
        if type == 'website':
            filename = None  # Ensure filename is NULL for link documents
            gcp_path = None  # GCP path is not applicable for links
            bucket = None  # Bucket is not applicable for links
        
        # Files
        else:
            link = None  # Ensure link is NULL for file documents

        query = """
            INSERT INTO files 
            (project_id, user_id, name, type, link, gcp_path, bucket,
            is_indexed, index_started_at, index_completed_at, index_failed_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            project_id,
            user_id,
            filename,
            type,
            link,
            gcp_path,
            bucket,
            False,  # is_indexed
            datetime.now(timezone.utc),  # index_started_at
            None,  # index_completed_at
            None   # index_failed_at
        )
        result = self.execute_query(query, values)
        return result
    
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
            values = (is_indexed, completed_at or datetime.now(timezone.utc), file_id)
        else:
            query = """
                UPDATE files 
                SET is_indexed = %s, 
                    index_completed_at = NULL,
                    index_failed_at = %s
                WHERE id = %s
            """
            values = (is_indexed, datetime.now(timezone.utc), file_id)
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

    def create_project(self, user_id, project_name):
        """
        Create a new project for a user.
        
        Args:
            user_id (int): ID of the user creating the project
            project_name (str): Name of the project
            
        Returns:
            int: ID of the newly created project
        """
        query = """
            INSERT INTO projects 
            (user_id, name, created_at) 
            VALUES (%s, %s, NOW())
        """
        return self.execute_query(query, (user_id, project_name))

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
    
    def delete_file(self, file_id, user_id):
        """
        Permanently delete a file from the database.
        
        Args:
            file_id (int): ID of the file to delete
            user_id (int): ID of the user who owns the file
        """
        query = """
            DELETE FROM files 
            WHERE id = %s AND user_id = %s
        """
        return self.execute_query(query, (file_id, user_id))
    
    def insert_rfp(self, name: str, gcp_path: str, bucket: str, project_id: int, user_id: int) -> int:
        """Insert new RFP record and return its ID"""
        query = """
            INSERT INTO rfps (name, status, original_file_path, bucket, project_id, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (name, 'processing', gcp_path, bucket, project_id, user_id)
        return self.execute_query(query, values)

    def update_rfp_status(self, rfp_id: int, status: str, processed_file_path: str = None):
        """Update RFP status and related fields"""
        query = """
            UPDATE rfps 
            SET status = %s,
                processed_file_path = %s,
                completed_at = %s
            WHERE id = %s
        """
        values = (status, processed_file_path, datetime.now(timezone.utc), rfp_id)
        self.execute_query(query, values)

    def get_file_gcp_details(self, file_id: int, user_id: int) -> tuple[str, str]:
        """
        Get the GCP bucket and path for a file by its ID and user ID.
        
        Args:
            file_id (int): ID of the file
            user_id (int): ID of the user who owns the file
            
        Returns:
            tuple[str, str]: Bucket and GCP path
        """
        
        query = """
            SELECT bucket, gcp_path FROM files WHERE id = %s AND user_id = %s
        """
        result = self.fetch_one(query, (file_id, user_id))
        return result['bucket'], result['gcp_path']

    def delete_project(self, project_id: int, user_id: int):
        """Delete a project by its ID and user ID"""
        query = """
            DELETE FROM projects WHERE id = %s AND user_id = %s
        """
        self.execute_query(query, (project_id, user_id))

    def insert_vector(
        self,
        file_id: int,
        user_id: int,
        project_id: int,
        vector_id: str,
        text: str,
        chunk_number: int,
        file_type: str,
        industry: str = None,
        sheet_name: str = None
    ) -> int:
        """
        Insert a vector chunk into the database
        
        Args:
            file_id (int): ID of the file
            user_id (int): ID of the user
            project_id (int): ID of the project
            vector_id (str): Vector Search ID (UUID)
            text (str): The text content of the chunk
            chunk_number (int): The chunk number within the file
            file_type (str): Type of the file (pdf, xlsx, etc.)
            industry (str, optional): Industry classification
            sheet_name (str, optional): Name of the sheet (for Excel files)
            
        Returns:
            int: ID of the newly inserted vector record
        """
        try:
            query = """
                INSERT INTO vectors 
                (file_id, user_id, project_id, vector_id, text, chunk_number, 
                file_type, industry, sheet_name) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                file_id,
                user_id,
                project_id,
                vector_id,
                text,
                chunk_number,
                file_type,
                industry,
                sheet_name
            )
            
            return self.execute_query(query, values)
        
        except Exception as e:
            logger.exception(f"Error inserting vector: {e}")
            raise
    
    def get_vectors_by_file(self, file_id: int, user_id: int) -> List[Dict]:
        """
        Get all vector IDs associated with a file
        
        Args:
            file_id (int): ID of the file
            user_id (int): ID of the user (for verification)
            
        Returns:
            List[Dict]: List of vector records
        """
        query = """
            SELECT vector_id 
            FROM vectors 
            WHERE file_id = %s AND user_id = %s
        """
        return self.fetch_all(query, (file_id, user_id))

    def delete_vectors_by_file(self, file_id: int, user_id: int) -> bool:
        """
        Delete all vector records associated with a file
        
        Args:
            file_id (int): ID of the file
            user_id (int): ID of the user (for verification)
            
        Returns:
            bool: True if deletion was successful
        """
        query = """
            DELETE FROM vectors 
            WHERE file_id = %s AND user_id = %s
        """
        try:
            self.execute_query(query, (file_id, user_id))
            return True
        except Exception as e:
            logger.exception(f"Error deleting vector records: {e}")
            return False
        
    def get_file_vectors_ordered(
        self,
        file_id: int,
        user_id: int,
        start_chunk: int,
        end_chunk: int
    ) -> List[Dict]:
        """
        Get vectors for a file ordered by chunk number, optionally within a range
        
        Args:
            file_id (int): ID of the file
            user_id (int): ID of the user
            start_chunk (int, optional): Starting chunk number (inclusive)
            end_chunk (int, optional): Ending chunk number (inclusive)
            
        Returns:
            List[Dict]: List of vector records ordered by chunk number
        """
        
        query = """
            SELECT text 
            FROM vectors 
            WHERE file_id = %s 
            AND user_id = %s 
            AND chunk_number >= %s 
            AND chunk_number <= %s
            ORDER BY chunk_number ASC
        """
        return self.fetch_all(query, (file_id, user_id, start_chunk, end_chunk))


    def get_file_name(self, file_id: int, user_id: int) -> str:
        """
        Get the name or link of a file
        
        Args:
            file_id (int): ID of the file
            user_id (int): ID of the user who owns the file
            
        Returns:
            str: Name of the file or link if it's a website
            
        Raises:
            Exception: If file not found or database error occurs
        """
        try:
            query = """
                SELECT name, type, link 
                FROM files 
                WHERE id = %s AND user_id = %s
            """
            result = self.fetch_one(query, (file_id, user_id))
            
            if not result:
                raise Exception(f"File not found: {file_id}")
            
            # For websites, return the link
            if result['type'] == 'website':
                return result['link']
            
            # For other files, return the name
            return result['name']
            
        except Exception as e:
            logger.exception(f"Error getting file name: {e}")
            raise