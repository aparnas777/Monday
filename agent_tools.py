import os
import requests
import json
from collections import defaultdict
from typing import Optional, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

MONDAY_API_URL = "https://api.monday.com/v2"
MAX_DATA_CHARS = 60_000


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

    response = requests.post(MONDAY_API_URL, json=payload, headers=_get_headers())
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
    return data if isinstance(data, dict) else {}


def _fetch_all_items(board_id: str) -> tuple:
    """Fetch all items from a board. Returns (board_name, flat_data)."""
    query = """
    query ($boardId: [ID!]) {
        boards(ids: $boardId) {
            name
            items_page(limit: 500) {
                items {
                    name
                    column_values {
                        column { title }
                        text
                    }
                }
            }
        }
    }
    """
    data = execute_graphql(query, {"boardId": [board_id]})
    if not isinstance(data, dict):
        return "", []

    boards = data.get("boards") or []
    if not boards:
        return "", []

    board = boards[0]
    board_name = board.get("name", board_id)
    items = board.get("items_page", {}).get("items", [])

    flat_data = []
    for item in items:
        row = {"Item Name": item.get("name")}
        for col_val in item.get("column_values", []):
            col_title = col_val.get("column", {}).get("title")
            val = col_val.get("text")
            row[col_title] = val if val is not None else "null"
        flat_data.append(row)

    return board_name, flat_data


def _parse_number(val) -> Optional[float]:
    """Parse a value as float, handling $, commas, INR, null etc."""
    if val is None or str(val).strip() in ("", "null", "None"):
        return None
    cleaned = (
        str(val)
        .replace("₹", "")
        .replace("$", "")
        .replace(",", "")
        .replace("USD", "")
        .replace("INR", "")
        .strip()
    )
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _filter_rows(flat_data: list, filters: dict) -> list:
    """
    Filter rows where column values contain the filter string (case-insensitive).
    All filters must match (AND logic).
    Falls back to searching all columns if filter_col not found.
    """
    if not filters:
        return flat_data

    result = []
    for row in flat_data:
        match = True
        for filter_col, filter_val in filters.items():
            filter_val_lower = str(filter_val).strip().lower()
            if filter_col in row:
                if filter_val_lower not in str(row.get(filter_col, "")).lower():
                    match = False
                    break
            else:
                if not any(filter_val_lower in str(v).lower() for v in row.values()):
                    match = False
                    break
        if match:
            result.append(row)
    return result


def _safe_truncate(filtered: list) -> tuple:
    """Truncate rows to stay within MAX_DATA_CHARS. Returns (rows, was_truncated)."""
    result_json = json.dumps(filtered)
    if len(result_json) <= MAX_DATA_CHARS:
        return filtered, False

    truncated, chars = [], 0
    for row in filtered:
        s = json.dumps(row)
        if chars + len(s) > MAX_DATA_CHARS:
            return truncated, True
        truncated.append(row)
        chars += len(s)
    return truncated, True


# ── Tool 1: Get All Boards ────────────────────────────────────────────────────

class GetAllBoardsInput(BaseModel):
    placeholder: Optional[str] = Field(default="", description="Leave empty.")


class GetAllBoardsTool(BaseTool):
    name: str = "get_all_boards"
    description: str = (
        "Fetches all accessible Monday.com boards with their IDs and names. "
        "Call this first if you don't know the board IDs."
    )
    args_schema: Type[BaseModel] = GetAllBoardsInput

    def _run(self, placeholder: str = "") -> str:
        query = "query { boards { id name description } }"
        data = execute_graphql(query)
        if not data:
            return "No data returned from Monday API."
        boards = data.get("boards", [])
        if not boards:
            return "No boards found."
        result = "Available Boards:\n"
        for b in boards:
            result += f"- '{b['name']}' (ID: {b['id']})\n"
        return result


# ── Tool 2: Get Board Schema ──────────────────────────────────────────────────

class GetBoardSchemaInput(BaseModel):
    board_id: str = Field(description="The numeric Monday.com board ID.")


class GetBoardSchemaTool(BaseTool):
    name: str = "get_board_schema"
    description: str = (
        "Fetches column names, a 5-row sample, and unique categorical values for a board. "
        "Call this if you are unsure about exact column names or available filter values."
    )
    args_schema: Type[BaseModel] = GetBoardSchemaInput

    def _run(self, board_id: str) -> str:
        board_name, flat_data = _fetch_all_items(board_id)
        if not flat_data:
            return f"No data found for board {board_id}."

        columns = list(flat_data[0].keys())
        sample = flat_data[:5]

        unique_vals = {}
        for col in columns:
            vals = set()
            for row in flat_data:
                v = str(row.get(col, "")).strip()
                if v and v != "null":
                    vals.add(v)
            if 1 < len(vals) <= 30:
                unique_vals[col] = sorted(vals)

        result = f"Board: '{board_name}' (ID: {board_id})\n"
        result += f"Total rows: {len(flat_data)}\n"
        result += f"Columns: {json.dumps(columns)}\n\n"
        result += f"Sample (5 rows):\n{json.dumps(sample, indent=2)}\n\n"
        result += f"Unique categorical values:\n{json.dumps(unique_vals, indent=2)}"
        return result


# ── Tool 3: Get Filtered Board Data ──────────────────────────────────────────

class GetFilteredBoardDataInput(BaseModel):
    board_id: str = Field(description="The numeric Monday.com board ID.")
    filters: Optional[dict] = Field(
        default=None,
        description=(
            "Dict of column_name -> value to filter rows. "
            "For Deals board use 'Sector/service' for sector. "
            "For Work Order board use 'Sector' for sector. "
            "Example: {'Sector/service': 'Mining'} or {'Sector': 'Mining', 'Execution Status': 'Ongoing'}. "
            "All filters are AND logic."
        )
    )


class GetFilteredBoardDataTool(BaseTool):
    name: str = "get_filtered_board_data"
    description: str = (
        "USE THIS when the user asks about a SPECIFIC sector, owner, status, or category. "
        "Fetches only matching rows — keeps token usage low. "
        "Examples: 'Mining pipeline', 'Open deals', 'OWNER_002 workload', 'Ongoing work orders'. "
        "NOTE: Deals board sector column = 'Sector/service'. Work Order board sector column = 'Sector'."
    )
    args_schema: Type[BaseModel] = GetFilteredBoardDataInput

    def _run(self, board_id: str, filters: dict = None) -> str:
        board_name, flat_data = _fetch_all_items(board_id)
        if not flat_data:
            return f"No data found for board {board_id}."

        total_rows = len(flat_data)
        filtered = _filter_rows(flat_data, filters) if filters else flat_data
        matched = len(filtered)

        if not filtered:
            return (
                f"No rows matched filters {filters} in board '{board_name}'. "
                f"Total rows: {total_rows}. "
                f"Tip: Use get_board_schema to verify exact column names and available values."
            )

        filtered, was_truncated = _safe_truncate(filtered)
        filter_desc = ", ".join(f"{k}='{v}'" for k, v in filters.items()) if filters else "none"
        summary = (
            f"Board: '{board_name}' | Filters: {filter_desc} | "
            f"Matched: {matched} of {total_rows} rows"
        )
        if was_truncated:
            summary += f" | WARNING: Showing {len(filtered)} rows due to size limit"

        return summary + "\n\n" + json.dumps(filtered)


# ── Tool 4: Get Board Aggregates ──────────────────────────────────────────────

class GetBoardAggregatesInput(BaseModel):
    board_id: str = Field(description="The numeric Monday.com board ID.")
    group_by_column: str = Field(
        description=(
            "Column name to group rows by. "
            "For Deals board use 'Sector/service' to group by sector. "
            "For Work Order board use 'Sector' to group by sector. "
            "Other examples: 'Deal Status', 'Execution Status', 'Owner code', 'BD/KAM Personnel code'."
        )
    )
    numeric_columns: Optional[list] = Field(
        default=None,
        description=(
            "List of numeric column names to sum and average per group. "
            "Deals board examples: ['Masked Deal value']. "
            "Work Order board examples: ['Amount in Rupees (Excl of GST) (Masked)', "
            "'Billed Value in Rupees (Excl of GST.) (Masked)', "
            "'Collected Amount in Rupees (Incl of GST.) (Masked)', "
            "'Amount Receivable (Masked)']. "
            "If not provided, only row counts per group are returned."
        )
    )


class GetBoardAggregatesTool(BaseTool):
    name: str = "get_board_aggregates"
    description: str = (
        "USE THIS when the user asks to COMPARE, RANK, or TOTAL across ALL categories. "
        "Examples: 'Compare all sectors', 'Which sector has highest revenue?', "
        "'Total deal value by stage', 'Rank owners by number of deals'. "
        "Processes ALL rows in Python — always 100% accurate, never hits token limits. "
        "NOTE: Deals board sector = 'Sector/service'. Work Order board sector = 'Sector'."
    )
    args_schema: Type[BaseModel] = GetBoardAggregatesInput

    def _run(self, board_id: str, group_by_column: str, numeric_columns: list = None) -> str:
        board_name, flat_data = _fetch_all_items(board_id)
        if not flat_data:
            return f"No data found for board {board_id}."

        total_rows = len(flat_data)

        # Group rows
        groups = defaultdict(list)
        for row in flat_data:
            key = str(row.get(group_by_column, "Unknown")).strip()
            if not key or key == "null":
                key = "(blank)"
            groups[key].append(row)

        if not groups:
            return (
                f"Column '{group_by_column}' not found or has no values in board '{board_name}'. "
                f"Available columns: {list(flat_data[0].keys()) if flat_data else []}"
            )

        # Aggregate per group
        summary = []
        for group_key, rows in sorted(groups.items()):
            entry = {"group": group_key, "count": len(rows)}

            if numeric_columns:
                for col in numeric_columns:
                    values = [_parse_number(r.get(col)) for r in rows]
                    values = [v for v in values if v is not None]
                    if values:
                        entry[f"{col}_total"] = round(sum(values), 2)
                        entry[f"{col}_avg"] = round(sum(values) / len(values), 2)
                        entry[f"{col}_parsed_count"] = len(values)
                    else:
                        entry[f"{col}_total"] = "N/A"

            summary.append(entry)

        # Sort by count descending
        summary.sort(key=lambda x: x["count"], reverse=True)

        return (
            f"Board: '{board_name}' | Total rows: {total_rows} | "
            f"Grouped by: '{group_by_column}'\n\n"
            f"{json.dumps(summary, indent=2)}\n\n"
            f"All {total_rows} rows processed in Python — full accuracy, no truncation."
        )


def get_tools():
    return [
        GetAllBoardsTool(),
        GetBoardSchemaTool(),
        GetFilteredBoardDataTool(),
        GetBoardAggregatesTool(),
    ]
