# Import smolagents 
import os # Import os to access environment variables
from smolagents import ToolCallingAgent, ToolCollection, LiteLLMModel
# Bring in MCP Client Side libraries
from mcp import StdioServerParameters
# Bring in Colorama for fancy printing
from colorama import Fore, Style
# Import and load .env file for environment variables
from dotenv import load_dotenv

load_dotenv(override=True) # Load .env before defining parameters

# --- Explicitly get the needed environment variables after loading .env ---
VOICE_SERVER_URL_FOR_MCP = os.getenv('VOICE_SERVER_URL')
if not VOICE_SERVER_URL_FOR_MCP:
    # Fail early in the agent if the URL isn't set, before trying to start MCP
    raise ValueError("AGENT ERROR: VOICE_SERVER_URL not found in environment or .env file. Cannot start voice MCP server.")

# Check for OpenAI API key for CAG+RAG server
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("AGENT ERROR: OPENAI_API_KEY not found in environment or .env file. Cannot start CAG+RAG server.")

# Check for Replicate API key for video generation
REPLICATE_API_KEY = os.getenv('REPLICATE_API_KEY')
if not REPLICATE_API_KEY:
    raise ValueError("AGENT ERROR: REPLICATE_API_KEY not found in environment or .env file. Cannot start video generation server.")

# Check for Sonauto API key for music generation
SONAUTO_API_KEY = os.getenv('SONAUTO_API_KEY')
if not SONAUTO_API_KEY:
    raise ValueError("AGENT ERROR: SONAUTO_API_KEY not found in environment or .env file. Cannot start video generation server.")

# Specify Ollama LLM via LiteLLM
model = LiteLLMModel(
        model_id="ollama_chat/qwen2.5:14b",
        num_ctx=8192) 

# --- Setup Yahoo Finance Server --- 
finance_server_parameters = StdioServerParameters(
    command="uv",
    args=["run", "server.py"], # Runs step1/server.py for yfinance
    env=None,
    # Optional: Add server_id for clearer logs if needed
    server_id="mlnewsserver"
)

# --- Setup Gmail Server --- 
gmail_server_parameters = StdioServerParameters(
    command="uv",
    args=["run", "mail_agent/gmail_server.py"], # Runs step1/mail_agent/gmail_server.py for gmail
    env=None,
    # Optional: Add server_id for clearer logs if needed
    server_id="gmail_server"
)

# --- Setup Voice Call MCP Server --- 
voice_mcp_parameters = StdioServerParameters(
    command="uv",
    args=["run", "call_agent/voice_mcp_server.py"], # Runs step1/voice_mcp_server.py
    # Explicitly pass the environment variable to the child process
    env={"VOICE_SERVER_URL": VOICE_SERVER_URL_FOR_MCP},
    # Optional: Add server_id for clearer logs if needed
    server_id="voice_mcp_server"
)

# --- Setup CAG+RAG Server ---
cag_rag_server_parameters = StdioServerParameters(
    command="uv",
    args=["run", "cag_rag/cag_rag_server.py"], # Runs step1/cag_rag_server.py
    # Pass OpenAI key from the parent environment to the server
    env={"OPENAI_API_KEY": OPENAI_API_KEY},
    server_id="cag_rag_server"
)

# --- Setup Video Generation Server ---
video_gen_server_parameters = StdioServerParameters(
    command="uv",
    args=["run", "video_server.py"], # Changed from video_gen/video_server.py since cwd is set to video_gen
    # Pass OpenAI key and Replicate key from the parent environment
    env={
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "REPLICATE_API_KEY": REPLICATE_API_KEY,
        "SONAUTO_API_KEY": SONAUTO_API_KEY
    },
    server_id="video_generator_server",
    cwd="video_gen"  # Set working directory to video_gen subfolder
)


# Run the agent using tools from ALL MCP servers
print(f"{Fore.CYAN}Connecting to MCP servers (Finance, Gmail, Voice, CAG+RAG, Video Generator)...{Style.RESET_ALL}")
# Use try-with-resources to ensure servers are shut down
try:
    with ToolCollection.from_mcp(finance_server_parameters, trust_remote_code=True) as finance_tools, \
         ToolCollection.from_mcp(gmail_server_parameters, trust_remote_code=True) as gmail_tools, \
         ToolCollection.from_mcp(voice_mcp_parameters, trust_remote_code=True) as voice_tools, \
         ToolCollection.from_mcp(cag_rag_server_parameters, trust_remote_code=True) as cag_rag_tools, \
         ToolCollection.from_mcp(video_gen_server_parameters, trust_remote_code=True) as video_gen_tools:
        
        print(f"{Fore.GREEN}Servers connected.{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Combining tools and initializing agent...{Style.RESET_ALL}")
        
        # Combine tools from all collections
        all_tools = [
            *finance_tools.tools, 
            *gmail_tools.tools, 
            *voice_tools.tools, 
            *cag_rag_tools.tools,
            *video_gen_tools.tools
        ]
        agent = ToolCallingAgent(tools=all_tools, model=model)
        
        print(f"{Fore.GREEN}Agent initialized. You can now chat.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Example: 'How does the voice call system work?'{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Example: 'Explain the steps to launch the voice call agent'{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Example: 'call +14155551212 and ask about their availability for a meeting next week'{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Example: 'Create a video about a futuristic programming school for kids with rock music'{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Example: 'Create a chain of videos showing a journey through a futuristic city with electronic music'{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Type 'quit' or 'exit' to end the session.{Style.RESET_ALL}")

        # Interactive loop
        while True:
            try:
                query = input(f"{Fore.BLUE}> {Style.RESET_ALL}")
                if query.lower() in ["quit", "exit"]:
                    break
                if not query:
                    continue
                
                print(f"{Fore.MAGENTA}Thinking...{Style.RESET_ALL}")
                # The agent handles the conversation history internally
                response = agent.run(query)
                # The agent's run method likely prints output, but we can print the final response too
                print(f"{Fore.GREEN}Agent: {response}{Style.RESET_ALL}") 
            
            except EOFError: # Handle Ctrl+D
                break
            except KeyboardInterrupt: # Handle Ctrl+C
                 print(f"\n{Fore.YELLOW}Interrupted. Type 'quit' or 'exit' to end.{Style.RESET_ALL}")
            except Exception as e:
                 print(f"{Fore.RED}An error occurred: {e}{Style.RESET_ALL}")

except Exception as e:
    print(f"{Fore.RED}Failed to initialize MCP servers or agent: {e}{Style.RESET_ALL}")
finally:
    print(f"\n{Fore.CYAN}Exiting agent session.{Style.RESET_ALL}")

# The ToolCollection context managers automatically handle server shutdown
    