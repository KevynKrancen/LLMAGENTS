import os
import requests
import logging
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)

# Get the URL of the running voice server (voicecall.py)
VOICE_SERVER_URL = os.getenv('VOICE_SERVER_URL')

if not VOICE_SERVER_URL:
    raise ValueError("Missing VOICE_SERVER_URL environment variable. Cannot connect to the voice server.")

# Create MCP server instance
mcp = FastMCP("voicemcp")

# --- MCP Tool Definition ---

@mcp.tool()
def initiate_call(phone_number: str = Field(..., description="The E.164 formatted phone number to call.")) -> str:
    """Initiates an outbound voice call to the specified phone number using the GET /make-call endpoint.
    Note: Any specific call objective must be handled by the voice agent's default configuration, as it's not passed via this GET request.
    
    Args:
        phone_number: The E.164 formatted phone number (e.g., +14155552671).
        
    Returns:
        str: Confirmation message indicating success or failure, potentially including the Call SID.
    """
    # Target the GET /make-call endpoint
    target_endpoint_base = f"{VOICE_SERVER_URL.rstrip('/')}/make-call"
    # Construct URL with query parameter
    target_url = f"{target_endpoint_base}?to={phone_number}" # Use 'to' as query param name
    
    logger.info(f"Sending GET request to {target_url}")
    
    try:
        # Make a GET request, no payload needed
        response = requests.get(target_url, timeout=10)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        response_data = response.json()
        call_sid = response_data.get('call_sid', 'N/A')
        success_message = response_data.get('message', 'Call triggered successfully via GET.')
        logger.info(f"Call triggered successfully via GET. Response: {response_data}")
        return f"{success_message} Call SID: {call_sid}"
        
    except requests.exceptions.HTTPError as http_err:
        error_detail = "Unknown error"
        try:
             error_detail = http_err.response.json().get('detail', http_err.response.text)
        except Exception:
             error_detail = str(http_err)
        logger.error(f"HTTP error occurred calling GET {target_url}: {http_err} - Detail: {error_detail}")
        return f"Error: Failed to trigger call via GET. Server responded with {http_err.response.status_code}. Detail: {error_detail}"
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error occurred calling GET {target_url}: {conn_err}")
        return f"Error: Could not connect to the voice server at {VOICE_SERVER_URL}. Is it running?"
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout occurred calling GET {target_url}: {timeout_err}")
        return f"Error: Request to the voice server timed out."
    except Exception as e:
        logger.error(f"An unexpected error occurred during GET request: {e}", exc_info=True)
        return f"Error: An unexpected error occurred while trying to trigger the call via GET: {str(e)}"

# --- Main Execution Guard (for MCP server) ---
if __name__ == "__main__":
    print(f"Starting Voice MCP Server. It will proxy requests to: {VOICE_SERVER_URL}")
    # Run the MCP server using stdio transport
    mcp.run(transport="stdio") 