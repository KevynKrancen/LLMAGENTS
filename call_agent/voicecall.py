import os
import json
import base64
import asyncio
import websockets
import requests
import ssl
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream
from twilio.rest import Client
from dotenv import load_dotenv
import logging
import time
from pathlib import Path
from openai import OpenAI
from pydantic import BaseModel
from urllib.parse import urlparse
from requests.exceptions import RequestException

load_dotenv(override=True)
# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PORT = int(os.getenv('PORT', 5050)) # Use the same port as defined in .env potentially used by MCP

# Load contact name from contact.json if it exists, otherwise use a default
contact_name = "Our Company" # Default name
try:
    with open('contact.json', 'r') as file:
        contact_data = json.load(file)
        contact_name = contact_data.get('name', contact_name)
except FileNotFoundError:
    print("Warning: contact.json not found. Using default contact name.")
except json.JSONDecodeError:
    print("Warning: Error decoding contact.json. Using default contact name.")


# System message - Modified for abstract agent
SYSTEM_MESSAGE = """
<bio>My name is Alex, a helpful voice assistant. I'm fluent in English, French, and Hebrew.</bio>

<voice_config>
    <voice_type>A light, confident female voice</voice_type>
    <voice_personality>Professional, friendly, concise, approachable</voice_personality>
    <voice_speed>Moderate-fast</voice_speed>
</voice_config>

<task>Act as a helpful and friendly voice assistant. Your primary goal is to understand the user's objective for this call and carry out the conversation naturally to achieve that objective. The specific objective will be provided in the initial user message.</task>

<important_rules>
    1. Maintain a professional yet pleasant and natural tone.
    2. Laught a lot ! be happy ! 
    2. Use clear, easy-to-understand language. Adapt to the language context if needed (English, French, Hebrew).
    3. Ask clarifying questions if the objective or next steps are unclear.
    4. Keep responses relatively concise and to the point.
    5. Let the other party finish speaking before responding.
</important_rules>

<instructions>
1.  **Opening:** Start the conversation based on the initial prompt provided. For example, if asked to greet and inquire about meeting availability, do so naturally.
2.  **Conversation Flow:** Engage in a natural conversation to fulfill the objective set by the initial user prompt (e.g., scheduling, asking questions, providing information).
3.  **Closing:** Conclude the call appropriately once the objective is met or the conversation naturally ends.
</instructions>

<objective>Be a helpful, friendly, and natural-sounding voice assistant, fulfilling the specific task given in the initial user prompt.</objective>
<IMPORTANT> GIVE SHORT, NATURAL-SOUNDING ANSWERS! </IMPORTANT>
"""
VOICE = 'alloy'
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created'
]
SHOW_TIMING_MATH = False

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not OPENAI_API_KEY:
    raise ValueError('Missing the OpenAI API key. Please set it in the .env file.')

# Add these variables for Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Define a generic Pydantic model for extracted call details
class CallDetails(BaseModel):
    """Model for storing extracted generic call information."""
    caller_name: str = "Unknown"
    call_objective_summary: str = ""
    key_discussion_points: list[str] = []
    action_items: list[str] = []
    sentiment: str = "Neutral" # e.g., Positive, Neutral, Negative

class CallInfo(BaseModel):
    """Model for storing call information."""
    customer_name: str = "Unknown"
    topics_discussed: list[str] = []
    security_concerns: list[str] = []
    features_requested: list[str] = []
    follow_up_required: bool = False
    follow_up_details: str = ""

@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": f"{contact_name}"} # Updated message

@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    try:
        form_data = await request.form()
        caller_id = form_data.get('From', 'Unknown')
        logger.info(f"Incoming call received from: {caller_id}")

        response = VoiceResponse()
        # Determine host dynamically
        host = request.url.hostname
        # Use wss:// for secure WebSocket connections, especially if deployed
        ws_protocol = "wss" # Assume secure by default
        # If running locally on standard HTTP, might need ws://, but wss:// is safer generally
        # if request.url.scheme == "http":
        #     ws_protocol = "ws"

        ws_url = f"{ws_protocol}://{host}/media-stream"


        # Initial greeting - Use the configured contact_name
        response.say(
            f"Welcome to your A I agent please wait for connexion ",
            voice="Polly.Matthew" # Example standard voice
        )
        response.pause(length=1)
        response.say("You can now speak with our AI agent")

        # Connect to media stream
        connect = Connect()
        # Use dynamic host and secure protocol
        connect.stream(url=ws_url)
        response.append(connect)

        logger.info(f"Returning TwiML response with stream URL: {ws_url}")
        return HTMLResponse(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error in incoming_call handler: {e}", exc_info=True)
        # Create a fallback response
        fallback = VoiceResponse()
        fallback.say("Sorry, we're experiencing technical difficulties connecting the call. Please try again later.")
        fallback.hangup()
        return HTMLResponse(content=str(fallback), media_type="application/xml")

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    logger.info("WebSocket client connected for media streaming")
    await websocket.accept()

    try:
        # OpenAI Realtime API endpoint
        openai_url = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01'
        logger.info(f"Attempting to connect to OpenAI at {openai_url}")

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }

        # Configure SSL context for WebSocket connection (consider security implications)
        ssl_context = ssl.create_default_context()
        # In production, you might want stricter SSL verification
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        logger.info("Connecting to OpenAI WebSocket...")
        async with websockets.connect(openai_url, extra_headers=headers, ssl=ssl_context) as openai_ws:
            logger.info("Successfully connected to OpenAI WebSocket")

            # Initialize the OpenAI session
            session_update = {
                "type": "session.update",
                "session": {
                    "turn_detection": {"type": "server_vad"},
                    "input_audio_format": "g711_ulaw",
                    "output_audio_format": "g711_ulaw",
                    "voice": VOICE,
                    "instructions": SYSTEM_MESSAGE,
                    "modalities": ["text", "audio"],
                    "temperature": 0.7,
                }
            }
            logger.info('Sending session update to OpenAI')
            await openai_ws.send(json.dumps(session_update))

            # Send initial user message to make the AI speak first
            initial_conversation_item = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            # Use configured contact_name and potentially a configured agent name
                            "text": f"Greet the user by saying: 'Hello, this is Alex, Nice to meet you whats your name ?"
                        }
                    ]
                }
            }
            logger.info('Sending initial user message to OpenAI')
            await openai_ws.send(json.dumps(initial_conversation_item))
            logger.info('Requesting initial response creation from OpenAI')
            await openai_ws.send(json.dumps({"type": "response.create"}))

            # Connection specific state
            stream_sid = None
            latest_media_timestamp = 0

            async def receive_from_twilio():
                """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
                nonlocal stream_sid, latest_media_timestamp
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        event = data.get('event')

                        if event == 'media':
                            # Debug logging for media chunks (optional)
                            # timestamp = data.get('media', {}).get('timestamp')
                            # if timestamp and int(timestamp) % 5000 == 0:
                            #     logger.info(f"Processing media chunk at timestamp {timestamp}")

                            # Save timestamp for potential interruption handling
                            timestamp = data.get('media', {}).get('timestamp')
                            if timestamp:
                                latest_media_timestamp = int(timestamp)

                            # Forward audio to OpenAI
                            payload = data.get('media', {}).get('payload')
                            if payload:
                                audio_append = {
                                    "type": "input_audio_buffer.append",
                                    "audio": payload
                                }
                                await openai_ws.send(json.dumps(audio_append))

                        elif event == 'start':
                            stream_sid = data.get('start', {}).get('streamSid')
                            logger.info(f"Incoming Twilio stream started: {stream_sid}")

                        elif event == 'stop':
                            logger.info(f"Twilio stream stopped (SID: {stream_sid})")
                            # Consider signaling OpenAI that the input stream has ended if necessary
                            # await openai_ws.send(json.dumps({"type": "input_audio_buffer.end"})) # Check API docs

                        elif event == 'mark':
                            logger.info(f"Received mark event: {data.get('mark', {}).get('name')}")

                        else:
                             logger.warning(f"Received unexpected Twilio event type: {event}")


                except WebSocketDisconnect as e:
                    logger.info(f"Twilio WebSocket disconnected: {e.code} - {e.reason}")
                except websockets.exceptions.ConnectionClosed as e:
                    logger.info(f"Twilio WebSocket connection closed unexpectedly: {e}")
                except Exception as e:
                    logger.error(f"Error in receive_from_twilio: {e}", exc_info=True)
                finally:
                    logger.info("Receive from Twilio task finished.")


            async def send_to_twilio():
                """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
                nonlocal stream_sid
                try:
                    event_count = 0
                    async for openai_message in openai_ws:
                        event_count += 1
                        if event_count % 100 == 0: # Log periodically
                            logger.info(f"Processed {event_count} events from OpenAI")

                        try:
                            response = json.loads(openai_message)
                            message_type = response.get('type', '')

                            # Process audio response delta
                            if message_type == 'response.audio.delta' and 'delta' in response:
                                if not stream_sid:
                                    # logger.warning("Received audio delta before stream SID was known. Skipping.")
                                    continue

                                # Process and forward audio to Twilio
                                try:
                                    # Decode base64 audio delta from OpenAI, re-encode for Twilio media event
                                    decoded_audio = base64.b64decode(response['delta'])
                                    audio_payload = base64.b64encode(decoded_audio).decode('utf-8')

                                    audio_delta_twilio = {
                                        "event": "media",
                                        "streamSid": stream_sid,
                                        "media": {
                                            "payload": audio_payload
                                        }
                                    }
                                    await websocket.send_json(audio_delta_twilio)

                                    # Optional: Mark when audio playback starts/ends if needed for clarity
                                    # if first_chunk_of_response:
                                    #     mark_start = {"event": "mark", "streamSid": stream_sid, "mark": {"name": "ai_speech_start"}}
                                    #     await websocket.send_json(mark_start)
                                    #     first_chunk_of_response = False # Reset flag

                                except Exception as e:
                                    logger.error(f"Error processing/sending audio delta to Twilio: {e}", exc_info=True)

                            # Handle end of AI speech response
                            elif message_type == 'response.content.done':
                                logger.info("OpenAI response content done.")
                                # Optional: Mark end of AI speech playback
                                # if stream_sid:
                                #     mark_end = {"event": "mark", "streamSid": stream_sid, "mark": {"name": "ai_speech_end"}}
                                #     await websocket.send_json(mark_end)
                                #     first_chunk_of_response = True # Ready for next response

                            # Log other interesting events for debugging
                            elif message_type in LOG_EVENT_TYPES:
                                logger.info(f"OpenAI event: {message_type} - {response.get('details', '')}")

                            # Handle potential errors from OpenAI
                            elif message_type == 'error':
                                logger.error(f"OpenAI error event: {response.get('message', 'No message')}")


                        except json.JSONDecodeError:
                            logger.warning(f"Failed to decode JSON from OpenAI: {openai_message[:200]}...")
                        except Exception as e:
                            logger.error(f"Error processing OpenAI message: {e} - Message: {openai_message[:200]}...", exc_info=True)

                except websockets.exceptions.ConnectionClosed as e:
                     logger.info(f"OpenAI WebSocket connection closed: {e}")
                except Exception as e:
                    logger.error(f"Error in send_to_twilio: {e}", exc_info=True)
                finally:
                    logger.info("Send to Twilio task finished.")


            # Start both coroutines and wait for them to complete
            logger.info("Starting Twilio <-> OpenAI communication tasks")
            await asyncio.gather(
                receive_from_twilio(),
                send_to_twilio()
            )
            logger.info("Twilio <-> OpenAI communication tasks finished")

    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"Failed to connect to OpenAI WebSocket: {e.status_code} {e.response_headers}", exc_info=True)
    except Exception as e:
        logger.error(f"Error in WebSocket connection handler: {e}", exc_info=True)
    finally:
        logger.info("WebSocket client disconnected.")
        # Gracefully close the WebSocket if it's still open
        if not websocket.client_state == websockets.protocol.State.CLOSED:
             await websocket.close()


@app.get("/make-call")
async def make_outgoing_call(request: Request, to: str = None):
    """Make an outgoing call using Twilio to connect to our cybersecurity agent."""

    try:
        # Check for essential Twilio credentials
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
            logger.error("Missing Twilio credentials in environment variables.")
            raise HTTPException(status_code=500, detail="Server configuration error: Missing Twilio credentials.")

        # Initialize Twilio client
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        # Get the host from the request headers or URL
        host = request.headers.get("host", request.url.hostname)
        # Construct base URL dynamically, preferring https
        scheme = request.url.scheme if request.url.scheme else "https"
        base_url = f"{scheme}://{host}"


        # Use provided phone number or default if none provided
        # TODO: Consider adding validation for the 'to' number format (E.164)
        to_number = to
        if not to_number:
             # Default number for testing if none provided - **Replace with a safe default or remove**
             to_number = os.getenv('DEFAULT_TEST_NUMBER', None) # Example: load from .env
             if not to_number:
                logger.error("No 'to' phone number provided and no default test number configured.")
                raise HTTPException(status_code=400, detail="Missing 'to' parameter (phone number to call).")


        logger.info(f"Initiating call to {to_number} from {TWILIO_PHONE_NUMBER}")

        # Construct the full URL for the incoming call handler TwiML
        # This is where Twilio will connect the *outgoing* call leg
        incoming_call_url = f"{base_url}/incoming-call"
        logger.info(f"Setting callback URL for outgoing call to: {incoming_call_url}")


        # Add a callback URL for when the recording is complete
        recording_callback_url = f"{base_url}/recording-callback"
        status_callback_url = f"{base_url}/call-status"
        fallback_url = f"{base_url}/fallback"

        # Make the call using the Twilio client
        call = twilio_client.calls.create(
            url=incoming_call_url, # Use URL for TwiML instructions instead of twiml param
            to=to_number,
            from_=TWILIO_PHONE_NUMBER,
            record=True, # Enable recording
            recording_channels='dual', # Record both legs separately if possible
            recording_status_callback=recording_callback_url, # Where to send recording info
            status_callback=status_callback_url, # Where to send call status updates
            status_callback_event=['initiated', 'ringing', 'answered', 'completed', 'failed'], # Events to track
            fallback_url=fallback_url # URL if the primary URL fails
        )

        logger.info(f"Call initiated with SID: {call.sid}")
        return JSONResponse(content={
            "success": True,
            "message": f"Outgoing call to {to_number} initiated. Connecting to agent.",
            "call_sid": call.sid,
            "callback_url": incoming_call_url # Return the URL used
        })
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly
        raise http_exc
    except Exception as e:
        error_message = f"Error initiating call: {str(e)}"
        logger.error(error_message, exc_info=True)
        # Return a generic server error response
        raise HTTPException(status_code=500, detail=error_message)

@app.post("/call-status")
async def call_status(request: Request):
    """Handle call status callbacks from Twilio."""
    try:
        form_data = await request.form()
        call_sid = form_data.get('CallSid')
        call_status = form_data.get('CallStatus')

        logger.info(f"Call Status Update - SID: {call_sid}, Status: {call_status}")
        if call_status == "failed":
            error_code = form_data.get('ErrorCode')
            error_message = form_data.get('ErrorMessage') # Twilio might send ErrorMessage
            logger.error(f"Call FAILED - SID: {call_sid}, ErrorCode: {error_code}, Message: {error_message}")
        elif call_status == "completed":
             duration = form_data.get('CallDuration')
             logger.info(f"Call COMPLETED - SID: {call_sid}, Duration: {duration}s")


        # Return 200 OK to Twilio
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"Error processing call-status callback: {e}", exc_info=True)
        # Still try to return OK to Twilio, but log the server error
        return JSONResponse(content={"status": "server_error"}, status_code=500)

@app.post("/fallback")
@app.get("/fallback") # Allow GET for simple testing/debugging
async def fallback_handler(request: Request):
    """Handle fallback for failed call connections or TwiML errors."""
    try:
        form_data = await request.form()
        call_sid = form_data.get('CallSid', 'Unknown')
        error_code = form_data.get('ErrorCode', 'N/A')

        logger.warning(f"Fallback handler triggered for call SID: {call_sid}, ErrorCode: {error_code}")

        # Generate a simple TwiML response to inform the caller
        response = VoiceResponse()
        response.say("We encountered an issue connecting your call. Please try again later or contact support.")
        response.hangup()

        return HTMLResponse(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error in fallback handler itself: {e}", exc_info=True)
        # Extremely basic fallback if the handler fails
        fallback_response = VoiceResponse()
        fallback_response.say("An error occurred. Goodbye.")
        fallback_response.hangup()
        return HTMLResponse(content=str(fallback_response), media_type="application/xml")


# --- Recording, Transcription, and Data Extraction ---

@app.post("/recording-callback")
async def recording_callback(request: Request):
    """Handle recording callback from Twilio, save, transcribe, and extract info."""
    try:
        form_data = await request.form()
        recording_url = form_data.get('RecordingUrl')
        recording_sid = form_data.get('RecordingSid')
        call_sid = form_data.get('CallSid')

        if not all([recording_url, recording_sid, call_sid]):
            logger.error(f"Missing required form data in recording callback. SID: {call_sid}")
            raise HTTPException(status_code=400, detail="Missing required form data (RecordingUrl, RecordingSid, CallSid)")

        logger.info(f"Recording complete notification received for Call SID: {call_sid}, Recording SID: {recording_sid}")
        logger.debug(f"Recording URL: {recording_url}") # Debug level for URL

        # --- Asynchronous Processing ---
        # Instead of blocking the response, trigger background tasks
        # This acknowledges Twilio quickly and processes the recording offline.
        # Requires an appropriate background task runner setup (e.g., asyncio.create_task if simple,
        # or a dedicated task queue like Celery/RQ for robustness)

        async def process_recording_async():
            logger.info(f"Starting async processing for recording {recording_sid} (Call SID: {call_sid})")
            # Fetch and save the recording
            saved_path, transcription_path = await fetch_and_save_recording_async(recording_url, call_sid, recording_sid)

            if saved_path:
                logger.info(f"Recording {recording_sid} saved to {saved_path}")
                if transcription_path:
                    logger.info(f"Transcription for {recording_sid} saved to {transcription_path}")
                    # Extract call info from the transcription
                    call_info_path = await extract_call_info_async(transcription_path, call_sid, recording_sid)
                    if call_info_path:
                        logger.info(f"Extracted call info for {recording_sid} saved to {call_info_path}")
                    else:
                        logger.error(f"Failed to extract call info for recording {recording_sid}")
                else:
                    logger.error(f"Failed to transcribe recording {recording_sid}")
            else:
                 logger.error(f"Failed to save recording {recording_sid} from URL")
            logger.info(f"Finished async processing for recording {recording_sid}")

        # Schedule the processing task to run in the background
        asyncio.create_task(process_recording_async())

        # Return immediate success response to Twilio
        return JSONResponse(content={
            "message": "Recording callback received. Processing started in background.",
            "call_sid": call_sid,
            "recording_sid": recording_sid
        })

    except HTTPException as http_exc:
        raise http_exc # Propagate HTTP exceptions
    except Exception as e:
        call_sid_err = form_data.get('CallSid', 'Unknown') if 'form_data' in locals() else 'Unknown'
        logger.error(f"Error in recording_callback for Call SID {call_sid_err}: {str(e)}", exc_info=True)
        # Return a server error, but Twilio might retry if it doesn't get 200 OK
        raise HTTPException(status_code=500, detail=f"Internal server error processing recording callback: {str(e)}")


async def fetch_and_save_recording_async(recording_url: str, call_sid: str, recording_sid: str, max_retries=3, retry_delay=5):
    """Asynchronously fetch recording from Twilio and save it locally."""
    # Ensure 'recordings' folder exists
    rec_folder = Path("recordings")
    rec_folder.mkdir(exist_ok=True)

    # Determine file extension, default to .mp3 if needed
    parsed_url = urlparse(recording_url)
    path_part = parsed_url.path
    extension = os.path.splitext(path_part)[1]
    if not extension or extension.lower() not in ['.mp3', '.wav']: # Allow wav too
        recording_url_with_ext = recording_url + '.mp3'
        file_extension = '.mp3'
    else:
        recording_url_with_ext = recording_url
        file_extension = extension

    # Optionally add RequestedChannels=2 for dual-channel (if supported and desired)
    # recording_url_final = recording_url_with_ext + '?RequestedChannels=2'
    recording_url_final = recording_url_with_ext # Keep it simple first

    file_path = rec_folder / f"{call_sid}_{recording_sid}{file_extension}" # Include recording SID for uniqueness

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt+1}: Fetching recording {recording_sid} from {recording_url_final}")
            # Use an async HTTP client like httpx or aiohttp if needed for true async download
            # For simplicity, using requests in a thread pool executor via asyncio.to_thread might be okay
            # Or just use requests directly if blocking here briefly is acceptable
            response = await asyncio.to_thread(
                 requests.get, recording_url_final, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=30 # Increased timeout
            )
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            # Save the file asynchronously
            with open(file_path, 'wb') as f:
                f.write(response.content) # Consider streaming write for large files
            logger.info(f"Recording {recording_sid} saved successfully to {file_path}")

            # Proceed to transcribe
            transcription_path = await transcribe_audio_async(str(file_path), call_sid, recording_sid)
            if transcription_path:
                return str(file_path), transcription_path
            else:
                logger.error(f"Failed to transcribe audio for recording {recording_sid}")
                return str(file_path), None # Return saved path even if transcription fails

        except RequestException as e:
            logger.warning(f"Attempt {attempt+1} failed to fetch recording {recording_sid}: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to fetch recording {recording_sid} after {max_retries} attempts: {str(e)}")
                return None, None
        except IOError as e:
            logger.error(f"Failed to save recording {recording_sid} to {file_path}: {str(e)}")
            return None, None
        except Exception as e:
            logger.error(f"Unexpected error in fetch_and_save_recording_async for {recording_sid}: {str(e)}", exc_info=True)
            return None, None
    return None, None # Should not be reached if retries are exhausted


async def transcribe_audio_async(audio_file_path: str, call_sid: str, recording_sid: str):
    """Asynchronously transcribe the audio file using OpenAI Whisper API."""
    try:
        # Ensure 'transcriptions' folder exists
        transcriptions_folder = Path("transcriptions")
        transcriptions_folder.mkdir(exist_ok=True)

        logger.info(f"Starting transcription for {recording_sid} from file {audio_file_path}")

        # Open the audio file in binary read mode
        with open(audio_file_path, "rb") as audio_file:
            # Call the OpenAI API asynchronously
            # Note: The OpenAI client library itself might handle async execution or use threads.
            # If it's blocking, wrap it with asyncio.to_thread for true async behavior.
             transcript = await asyncio.to_thread(
                 client.audio.transcriptions.create,
                 model="whisper-1",
                 file=audio_file,
                 response_format="json", # Get structured JSON output
                 language="en"  # Specify language if known, helps accuracy
             )


        # Prepare the JSON data for saving
        transcription_data = {
            "call_sid": call_sid,
            "recording_sid": recording_sid,
            "transcription": transcript.text,
            "language": transcript.language if hasattr(transcript, 'language') else 'unknown', # Store detected language if available
             # Consider adding timestamp if needed later
        }

        # Save the transcription as a JSON file
        json_file_path = transcriptions_folder / f"{call_sid}_{recording_sid}_transcription.json"
        with open(json_file_path, "w") as json_file:
            json.dump(transcription_data, json_file, indent=2)

        logger.info(f"Transcription for {recording_sid} saved successfully to {json_file_path}")
        return str(json_file_path)

    except Exception as e:
        logger.error(f"Error during transcription for {recording_sid}: {str(e)}", exc_info=True)
        return None


async def extract_call_info_async(transcription_file_path: str, call_sid: str, recording_sid: str):
    """Asynchronously extract structured call information from transcription using OpenAI."""
    try:
        # Read the transcription JSON file
        with open(transcription_file_path, 'r') as file:
            transcription_data = json.load(file)

        transcription_text = transcription_data.get('transcription', '')
        if not transcription_text:
             logger.warning(f"Transcription text is empty for {recording_sid}. Cannot extract info.")
             return None


        logger.info(f"Starting call info extraction for {recording_sid}...")

        # Prepare prompt for OpenAI to extract structured data according to CallInfo model
        # This prompt guides the LLM to output JSON matching the Pydantic model structure.
        extraction_prompt = f"""
        Analyze the following call transcription between an expert and a customer.
        Extract the specified information and structure it as a JSON object matching this schema:
        {{
          "customer_name": "string (or 'Unknown' if not mentioned)",
          "topics_discussed": ["string"],
          "security_concerns": ["string"],
          "features_requested": ["string"],
          "follow_up_required": "boolean",
          "follow_up_details": "string (details if follow_up_required is true, otherwise empty)"
        }}

        Transcription:
        ---
        {transcription_text}
        ---

        Extracted JSON:
        """


        completion = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",  # Or another suitable model like gpt-4o
            messages=[
                {"role": "system", "content": "You are an expert assistant tasked with extracting structured information from call transcripts into a specific JSON format."},
                {"role": "user", "content": extraction_prompt},
            ],
            response_format={"type": "json_object"}, # Request JSON output directly
            temperature=0.2, # Lower temperature for more deterministic extraction
        )


        # Parse the response content which should be a JSON string
        extracted_json_string = completion.choices[0].message.content
        extracted_data = json.loads(extracted_json_string) # Parse the JSON string

        # Validate against Pydantic model (optional but good practice)
        try:
            call_info_validated = CallInfo(**extracted_data)
            call_info_dict = call_info_validated.model_dump() # Convert Pydantic model to dict for saving
        except Exception as pydantic_error:
             logger.error(f"Pydantic validation failed for extracted data {recording_sid}: {pydantic_error}. Saving raw extracted data.", exc_info=True)
             # Fallback: save the raw extracted data if validation fails
             call_info_dict = extracted_data


        # Add metadata
        call_info_dict['call_sid'] = call_sid
        call_info_dict['recording_sid'] = recording_sid


        # Ensure 'call_data' folder exists
        data_folder = Path("call_data")
        data_folder.mkdir(exist_ok=True)

        # Save the extracted info as a JSON file
        json_file_path = data_folder / f"{call_sid}_{recording_sid}_call_info.json"
        with open(json_file_path, "w") as json_file:
            json.dump(call_info_dict, json_file, indent=2)

        logger.info(f"Call information for {recording_sid} extracted and saved to {json_file_path}")
        return str(json_file_path)

    except json.JSONDecodeError as json_err:
         logger.error(f"Failed to decode JSON response from OpenAI for {recording_sid}: {json_err} - Response: {extracted_json_string[:200]}...", exc_info=True)
         return None
    except Exception as e:
        logger.error(f"Error in extract_call_info_async for {recording_sid}: {str(e)}", exc_info=True)
        return None


# --- Main Execution Guard ---
if __name__ == "__main__":
    import uvicorn
    # Ensure essential Twilio vars are present before starting server
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, OPENAI_API_KEY]):
         logger.critical("CRITICAL: Missing required environment variables (Twilio SID/Token/Number or OpenAI Key). Server cannot start.")
         # Optionally raise an error here instead of just logging
         # raise ValueError("Missing required environment variables.")
    else:
        print(f"Starting {contact_name} Voice Agent Server on port {PORT}...")
        # Run the Uvicorn server, binding to all interfaces
        uvicorn.run(app, host="0.0.0.0", port=PORT)
