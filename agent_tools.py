import os
import requests
import json
from typing import Optional, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

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


# ── Tool 1: Get All Boards ────────────────────────────────────────────────────
# Using BaseTool + explicit schema avoids the `__arg1 in None` crash that
# happens when a @tool function has zero parameters and Groq sends null input.

class GetAllBoardsInput(BaseModel):
    # Dummy field — tool needs no real input, but LangChain/Groq require
    # at least one field in the schema or they send null and crash.
    placeholder: Optional[str] = Field(
        default="",
        description="Leave empty. This tool requires no input."
    )


class GetAllBoardsTool(BaseTool):
    name: str = "get_all_boards"
    description: str = (
        "Fetches a list of all accessible Monday.com boards. "
        "Returns their IDs and names. Call this first if you don't know the board IDs."
    )
    args_schema: Type[BaseModel] = GetAllBoardsInput

    def _run(self, placeholder: str = "") -> str:
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


# ── Tool 2: Get Board Data ────────────────────────────────────────────────────

class GetBoardDataInput(BaseModel):
    board_id: str = Field(
        description="The numeric Monday.com board ID to fetch data from."
    )


class GetBoardDataTool(BaseTool):
    name: str = "get_board_data"
    description: str = (
        "Fetches ALL items and their column values for a specific Monday.com board ID. "
        "Use this to answer business intelligence questions about deals, revenue, pipeline, etc. "
        "Returns data as a JSON string."
    )
    args_schema: Type[BaseModel] = GetBoardDataInput

    def _run(self, board_id: str) -> str:
        query = """
        query ($boardId: [ID!]) {
            boards(ids: $boardId) {
                name
                items_page(limit: 500) {
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

        if not isinstance(data, dict):
            return f"No data returned for board {board_id}."

        boards = data.get("boards") or []
        if not boards:
            return f"Board {board_id} not found."

        board = boards[0]
        items = board.get("items_page", {}).get("items", [])

        if not items:
            return f"No items found in board '{board['name']}'."

        flat_data = []
        for item in items:
            row = {"Item Name": item.get("name")}
            for col_val in item.get("column_values", []):
                col_title = col_val.get("column", {}).get("title")
                val = col_val.get("text")
                row[col_title] = val if val is not None else "null"
            flat_data.append(row)

        return json.dumps(flat_data)


def get_tools():
    return [GetAllBoardsTool(), GetBoardDataTool()]
