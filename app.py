import os
import streamlit as st
from dotenv import load_dotenv

from langchain.agents import AgentExecutor, create_react_agent
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from agent_tools import get_tools

load_dotenv()

st.set_page_config(page_title="Monday.com BI Agent", layout="wide")
st.title("📊 Monday.com Business Intelligence Agent")

# Verification
api_token = os.environ.get("MONDAY_API_TOKEN", "")
groq_key = os.environ.get("GROQ_API_KEY", "")

if not api_token or not groq_key:
    st.warning("Please ensure MONDAY_API_TOKEN and GROQ_API_KEY are set in your environment variables or Secrets.")
    st.stop()

@st.cache_resource
def get_agent_executor():
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )
    tools = get_tools()

    # ReAct prompt — required format for create_react_agent
    # Must include: {tools}, {tool_names}, {input}, {agent_scratchpad}
    # chat_history is optional but supported
    react_prompt = PromptTemplate.from_template(
        """You are an expert Business Intelligence AI Agent for executives and founders.
Your job is to answer founder-level business questions about Deals and Work Orders.

You have access to live Monday.com data tools. You MUST fetch fresh data every time via
`get_board_data` when asked a question. If you do not know the board IDs, first call `get_all_boards`.

WARNING: Monday.com data can be messy (nulls, inconsistent formats). Clean/parse defensively before math.
Provide concise, executive-focused answers. Note any 'Data Quality Caveats' briefly.

Previous conversation:
{chat_history}

You have access to the following tools:
{tools}

Use the following format EXACTLY:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
    )

    agent = create_react_agent(llm, tools, react_prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        return_intermediate_steps=True,
        handle_parsing_errors=True,   # prevents crashes on malformed LLM output
        max_iterations=10
    )

agent_executor = get_agent_executor()

# Chat state
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
            # Build chat history string for ReAct prompt (simpler than message objects)
            history_lines = []
            for m in st.session_state.messages[:-1]:
                role = "Human" if m["role"] == "user" else "Assistant"
                history_lines.append(f"{role}: {m['content']}")
            chat_history_str = "\n".join(history_lines) if history_lines else "None"

            try:
                response = agent_executor.invoke({
                    "input": prompt,
                    "chat_history": chat_history_str,
                })

                output = response.get("output", "")
                intermediate_steps = response.get("intermediate_steps", [])

                if not output:
                    st.error("Agent returned no output.")
                else:
                    st.markdown(output)  # ← this was missing before!

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
                st.exception(e)  # shows full traceback during debugging
