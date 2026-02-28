# Monday.com Business Intelligence Agent

An AI agent that answers founder-level business intelligence queries by integrating with Monday.com boards containing Work Orders and Deals data in real-time.

## Features
- **Live Monday.com Integration**: Executes API calls exactly at query time. No data is cached or preloaded inside the agent.
- **Data Resilience**: Gracefully handles dirty data using pandas during the ingestion and analysis steps.
- **Agentic BI capabilities**: Uses `langchain` and `gpt-4o` (or `gpt-3.5-turbo`) to write Python code to execute analysis over Monday.com GraphQL data.
- **Streamlit Interface**: An interactive chat interface to converse with the agent.

## How to run on Streamlit Community Cloud

Hosting on Streamlit Community Cloud is the easiest way to share a live, no-setup prototype.

### 1. Push to GitHub
1. Create a new public (or private) GitHub repository.
2. Upload all the Python files from this repo (`app.py`, `ingest.py`, `agent_tools.py`, `requirements.txt`).

### 2. Data Ingestion (One-time setup locally)
Before deploying, you need to create the boards on Monday.com and populate them with the provided Excel data.
You can run the ingestion script locally on your machine or in a Colab/Kaggle notebook:
```bash
# Ensure you have your MONDAY_API_TOKEN set as an environment variable
pip install pandas requests openpyxl
python ingest.py --work-orders "path/to/Work_Order_Tracker Data.xlsx" --deals "path/to/Deal funnel Data.xlsx"
```
*Note: The script outputs the IDs of the newly created boards. Write them down.*

### 3. Deploy to Streamlit
1. Go to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.
2. Click **New app**.
3. Select the repository, branch, and set the Main file path to `app.py`.
4. **CRITICAL:** Before clicking Deploy, click on **Advanced settings**.
5. In the **Secrets** section, add your API keys like this:
   ```toml
   MONDAY_API_TOKEN = "your_actual_monday_token"
   GROQ_API_KEY = "your_actual_groq_api_key"
   ```
6. Click **Save** and then **Deploy!**

Your agent will now be live and accessible via a public URL provided by Streamlit.
