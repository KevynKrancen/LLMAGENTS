import os.path
import base64
from email.mime.text import MIMEText

# Bring in colorama for fancy printing
from colorama import Fore
# Bring in MCP Server SDK
from mcp.server.fastmcp import FastMCP

# Imports for Google API
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")

# Create server
mcp = FastMCP("gmailserver")

def get_gmail_service():
    """Authenticates with Google and returns the Gmail service object."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception as e:
            print(f"{Fore.RED}Error loading credentials from {TOKEN_PATH}: {e}")
            creds = None # Force re-authentication if file is invalid

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print(f"{Fore.YELLOW}Refreshing credentials...")
                creds.refresh(Request())
            except Exception as e:
                print(f"{Fore.RED}Error refreshing credentials: {e}")
                # Fallback to re-authentication
                creds = None
        else:
             # Check if credentials.json exists for the flow
            if not os.path.exists(CREDENTIALS_PATH):
                 raise FileNotFoundError(
                    f"{Fore.RED}Error: {CREDENTIALS_PATH} not found. "
                    f"Please download your OAuth 2.0 client secrets file from Google Cloud Console "
                    f"and save it as {CREDENTIALS_PATH} in the same directory."
                    f"Then delete {TOKEN_PATH} if it exists and restart."
                 )
            print(f"{Fore.YELLOW}No valid credentials found or refresh failed. Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            # Run flow with no_browser=True to avoid opening a browser, user needs to copy/paste URL
            creds = flow.run_local_server(port=0) # Preferred over run_console if possible

        # Save the credentials for the next run
        try:
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
            print(f"{Fore.GREEN}Credentials saved to {TOKEN_PATH}")
        except Exception as e:
            print(f"{Fore.RED}Error saving credentials to {TOKEN_PATH}: {e}")


    try:
        service = build("gmail", "v1", credentials=creds)
        print(f"{Fore.GREEN}Gmail service created successfully.")
        return service
    except HttpError as error:
        print(f"{Fore.RED}An error occurred building the Gmail service: {error}")
        return None
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred: {e}")
        return None


@mcp.tool()
def read_latest_email(max_results: int = 1) -> str:
    """Reads the latest email(s) from the user's inbox.
    Args:
        max_results: The maximum number of emails to retrieve (default is 1).
                     Cannot exceed 5.

    Returns:
        str: A summary of the latest email(s) including sender, subject, and snippet,
             or an error message.
    """
    if max_results > 5:
        return "Error: Cannot retrieve more than 5 emails at a time."

    service = get_gmail_service()
    if not service:
        return "Error: Could not authenticate or build Gmail service."

    try:
        # List messages
        results = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=max_results).execute()
        messages = results.get("messages", [])

        if not messages:
            return "No new messages found."

        email_summaries = []
        for msg_ref in messages:
            msg = service.users().messages().get(userId="me", id=msg_ref["id"]).execute()
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "No Sender")
            snippet = msg.get("snippet", "No snippet available.")
            email_summaries.append(f"From: {sender}\nSubject: {subject}\nSnippet: {snippet}\n---")

        return "\n".join(email_summaries)

    except HttpError as error:
        print(f"{Fore.RED}An error occurred accessing Gmail API: {error}")
        return f"An error occurred: {error}"
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred: {e}")
        return f"An unexpected error occurred: {e}"


@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """Sends an email using the user's Gmail account.
    Args:
        to: The recipient's email address.
        subject: The subject line of the email.
        body: The plain text body of the email.

    Returns:
        str: Confirmation message including the ID of the sent email or an error message.
    """
    service = get_gmail_service()
    if not service:
        return "Error: Could not authenticate or build Gmail service."

    try:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        # Ensure 'From' is set correctly if needed, though Gmail API often handles this
        # message['from'] = 'your_email@gmail.com' # Usually not needed

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"raw": raw_message}

        sent_message = (
            service.users()
            .messages()
            .send(userId="me", body=create_message)
            .execute()
        )
        print(f"{Fore.GREEN}Message Id: {sent_message['id']}")
        return f"Email sent successfully. Message ID: {sent_message['id']}"

    except HttpError as error:
        print(f"{Fore.RED}An error occurred sending email via Gmail API: {error}")
        return f"An error occurred: {error}"
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred: {e}")
        return f"An unexpected error occurred: {e}"


# Kick off server if file is run
if __name__ == "__main__":
    # Attempt to get service once at startup to potentially trigger auth flow early
    print(f"{Fore.CYAN}Initializing Gmail Server and checking credentials...")
    get_gmail_service()
    print(f"{Fore.CYAN}Starting MCP server...")
    mcp.run(transport="stdio") 