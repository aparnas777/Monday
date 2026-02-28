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
         "Your job is to answer founder-level business questions about Deals and Work Orders. "
         "\n\nYou have access to live Monday.com data tools. You MUST fetch fresh data every time "
         "via `get_board_data` when asked a question. If you do not know the board IDs, first call `get_all_boards`. "
         "\n\nWARNING: Monday.com data can be messy (nulls, inconsistent formats). "
         "Clean and parse defensively before doing any math or aggregation. "
         "Provide concise, executive-focused answers. Note any 'Data Quality Caveats' briefly."),
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
        max_iterations=10
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
if prompt := st.chat_input("Ask a question about your business (e.g. 'How is our pipeline looking in the Energy sector?')"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Fetching live data from Monday.com & analyzing..."):
            chat_history = []
            for m in st.session_state.messages[:-1]:
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
                st.error(f"Error executing BI Query: {str(e)}")
                st.exception(e)
