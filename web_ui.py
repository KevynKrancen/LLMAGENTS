import os
from flask import Flask, render_template, request, jsonify, session, send_from_directory
from dotenv import load_dotenv
from smolagents import ToolCallingAgent, ToolCollection, LiteLLMModel
from mcp import StdioServerParameters
import threading
import json
import uuid
import time
import contextlib

# Load environment variables
load_dotenv(override=True)

# Create Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.urandom(24)

# Create templates directory if it doesn't exist
os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), "static"), exist_ok=True)

# Initialize agent globals
agent = None
agent_ready = threading.Event()
startup_error = None
# Keep track of all context managers
tool_contexts = []

def validate_environment():
    """Validate that all necessary environment variables are set"""
    required_vars = {
        'VOICE_SERVER_URL': 'VOICE_SERVER_URL not found. Cannot start voice MCP server.',
        'OPENAI_API_KEY': 'OPENAI_API_KEY not found. Cannot start CAG+RAG server.',
        'REPLICATE_API_KEY': 'REPLICATE_API_KEY not found. Cannot start video generation server.',
        'SONAUTO_API_KEY': 'SONAUTO_API_KEY not found. Cannot start video generation server.'
    }
    
    missing = []
    for var, message in required_vars.items():
        if not os.getenv(var):
            missing.append(message)
    
    return missing

# Create a custom context manager to handle multiple tool contexts
class MultiToolContext:
    def __init__(self):
        self.contexts = []
        self.tools = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close contexts in reverse order
        for context in reversed(self.contexts):
            context.__exit__(exc_type, exc_val, exc_tb)
        self.contexts = []
        self.tools = []
    
    def add_context(self, context_manager):
        context = context_manager.__enter__()
        self.contexts.append(context_manager)
        self.tools.extend(context.tools)
        return context

def init_agent():
    """Initialize all MCP servers and the agent"""
    global agent, startup_error, tool_contexts
    
    # Check environment variables
    missing_vars = validate_environment()
    if missing_vars:
        startup_error = "Missing environment variables: " + ", ".join(missing_vars)
        agent_ready.set()  # Signal that initialization is complete (with error)
        return
    
    try:
        # Specify Ollama LLM via LiteLLM
        model = LiteLLMModel(model_id="ollama_chat/qwen2.5:14b", num_ctx=8192)

        # Set up all server parameters
        mlnewsserver_server_parameters = StdioServerParameters(
            command="uv", args=["run", "server.py"], env=None, server_id="mlnewsserver"
        )
        
        gmail_server_parameters = StdioServerParameters(
            command="uv", args=["run", "mail_agent/gmail_server.py"], env=None, server_id="gmail_server"
        )
        
        voice_mcp_parameters = StdioServerParameters(
            command="uv", args=["run", "call_agent/voice_mcp_server.py"],
            env={"VOICE_SERVER_URL": os.getenv('VOICE_SERVER_URL')}, server_id="voice_mcp_server"
        )
        
        cag_rag_server_parameters = StdioServerParameters(
            command="uv", args=["run", "cag_rag/cag_rag_server.py"],
            env={"OPENAI_API_KEY": os.getenv('OPENAI_API_KEY')}, server_id="cag_rag_server"
        )
        
        video_gen_server_parameters = StdioServerParameters(
            command="uv", args=["run", "video_server.py"],
            env={
                "OPENAI_API_KEY": os.getenv('OPENAI_API_KEY'),
                "REPLICATE_API_KEY": os.getenv('REPLICATE_API_KEY'),
                "SONAUTO_API_KEY": os.getenv('SONAUTO_API_KEY')
            },
            server_id="video_generator_server", cwd="video_gen"
        )

        # Initialize all tool collections using the multi-context manager
        multi_context = MultiToolContext()
        
        # Add each tool collection to the multi-context
        multi_context.add_context(ToolCollection.from_mcp(mlnewsserver_server_parameters, trust_remote_code=True))
        multi_context.add_context(ToolCollection.from_mcp(gmail_server_parameters, trust_remote_code=True))
        multi_context.add_context(ToolCollection.from_mcp(voice_mcp_parameters, trust_remote_code=True))
        multi_context.add_context(ToolCollection.from_mcp(cag_rag_server_parameters, trust_remote_code=True))
        multi_context.add_context(ToolCollection.from_mcp(video_gen_server_parameters, trust_remote_code=True))
        
        # Store the context manager globally to keep it alive
        tool_contexts.append(multi_context)
        
        # Create agent using all tools from the multi-context
        agent = ToolCallingAgent(tools=multi_context.tools, model=model)
        agent_ready.set()  # Signal that initialization is complete

    except Exception as e:
        startup_error = f"Failed to initialize MCP servers or agent: {str(e)}"
        agent_ready.set()  # Signal that initialization is complete (with error)

# Start agent initialization in a separate thread
threading.Thread(target=init_agent, daemon=True).start()

# Routes
@app.route('/')
def index():
    """Render the main chat interface"""
    # Generate a new session ID if one doesn't exist
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    return render_template('index.html')

# Route to serve pipeline diagram files
@app.route('/step1/<path:filename>')
def serve_pipeline(filename):
    """Serve pipeline diagram files from the step1 directory"""
    return send_from_directory('.', filename)

@app.route('/status')
def status():
    """Check if the agent is ready"""
    # Wait for a maximum of 0.1 seconds to avoid blocking
    agent_ready.wait(0.1)
    
    if agent_ready.is_set():
        if startup_error:
            return jsonify({"status": "error", "message": startup_error})
        else:
            return jsonify({"status": "ready"})
    else:
        return jsonify({"status": "initializing"})

@app.route('/chat', methods=['POST'])
def chat():
    """Process a chat message"""
    if not agent_ready.is_set() or startup_error:
        return jsonify({
            "error": startup_error or "Agent is still initializing"
        }), 503
    
    data = request.json
    query = data.get('message', '').strip()
    
    if not query:
        return jsonify({"error": "Empty message"}), 400
    
    try:
        response = agent.run(query)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": f"Error processing message: {str(e)}"}), 500

# Cleanup function to ensure all contexts are closed properly
def cleanup_contexts():
    for ctx in tool_contexts:
        try:
            ctx.__exit__(None, None, None)
        except:
            pass

# Register the cleanup function to run when the Flask app exits
import atexit
atexit.register(cleanup_contexts)

if __name__ == '__main__':
    app.run(debug=True, port=5000) 