import os
import time
import json
import argparse
import pandas as pd
import requests

from dotenv import load_dotenv

load_dotenv()
MONDAY_API_TOKEN = os.environ.get("MONDAY_API_TOKEN", "")
MONDAY_API_URL = "https://api.monday.com/v2"

HEADERS = {
    "Authorization": MONDAY_API_TOKEN,
    "Content-Type": "application/json",
    "API-Version": "2024-01"
}

def execute_graphql(query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    response = requests.post(MONDAY_API_URL, json=payload, headers=HEADERS)
    response.raise_for_status()
    res_json = response.json()
    if 'errors' in res_json:
        print(f"GraphQL Error: {res_json['errors']}")
    return res_json.get("data", {})

def create_board(board_name):
    query = """
    mutation ($boardName: String!) {
        create_board (board_name: $boardName, board_kind: public) {
            id
        }
    }
    """
    res = execute_graphql(query, {"boardName": board_name})
    return res.get("create_board", {}).get("id")

def create_column(board_id, title, column_type):
    query = """
    mutation ($boardId: ID!, $title: String!, $columnType: ColumnType!) {
        create_column (board_id: $boardId, title: $title, column_type: $columnType) {
            id
        }
    }
    """
    res = execute_graphql(query, {"boardId": board_id, "title": title, "columnType": column_type})
    return res.get("create_column", {}).get("id")

def create_item(board_id, item_name, column_values):
    query = """
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item (board_id: $boardId, item_name: $itemName, column_values: $columnValues) {
            id
        }
    }
    """
    # columnValues must be a serialized string
    res = execute_graphql(query, {
        "boardId": board_id,
        "itemName": str(item_name),
        "columnValues": json.dumps(column_values)
    })
    return res.get("create_item", {}).get("id")

def map_pandas_dtype_to_monday(dtype):
    if pd.api.types.is_numeric_dtype(dtype):
        return "numbers"
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return "date"
    else:
        return "text"

def clean_data(df):
    """Data Resilience: Normalize messy business data."""
    # Convert obvious currency or percentage strings to numeric
    for col in df.columns:
        if df[col].dtype == object:
            # Check if it looks like a number with $ or %
            sample = df[col].dropna().astype(str).str.strip().str.replace(r'[\$\,\%]', '', regex=True)
            if sample.str.isnumeric().all() or sample.str.replace('.', '', 1).str.isnumeric().all():
                try:
                    df[col] = pd.to_numeric(sample)
                except:
                    pass
    
    # Fill Nans safely
    df = df.where(pd.notnull(df), None)
    return df

def ingest_dataframe(board_name, filepath):
    print(f"Reading {filepath}...")
    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)
        
    df = clean_data(df)
    
    print(f"Creating board '{board_name}'...")
    board_id = create_board(board_name)
    if not board_id:
        print("Failed to create board.")
        return
        
    print(f"Board created with ID: {board_id}")
    
    # Analyze columns (skip first column as Item Name)
    columns = list(df.columns)
    item_name_col = columns[0]
    
    col_mapping = {}
    for col in columns[1:]:
        monday_type = map_pandas_dtype_to_monday(df[col].dtype)
        col_id = create_column(board_id, col, monday_type)
        if col_id:
            col_mapping[col] = {"id": col_id, "type": monday_type}
        time.sleep(0.2) # Rate limit avoidance
        
    print(f"Created {len(col_mapping)} columns. Uploading rows...")
    
    for index, row in df.iterrows():
        item_name = row[item_name_col] or f"Item {index}"
        column_values = {}
        for col, col_info in col_mapping.items():
            val = row[col]
            if val is None:
                continue
                
            if col_info["type"] == "text":
                column_values[col_info["id"]] = str(val)
            elif col_info["type"] == "numbers":
                column_values[col_info["id"]] = str(val)
            elif col_info["type"] == "date":
                # Monday date format YYYY-MM-DD
                if isinstance(val, pd.Timestamp):
                    column_values[col_info["id"]] = {"date": val.strftime('%Y-%m-%d')}
                else:
                    column_values[col_info["id"]] = str(val)
                    
        create_item(board_id, item_name, column_values)
        if index % 20 == 0 and index > 0:
            print(f"Uploaded {index} rows...")
            
    print(f"Finished ingesting {board_name}. Board ID: {board_id}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest CSV/Excel to Monday.com")
    parser.add_argument("--work-orders", required=True, help="Path to Work Orders data")
    parser.add_argument("--deals", required=True, help="Path to Deals data")
    
    args = parser.parse_args()
    
    if not MONDAY_API_TOKEN:
        print("Error: MONDAY_API_TOKEN is not set in environment or .env file")
        exit(1)
        
    ingest_dataframe("Work Orders", args.work_orders)
    ingest_dataframe("Deals Funnel", args.deals)