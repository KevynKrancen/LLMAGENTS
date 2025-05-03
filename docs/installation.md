# Installation and Setup Guide

This guide will walk you through setting up the MCP project environment and all its components.

## System Requirements

- **Python**: 3.12 or later
- **Operating System**: macOS, Linux, or Windows
- **RAM**: 8GB minimum (16GB+ recommended for running multiple servers and LLMs)
- **Disk Space**: 1GB+ for code, dependencies, and databases
- **Internet Connection**: Required for API access (OpenAI, Google, Twilio, etc.)

## Environment Setup

### 1. Clone or Download the Project

```bash
git clone https://github.com/yourusername/your-repo.git
cd your-repo/step1
```

### 2. Create a Python Virtual Environment

Using UV (recommended):
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Using Python's built-in venv:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

Using UV (faster):
```bash
uv sync
```

Or using pip:
```bash
pip install -r requirements.txt  # If you have a requirements.txt file
# Or
pip install -e .  # If you have a pyproject.toml file
```

## Configuration

### Environment Variables

Create a `.env` file in the `step1` directory with the following variables:

```
# Required for Voice Call functionality
VOICE_SERVER_URL=http://localhost:8000

# Required for CAG+RAG functionality
OPENAI_API_KEY=your_openai_api_key

# Optional: Twilio credentials for voice call functionality
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
```

### Service-Specific Setup

#### 1. Gmail Integration

1. Create a Google Cloud project and enable the Gmail API
2. Create OAuth credentials (Desktop application type)
3. Download the credentials JSON file and save it as `credentials.json` in the `step1` directory
4. The first time you run the Gmail server, it will prompt you to authenticate

#### 2. Voice Call Setup

1. Create a Twilio account if you don't have one
2. Get your Account SID and Auth Token from the Twilio console
3. Acquire a Twilio phone number with voice capabilities
4. Add these details to your `.env` file

#### 3. CAG+RAG Setup

1. Create an OpenAI API key if you don't have one
2. Add it to your `.env` file as `OPENAI_API_KEY`
3. Build the FAISS index by running `uv run CAG_RAG/cag_rag.py` once before using the CAG+RAG server

#### 4. Ollama Setup (for Local LLM)

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Pull the Qwen 2.5 model:
   ```bash
   ollama pull qwen2.5:14b
   ```
3. Ensure Ollama is running when you start the agent

## Starting the System

### Individual Components

Each component can be run individually for testing:

- **Finance Server**: `uv run server.py`
- **Gmail Server**: `uv run mail_agent/gmail_server.py`
- **Voice Server**: `uv run call_agent/voicecall.py`
- **Voice MCP Server**: `uv run call_agent/voice_mcp_server.py`
- **CAG+RAG Server**: `uv run cag_rag/cag_rag_server.py`

### Full System

To run the entire system:

1. Start the Voice Server first:
   ```bash
   uv run call_agent/voicecall.py
   ```

2. In a separate terminal, start the main agent (which will start all MCP servers):
   ```bash
   uv run agent.py
   ```

## Troubleshooting

### Common Issues

- **Module Not Found Errors**: Ensure you've installed all dependencies with `uv sync`
- **OAuth Errors**: Delete `token.json` and try authenticating again
- **OpenAI API Errors**: Verify your API key is correct and has sufficient credits
- **LLM Errors**: Make sure Ollama is running and the specified model is available
- **Voice Call Errors**: Verify Twilio credentials and that your `VOICE_SERVER_URL` points to a running Voice Server

### Logs

If you encounter issues, check:
- Terminal output for error messages
- `.log` files in your project directories (if any)
- Server responses for specific error codes

## Updating

To update the project:

1. Pull the latest changes:
   ```bash
   git pull
   ```

2. Update dependencies:
   ```bash
   uv sync
   ```

3. Rebuild any necessary indexes:
   ```bash
   uv run CAG_RAG/cag_rag.py
   ``` 