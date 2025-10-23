from sqlalchemy.engine.url import URL
from langchain_community.utilities import SQLDatabase

from config import (
    SQL_SERVER_USERNAME,
    SQL_SERVER_NAME,
    SQL_SERVER_PASSWORD,
    SQL_SERVER_DATABASE
)

from services.telemetry_client import telemetry_client 


class Database:
    """
    Database class to handle SQL Server connections using environment variables.
    NOTE: All queries should include UserID filter for data isolation.
    """

    def __init__(self):
        """Initialize the database connection."""

        try: 
            self.db_config = self._get_db_config()
            self.db_url = URL.create(**self.db_config)
            self.db = self._create_connection()

            telemetry_client.log_info("Initialized the database connection with user isolation support.")

        except Exception as e:
            telemetry_client.log_exception(e, {"error": f"Database Connection failed because of {e}"})

    def _get_db_config(self):
        """Retrieves database configuration from environment variables."""

        return {
            "drivername": "mssql+pyodbc",
            "username": SQL_SERVER_USERNAME,
            "password": SQL_SERVER_PASSWORD,
            "host": SQL_SERVER_NAME, 
            "port": 1433,  
            "database": SQL_SERVER_DATABASE,
            "query": {"driver": "ODBC Driver 17 for SQL Server"},
        }

    def _create_connection(self):
        '''Creates a SQLDatabase instance from the connection URL and verifies the connection.'''
        try:
            db = SQLDatabase.from_uri(self.db_url)

            test_query = 'SELECT @@VERSION'
            result = db.run(test_query)

            if result:
                telemetry_client.log_info(f'✅ Database connection successful! SQL Server Version: {result}')
            else:
                telemetry_client.log_info('⚠️ Connected but unable to fetch SQL Server version!')

            return db
        
        except Exception as e:
            telemetry_client.log_exception('Database: Failed to create SQL connection', e)
            return None

    def get_db(self):
        '''Returns the database connection.'''
        return self.db


# Singleton instance
database = Database()