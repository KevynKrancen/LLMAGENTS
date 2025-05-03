# Gmail MCP Server

## Overview
The Gmail MCP server provides tools to interact with Gmail, enabling users to read latest emails and send emails through the Google Gmail API. It handles authentication, token management, and Gmail API operations in a secure way.

## Purpose
This server enables users to:
- Read the latest emails from their Gmail inbox
- Send emails to any recipient
- All while maintaining security through OAuth 2.0 authentication

The Gmail server expands the agent's capabilities to include email communication, making it useful for automated assistant tasks that require email interaction.

## How It Works

### Technology
- **Google Gmail API**: Provides access to Gmail functionality
- **OAuth 2.0**: Manages authentication securely
- **FastMCP**: Server framework that exposes Gmail operations as tools

### Authentication Flow
The server implements a complete OAuth 2.0 flow:
1. Checks for existing OAuth tokens (`token.json`)
2. If token exists but is expired, attempts to refresh
3. If no token or refresh fails, initiates a new OAuth flow
4. Saves the token for future use

### Components

#### 1. MCP Server Instance
```python
mcp = FastMCP("gmailserver")
```
Creates an MCP server named "gmailserver" that handles Gmail-related requests.

#### 2. Gmail Service Setup
```python
def get_gmail_service():
```
Handles authentication and creates a Gmail service object for API operations. This function:
- Loads credentials from `token.json` if available
- Refreshes expired tokens
- Initiates OAuth flow if needed
- Returns a configured Gmail service ready for API calls

#### 3. Tools

##### Read Latest Email Tool
```python
@mcp.tool()
def read_latest_email(max_results: int = 1) -> str:
```
Retrieves the most recent emails from the user's inbox, with a default of 1 email and a maximum of 5 emails at a time. It returns a formatted summary of each email including sender, subject, and a snippet of the content.

##### Send Email Tool
```python
@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
```
Sends an email to the specified recipient with the given subject and body content. It returns a confirmation message with the sent email's ID upon success.

## Data Flow
1. The agent sends a Gmail-related request to the MCP server
2. The server authenticates with Gmail if needed
3. The relevant tool is executed, interacting with the Gmail API
4. Results are formatted and returned to the agent

## Setup and Launch

### Prerequisites
- Python 3.12 or later
- Dependencies installed via uv: `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`
- Credentials from Google Cloud Console (saved as `credentials.json`)

### Google Cloud Console Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Gmail API
4. Create OAuth 2.0 credentials (Desktop application type)
5. Download the credentials and save as `credentials.json` in the `step1` directory

### How to Launch
The server can be launched in several ways:

1. **Direct Launch** (for testing or standalone use):
   ```bash
   cd step1
   uv run mail_agent/gmail_server.py
   ```

2. **Inspector Mode** (for debugging and monitoring):
   ```bash
   uv run mcp dev mail_agent/gmail_server.py
   ```

3. **Via Agent** (normal usage):
   The server is automatically launched when running the main agent:
   ```bash
   uv run agent.py
   ```

### Authentication Process
The first time you run the Gmail server:
1. A browser window will open asking you to sign in to your Google account
2. You'll need to grant permission for the application to access your Gmail
3. After authorization, a token is saved locally for future use

### Troubleshooting
- If authentication fails, delete `token.json` and try again
- Ensure `credentials.json` is correctly placed in the project directory
- Check that the Gmail API is enabled in your Google Cloud project
- Verify that the scopes in the code match the ones configured in Google Cloud Console 