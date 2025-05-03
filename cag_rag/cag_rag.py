#!/usr/bin/env python3
"""
cag_rag.py — CAG + RAG with LangGraph for Multi-Project Q&A

Dependencies:
  pip install -U langgraph langchain langchain-openai langchain-community faiss-cpu tiktoken

Run:
  python cag_rag.py
  → enter your OpenAI key
  → Ask questions about the documented projects until you type "exit"
"""
import os
import sys # Import sys for stderr printing if needed
import logging # Import logging
from getpass import getpass
from typing import List, TypedDict
from pathlib import Path

# Langchain/LangGraph imports
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph, END

# --- Base Directory Setup ---
# Get the directory where this script (cag_rag.py) is located
CAG_RAG_DIR = Path(__file__).parent
# Get the root project directory (one level up)
PROJECT_ROOT_DIR = CAG_RAG_DIR.parent

# ─── 1) SET UP LLM & CACHE ───────────────────────────────────────────────────

# Ensure OpenAI API key is available
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    if __name__ == "__main__":
        # Prompt only if running directly
        os.environ["OPENAI_API_KEY"] = getpass("OpenAI API Key: ")
        OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    else:
        # Log a fatal error and potentially exit if imported without the key
        logging.critical("FATAL ERROR: OPENAI_API_KEY environment variable not set. CAG+RAG agent cannot function.")
        # Option 1: Raise an exception to stop server loading
        raise ValueError("OPENAI_API_KEY environment variable not set.")
        # Option 2: Allow server to continue but LLM will fail (current behavior, but now with explicit log)
        # For now, let's just log the critical error.

# Create cache directory if it doesn't exist
os.makedirs(CAG_RAG_DIR, exist_ok=True)

# Persist prompt→completion pairs locally (use path relative to CAG_RAG_DIR)
cache_db_path = CAG_RAG_DIR / "cag_cache.db"
cache = SQLiteCache(database_path=str(cache_db_path))
set_llm_cache(cache)

# Instantiate the LLM (used for CAG context generation and final answer)
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# --- Setup Logging (configure if not already done by importer) ---
# If this script is run directly, configure logging.
# If imported, assume the main server script configures logging.
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
else:
    # Ensure a handler exists if imported, preventing "No handlers could be found"
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(levelname)s - %(message)s')


# ─── 2) PREPARE DOCUMENTATION CHUNKS (for CAG context) ────────────────────────

# Load project documentation from the top-level 'docs' directory (relative to PROJECT_ROOT_DIR)
docs_dir_path = PROJECT_ROOT_DIR / "docs"
logging.info(f"Loading project documentation for CAG from: {docs_dir_path}")
# Removed PyPDFDirectoryLoader import and related code
docs_loader = DirectoryLoader(str(docs_dir_path), glob="**/*.md", show_progress=True, use_multithreading=True)
project_docs = docs_loader.load()
# We'll use these docs directly in the CAG node, no intermediate chunks needed here.
logging.info(f"Loaded {len(project_docs)} documentation files.")


# ─── 3) BUILD COMBINED CODE RAG INDEX ─────────────────────────────────────────

# Define project directories (relative to PROJECT_ROOT_DIR)
# Updated to include all relevant code directories
PROJECT_DIRS_RELATIVE = ["cag_rag", "mail_agent", "call_agent", "video_gen", "ticker_db", "templates"]

# Create FAISS index directory if it doesn't exist
COMBINED_CODE_INDEX_PATH = CAG_RAG_DIR / "faiss_combined_code_index"
os.makedirs(COMBINED_CODE_INDEX_PATH, exist_ok=True)

# Load Python code from all specified project directories
logging.info("Loading Python code from project directories for RAG...")
all_code_docs = []
for proj_rel_dir in PROJECT_DIRS_RELATIVE:
    # Construct absolute path
    proj_abs_dir = PROJECT_ROOT_DIR / proj_rel_dir
    if proj_abs_dir.is_dir():
        logging.info(f"  Loading code from: {proj_abs_dir}")
        code_loader = DirectoryLoader(
            str(proj_abs_dir),
            glob="**/*.py",
            show_progress=True,
            use_multithreading=True,
            recursive=True,
            exclude=["**/.*", "**/__pycache__/**", "**/wandb/**", "**/data/**", "**/ckpts/**", "**/.venv/**"] # Exclude .venv too
        )
        try:
             all_code_docs.extend(code_loader.load())
        except Exception as e:
             logging.warning(f"    Warning: Could not load code from {proj_abs_dir}. Error: {e}")
    else:
        logging.warning(f"  Warning: Directory not found, skipping: {proj_abs_dir}")

# Also include important files from the root directory
root_files = ["agent.py", "server.py", "web_ui.py"]
for file_name in root_files:
    file_path = PROJECT_ROOT_DIR / file_name
    if file_path.exists():
        logging.info(f"  Loading code from: {file_path}")
        try:
            from langchain.document_loaders import TextLoader
            loader = TextLoader(str(file_path))
            all_code_docs.extend(loader.load())
        except Exception as e:
            logging.warning(f"    Warning: Could not load code from {file_path}. Error: {e}")

logging.info(f"Loaded {len(all_code_docs)} Python files total.")

# Split code documents into chunks
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
code_chunks = splitter.split_documents(all_code_docs)
logging.info(f"Split code into {len(code_chunks)} chunks.")

# Generate embeddings and build/load FAISS vectorstore for combined code
# NOTE: Still using OpenAI embeddings for RAG. Ensure OPENAI_API_KEY is set in env.
if "OPENAI_API_KEY" not in os.environ:
    logging.warning("Warning: OPENAI_API_KEY not found in environment. Needed for embeddings.")
    # Consider adding a fallback or prompting if needed: os.environ["OPENAI_API_KEY"] = getpass("OpenAI API Key for Embeddings: ")
embeddings = OpenAIEmbeddings()

# Use the absolute path string for FAISS
code_index_path_str = str(COMBINED_CODE_INDEX_PATH)
if COMBINED_CODE_INDEX_PATH.exists() and any(COMBINED_CODE_INDEX_PATH.iterdir()):
    logging.info(f"Loading existing combined code index from: {code_index_path_str}")
    code_vectorstore = FAISS.load_local(code_index_path_str, embeddings, allow_dangerous_deserialization=True)
else:
    logging.info(f"Building new combined code index at: {code_index_path_str}")
    code_vectorstore = FAISS.from_documents(code_chunks, embeddings)
    code_vectorstore.save_local(code_index_path_str)
    logging.info("Index saved.")

# Create retriever for the combined code index
code_retriever = code_vectorstore.as_retriever(search_kwargs={"k": 10})
logging.info("Combined code RAG retriever ready.")

# Removed docs index loading/creation and docs_retriever


# ─── 4) DEFINE GRAPH STATE & NODES ────────────────────────────────────────────

# Define the state dictionary - removed doc_context
class CAGRAGState(TypedDict, total=False):
    query: str
    doc_summary_context: str # Renamed cached_context for clarity
    code_context: str
    answer: str

# Node to use CAG for summarizing relevant documentation
def summarize_docs_cag(state: CAGRAGState) -> CAGRAGState:
    logging.info("Node: summarize_docs_cag")
    # Combine all loaded documentation content
    doc_text = "\n\n---\n\n".join([doc.page_content for doc in project_docs])

    prompt = (
        f"You are an expert technical writer. Based *only* on the following project documentation, produce a concise context summary that is most relevant to the user's query.\n\n"
        f"PROJECT DOCUMENTATION:\n{doc_text}\n\n"
        f"---\n\n"
        f"USER QUERY:\n{state['query']}\n\n"
        f"Concise Relevant Summary (focus on explaining concepts, setup, or components mentioned in the query based on the docs):"
    )
    # Use the cached LLM for this step
    summary = llm.invoke(prompt).content
    logging.info(f"  Generated doc summary context (length: {len(summary)} chars)")
    return {"doc_summary_context": summary}

# Removed retrieve_docs node

# Node to retrieve relevant code snippets using RAG
def retrieve_code_rag(state: CAGRAGState) -> CAGRAGState:
    logging.info("Node: retrieve_code_rag")
    query = state["query"]
    retrieved_code_docs = code_retriever.invoke(query) # Updated to use invoke
    # Format code snippets with metadata
    code_context = "\n\n---\n\n".join(
        # Ensure metadata exists before trying to access keys
        f"### File: {d.metadata.get('source', 'Unknown Source')}\n"
        # Add line numbers if available in metadata (RecursiveCharacterTextSplitter doesn't add them by default)
        # f"Lines: {d.metadata.get('start_index', '?')} onwards\n" # Example if metadata had line info
        f"```python\n{d.page_content}\n```"
        for d in retrieved_code_docs
    )
    logging.info(f"  Retrieved {len(retrieved_code_docs)} code snippets (total length: {len(code_context)} chars)")
    return {"code_context": code_context}

# Node to generate the final answer using LLM
def generate_final_answer(state: CAGRAGState) -> CAGRAGState:
    logging.info("Node: generate_final_answer")

    prompt = f"""
 You are a helpful AI assistant knowledgeable about several software projects.
 Answer the user's query based *only* on the provided project documentation summary and relevant code snippets.

 If the documentation summary or code snippets do not contain the answer, state that clearly. Do not make up information.

 --- PROJECT DOCUMENTATION SUMMARY ---
 {state['doc_summary_context']}

 --- RELEVANT CODE SNIPPETS ---
 {state['code_context']}

 --- USER QUERY ---
 {state['query']}

 --- YOUR ANSWER ---
 """
    # Use the LLM (caching enabled via set_llm_cache earlier)
    ans = llm.invoke(prompt).content
    logging.info("  Generated final answer.")
    return {"answer": ans}


# ─── 5) ASSEMBLE THE GRAPH ─────────────────────────────────────────────────────
logging.info("Assembling the graph...")
graph = StateGraph(CAGRAGState)

# Add nodes
graph.add_node("summarize_docs", summarize_docs_cag) # Renamed from "cag"
graph.add_node("retrieve_code", retrieve_code_rag) # Renamed from "code"
# Removed "docs" node
graph.add_node("generate_answer", generate_final_answer) # Renamed from "final"

# Define edges
graph.add_edge("summarize_docs", "retrieve_code") # CAG -> RAG(Code)
graph.add_edge("retrieve_code", "generate_answer") # RAG(Code) -> Final Answer
graph.add_edge("generate_answer", END)

# Set entry point
graph.set_entry_point("summarize_docs")

# Compile the graph
app = graph.compile()
logging.info("CAG+RAG Graph compiled successfully.")


# ─── 6) RUN A SIMPLE CHAT LOOP ─────────────────────────────────────────────────
if __name__ == "__main__":
    # Use print here since it's direct user interaction in __main__
    print("\n--- Multi-Project Q&A Assistant (Direct Run) ---")
    print("Ask questions about the project code and documentation.")
    print("Type 'exit' or 'quit' to end.")
    while True:
        q = input("\nAsk a question> ").strip()
        if not q:
            continue
        if q.lower() in ("exit", "quit"):
            break
        print("Processing...")
        # Pass only the query; generator and service are handled internally if needed by nodes
        # The state dictionary includes the required components (llm, retrievers) implicitly via the node functions
        inputs = {"query": q}
        try:
            # Stream events for better feedback (optional)
            # for event in app.stream(inputs):
            #     print(f"Event: {event}") # Print event details
            # final_state = event # The last event is the final state

            # Or just invoke directly
            final_state = app.invoke(inputs)

            print("\nAnswer:")
            print(final_state["answer"])
        except Exception as e:
            print(f"\nError processing request: {e}")
            # Optionally add more detailed error logging here
            # import traceback
            # print(traceback.format_exc())

    print("\nExiting...")
