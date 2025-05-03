# Import required libraries for web search
import requests
import json
from datetime import datetime
# Bring in colorama for fancy printing
from colorama import Fore
# Bring in MCP Server SDK
from mcp.server.fastmcp import FastMCP
# Create server 
mcp = FastMCP("mlnewsserver")

# Add in a prompt function
@mcp.prompt()
def news_summary(news_data:str) -> str:
    """Prompt template for summarising machine learning news"""
    return f"""You are a helpful AI assistant specializing in machine learning and deep learning news.
                Using the information below, summarize the key points and developments in machine learning and deep learning.
                Data: {news_data}"""
                
# Build server function for ML/DL search
@mcp.tool()
def search_ml_news(query: str, num_results: int = 5) -> str:
    """This tool searches for machine learning and deep learning news based on a query.
    Args:
        query: A search query related to machine learning or deep learning
        num_results: Number of results to return (default: 5, max: 10)
        Example payload: "transformer models advances"

    Returns:
        str: Formatted search results with titles, snippets, and URLs
    """
    # Validate inputs
    if num_results > 10:
        num_results = 10  # Cap at 10 results
    
    # Construct search query to focus on ML/DL news
    enhanced_query = f"{query} machine learning deep learning AI news research"
    
    # Use a search API (this example uses serpapi.com format, but you'd need to replace with your chosen API)
    try:
        # Replace this with your actual search implementation
        # For now, we'll use a mock example that would need to be replaced with a real API
        search_url = "https://api.search.com/search"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        params = {
            "q": enhanced_query,
            "num": num_results
        }
        
        print(Fore.YELLOW + f"Searching for: {enhanced_query}")
        
        # This is a placeholder. In a real implementation, you would:
        # response = requests.get(search_url, headers=headers, params=params)
        # results = response.json()
        
        # For now, return a formatted message about the search
        return f"Searched for ML/DL news about: '{query}'. Please implement an actual search API (like Google Custom Search, Bing News, etc.) by modifying the server.py file with your API credentials."
    
    except Exception as e:
        return f"Error searching for ML/DL news: {str(e)}"

@mcp.tool()
def get_trending_ml_topics() -> str:
    """This tool returns currently trending topics in machine learning and deep learning.
    
    Returns:
        str: List of trending topics in ML/DL with brief descriptions
    """
    try:
        # This would typically call an API or scrape a website for trending topics
        # For now, return a placeholder message
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        return f"""Trending ML/DL topics as of {current_date}:
        
        Note: This is a placeholder. Replace the implementation in server.py with an actual news API or web scraping solution.
        
        To implement real trending topics:
        1. Sign up for a news API like NewsAPI.org, Google News API, or Bing News Search
        2. Update the server.py file with your API key and implementation
        3. Parse the results to extract trending machine learning topics
        """
    except Exception as e:
        return f"Error fetching trending ML/DL topics: {str(e)}"

@mcp.tool()
def get_ml_research_papers(topic: str, max_results: int = 3) -> str:
    """This tool searches for recent machine learning research papers on a specific topic.
    Args:
        topic: A specific ML/DL topic to search for papers
        max_results: Maximum number of papers to return (default: 3, max: 5)
        Example payload: "generative adversarial networks"

    Returns:
        str: Formatted list of research papers with titles, authors, and links
    """
    # Validate inputs
    if max_results > 5:
        max_results = 5  # Cap at 5 results
    
    try:
        # This would typically call an API like arXiv or Semantic Scholar
        # For demonstration, return a placeholder
        return f"""Research papers search for "{topic}":
        
        Note: This is a placeholder. Implement actual research paper search by:
        1. Using the arXiv API (arxiv.org/help/api)
        2. Using the Semantic Scholar API
        3. Or another academic paper search API
        
        Update server.py with your implementation to get real research paper results.
        """
    except Exception as e:
        return f"Error searching for research papers: {str(e)}"

# Kick off server if file is run 
if __name__ == "__main__":
    mcp.run(transport="stdio")