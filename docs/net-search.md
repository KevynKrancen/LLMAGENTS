# ML/DL News MCP Server

## Overview
The ML/DL News MCP server provides a set of tools to search and retrieve information about machine learning and deep learning news, trending topics, and research papers. It serves as a specialized knowledge source for AI advancements and research.

## Purpose
This server enables users to:
- Search for machine learning and deep learning news based on queries
- Retrieve currently trending topics in ML/DL
- Find recent research papers on specific ML/DL topics

The server is designed to be used within a larger multi-agent system, providing specialized ML/DL news capabilities to the main agent.

## How It Works

### Technology
- **News API**: Placeholder for integration with search APIs like Google Custom Search, Bing News, etc.
- **Research Paper APIs**: Placeholder for integration with arXiv or Semantic Scholar
- **FastMCP**: Server framework that exposes tools and resources to MCP clients

### Components

#### 1. MCP Server Instance
```python 
mcp = FastMCP("mlnewsserver")
```
Creates an MCP server named "mlnewsserver" that handles requests from clients.

#### 2. Prompt Template
```python
@mcp.prompt()
def news_summary(news_data:str) -> str:
```
Provides a template for summarizing machine learning news data in a structured format.

#### 3. Tools

##### Search ML News Tool
```python
@mcp.tool()
def search_ml_news(query: str, num_results: int = 5) -> str:
```
Searches for machine learning and deep learning news based on a query, returning formatted results.

##### Trending ML Topics Tool
```python
@mcp.tool()
def get_trending_ml_topics() -> str:
```
Retrieves currently trending topics in machine learning and deep learning.

##### ML Research Papers Tool
```python
@mcp.tool()
def get_ml_research_papers(topic: str, max_results: int = 3) -> str:
```
Searches for recent machine learning research papers on a specific topic.

## Data Flow
1. The client sends a request to the ML/DL News MCP server
2. The server processes the request using the appropriate tool
3. The tool retrieves data from the corresponding API (news API, research paper API)
4. The server formats and returns the data to the client

## Setup and Launch

### Prerequisites
- Python 3.12 or later
- Dependencies installed via uv: `requests`, `colorama`, `mcp`
- (Optional) API keys for news search and research paper services

### How to Launch
The server can be launched in three ways:

1. **Direct Launch** (for testing or standalone use):
   ```bash
   uv run server.py
   ```

2. **Inspector Mode** (for debugging and monitoring):
   ```bash
   uv run mcp dev server.py
   ```

3. **Via Agent** (normal usage):
   The server is automatically launched when running the main agent:
   ```bash
   uv run agent.py
   ```

### Implementation Notes
The current implementation uses placeholder responses. To get actual results:
1. Sign up for a news API like NewsAPI.org, Google News API, or Bing News Search
2. Update the server.py file with your API key and implementation
3. For research papers, consider integrating with arXiv API or Semantic Scholar API 