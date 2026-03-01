# Monday.com Business Intelligence Agent

An AI agent that answers founder-level business intelligence queries by integrating with Monday.com boards containing Work Orders and Deals data in real-time.

## Features
- **Live Monday.com Integration**: Executes API calls exactly at query time. No data is cached or preloaded inside the agent.
- **Data Resilience**: Gracefully handles dirty data using pandas during the ingestion and analysis steps.
- **Agentic BI capabilities**: Uses `langchain` and `gpt-4o` (or `gpt-3.5-turbo`) to write Python code to execute analysis over Monday.com GraphQL data.
- **Streamlit Interface**: An interactive chat interface to converse with the agent.



