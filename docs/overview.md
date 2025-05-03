# MCP Agents Overview

This documentation provides an overview of the Multi-agent Conversation Protocol (MCP) system implemented in this project. The system consists of multiple specialized agents that work together through a central coordinator.

## Project Structure

The project is organized into several specialized MCP servers, each responsible for different functionality:

- **ML/DL News Server** (`server.py`) - Provides tools for machine learning and deep learning news search
- **Gmail Server** (`mail_agent/gmail_server.py`) - Enables email interaction via Gmail
- **Voice Call Server** (`call_agent/voice_mcp_server.py`) - Facilitates voice calls and transcriptions
- **CAG+RAG Server** (`cag_rag/cag_rag_server.py`) - Provides context-aware generation and retrieval augmented generation for answering questions about the project codebase

## Architecture

The system follows a modular architecture where:

1. Each specialized functionality is contained in its own MCP server
2. The main agent (`agent.py`) coordinates all servers and exposes their tools to the user
3. Each server implements the MCP protocol via FastMCP or StdioServer
4. Communication happens through standardized tool definitions

## Core Components

- **Main Agent** (`agent.py`): Orchestrates all MCP servers, combines their tools, and provides a unified chat interface
- **MCP Servers**: Independent specialized servers that expose tools for specific domains
- **FastMCP**: Server-side SDK that facilitates creating MCP-compatible tools and resources
- **Tool Collections**: Client-side representations of server tools that the agent can use

## Technology Stack

- **Python 3.12**: Core programming language
- **UV**: Package manager and Python environment manager
- **LangChain/LangGraph**: For building the CAG+RAG agent
- **OpenAI**: For AI capabilities in the CAG+RAG agent
- **Google API**: For Gmail integration
- **Web Search APIs**: For machine learning and deep learning news
- **Twilio/Voice API**: For voice calling capabilities

## Getting Started

1. Set up the environment:
   ```bash
   uv venv
   source .venv/bin/activate
   uv sync
   ```

2. Configure necessary credentials (Gmail, OpenAI, Voice service)

3. Run the main agent:
   ```bash
   uv run agent.py
   ```

For detailed information about each MCP server, refer to their respective documentation:
- [Finance Server Documentation](finance-server.md)
- [Gmail Server Documentation](gmail-server.md)
- [Voice Call Server Documentation](voice-server.md)
- [CAG+RAG Server Documentation](cag-rag-server.md)
- [Video Generator Documentation](video-generator.md) 