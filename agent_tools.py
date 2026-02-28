import os
import requests
import json
import pandas as pd
from typing import List, Dict, Any
from langchain_core.tools import tool

MONDAY_API_URL = "https://api.monday.com/v2"

def _get_headers():
    token = os.environ.get("MONDAY_API_TOKEN", "")
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "API-Version": "2024-01"
    }

def execute_graphql(query: str, variables: dict = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(
        MONDAY_API_URL,
        json=payload,
        headers=_get_headers()
    )

    response.raise_for_status()

    try:
        res_json = response.json()
        print("DEBUG → GraphQL Query Variables:", variables)
        print("DEBUG → Response JSON:", res_json)
    except Exception:
        return {}

    if not isinstance(res_json, dict):
        return {}

    if res_json.get("errors"):
        print(f"[Monday API Error]: {res_json['errors']}")
        return {}

    data = res_json.get("data")

    if not isinstance(data, dict):
        return {}

    return data

@tool
def get_all_boards() -> str:
    """Fetches a list of all accessible Monday.com boards. Returns their IDs and names."""
    print("DEBUG → get_all_boards CALLED")

    query = """
    query {
        boards {
            id
            name
            description
        }
    }
    """
    data = execute_graphql(query)

    if not data:
        return "No data returned from Monday API."

    boards = data.get("boards", [])
    if not boards:
        return "No boards found."
    
    result = "Available Boards:\n"
    for b in boards:
        result += f"- Board Name: '{b['name']}' (ID: {b['id']})\n"
    return result

@tool
def get_board_data(board_id: str) -> str:
    """Fetches ALL items and their column values for a specific board ID.
    Use this when you need to answer business intelligence questions.
    The data is returned as a JSON string representing the table.
    """

    print("DEBUG → get_board_data CALLED")
    print("DEBUG → Board ID Received:", board_id)
    query = """
    query ($boardId: [ID!]) {
        boards(ids: $boardId) {
            name
            items_page (limit: 500) {
                cursor
                items {
                    name
                    column_values {
                        column {
                            title
                        }
                        text
                    }
                }
            }
        }
    }
    """
    data = execute_graphql(query, {"boardId": [board_id]})
    print("DEBUG → Raw Data From Monday:", data)

    if not isinstance(data, dict):
        return f"No data returned for board {board_id}."

    boards = data.get("boards") or []
    if not boards:
        return f"Board {board_id} not found."
    
    board = boards[0]
    items = board.get("items_page", {}).get("items", [])
    
    if not items:
        return f"No items found in board '{board['name']}'."
        
    # Flatten the data to be easily understandable by the LLM
    flat_data = []
    for item in items:
        row = {"Item Name": item.get("name")}
        for col_val in item.get("column_values", []):
            col_title = col_val.get("column", {}).get("title")
            # Clean text (handle nulls)
            val = col_val.get("text")
            if val is not None:
                row[col_title] = val
            else:
                row[col_title] = "null"
        flat_data.append(row)
        
    return json.dumps(flat_data)

def get_tools():
    return [get_all_boards, get_board_data]
