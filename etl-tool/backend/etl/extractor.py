import pandas as pd
import json
import requests
from typing import Dict, Any, List
from abc import ABC, abstractmethod


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


class APIExtractor(BaseExtractor):
    """Extract data from REST APIs"""
    
    def extract(self, config: Dict[str, Any]) -> pd.DataFrame:
        url = config.get("url")
        if not url:
            raise ValueError("url is required for API extraction")
        
        headers = config.get("headers", {})
        params = config.get("params", {})
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle different API response formats
        if isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            # Try to find a data field
            if "data" in data and isinstance(data["data"], list):
                return pd.DataFrame(data["data"])
            else:
                return pd.DataFrame([data])
        else:
            raise ValueError("API response must be JSON object or array")


class DatabaseExtractor(BaseExtractor):
    """Extract data from databases"""
    
    def extract(self, config: Dict[str, Any]) -> pd.DataFrame:
        # This is a placeholder - would need database-specific implementation
        connection_string = config.get("connection_string")
        query = config.get("query")
        
        if not connection_string or not query:
            raise ValueError("connection_string and query are required for database extraction")
        
        # Example for SQLite (would need to support other databases)
        import sqlite3
        conn = sqlite3.connect(connection_string)
        return pd.read_sql_query(query, conn)


class XLSXExtractor(BaseExtractor):
    """Extract data from XLSX files"""
    
    def extract(self, config: Dict[str, Any]) -> pd.DataFrame:
        file_path = config.get("file_path")
        if not file_path:
            raise ValueError("file_path is required for XLSX extraction")
        
        # Read XLSX file
        return pd.read_excel(file_path, engine='openpyxl')


class Extractor:
    """Factory class for creating extractors"""
    
    _extractors = {
        "csv": CSVExtractor(),
        "json": JSONExtractor(),
        "xlsx": XLSXExtractor(),
        "api": APIExtractor(),
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

