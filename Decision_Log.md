Tech Stack Choices

Python 3.10 & LangChain
Python was chosen for its strong data ecosystem. LangChain’s create_tool_calling_agent was selected for stable, native tool-calling support with Groq.

Groq (LLaMA 3.3 70B)
Selected as a cost-efficient inference layer after OpenAI API credits were exhausted. Provides fast responses with native tool calling.

Streamlit
Used for rapid development of a conversational BI interface with tool-trace visibility for debugging.

Monday.com GraphQL API
Used for live, structured data retrieval with precise column-level queries.

Agent Architecture Decision

Instead of letting the LLM:

Perform numeric aggregation

Parse raw board rows

Construct complex GraphQL queries

The system uses structured tools and shifts all aggregation logic to Python.

What This System Can Do

The Monday.com BI Agent can:

Answer sector-level performance questions
(“How is Mining doing?”)

Analyze pipeline health
(Deal stages, closure probability, stuck deals)

Track revenue and billing metrics

Identify red flags
(Paused work orders, overdue invoices, high receivables)

Combine insights across multiple boards
(Sales + Execution data)

Deliver structured, founder-ready responses:

Executive summary

Key metrics tables

Risk alerts

Business insights

Guided follow-up questions
