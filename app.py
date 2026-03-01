import os
import streamlit as st
from dotenv import load_dotenv

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from agent_tools import get_tools

load_dotenv()

st.set_page_config(page_title="Monday.com BI Agent", layout="wide")
st.title("📊 Monday.com Business Intelligence Agent")

api_token = os.environ.get("MONDAY_API_TOKEN", "")
groq_key = os.environ.get("GROQ_API_KEY", "")

if not api_token or not groq_key:
    st.warning("Please ensure MONDAY_API_TOKEN and GROQ_API_KEY are set in your Streamlit secrets.")
    st.stop()


# Column reference kept outside prompt — used only if LLM needs a hint via get_board_schema
DEALS_COLS = {
    "sector": "Sector/service",
    "owner": "Owner code",
    "value": "Masked Deal value",
    "status": "Deal Status",
    "stage": "Deal Stage",
    "probability": "Closure Probability",
    "close_date": "Tentative Close Date",
    "created": "Created Date",
}

WO_COLS = {
    "sector": "Sector",
    "owner": "BD/KAM Personnel code",
    "value_excl": "Amount in Rupees (Excl of GST) (Masked)",
    "billed": "Billed Value in Rupees (Excl of GST.) (Masked)",
    "collected": "Collected Amount in Rupees (Incl of GST.) (Masked)",
    "receivable": "Amount Receivable (Masked)",
    "exec_status": "Execution Status",
    "invoice_status": "Invoice Status",
    "billing_status": "Billing Status",
    "wo_status": "WO Status (billed)",
}


@st.cache_resource
def get_agent_executor():
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )
    tools = get_tools()

    # Compact system prompt — kept under ~800 tokens to leave room for data + response
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a BI agent for a founder. Answer questions using live Monday.com data.\n\n"

         "TWO BOARDS:\n"
         "1. Deals board — sales pipeline. Sector col = 'Sector/service'. Owner col = 'Owner code'. Value col = 'Masked Deal value'.\n"
         "   Sectors: Mining/Powerline/Renewables/Railways/Construction/Others.\n"
         "   Status: Open/Closed/Lost. Stage: e.g. 'B. Sales Qualified Leads'.\n\n"
         "2. Work Order board — execution tracking. Sector col = 'Sector'. Owner col = 'BD/KAM Personnel code'.\n"
         "   Value col = 'Amount in Rupees (Excl of GST) (Masked)'. Execution Status: Completed/Ongoing/Not Started/Partial Completed/Pause/struck.\n"
         "   Invoice Status: Fully Billed/Partially Billed/Not billed yet/Stuck. All amounts in INR.\n\n"

         "RULES:\n"
         "- ALWAYS query BOTH boards and combine the answer.\n"
         "- ANY question about a sector/owner/status (even specific like 'How is Mining doing?') → get_board_aggregates grouped by that column on BOTH boards. Python summarizes ALL groups, you read the relevant one. Lowest tokens, full accuracy.\n"
         "- Need ROW-LEVEL detail only (list of stuck deal names, specific overdue WO serials) → get_filtered_board_data.\n"
         "- Simple listing ('what boards?') → get_all_boards only.\n"
         "- If unsure of column names → get_board_schema first.\n\n"
         "AGGREGATION COLUMN MAP (exact names):\n"
         "Deals: sector='Sector/service', owner='Owner code', status='Deal Status', stage='Deal Stage', value='Masked Deal value'\n"
         "WO: sector='Sector', owner='BD/KAM Personnel code', exec='Execution Status', invoice='Invoice Status', value='Amount in Rupees (Excl of GST) (Masked)', receivable='Amount Receivable (Masked)'\n\n"

         "RESPONSE FORMAT (always follow):\n"
         "### 📊 [Topic] Summary\n"
         "One line executive finding.\n\n"
         "**Deals Pipeline**\n"
         "| Metric | Value |\n"
         "|--------|-------|\n"
         "| Total Deals | X |\n"
         "| Total Value | ₹X.XXCr |\n"
         "| Avg Deal Value | ₹X.XXL |\n"
         "| Open / Closed / Lost | X / X / X |\n\n"
         "**Work Orders**\n"
         "| Metric | Value |\n"
         "|--------|-------|\n"
         "| Total WOs | X |\n"
         "| Contract Value | ₹X.XXCr |\n"
         "| Billed | ₹X.XXCr |\n"
         "| Receivable | ₹X.XXL |\n\n"
         "Format all INR values as ₹X.XXCr (crores) or ₹X.XXL (lakhs) — never raw numbers.\n\n"
         "**Red Flags** — call out: stuck deals, high-value/low-probability deals, "
         "paused WOs, stuck invoices, high receivables. Name the deal code and owner.\n\n"
         "**Insights** — 2-3 bullets on what this means for the business.\n\n"
         "**Follow-up Questions** — exactly 3 specific questions the founder should ask next."
         ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
        max_iterations=20
    )


agent_executor = get_agent_executor()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tools"):
            with st.expander("🛠️ Tool Call Trace"):
                for step in msg["tools"]:
                    st.code(f"Action: {step[0].tool}\nInput: {step[0].tool_input}")
                    tool_output = str(step[1])
                    if len(tool_output) > 500:
                        tool_output = tool_output[:500] + "... [TRUNCATED]"
                    st.text(f"Raw Output:\n{tool_output}")

# Chat input
if prompt := st.chat_input("Ask about your business (e.g. 'How is the Mining sector doing?')"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Fetching live data from both boards & analyzing..."):

            # Conversation memory trimmed to last 6 turns to save tokens
            prior_messages = st.session_state.messages[:-1]
            prior_messages = prior_messages[-6:]

            chat_history = []
            for m in prior_messages:
                if m["role"] == "user":
                    chat_history.append(HumanMessage(content=m["content"]))
                elif m["role"] == "assistant":
                    chat_history.append(AIMessage(content=m["content"]))

            try:
                response = agent_executor.invoke({
                    "input": prompt,
                    "chat_history": chat_history,
                })

                output = response.get("output", "")
                intermediate_steps = response.get("intermediate_steps", [])

                if not output:
                    st.error("Agent returned no output.")
                else:
                    st.markdown(output)

                    if intermediate_steps:
                        with st.expander("🛠️ Tool Call Trace"):
                            for step in intermediate_steps:
                                st.code(f"Action: {step[0].tool}\nInput: {step[0].tool_input}")
                                tool_output = str(step[1])
                                if len(tool_output) > 500:
                                    tool_output = tool_output[:500] + "... [TRUNCATED]"
                                st.text(f"Raw Output:\n{tool_output}")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": output,
                        "tools": intermediate_steps
                    })

            except Exception as e:
                # Friendly token limit message instead of raw crash
                err = str(e)
                if "413" in err and "tokens" in err:
                    st.error(
                        " Response too large for Groq free tier (12k tokens/min limit). "
                        "Try asking a more specific question, e.g. add a sector or owner filter."
                    )
                else:
                    st.error(f"Error executing BI Query: {err}")
                    st.exception(e)
