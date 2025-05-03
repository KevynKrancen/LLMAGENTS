# Video Generator MCP Server

## Overview
The Video Generator MCP server provides tools to create customized videos from natural language descriptions. It leverages various AI models to generate images, videos, music, and voice narration, and combines them into a cohesive output.

## Purpose
This server enables users to:
- Generate single videos with custom content, style, and narration
- Create chains of connected videos that transition from one to another
- Customize video duration, style, and background music
- Add voice narration to videos

The video generation functionality extends the agent system with multimedia creation capabilities, making it useful for creating content for presentations, social media, or other creative purposes.

## How It Works

### Architecture
The Video Generator MCP implementation uses:
1. **MCP Server** (`video_server.py`): Provides the MCP tool interface for the agent
2. **Video Generation Core** (`video_gen.py`): Handles the actual video generation functionality

The MCP server exposes tools that coordinate the different steps of video generation, from idea creation to final video output.

### Technology
- **FastMCP**: Server framework that exposes video generation operations as tools
- **Replicate**: API service for image and video generation
- **OpenAI**: For idea generation and voice narration
- **Sonauto**: For music generation
- **OpenCV**: For video processing tasks

## Detailed Setup

### 1. API Keys Configuration
The video generator requires several API keys to function:

1. **OpenAI API Key**: Used for idea generation and voice narration
   - Create an account at [OpenAI](https://openai.com/) if you don't have one
   - Generate an API key from your account dashboard

2. **Replicate API Key**: Used for image and video generation
   - Create an account at [Replicate](https://replicate.com/) if you don't have one
   - Generate an API key from your account settings

3. **Sonauto API Key**: Used for music generation
   - Create an account at [Sonauto](https://sonauto.ai/) if you don't have one
   - Generate an API key from your account dashboard

### 2. Environment Variables
Add your API keys to your `.env` file in the project root:

```
# OpenAI API key (required for idea generation and voice narration)
OPENAI_API_KEY=your_openai_api_key

# Replicate API key (required for image and video generation)
REPLICATE_API_KEY=your_replicate_api_key

# Sonauto API key (required for music generation)
SONAUTO_API_KEY=your_sonauto_api_key
```

### 3. Directory Structure
The video generator requires several directories to store generated content:
- `image/`: Stores generated images
- `video/`: Stores generated videos
- `music/`: Stores generated music
- `voice/`: Stores generated voice narration
- `prompts/`: Contains prompt templates for generation

These directories will be created automatically when the server starts.

## Components

### 1. MCP Server Instance
```python
mcp = FastMCP("video_generator_server")
```
Creates an MCP server named "video_generator_server" that handles video generation requests.

### 2. Tools

#### Create Custom Video Tool
```python
@mcp.tool()
async def create_custom_video(request: str) -> Dict[str, Any]:
```
Processes a natural language request, extracts parameters, and generates a customized video.

#### Create Chain Video Tool
```python
@mcp.tool()
async def create_chain_video(request: str, video_count: int) -> Dict[str, Any]:
```
Creates multiple connected videos that transition from one to another.

#### Get Video Info Tool
```python
@mcp.tool()
async def get_video_info() -> Dict[str, Any]:
```
Returns information about the video generation system and its capabilities.

## Data Flow
1. The agent calls one of the video generation tools with a natural language description
2. The system extracts parameters from the request (duration, style, music type, etc.)
3. An idea is generated based on the request using OpenAI
4. An image is created based on the idea using Replicate's Flux model
5. Videos are generated from the image using Replicate's Kling model
6. Music is generated using Sonauto API
7. Voice narration is created using OpenAI's voice generation (if requested)
8. All components are merged into a final video
9. The path to the final video is returned to the agent

## Launch from agent.py

The Video Generator server is automatically started when you run the main agent.py file. The agent sets up the server with the following configuration:

```python
# Setup Video Generation Server
video_gen_server_parameters = StdioServerParameters(
    command="uv",
    args=["run", "video_server.py"], 
    env={
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "REPLICATE_API_KEY": REPLICATE_API_KEY,
        "SONAUTO_API_KEY": SONAUTO_API_KEY
    },
    server_id="video_generator_server",
    cwd="video_gen"  # Sets working directory to video_gen subfolder
)
```

To start the server as part of the agent system:

1. Ensure your `.env` file contains all required API keys
2. Run the main agent:
   ```bash
   uv run agent.py
   ```

The agent will automatically start the Video Generator server along with other servers.

## Using the Video Generator

### Basic Video Creation
To create a basic video through the agent:
```
Create a video about a futuristic programming school for kids with rock background music saying "Join us for a coding adventure!"
```

### Creating Video Chains
To create a chain of connected videos:
```
Create a chain of videos showing a journey through a futuristic city with electronic music
```

## Troubleshooting

### Common Issues
- **Missing API Keys**: Ensure all required API keys are set in your `.env` file
- **API Rate Limits**: If you encounter errors about rate limits, you may need to wait before making more requests
- **Video Generation Failures**: If video generation fails, try simplifying your request or using different keywords

### Specific Error Messages
- "Failed to generate an image after multiple attempts": Try a different description or check your Replicate API key
- "Error during music generation": Verify your Sonauto API key and check if the service is available
- "Voice dialog generation failed": Check your OpenAI API key and ensure you have access to the voice generation feature

### Environment Setup Issues
- Verify all environment variables are correctly set in your `.env` file
- Ensure your Python environment has all the required dependencies installed

## Additional Resources
- [Replicate Documentation](https://replicate.com/docs)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Sonauto API Documentation](https://docs.sonauto.ai) 