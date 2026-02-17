import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
import os
import numpy as np
from dotenv import load_dotenv
import logging
from src.logger_config import setup_logging
from src.secrets_utils import get_secret

# Load environment variables from .env
load_dotenv()
setup_logging()

def get_db_connection():
    """Create and return a database connection using credentials from .env file."""
    DB_USER = get_secret("DB_USER")
    DB_PASSWORD = get_secret("DB_PASSWORD")
    DB_HOST = get_secret("DB_HOST")
    DB_PORT = get_secret("DB_PORT")
    DB_NAME = get_secret("DB_NAME")
    
    # Debug: Print what we got (remove password from logs!)
    # logging.info(f"DB_USER: {DB_USER is not None and len(DB_USER) > 0}")
    # logging.info(f"DB_PASSWORD: {DB_PASSWORD is not None and len(DB_PASSWORD) > 0}")
    # logging.info(f"DB_HOST: {DB_HOST}")
    # logging.info(f"DB_PORT: {DB_PORT}")
    # logging.info(f"DB_NAME: {DB_NAME}")
    
    # Validate that all required env vars are present and not empty
    missing_vars = []
    if not DB_USER or DB_USER.strip() == "":
        missing_vars.append("DB_USER")
    if not DB_PASSWORD or DB_PASSWORD.strip() == "":
        missing_vars.append("DB_PASSWORD")
    if not DB_HOST or DB_HOST.strip() == "":
        missing_vars.append("DB_HOST")
    if not DB_PORT or DB_PORT.strip() == "":
        missing_vars.append("DB_PORT")
    if not DB_NAME or DB_NAME.strip() == "":
        missing_vars.append("DB_NAME")
    
    if missing_vars:
        raise ValueError(f"Missing or empty environment variables: {', '.join(missing_vars)}")
    
    # Ensure PORT is treated as integer
    try:
        port_int = int(DB_PORT)
    except (ValueError, TypeError):
        raise ValueError(f"DB_PORT must be a valid integer, got: {DB_PORT}")
    
    # logging.info(f"Attempting to connect to {DB_HOST}:{port_int}/{DB_NAME} as user {DB_USER[0:12]}")
    
    connection = psycopg2.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=port_int,  # Use the integer version
        dbname=DB_NAME,
        sslmode=get_secret("DB_SSLMODE")
    )
    return connection

def insert_dataframe_to_db(df: pd.DataFrame, schema: str, table_name: str) -> dict:
    """
    Insert a pandas DataFrame into a PostgreSQL table.
    
    Args:
        df: pandas DataFrame to insert
        schema: Database schema name (e.g., 'public')
        table_name: Name of the target table
        
    Returns:
        dict with 'success' (bool), 'message' (str), and 'rows_inserted' (int)
    """
    connection = None
    cursor = None
    
    try:
        # Establish connection
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get column names from DataFrame
        columns = df.columns.tolist()
        columns_str = ", ".join(columns)
        
        # Create placeholders for VALUES clause
        placeholders = ", ".join(["%s"] * len(columns))
        
        # Build the INSERT query
        query = f"""
            INSERT INTO {schema}.{table_name} ({columns_str})
            VALUES ({placeholders})
        """
        
        # Helper: convert values to Python-native types psycopg2 can adapt
        def _to_python(value):
            if pd.isna(value):
                return None
            # Numpy types → built-in Python
            if isinstance(value, np.integer):
                return int(value)
            if isinstance(value, np.floating):
                return float(value)
            if isinstance(value, np.bool_):
                return bool(value)
            # Pandas Timestamp → Python datetime
            if isinstance(value, pd.Timestamp):
                return value.to_pydatetime()
            return value

        # Convert DataFrame to list of tuples (each row) with proper types
        data = [tuple(_to_python(x) for x in row) for row in df.itertuples(index=False, name=None)]
        
        # Execute batch insert for better performance
        execute_batch(cursor, query, data, page_size=1000)
        
        # Commit the transaction
        connection.commit()
        
        rows_inserted = len(data)
        
        return {
            "success": True,
            "message": f"Successfully inserted {rows_inserted} rows into {schema}.{table_name}",
            "rows_inserted": rows_inserted
        }
        
    except Exception as e:
        if connection:
            connection.rollback()
        return {
            "success": False,
            "message": f"Failed to insert data: {str(e)}",
            "rows_inserted": 0
        }
        
    finally:
        # Clean up
        if cursor:
            cursor.close()
        if connection:
            connection.close()
