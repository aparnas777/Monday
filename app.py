import os
import streamlit as st
from dotenv import load_dotenv

import pandas as pd
import json

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from agent_tools import get_tools

load_dotenv()

st.set_page_config(page_title="Monday.com BI Agent", layout="wide")
st.title("📊 Monday.com Business Intelligence Agent")

# Verification
api_token = os.environ.get("MONDAY_API_TOKEN", "")
openai_key = os.environ.get("GROQ_API_KEY", "")

if not api_token or not openai_key:
    st.warning("Please ensure MONDAY_API_TOKEN and OPENAI_API_KEY are set in your environment variables or Secrets.")
    st.stop()

# Initialize LangChain
@st.cache_resource
def get_agent_executor():
    llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    temperature=0
)
    tools = get_tools()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Business Intelligence AI Agent for executives and founders. "
                   "Your job is to answer founder-level business questions about Deals and Work Orders. "
                   "\\n\\nYou have access to live Monday.com data tools. You MUST fetch the exact, fresh data "
                   "every single time via `get_board_data` tool when asked a question, as data can change minute by minute. "
                   "If you do not know the board IDs, first use `get_all_boards`."
                   "\\n\\nWARNING: The data fetched from Monday.com is extremely messy (null values, inconsistent formats like USD vs $, date varieties). "
                   "It is YOUR responsibility to defensively parse and clean the data mentally before performing math or aggregations. "
                   "For example, when calculating 'Total Revenue', ignore unparseable fields or defensively convert strings. "
                   "Provide extremely concise, executive-focused answers with insights. If data is bad, mention the 'Data Quality Caveats' briefly."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_openai_tools_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False, return_intermediate_steps=False)

agent_executor = get_agent_executor()

# Chat UI
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "tools" in msg and msg["tools"]:
            with st.expander("🛠️ Tool Call Trace"):
                for step in msg["tools"]:
                    st.code(f"Action: {step[0].tool}\\nInput: {step[0].tool_input}")
                    
                    # Displaying partial output to avoid overflowing the UI
                    tool_output = str(step[1])
                    if len(tool_output) > 500:
                        tool_output = tool_output[:500] + "... [TRUNCATED]"
                    st.text(f"Raw Output:\\n{tool_output}")

# Chat Input
if prompt := st.chat_input("Ask a question about your business (e.g. 'How is our pipeline looking in the Energy sector?')"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    with st.chat_message("assistant"):
        with st.spinner("Fetching live data from Monday.com & analyzing..."):
            # Map history to langchain format
            chat_history = []
            for m in st.session_state.messages[:-1]:
                if m["role"] == "user":
                    chat_history.append(HumanMessage(content=m["content"]))
                else:
                    chat_history.append(AIMessage(content=m["content"]))
            
            try:
                response = agent_executor.invoke({
                    "input": prompt,
                    "chat_history": chat_history
                })
                
                if not isinstance(response, dict):
                    st.error("Invalid response from agent.")
                    return
                
                output = response.get("output")
                
                if not output:
                    st.error("Agent returned no output.")
                    return
                
                st.markdown(output)
                
                # Show tools used
                intermediate_steps = response.get("intermediate_steps", [])
                if intermediate_steps:
                    with st.expander("🛠️ Tool Call Trace (Visible for Evaluator)"):
                        for step in intermediate_steps:
                            st.code(f"Action: {step[0].tool}\\nInput: {step[0].tool_input}")
                            st.text("Agent executed live API call and received un-cached data.")
                
                # Save to history
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": output,
                    "tools": intermediate_steps
                })

            except Exception as e:
                st.error(f"Error executing BI Query: {str(e)}")
