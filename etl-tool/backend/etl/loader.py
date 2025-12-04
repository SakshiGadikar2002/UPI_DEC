import pandas as pd
import json
from typing import Dict, Any
from abc import ABC, abstractmethod


class BaseLoader(ABC):
    """Base class for data loaders"""
    
    @abstractmethod
    def load(self, df: pd.DataFrame, config: Dict[str, Any]) -> None:
        """Load data to destination"""
        pass


class CSVLoader(BaseLoader):
    """Load data to CSV files"""
    
    def load(self, df: pd.DataFrame, config: Dict[str, Any]) -> None:
        file_path = config.get("file_path")
        if not file_path:
            raise ValueError("file_path is required for CSV loading")
        
        df.to_csv(file_path, index=False)


class JSONLoader(BaseLoader):
    """Load data to JSON files"""
    
    def load(self, df: pd.DataFrame, config: Dict[str, Any]) -> None:
        file_path = config.get("file_path")
        if not file_path:
            raise ValueError("file_path is required for JSON loading")
        
        # Convert DataFrame to JSON
        data = df.to_dict(orient="records")
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)


class DatabaseLoader(BaseLoader):
    """Load data to databases"""
    
    def load(self, df: pd.DataFrame, config: Dict[str, Any]) -> None:
        connection_string = config.get("connection_string")
        table_name = config.get("table_name")
        
        if not connection_string or not table_name:
            raise ValueError("connection_string and table_name are required for database loading")
        
        # Example for SQLite (would need to support other databases)
        import sqlite3
        conn = sqlite3.connect(connection_string)
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.close()


class XLSXLoader(BaseLoader):
    """Load data to XLSX files"""
    
    def load(self, df: pd.DataFrame, config: Dict[str, Any]) -> None:
        file_path = config.get("file_path")
        if not file_path:
            raise ValueError("file_path is required for XLSX loading")
        
        df.to_excel(file_path, index=False, engine='openpyxl')


class Loader:
    """Factory class for creating loaders"""
    
    _loaders = {
        "csv": CSVLoader(),
        "json": JSONLoader(),
        "xlsx": XLSXLoader(),
        "database": DatabaseLoader(),
    }
    
    @classmethod
    def get_loader(cls, destination_type: str) -> BaseLoader:
        """Get a loader for the given destination type"""
        loader = cls._loaders.get(destination_type.lower())
        if not loader:
            raise ValueError(f"Unsupported destination type: {destination_type}")
        return loader
    
    @classmethod
    def load(cls, df: pd.DataFrame, destination_type: str, config: Dict[str, Any]) -> None:
        """Load data using the appropriate loader"""
        loader = cls.get_loader(destination_type)
        loader.load(df, config)

