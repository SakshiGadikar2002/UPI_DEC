import pandas as pd
from typing import Dict, Any, List


class Transformer:
    """Transform data using various transformation rules"""
    
    @staticmethod
    def transform(df: pd.DataFrame, transformations: List[Dict[str, Any]]) -> pd.DataFrame:
        """Apply transformations to a DataFrame"""
        result_df = df.copy()
        
        for transformation in transformations:
            transform_type = transformation.get("type")
            
            if transform_type == "filter":
                # Filter rows based on condition
                column = transformation.get("column")
                operator = transformation.get("operator")
                value = transformation.get("value")
                
                if operator == "equals":
                    result_df = result_df[result_df[column] == value]
                elif operator == "greater_than":
                    result_df = result_df[result_df[column] > value]
                elif operator == "less_than":
                    result_df = result_df[result_df[column] < value]
                elif operator == "contains":
                    result_df = result_df[result_df[column].astype(str).str.contains(str(value))]
            
            elif transform_type == "select_columns":
                # Select specific columns
                columns = transformation.get("columns", [])
                if columns:
                    result_df = result_df[columns]
            
            elif transform_type == "rename_columns":
                # Rename columns
                rename_map = transformation.get("rename_map", {})
                result_df = result_df.rename(columns=rename_map)
            
            elif transform_type == "add_column":
                # Add a new column
                column_name = transformation.get("column_name")
                value = transformation.get("value")
                result_df[column_name] = value
            
            elif transform_type == "drop_duplicates":
                # Remove duplicate rows
                result_df = result_df.drop_duplicates()
            
            elif transform_type == "sort":
                # Sort by column
                column = transformation.get("column")
                ascending = transformation.get("ascending", True)
                result_df = result_df.sort_values(by=column, ascending=ascending)
        
        return result_df

