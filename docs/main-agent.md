# Main Agent

## Overview
The Main Agent (`agent.py`) serves as the coordinator for all MCP servers in the system. It establishes connections to each specialized MCP server, combines their tools, and provides a unified interface for the user to interact with all available functionalities.

## Purpose
The Main Agent enables users to:
- Access all capabilities through a single entry point
- Interact with multiple services via natural language
- Seamlessly combine capabilities from different servers (e.g., get stock prices and send them via email)
- Manage the lifecycle of MCP servers

It serves as the "brain" of the system, coordinating specialized services and presenting them as an integrated whole.

## How It Works

### Technology
- **smolagents**: Library for creating tool-calling agents
- **LiteLLM**: Wrapper for connecting to various LLM providers
- **MCP**: Multi-agent Conversation Protocol client libraries
- **Colorama**: For styled console output

### Architecture
The Main Agent follows a modular architecture where:
1. Each MCP server is started as a child process
2. Tools from all servers are collected and combined
3. A single LLM-powered agent manages user interactions and tool selection

### Components

#### 1. Environment Setup
```python
load_dotenv(override=True)
```
Loads environment variables needed for the various servers.

#### 2. Language Model
```python
model = LiteLLMModel(
        model_id="ollama_chat/qwen2.5:14b",
        num_ctx=8192)
```
Configures the Qwen 2.5 (14B) model via Ollama for the agent.

#### 3. MCP Server Parameters
```python
finance_server_parameters = StdioServerParameters(...)
gmail_server_parameters = StdioServerParameters(...)
voice_mcp_parameters = StdioServerParameters(...)
cag_rag_server_parameters = StdioServerParameters(...)
```
Defines launch parameters for each MCP server, including command, arguments, and environment variables.

#### 4. Tool Collection
```python
with ToolCollection.from_mcp(...) as finance_tools, ...:
```
Connects to each MCP server and collects their tools.

#### 5. Agent Creation
```python
agent = ToolCallingAgent(tools=all_tools, model=model)
```
Creates a single agent with access to all tools from all servers.

## Server Coordination

The Main Agent coordinates the following servers:
1. **Yahoo Finance Server** (`server.py`) - Stock market data
2. **Gmail Server** (`mail_agent/gmail_server.py`) - Email operations
3. **Voice Call Server** (`call_agent/voice_mcp_server.py`) - Voice calling
4. **CAG+RAG Server** (`cag_rag/cag_rag_server.py`) - Project knowledge base

Each server runs as a separate process, and the Main Agent communicates with them via the MCP protocol.

## Setup and Launch

### Prerequisites
- Python 3.12 or later
- Dependencies installed via uv: `smolagents`, `mcp`, `colorama`, `dotenv`
- Environment variables:
  - `VOICE_SERVER_URL`: URL of the running Voice Server
  - Any server-specific environment variables (e.g., `OPENAI_API_KEY` for the CAG+RAG server)

### How to Launch
To start the Main Agent along with all the MCP servers:

```bash
cd step1
uv run agent.py
```

This will:
1. Start all MCP servers as child processes
2. Connect to each server and collect their tools
3. Initialize the agent with all tools
4. Present an interactive chat interface

### Usage Examples
Once the agent is running, you can interact with it using natural language:

1. **Finance queries**:
   - "What is the current price of AAPL stock?"
   - "Get me the income statement for Microsoft."

2. **Email operations**:
   - "Read my latest email."
   - "Send an email to example@example.com with the subject 'Meeting' and body 'Let's meet tomorrow.'"

3. **Voice calls**:
   - "Call +14155551212 and ask about their availability for a meeting next week."

4. **Project information**:
   - "What is the purpose of the CAG_RAG project?"
   - "How does the Gmail server authenticate with Google?"

### Troubleshooting
- If a specific functionality isn't working, check that the corresponding MCP server is running
- For environment-related issues, verify that all required environment variables are set
- If the agent won't start, check for errors in the console output related to server initialization
- For LLM-related issues, verify that Ollama is running and the specified model is available 