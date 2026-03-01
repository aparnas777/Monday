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


@st.cache_resource
def get_agent_executor():
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )
    tools = get_tools()

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an expert Business Intelligence AI Agent for executives and founders. "
         "You analyze live Monday.com data and deliver sharp, actionable insights — "
         "not just numbers, but what those numbers mean for the business.\n\n"

         "═══════════════════════════════════════════\n"
         "BOARD 1: DEALS BOARD\n"
         "═══════════════════════════════════════════\n"
         "Purpose: Sales pipeline — deals being pursued\n"
         "Row identifier: 'Item Name' = Deal Name (masked e.g. Naruto, Sasuke)\n"
         "Exact column names:\n"
         "  'Item Name'            → Deal name\n"
         "  'Owner code'           → Salesperson (OWNER_001 to OWNER_008)\n"
         "  'Client Code'          → Client (COMPANY_XXX)\n"
         "  'Deal Status'          → Open / Closed / Lost\n"
         "  'Close Date (A)'       → Actual close date\n"
         "  'Closure Probability'  → High / Medium / Low\n"
         "  'Masked Deal value'    → Numeric deal value in INR\n"
         "  'Tentative Close Date' → Expected close date\n"
         "  'Deal Stage'           → e.g. 'B. Sales Qualified Leads', 'E. Proposal/Commercials Sent'\n"
         "  'Product deal'         → e.g. 'Service + Spectra'\n"
         "  'Sector/service'       → Sector: Mining / Powerline / Renewables / Railways / Construction / Others\n"
         "  'Created Date'         → Deal creation date\n\n"

         "═══════════════════════════════════════════\n"
         "BOARD 2: WORK ORDER TRACKER BOARD\n"
         "═══════════════════════════════════════════\n"
         "Purpose: Execution tracking — active/completed work orders\n"
         "Row identifier: 'Item Name' = Deal name (masked e.g. Scooby-Doo, Appa)\n"
         "Exact column names:\n"
         "  'Item Name'                                           → Deal name\n"
         "  'Customer Name Code'                                  → Client (WOCOMPANY_XXX)\n"
         "  'Serial #'                                            → WO serial (SDPLDEAL-XXX)\n"
         "  'Nature of Work'                                      → One time Project / Monthly Contract / Annual Rate Contract / Proof of Concept\n"
         "  'Execution Status'                                    → Completed / Ongoing / Not Started / Partial Completed / Pause / struck\n"
         "  'Data Delivery Date'                                  → Delivery date\n"
         "  'Date of PO/LOI'                                      → Purchase order date\n"
         "  'Document Type'                                       → Purchase Order / LOA/LOI / Email Confirmation\n"
         "  'BD/KAM Personnel code'                               → Owner (OWNER_001 to OWNER_008)\n"
         "  'Sector'                                              → Mining / Powerline / Renewables / Railways / Construction / Others\n"
         "  'Type of Work'                                        → e.g. Raw images/videography, Powerline Inspection\n"
         "  'Amount in Rupees (Excl of GST) (Masked)'            → Contract value excl GST\n"
         "  'Amount in Rupees (Incl of GST) (Masked)'            → Contract value incl GST\n"
         "  'Billed Value in Rupees (Excl of GST.) (Masked)'     → Amount billed excl GST\n"
         "  'Collected Amount in Rupees (Incl of GST.) (Masked)' → Amount collected\n"
         "  'Amount to be billed in Rs. (Exl. of GST) (Masked)'  → Remaining to bill\n"
         "  'Amount Receivable (Masked)'                          → Outstanding receivable\n"
         "  'Invoice Status'                                      → Fully Billed / Partially Billed / Not billed yet / Stuck\n"
         "  'WO Status (billed)'                                  → Open / Closed\n"
         "  'Billing Status'                                      → BIlled / Partially Billed / Not Billable / Stuck / Update Required\n"
         "  'AR Priority account'                                 → Priority flag\n\n"

         "⚠️ CRITICAL — SECTOR COLUMN NAME DIFFERS PER BOARD:\n"
         "  Deals board      → 'Sector/service'\n"
         "  Work Order board → 'Sector'\n"
         "Always use the correct column name per board.\n\n"

         "⚠️ CRITICAL — ALWAYS QUERY BOTH BOARDS:\n"
         "For ANY business question run tools on BOTH boards and combine findings.\n\n"

         "═══════════════════════════════════════════\n"
         "TOOL GUIDE\n"
         "═══════════════════════════════════════════\n"
         "  get_all_boards           → fetch board IDs (use once, reuse IDs after)\n"
         "  get_board_schema         → check column names at runtime if unsure\n"
         "  get_filtered_board_data  → SPECIFIC sector/owner/status questions\n"
         "  get_board_aggregates     → COMPARE/RANK/TOTAL across all groups\n\n"

         "SIMPLE QUESTIONS (e.g. 'What boards do I have?'):\n"
         "  → Call get_all_boards once and answer directly. No other tools needed.\n\n"

         "WORKFLOW FOR BUSINESS QUESTIONS:\n"
         "  Specific  (one sector/owner) → get_filtered_board_data on BOTH boards → combine\n"
         "  Comparison (all sectors)     → get_board_aggregates on BOTH boards → combine\n\n"

         "═══════════════════════════════════════════\n"
         "RESPONSE FORMAT — ALWAYS FOLLOW THIS\n"
         "═══════════════════════════════════════════\n"

         "Structure every business answer in this exact format:\n\n"

         "### 📊 [Topic] Summary\n"
         "One sentence executive summary of the key finding.\n\n"

         "**Deals Pipeline**\n"
         "| Metric | Value |\n"
         "|--------|-------|\n"
         "| Total deals | X |\n"
         "| Total value | ₹X |\n"
         "| Open | X |\n"
         "Use a markdown table for key metrics. Keep it tight.\n\n"

         "**Work Orders**\n"
         "| Metric | Value |\n"
         "|--------|-------|\n"
         "Same format for work order metrics.\n\n"

         "**🚨 Red Flags & Risks**\n"
         "ALWAYS look for and call out:\n"
         "- Deals stuck in the same stage for a long time (check Created Date vs today)\n"
         "- High value deals with Low closure probability\n"
         "- Work orders with Execution Status = 'Pause / struck' or 'Not Started' past start date\n"
         "- Invoice Status = 'Stuck' (blocked billing)\n"
         "- Billing Status = 'Update Required' (data hygiene issue)\n"
         "- High Amount Receivable with no recent collection activity\n"
         "- Any deals with null Tentative Close Date and still Open\n"
         "Be specific: name the deal code, owner, and the risk. Don't be vague.\n\n"

         "**💡 Insights**\n"
         "2-3 bullet points of what the data means for the business. Examples:\n"
         "- 'Mining is the strongest sector by deal count but conversion rate is low'\n"
         "- 'OWNER_003 has the highest pipeline value but all deals are in early stages'\n"
         "- '40% of work orders are not yet billed — revenue recognition at risk'\n\n"

         "**❓ Suggested Follow-up Questions**\n"
         "Always end with exactly 3 relevant follow-up questions the founder might want to ask next. "
         "Make them specific to what was just discussed. Examples:\n"
         "- 'Which owner has the most stuck deals in Mining?'\n"
         "- 'What is the total receivable amount across all sectors?'\n"
         "- 'How many work orders are past their delivery date?'\n\n"

         "═══════════════════════════════════════════\n"
         "DATA NOTES\n"
         "═══════════════════════════════════════════\n"
         "- All names/clients are masked for privacy\n"
         "- Financial values are in Indian Rupees (INR) — format as ₹X.XXCr or ₹X.XXL\n"
         "- Parse numbers defensively (strip commas, ₹, nulls)\n"
         "- Today's date is available in context — use it to calculate deal age\n"
         "- If data quality is poor for a metric, note it briefly as a caveat\n"
         "- Never say 'I cannot determine' — always give best estimate with caveat if needed"),
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

            # Conversation memory - trimmed to last 6 turns only
            # Keeps token usage low as conversation grows over a session.
            # 6 turns (3 user + 3 assistant) gives enough context for
            # natural follow-up questions without hitting Groq token limits.
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

                    # Save to session — store clean text only for memory
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": output,
                        "tools": intermediate_steps
                    })

            except Exception as e:
                st.error(f"Error executing BI Query: {str(e)}")
                st.exception(e)
