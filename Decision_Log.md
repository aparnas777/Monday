# Decision Log

## Tech Stack Choices

1. **Python & LangChain**: Python is the lingua franca of Data Science and AI. LangChain provides excellent abstractions for tool-calling agents. It allows seamless integration with OpenAI's latest function-calling models (`gpt-4o` / `gpt-3.5-turbo`) to enforce strict API parameter types.
2. **Streamlit**: Selected for the frontend because it allows ultra-fast development of conversational AI tools. It is heavily used in the data ecosystem and simple to host on platforms like Streamlit Community Cloud, or via localtunnel on Kaggle.
3. **Monday.com GraphQL API**: Used over REST since Monday.com heavily invests in its GraphQL endpoint. It provides highly specific queries to fetch column values efficiently.

## Agent Approach: Tool Calling vs Python REPL

**Problem:** The prompt states "Every query must trigger live API calls at query time. Do NOT preload or cache data." and "Business intelligence... provide insights across revenue, pipeline health, sector performance."

Providing a generic `execute_graphql` tool to an LLM often results in hallucinations, as the LLM doesn't perfectly understand Monday.com's complex query schema. However, providing generic board fetching tools puts the aggregation burden on the LLM's context window. 

**Decision**: The agent is provided with structural tools:
- `list_boards()`
- `get_board_schema(board_id)`
- `fetch_board_data(board_id)`

To do complex aggregations ("What is the total revenue in the energy sector?"), asking an LLM to sum numbers in its head is unreliable. Instead, since we are fetching live data when the user asks, we will expose the downloaded data as a Pandas DataFrame within a **LangChain Python REPL Agent**. 

1. The LLM gets a user question.
2. The LLM creates Python code that uses the `MondayAPI` wrapper to fetch fresh data for specific boards (satisfying the "Live API Call" requirement).
3. The LLM uses Pandas within the REPL to aggregate, filter, and compute the answer accurately, overcoming the messy data format (satisfying the "Data Resilience" requirement).
4. Since the agent executes real Python code behind the scenes, we can guarantee mathematical accuracy for aggregation queries.

## Data Resilience Handling

The raw data is intentionally messy (e.g., revenue as `$1,000` strings, mixed date formats, null values).
These issues are handled at two layers:
1. **Ingestion Layer (`ingest.py`)**: When syncing to Monday.com, we use Pandas to normalize values (strip `$`, convert to numeric, normalize dates). We explicitly map data types to Monday.com column types (e.g., Dates to `date`, Numbers to `numeric`).
2. **Agent Layer**: The LLM is instructed to treat all data defensively, cleaning columns (like filling `NaN` or stripping unexpected chars) in the Python REPL before grouping and summarizing.
