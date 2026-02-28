# Monday.com Business Intelligence Agent

An AI agent that answers founder-level business intelligence queries by integrating with Monday.com boards containing Work Orders and Deals data in real-time.

## Features
- **Live Monday.com Integration**: Executes API calls exactly at query time. No data is cached or preloaded inside the agent.
- **Data Resilience**: Gracefully handles dirty data using pandas during the ingestion and analysis steps.
- **Agentic BI capabilities**: Uses `langchain` and `gpt-4o` (or `gpt-3.5-turbo`) to write Python code to execute analysis over Monday.com GraphQL data.
- **Streamlit Interface**: An interactive chat interface to converse with the agent.

## How to run on Kaggle

Since this provides a Streamlit web app, running it entirely inside a Kaggle notebook requires tunneling the web port.

### 1. Setup Data and Keys
1. Create a Kaggle Notebook.
2. Upload the `Deal funnel Data.xlsx` and `Work_Order_Tracker Data.xlsx` files to your Kaggle input directory (e.g., `/kaggle/input/...`).
3. Upload all the Python files from this repo (`app.py`, `ingest.py`, `agent_tools.py`, `requirements.txt`).
4. In Kaggle, add your API keys in the **Add-ons -> Secrets** menu:
   - `MONDAY_API_TOKEN`: Your Monday.com API Token.
   - `OPENAI_API_KEY`: Your OpenAI API Key.

### 2. Install Dependencies
Run the following in a notebook cell:
```python
!pip install -r requirements.txt
!npm install -g localtunnel
```

### 3. Data Ingestion (One-time setup)
First, you need to create the boards on Monday.com and populate them with the provided Excel data.
Run the ingestion script in a cell:
```python
import os
from kaggle_secrets import UserSecretsClient

user_secrets = UserSecretsClient()
os.environ["MONDAY_API_TOKEN"] = user_secrets.get_secret("MONDAY_API_TOKEN")

# Run the ingestion script (update the paths to your kaggle input directory)
!python ingest.py --work-orders "/kaggle/input/your-dataset/Work_Order_Tracker Data.xlsx" --deals "/kaggle/input/your-dataset/Deal funnel Data.xlsx"
```
*Note: The script outputs the IDs of the newly created boards. Write them down.*

### 4. Run the Streamlit Agent
Finally, start the Streamlit app and Expose it via Localtunnel:
```python
import os
from kaggle_secrets import UserSecretsClient

user_secrets = UserSecretsClient()
os.environ["MONDAY_API_TOKEN"] = user_secrets.get_secret("MONDAY_API_TOKEN")
os.environ["OPENAI_API_KEY"] = user_secrets.get_secret("OPENAI_API_KEY")

!streamlit run app.py & npx localtunnel --port 8501
```

Click the `localtunnel` URL in the output to access your hosted app. (Localtunnel might ask for your public IP, which you can get by running `!curl ipv4.icanhazip.com`).
