import pandas as pd
import json
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()


class BaseExtractor(ABC):
    """Base class for data extractors"""
    
    @abstractmethod
    def extract(self, config: Dict[str, Any]) -> pd.DataFrame:
        """Extract data and return as DataFrame"""
        pass


class CSVExtractor(BaseExtractor):
    """Extract data from CSV files"""
    
    def extract(self, config: Dict[str, Any]) -> pd.DataFrame:
        file_path = config.get("file_path")
        if not file_path:
            raise ValueError("file_path is required for CSV extraction")
        
        return pd.read_csv(file_path)


class JSONExtractor(BaseExtractor):
    """Extract data from JSON files"""
    
    def extract(self, config: Dict[str, Any]) -> pd.DataFrame:
        file_path = config.get("file_path")
        if not file_path:
            raise ValueError("file_path is required for JSON extraction")
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Handle both list of objects and single object
        if isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            return pd.DataFrame([data])
        else:
            raise ValueError("JSON must be an object or array of objects")


class DatabaseExtractor(BaseExtractor):
    """
    Extract data from PostgreSQL database, specifically from api_connector_data table.
    This enforces the architecture: API → Database → Pipeline (pipeline only reads from DB).
    """
    
    def extract(self, config: Dict[str, Any]) -> pd.DataFrame:
        """
        Extract data from api_connector_data table.
        
        Config options:
        - connector_id (required): The connector ID to fetch data for
        - limit (optional): Maximum number of records to fetch (default: 1000)
        - order_by (optional): Column to order by (default: 'timestamp DESC')
        - query (optional): Custom SQL query (if provided, overrides connector_id-based query)
        
        Returns:
            pd.DataFrame: DataFrame containing the extracted data
        """
        # PostgreSQL connection settings from environment
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = int(os.getenv("POSTGRES_PORT", "5432"))
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "")
        db_name = os.getenv("POSTGRES_DB", "etl_tool")
        
        # Build connection string
        conn = None
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=db_name
            )
            
            # Check if custom query is provided
            custom_query = config.get("query")
            if custom_query:
                return pd.read_sql_query(custom_query, conn)
            
            # Default: query api_connector_data table by connector_id
            connector_id = config.get("connector_id")
            if not connector_id:
                raise ValueError("connector_id is required for database extraction from api_connector_data")
            
            limit = config.get("limit", 1000)
            order_by = config.get("order_by", "timestamp DESC")
            
            # Query to extract data from api_connector_data
            # The 'data' column contains the JSONB response data
            query = f"""
                SELECT 
                    id,
                    connector_id,
                    timestamp,
                    exchange,
                    instrument,
                    price,
                    data,
                    message_type,
                    raw_response,
                    status_code,
                    response_time_ms,
                    source_id,
                    session_id
                FROM api_connector_data
                WHERE connector_id = %s
                ORDER BY {order_by}
                LIMIT %s
            """
            
            df = pd.read_sql_query(query, conn, params=(connector_id, limit))
            
            # If the 'data' column is JSONB, expand it into columns
            if not df.empty and 'data' in df.columns:
                # Convert JSONB to dict if it's stored as string
                try:
                    # Try to parse data column if it's JSON string
                    data_list = []
                    for idx, row in df.iterrows():
                        data_val = row['data']
                        if isinstance(data_val, str):
                            try:
                                data_val = json.loads(data_val)
                            except:
                                pass
                        data_list.append(data_val)
                    
                    # If data is a list or dict, try to normalize
                    if data_list and isinstance(data_list[0], (list, dict)):
                        # For list of dicts, create a DataFrame
                        if isinstance(data_list[0], list):
                            # Flatten list of lists into single list
                            flat_list = []
                            for item in data_list:
                                if isinstance(item, list):
                                    flat_list.extend(item)
                                else:
                                    flat_list.append(item)
                            if flat_list:
                                expanded_df = pd.json_normalize(flat_list)
                                # Merge with metadata columns
                                meta_cols = ['id', 'connector_id', 'timestamp', 'exchange', 
                                           'instrument', 'price', 'message_type', 'status_code', 
                                           'response_time_ms', 'source_id', 'session_id']
                                meta_df = df[meta_cols].copy()
                                # Repeat metadata rows for each data item
                                if len(flat_list) > len(df):
                                    # Expand metadata rows to match
                                    expanded_meta = meta_df.loc[meta_df.index.repeat(
                                        [len(item) if isinstance(item, list) else 1 for item in data_list]
                                    )].reset_index(drop=True)
                                    df = pd.concat([expanded_meta, expanded_df], axis=1)
                                else:
                                    df = pd.concat([meta_df.reset_index(drop=True), expanded_df.reset_index(drop=True)], axis=1)
                        elif isinstance(data_list[0], dict):
                            # For list of dicts, normalize each and combine
                            expanded_df = pd.json_normalize(data_list)
                            meta_cols = ['id', 'connector_id', 'timestamp', 'exchange', 
                                       'instrument', 'price', 'message_type', 'status_code', 
                                       'response_time_ms', 'source_id', 'session_id']
                            meta_df = df[meta_cols].reset_index(drop=True)
                            df = pd.concat([meta_df, expanded_df.reset_index(drop=True)], axis=1)
                except Exception as e:
                    # If expansion fails, keep original data column
                    pass
            
            return df
            
        except Exception as e:
            raise ValueError(f"Database extraction failed: {str(e)}")
        finally:
            if conn:
                conn.close()


class XLSXExtractor(BaseExtractor):
    """Extract data from XLSX files"""
    
    def extract(self, config: Dict[str, Any]) -> pd.DataFrame:
        file_path = config.get("file_path")
        if not file_path:
            raise ValueError("file_path is required for XLSX extraction")
        
        # Read XLSX file
        return pd.read_excel(file_path, engine='openpyxl')


class Extractor:
    """
    Factory class for creating extractors.
    
    Note: APIExtractor has been removed to enforce architecture:
    API → Database → Pipeline (pipeline only reads from database)
    """
    
    _extractors = {
        "csv": CSVExtractor(),
        "json": JSONExtractor(),
        "xlsx": XLSXExtractor(),
        "database": DatabaseExtractor(),
    }
    
    @classmethod
    def get_extractor(cls, source_type: str) -> BaseExtractor:
        """Get an extractor for the given source type"""
        extractor = cls._extractors.get(source_type.lower())
        if not extractor:
            raise ValueError(f"Unsupported source type: {source_type}")
        return extractor
    
    @classmethod
    def extract(cls, source_type: str, config: Dict[str, Any]) -> pd.DataFrame:
        """Extract data using the appropriate extractor"""
        extractor = cls.get_extractor(source_type)
        return extractor.extract(config)

