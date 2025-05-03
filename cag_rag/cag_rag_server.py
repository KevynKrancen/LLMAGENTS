#!/usr/bin/env python3
"""
cag_rag_server.py - MCP Server for CAG+RAG Multi-Project Q&A

Exposes the CAG+RAG graph from cag_rag.py as a tool for an agent.
"""

import os
import sys
import logging
from typing import List, TypedDict
from pathlib import Path
import asyncio # Needed for async tool function

# MCP/Tool-related imports
from mcp.server.fastmcp import FastMCP # Updated to use FastMCP
from pydantic import BaseModel, Field # For defining tool input schema

# Langchain/LangGraph imports (ensure these are installed in the server's env)
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph, END

# Bring in colorama for fancy printing like in gmail_server.py
from colorama import Fore

# --- Base Directory Setup ---
# Get the directory where this script (cag_rag_server.py) is located
SERVER_DIR = Path(__file__).parent
# Get the root project directory (one level up)
PROJECT_ROOT_DIR = SERVER_DIR.parent

# --- Setup Logging ---
# Configure basic logging. The agent process might have its own config.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger("cag_rag_server")

# Create FastMCP server
mcp = FastMCP("cagragserver")

# --- 1) Check Environment & Load LLM ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.critical("FATAL ERROR: OPENAI_API_KEY environment variable not set. CAG+RAG server cannot function.")
    # Exit if the key is missing, as the server is unusable without it.
    sys.exit("OPENAI_API_KEY environment variable not set.")

# Create necessary directories
os.makedirs(SERVER_DIR, exist_ok=True)

# Persist prompt→completion pairs locally (use path relative to SERVER_DIR)
cache_db_path = SERVER_DIR / "cag_cache.db"
os.makedirs(os.path.dirname(cache_db_path), exist_ok=True)
cache = SQLiteCache(database_path=str(cache_db_path))
set_llm_cache(cache)

# Instantiate the LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)
logger.info("LLM and cache initialized.")

# --- 2) Load Documentation (for CAG) ---
# Load project documentation from the top-level 'docs' directory (relative to PROJECT_ROOT_DIR)
docs_dir_path = PROJECT_ROOT_DIR / "docs"
logger.info(f"Loading project documentation for CAG from: {docs_dir_path}")
if not docs_dir_path.is_dir():
    logger.error(f"Documentation directory not found: {docs_dir_path}")
    sys.exit(f"Documentation directory not found: {docs_dir_path}")

docs_loader = DirectoryLoader(str(docs_dir_path), glob="**/*.md", show_progress=False, use_multithreading=True)
try:
    project_docs = docs_loader.load()
    logger.info(f"Loaded {len(project_docs)} documentation files for CAG.")
    # Combine all loaded documentation content once
    DOC_TEXT_COMBINED = "\n\n---\n\n".join([doc.page_content for doc in project_docs])
except Exception as e:
    logger.error(f"Failed to load documentation: {e}")
    sys.exit(f"Failed to load documentation: {e}")


# --- 3) Load Combined Code RAG Index ---
# Define project directories (relative to PROJECT_ROOT_DIR)
PROJECT_DIRS_RELATIVE = ["cag_rag", "mail_agent", "call_agent"] # Updated to match current structure
# Path for the FAISS index (relative to SERVER_DIR)
COMBINED_CODE_INDEX_PATH = SERVER_DIR / "faiss_combined_code_index"
os.makedirs(COMBINED_CODE_INDEX_PATH, exist_ok=True)

# Ensure embeddings can be created
embeddings = OpenAIEmbeddings()

# Load the FAISS vectorstore for combined code
code_index_path_str = str(COMBINED_CODE_INDEX_PATH)
if COMBINED_CODE_INDEX_PATH.exists() and any(COMBINED_CODE_INDEX_PATH.iterdir()):
    logger.info(f"Loading existing combined code index from: {code_index_path_str}")
    try:
        code_vectorstore = FAISS.load_local(code_index_path_str, embeddings, allow_dangerous_deserialization=True)
        code_retriever = code_vectorstore.as_retriever(search_kwargs={"k": 10})
        logger.info("Combined code RAG retriever ready.")
    except Exception as e:
        logger.error(f"Failed to load FAISS index from {code_index_path_str}: {e}")
        logger.info("Building new FAISS index...")
        
        # Load Python code from all specified project directories
        all_code_docs = []
        for proj_rel_dir in PROJECT_DIRS_RELATIVE:
            proj_abs_dir = PROJECT_ROOT_DIR / proj_rel_dir
            if proj_abs_dir.is_dir():
                logger.info(f"Loading code from: {proj_abs_dir}")
                code_loader = DirectoryLoader(
                    str(proj_abs_dir),
                    glob="**/*.py",
                    show_progress=False,
                    use_multithreading=True,
                    recursive=True,
                    exclude=["**/.*", "**/__pycache__/**", "**/wandb/**", "**/data/**", "**/ckpts/**", "**/.venv/**"]
                )
                try:
                    all_code_docs.extend(code_loader.load())
                except Exception as load_err:
                    logger.warning(f"Could not load code from {proj_abs_dir}. Error: {load_err}")
        
        # Also include server.py from the root
        server_py_path = PROJECT_ROOT_DIR / "server.py"
        if server_py_path.exists():
            try:
                from langchain.document_loaders import TextLoader
                server_loader = TextLoader(str(server_py_path))
                all_code_docs.extend(server_loader.load())
            except Exception as srv_err:
                logger.warning(f"Could not load code from {server_py_path}. Error: {srv_err}")
        
        # Split and build index
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        code_chunks = splitter.split_documents(all_code_docs)
        code_vectorstore = FAISS.from_documents(code_chunks, embeddings)
        code_vectorstore.save_local(code_index_path_str)
        code_retriever = code_vectorstore.as_retriever(search_kwargs={"k": 10})
        logger.info(f"New FAISS index built and saved at {code_index_path_str}")
else:
    logger.info(f"Building new FAISS index at: {code_index_path_str}")
    
    # Load Python code from all specified project directories
    all_code_docs = []
    for proj_rel_dir in PROJECT_DIRS_RELATIVE:
        proj_abs_dir = PROJECT_ROOT_DIR / proj_rel_dir
        if proj_abs_dir.is_dir():
            logger.info(f"Loading code from: {proj_abs_dir}")
            code_loader = DirectoryLoader(
                str(proj_abs_dir),
                glob="**/*.py",
                show_progress=False,
                use_multithreading=True,
                recursive=True,
                exclude=["**/.*", "**/__pycache__/**", "**/wandb/**", "**/data/**", "**/ckpts/**", "**/.venv/**"]
            )
            try:
                all_code_docs.extend(code_loader.load())
            except Exception as e:
                logger.warning(f"Could not load code from {proj_abs_dir}. Error: {e}")
    
    # Also include server.py from the root
    server_py_path = PROJECT_ROOT_DIR / "server.py"
    if server_py_path.exists():
        try:
            from langchain.document_loaders import TextLoader
            server_loader = TextLoader(str(server_py_path))
            all_code_docs.extend(server_loader.load())
        except Exception as e:
            logger.warning(f"Could not load code from {server_py_path}. Error: {e}")
    
    if not all_code_docs:
        logger.error("No code files could be loaded. Cannot build FAISS index.")
        sys.exit("Failed to load any code files")
    
    # Split and build index
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    code_chunks = splitter.split_documents(all_code_docs)
    code_vectorstore = FAISS.from_documents(code_chunks, embeddings)
    code_vectorstore.save_local(code_index_path_str)
    code_retriever = code_vectorstore.as_retriever(search_kwargs={"k": 10})
    logger.info(f"Built and saved new FAISS index at {code_index_path_str}")


# --- 4) Define Graph State & Nodes (Adapted from cag_rag.py) ---
class CAGRAGState(TypedDict, total=False):
    query: str
    doc_summary_context: str
    code_context: str
    answer: str

# Node for CAG summary
def summarize_docs_cag(state: CAGRAGState) -> CAGRAGState:
    logger.debug("Node: summarize_docs_cag")
    prompt = (
        f"You are an expert technical writer. Based *only* on the following project documentation, produce a concise context summary that is most relevant to the user's query.\n\n"
        f"PROJECT DOCUMENTATION:\n{DOC_TEXT_COMBINED}\n\n" # Use pre-loaded combined text
        f"---\n\n"
        f"USER QUERY:\n{state['query']}\n\n"
        f"Concise Relevant Summary (focus on explaining concepts, setup, or components mentioned in the query based on the docs):"
    )
    summary = llm.invoke(prompt).content
    logger.debug(f"  Generated doc summary context (length: {len(summary)} chars)")
    return {"doc_summary_context": summary}

# Node for RAG code retrieval
def retrieve_code_rag(state: CAGRAGState) -> CAGRAGState:
    logger.debug("Node: retrieve_code_rag")
    query = state["query"]
    retrieved_code_docs = code_retriever.invoke(query)
    code_context = "\n\n---\n\n".join(
        f"### File: {d.metadata.get('source', 'Unknown Source')}\n"
        f"```python\n{d.page_content}\n```"
        for d in retrieved_code_docs
    )
    logger.debug(f"  Retrieved {len(retrieved_code_docs)} code snippets (total length: {len(code_context)} chars)")
    return {"code_context": code_context}

# Node for final answer generation
def generate_final_answer(state: CAGRAGState) -> CAGRAGState:
    logger.debug("Node: generate_final_answer")
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
    ans = llm.invoke(prompt).content
    logger.debug("  Generated final answer.")
    return {"answer": ans}


# --- 5) Assemble Graph ---
logger.info("Assembling the CAG+RAG graph...")
graph_builder = StateGraph(CAGRAGState)
graph_builder.add_node("summarize_docs", summarize_docs_cag)
graph_builder.add_node("retrieve_code", retrieve_code_rag)
graph_builder.add_node("generate_answer", generate_final_answer)
graph_builder.add_edge("summarize_docs", "retrieve_code")
graph_builder.add_edge("retrieve_code", "generate_answer")
graph_builder.add_edge("generate_answer", END)
graph_builder.set_entry_point("summarize_docs")
compiled_graph = graph_builder.compile()
logger.info("CAG+RAG Graph compiled successfully.")


# --- 6) Define MCP Tool ---
# Use FastMCP tool decorator pattern instead of explicit ToolDefinition

@mcp.tool()
def ask_about_projects(query: str) -> str:
    """Answers questions about the code, documentation, and how the project works.
    USE THIS TOOL for any questions about:
    - How the code works
    - How to use or launch any part of the system
    - Project architecture or components
    - Technical explanations of any features
    - Understanding the codebase

    Args:
        query: The question about the project code, structure, or functionality.

    Returns:
        str: A detailed explanation based on the project documentation and code.
    """
    print(f"{Fore.CYAN}Received query for CAG+RAG: '{query}'{Fore.RESET}")
    graph_input = {"query": query}
    try:
        # Run the graph synchronously
        final_state = compiled_graph.invoke(graph_input)
        answer = final_state.get("answer", "Error: Could not generate answer.")
        print(f"{Fore.GREEN}Successfully generated answer via CAG+RAG graph.{Fore.RESET}")
        return answer
    except Exception as e:
        error_msg = f"Error processing query with CAG+RAG graph: {e}"
        print(f"{Fore.RED}{error_msg}{Fore.RESET}")
        logger.error(error_msg, exc_info=True)
        return f"Error processing your query: {e}"


# --- 7) Start MCP Server ---
if __name__ == "__main__":
    print(f"{Fore.CYAN}Starting CAG+RAG MCP server...{Fore.RESET}")
    print(f"{Fore.CYAN}Initializing CAG+RAG Server...{Fore.RESET}")
    # Server is already initialized above
    print(f"{Fore.CYAN}Starting MCP server...{Fore.RESET}")
    mcp.run(transport="stdio")
    print(f"{Fore.CYAN}CAG+RAG MCP server stopped.{Fore.RESET}") 