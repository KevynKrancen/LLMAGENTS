# Voice Call MCP Server

## Overview
The Voice Call MCP server provides a tool to initiate outbound voice calls to phone numbers. It serves as a bridge between the main agent and a separate voice service that handles the actual call functionality.

## Purpose
This server enables users to:
- Initiate voice calls to any valid phone number
- Connect the agent's capabilities to voice telephony
- Communicate with external parties through voice calls

The voice call functionality extends the agent system to work in the audio medium, making it useful for scenarios where text communication is insufficient or phone calls are preferred.

## How It Works

### Architecture
The Voice Call MCP implementation follows a two-tier architecture:
1. **MCP Server** (`voice_mcp_server.py`): Provides the MCP tool interface for the agent
2. **Voice Server** (`voicecall.py`): Handles the actual voice call functionality

The MCP server acts as a proxy that forwards requests to the Voice Server, which manages the connection to telephony services.

### Technology
- **FastMCP**: Server framework that exposes voice call operations as tools
- **Twilio**: Backend service for handling the actual voice calls
- **FastAPI**: Powers the Voice Server for call handling
- **WebSockets**: Used for real-time audio streaming
- **ngrok**: Creates a public URL to your local server for Twilio webhooks

## Detailed Setup

### 1. Twilio Account Setup
1. Create a Twilio account at [twilio.com](https://www.twilio.com/) if you don't have one
2. Purchase a phone number with voice capabilities from the Twilio console
3. Note your Twilio Account SID, Auth Token, and Phone Number

### 2. ngrok Setup
1. Create an ngrok account at [ngrok.com](https://ngrok.com/) if you don't have one
2. Download and install ngrok
3. Authenticate ngrok with your authtoken:
   ```bash
   ngrok authtoken your_auth_token
   ```
4. Start ngrok to expose your local server:
   ```bash
   ngrok http 5050
   ```
5. Copy the HTTPS URL provided by ngrok (e.g., `https://a1b2c3d4.ngrok.io`)

### 3. Twilio Phone Number Configuration
1. Go to the Twilio Console > Phone Numbers > Manage > Active Numbers
2. Click on your voice-enabled phone number
3. Under "Voice & Fax" > "A Call Comes In", set the webhook to:
   ```
   [YOUR_NGROK_URL]/incoming-call
   ```
   (e.g., `https://a1b2c3d4.ngrok.io/incoming-call`)
4. Set the webhook method to HTTP POST
5. Save your changes

### 4. Environment Variables
Create or update your `.env` file with the following variables:

```
# Twilio credentials
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+12345678901  # Your Twilio phone number in E.164 format

# Server configuration
VOICE_SERVER_PORT=5050  # This must match the port used in your ngrok command
VOICE_SERVER_URL=http://localhost:5050  # Local URL for the voice server

# Voice agent configuration
PHONE_NUMBER_TO_USE=+12345678901  # Default phone number for outbound calls
DEFAULT_USER_PHONE=+19876543210  # Your personal phone to receive test calls
```

### Components

#### 1. MCP Server Instance
```python
mcp = FastMCP("voicemcp")
```
Creates an MCP server named "voicemcp" that handles voice call requests.

#### 2. Voice Server Connection
```python
VOICE_SERVER_URL = os.getenv('VOICE_SERVER_URL')
```
Connects to a separately running voice server through a URL specified in the environment.

#### 3. Tools

##### Initiate Call Tool
```python
@mcp.tool()
def initiate_call(phone_number: str) -> str:
```
Initiates a call to the specified phone number. The phone number must be in E.164 format (e.g., +14155552671).

## Data Flow
1. The agent calls the `initiate_call` tool with a phone number
2. The MCP server sends a request to the Voice Server
3. The Voice Server initiates the call using Twilio
4. The call connects, and any conversation is handled by the Voice Server
5. Status information is returned to the agent

## Launch Sequence

For the complete voice call functionality, follow these steps in order:

### 1. Start ngrok
```bash
ngrok http 5050
```
Copy the HTTPS URL provided by ngrok. If this URL changes, you'll need to update your Twilio webhook settings.

### 2. Start the Voice Server
```bash
cd step1
uvicorn call_agent.voicecall:app --host 0.0.0.0 --port 5050
```
Or alternatively:
```bash
cd step1
uv run call_agent/voicecall.py
```
This starts the FastAPI server that handles the actual call functionality.

### 3. Start the Main Agent
In a separate terminal window:
```bash
cd step1
uv run agent.py
```
The agent automatically starts the Voice MCP Server along with other servers.

### Voice Calls in Action
To make a voice call through the agent:
1. Ensure both the Voice Server and the MCP Server are running
2. Through the agent, use a command like: "Call +14155551212 and ask about their availability next week"
3. The system will initiate the call and handle the conversation

## Troubleshooting

### Common Issues
- **Webhook Not Receiving Calls**: Verify your ngrok URL is correctly set in Twilio
- **ngrok Tunnel Closed**: ngrok tunnels expire after a period; restart if necessary
- **Port Already in Use**: If port 5050 is occupied, change both the uvicorn port and ngrok port
- **Twilio Authentication Errors**: Double-check your Account SID and Auth Token
- **Voice Server Not Responding**: Ensure the Voice Server is running before starting the agent

### Twilio-Specific Issues
- Check Twilio console logs for webhook failures
- Verify your Twilio phone number has voice capabilities
- Ensure your Twilio account has sufficient credit

### Environment Setup Issues
- Verify all environment variables are correctly set in your `.env` file
- Ensure your `.env` file is in the correct location (in the `step1` directory)
- Make sure the `VOICE_SERVER_URL` in your `.env` file points to the correct local URL

### Connection Issues
- If the Voice Server can't communicate with Twilio, check your internet connection
- If the Agent can't communicate with the Voice Server, verify the `VOICE_SERVER_URL` is correct
- If ngrok shows error messages, restart it or check your ngrok account status 