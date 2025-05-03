# CAG+RAG MCP Server

## Overview
The CAG+RAG (Context-Aware Generation + Retrieval Augmented Generation) MCP server provides a sophisticated question-answering system that can respond to queries about the project codebase and documentation. It combines context-aware document summarization with code retrieval to provide informative and accurate responses.

## Purpose
This server enables users to:
- Ask questions about the project's codebase and how it works
- Understand various components and their relationships
- Get explanations of concepts implemented in the code
- Access documentation-based context about the project

The CAG+RAG server acts as a knowledge base assistant for the project, making it easier for users to understand the system without needing to manually search through files.

## How It Works

### Technology Stack
- **LangChain/LangGraph**: Orchestrates the multi-stage processing pipeline
- **OpenAI**: Provides the language model capabilities for both CAG and answer generation
- **FAISS**: Vector database for storing and retrieving relevant code snippets
- **FastMCP**: Exposes the CAG+RAG capabilities as tools through the MCP protocol

### Architecture
CAG+RAG uses a graph-based pipeline with three main stages:
1. **Context-Aware Generation (CAG)**: Summarizes relevant documentation based on the query
2. **Retrieval Augmented Generation (RAG)**: Retrieves relevant code snippets from the codebase
3. **Final Answer Generation**: Combines document summaries and code snippets to provide a comprehensive answer

### Components

#### 1. MCP Server Instance
```python
mcp = FastMCP("cagragserver")
```
Creates an MCP server named "cagragserver" that handles CAG+RAG queries.

#### 2. Document Loading
```python
docs_loader = DirectoryLoader(str(docs_dir_path), glob="**/*.md", show_progress=False, use_multithreading=True)
```
Loads project documentation from Markdown files in the `docs` directory.

#### 3. Code Index
```python
code_vectorstore = FAISS.load_local(code_index_path_str, embeddings, allow_dangerous_deserialization=True)
```
Loads a pre-built FAISS index containing embeddings of code from the project.

#### 4. Processing Graph
```python
graph_builder = StateGraph(CAGRAGState)
```
Defines a processing pipeline with nodes for document summarization, code retrieval, and answer generation.

#### 5. MCP Tool
```python
@mcp.tool()
def ask_about_projects(query: str) -> str:
```
Exposes the CAG+RAG capabilities as a tool that accepts a question and returns an answer based on project documentation and code.

## Data Flow
1. User submits a query through the agent
2. The query is processed by the CAG stage to generate a document summary
3. The RAG stage retrieves relevant code snippets based on the query
4. The answer generation stage combines document context and code snippets to create a comprehensive answer
5. The answer is returned to the agent and presented to the user

## Setup and Launch

### Prerequisites
- Python 3.12 or later
- Dependencies: `langgraph`, `langchain`, `langchain-openai`, `langchain-community`, `faiss-cpu`, `tiktoken`
- OpenAI API key set as environment variable `OPENAI_API_KEY`
- Pre-built FAISS index for code retrieval

### Index Building
Before using the CAG+RAG server for the first time, you need to build the code index:

1. Run the original `cag_rag.py` script once:
   ```bash
   cd step1
   uv run CAG_RAG/cag_rag.py
   ```
   This will create the FAISS index in `step1/CAG_RAG/faiss_combined_code_index/`.

2. Once the index is built, it will be reused by the MCP server.

### How to Launch

The server can be launched in several ways:

1. **Direct Launch** (for testing or standalone use):
   ```bash
   cd step1
   uv run cag_rag/cag_rag_server.py
   ```

2. **Via Agent** (normal usage):
   ```bash
   uv run agent.py
   ```
   The agent automatically starts the CAG+RAG server.

### Using the CAG+RAG Server
To use the CAG+RAG functionality through the agent:
1. Start the agent with `uv run agent.py`
2. Ask questions about the project, for example:
   - "What is the purpose of the CAG_RAG project?"
   - "How does the Gmail server authenticate with Google?"
   - "Explain how the voice call system works"

### Troubleshooting
- If the server fails to start, ensure `OPENAI_API_KEY` is set in your environment
- If answers are not relevant, verify that the FAISS index exists and has been properly built
- The server requires access to the `docs` directory; make sure it exists and contains relevant documentation
- If you update the codebase significantly, rebuild the FAISS index by running `cag_rag.py` again 