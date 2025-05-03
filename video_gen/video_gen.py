import os
import base64
import time
import json
import requests
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
import replicate
from openai import OpenAI
import cv2
from typing import Optional, List, Dict, Any, Union
import httpx
import re
import asyncio

# Load environment variables from .env file
load_dotenv()

# Get API keys from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SONAUTO_API_KEY = os.getenv("SONAUTO_API_KEY")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")

# Set Replicate API key for the replicate client
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_KEY

# Ensure output directories exist - create them both relative to script and in CWD
def ensure_directories():
    """Ensure all required output directories exist."""
    # Create directories relative to script location for server use
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for dir_name in ["image", "video", "music", "voice"]:
        Path(os.path.join(script_dir, dir_name)).mkdir(exist_ok=True)
    
    # Also create in current working directory for direct script use
    for dir_name in ["image", "video", "music", "voice"]:
        Path(dir_name).mkdir(exist_ok=True)

# Create directories at import time
ensure_directories()

# Constants for the idea logging system
LAST_IDEAS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_ideas.json")
MAX_STORED_IDEAS = 6

def read_file(file_path):
    """Read the content of a file."""
    # Try first as a relative path to the script's location
    abs_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path)
    
    try:
        with open(abs_file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        # If not found relative to script, try as a relative path to CWD
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            print(f"Error: Prompt file not found at {abs_file_path} or {file_path}")
            return ""  # Return empty for now

def save_file(file_path, content, mode='wb'):
    """Save content to a file."""
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, mode) as file:
        file.write(content)

def load_last_ideas():
    """Load the list of recently generated ideas."""
    if os.path.exists(LAST_IDEAS_FILE):
        try:
            with open(LAST_IDEAS_FILE, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError:
            # If the file exists but is corrupted, return an empty list
            return []
    return []

def save_idea_to_history(idea):
    """Save an idea to the history file, keeping only the most recent ones."""
    ideas = load_last_ideas()
    
    # Add the new idea
    ideas.append(idea)
    
    # Keep only the most recent MAX_STORED_IDEAS
    if len(ideas) > MAX_STORED_IDEAS:
        ideas = ideas[-MAX_STORED_IDEAS:]
    
    # Save the updated list
    with open(LAST_IDEAS_FILE, 'w') as file:
        json.dump(ideas, file)

def generate_idea(theme: str = None):
    """Step 1: Generate an idea using OpenAI API, optionally guided by theme."""
    print("Step 1: Generating idea using OpenAI API...")

    # Read prompt template from idea_gen.txt
    idea_prompt_template = read_file("prompts/idea_gen.txt")
    if not idea_prompt_template:
         raise FileNotFoundError("Could not read prompts/idea_gen.txt")

    # Prepare theme context
    theme_instruction = ""
    if theme:
        print(f"Guiding idea generation with theme: {theme}")
        theme_instruction = f"\nFocus specifically on this theme: {theme}\n"

    # Inject theme context into the placeholder
    idea_prompt = idea_prompt_template.replace("{theme_context}", theme_instruction)

    # Load recently used ideas and add avoidance context
    last_ideas = load_last_ideas()
    if last_ideas:
        avoid_prompt_section = "\n\nPlease avoid generating ideas similar to these recently created ones:\n" + "\n".join([f"{i+1}. {idea_item}" for i, idea_item in enumerate(last_ideas)])
        idea_prompt += avoid_prompt_section

    # Call OpenAI API
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": idea_prompt}]
    )

    result = response.choices[0].message.content

    # Parse the result to extract idea and prompt
    parts = result.split("Prompt:")
    idea = parts[0].replace("Idea:", "").strip()
    prompt = parts[1].strip() if len(parts) > 1 else ""

    # Clean up idea text (remove example markers, markdown)
    if "Example" in idea and ":" in idea.split("Example")[1]:
        try:
            example_parts = idea.split(":", 1)
            if len(example_parts) > 1: idea = example_parts[1].strip()
        except: pass
    idea = idea.replace('*', '')
    idea = ' '.join(idea.split())

    print(f"Generated Idea: {idea}")
    print(f"Generated Prompt: {prompt[:100]}...")

    save_idea_to_history(idea)
    return {"idea": idea, "prompt": prompt}

# Synchronous version of generate_image
def generate_image(prompt, output_image_path=None):
    """Generate an image using Flux AI (synchronous)."""
    print(f"Step 2: Generating image using Flux Image AI with prompt: {prompt[:50]}...")
    
    # Generate output path if not provided
    if output_image_path is None:
        timestamp = int(time.time())
        output_image_path = f"image/flux_image_{timestamp}.png"
    
    # Check if prompt is empty or None
    if not prompt or prompt.strip() == "":
        print("Warning: Empty prompt detected. Using a fallback prompt.")
        prompt = "A mysterious atmospheric scene with dramatic lighting and cinematic composition."
    
    # Call Flux Image API with 9:16 aspect ratio dimensions
    input_data = {
        "width": 768,
        "height": 1344,
        "prompt": prompt,
        "output_format": "png",  # Explicitly request PNG format
        "aspect_ratio": "9:16",  # Explicitly set aspect ratio to 9:16
        "safety_tolerance": 6    # Set safety tolerance to maximum (6)
    }
    
    try:
        print(f"Calling Replicate API with prompt: {prompt}")
        output = replicate.run(
            "black-forest-labs/flux-pro",
            input=input_data
        )
        
        # Download and save the image
        print(f"Image URL received, downloading...")
        response = requests.get(output)
        if response.status_code != 200:
            print(f"Error downloading image: Status code {response.status_code}")
            raise ValueError(f"Image download failed with status code {response.status_code}")
            
        save_file(output_image_path, response.content)
        
        print(f"Image generated and saved to {output_image_path}")
        return output_image_path
    except Exception as e:
        print(f"Error during image generation: {str(e)}")
        print("Trying again with simplified prompt...")
        
        # Try again with a simplified prompt
        simplified_prompt = prompt.split('.')[0] if '.' in prompt else prompt[:100]
        simplified_prompt = simplified_prompt + ", high quality, detailed"
        print(f"Using simplified prompt: {simplified_prompt}")
        input_data["prompt"] = simplified_prompt
        
        try:
            print("Making second API call with simplified prompt...")
            output = replicate.run(
                "black-forest-labs/flux-pro",
                input=input_data
            )
            
            # Download and save the image
            print("Second attempt successful, downloading image...")
            response = requests.get(output)
            if response.status_code != 200:
                print(f"Error downloading image (second attempt): Status code {response.status_code}")
                raise ValueError(f"Image download failed on retry with status code {response.status_code}")
                
            save_file(output_image_path, response.content)
            
            print(f"Image generated and saved to {output_image_path}")
            return output_image_path
        except Exception as e2:
            print(f"Second attempt failed: {str(e2)}")
            # No fallback to default image, just raise the exception
            raise ValueError(f"Image generation failed after multiple attempts: {str(e2)}")

# Async version of generate_image
async def generate_image_async(prompt: str, output_image_path: str) -> Optional[str]:
    """Generate an image using Flux AI (async) and save to specified path."""
    print(f"Generating image to {output_image_path} using Flux Image AI with prompt: {prompt[:50]}...")
    
    # Check if prompt is empty or None
    if not prompt or prompt.strip() == "":
        print("Warning: Empty prompt detected. Using a fallback prompt.")
        prompt = "A mysterious atmospheric scene with dramatic lighting and cinematic composition."
    
    # Call Flux Image API with 9:16 aspect ratio dimensions
    input_data = {
        "width": 768,
        "height": 1344,
        "prompt": prompt,
        "output_format": "png",  # Explicitly request PNG format
        "aspect_ratio": "9:16",  # Explicitly set aspect ratio to 9:16
        "safety_tolerance": 6    # Set safety tolerance to maximum (6)
    }
    
    try:
        print(f"Calling Replicate API asynchronously with prompt: {prompt}")
        
        # IMPORTANT: Use the synchronous version instead
        # This is more reliable for handling the Replicate API outputs
        print("Using synchronous version for better reliability")
        return generate_image(prompt, output_image_path)
        
    except Exception as e:
        print(f"Error during image generation: {str(e)}")
        raise ValueError(f"Async image generation failed: {str(e)}")

def extract_last_frame(video_path, output_path):
    """
    Extract the last frame from a video file and save it as an image.
    
    Args:
        video_path (str): Path to the video file
        output_path (str): Path where the extracted frame will be saved
    """
    # Check if the video file exists
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return False
    
    # Open the video file
    cap = cv2.VideoCapture(video_path)
    
    # Check if video opened successfully
    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}")
        return False
    
    # Get total number of frames
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if total_frames == 0:
        print(f"Error: No frames found in the video file {video_path}")
        return False
    
    # Set the position to the last frame
    # Note: Setting to total_frames-1 as frame counting starts from 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
    
    # Read the last frame
    ret, frame = cap.read()
    
    # Check if frame was successfully read
    if not ret:
        print("Error: Could not read the last frame")
        return False
    
    # Save the frame as an image
    cv2.imwrite(output_path, frame)
    print(f"Last frame successfully saved to {output_path}")
    
    # Release video capture object
    cap.release()
    
    return True

# Synchronous version of generate_video
def generate_video(image_path, prompt, output_video_path=None):
    """Generate a video using Kling AI (synchronous)."""
    print(f"Step 3: Generating video using Kling AI...")
    
    # Generate output path if not provided
    if output_video_path is None:
        timestamp = int(time.time())
        output_video_path = f"video/kling_video_{timestamp}.mp4"
    
    # Read video generation settings
    video_settings = read_file("prompts/video_gen.txt")
    
    # Parse video settings
    settings = {}
    for line in video_settings.strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            settings[key.strip()] = value.strip()
    
    # Prepare video generation payload
    # IMPORTANT: Kling API only allows 5 or 10 seconds
    duration = int(settings.get('duration', 10))
    if duration not in [5, 10]:
        print(f"Adjusting duration {duration} to 10 seconds (API only allows 5 or 10)")
        duration = 10
        
    aspect_ratio = settings.get('aspect_ratio', '9:16')
    cfg_scale = float(settings.get('cfg_scale', 0.5))
    negative_prompt = settings.get('negative_prompt', '')
    
    # Ensure prompt isn't too long (limit as in working code)
    if len(prompt) > 100:
        print(f"Shortening long prompt from {len(prompt)} chars to 100 chars")
        prompt = prompt[:100]
    
    print(f"Using video prompt: '{prompt}'")
    
    # Open the image for upload
    try:
        with open(image_path, "rb") as image_file:
            # Call Kling Video API
            input_data = {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "aspect_ratio": aspect_ratio,
                "cfg_scale": cfg_scale,
                "duration": duration,
                "start_image": image_file
            }
            
            try:
                print(f"Attempting to generate video with Kling v1.6-standard")
                output = replicate.run(
                    "kwaivgi/kling-v1.6-standard",  # Use v1.6-standard instead of v1.6
                    input=input_data
                )
                
                # Download and save the video
                response = requests.get(output)
                save_file(output_video_path, response.content)
                
                print(f"Video generated and saved to {output_video_path}")
                return output_video_path
            except Exception as e:
                print(f"Error with Kling v1.6-standard: {str(e)}")
                raise ValueError(f"Video generation failed: {str(e)}")
    except Exception as e:
        print(f"Video generation failed: {str(e)}")
        raise ValueError(f"Video generation failed: {str(e)}")

# Asynchronous version of generate_video
async def generate_video_async(image_path, prompt, output_video_path=None):
    """Generate a video using Kling AI (asynchronous)."""
    print(f"Step 3: Generating video using Kling AI... (async)")
    
    # Generate output path if not provided
    if output_video_path is None:
        timestamp = int(time.time())
        output_video_path = f"video/kling_video_{timestamp}.mp4"
    
    # Read video generation settings
    video_settings = read_file("prompts/video_gen.txt")
    
    # Parse video settings
    settings = {}
    for line in video_settings.strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            settings[key.strip()] = value.strip()
    
    # Prepare video generation payload
    # IMPORTANT: Kling API only allows 5 or 10 seconds
    duration = int(settings.get('duration', 10))
    if duration not in [5, 10]:
        print(f"Adjusting duration {duration} to 10 seconds (API only allows 5 or 10)")
        duration = 10
        
    aspect_ratio = settings.get('aspect_ratio', '9:16')
    cfg_scale = float(settings.get('cfg_scale', 0.5))
    negative_prompt = settings.get('negative_prompt', '')
    
    # Ensure prompt isn't too long (limit as in working code)
    if len(prompt) > 100:
        print(f"Shortening long prompt from {len(prompt)} chars to 100 chars")
        prompt = prompt[:100]
    
    print(f"Using video prompt: '{prompt}'")
    
    # Open the image for upload
    try:
        with open(image_path, "rb") as image_file:
            # Call Kling Video API
            input_data = {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "aspect_ratio": aspect_ratio,
                "cfg_scale": cfg_scale,
                "duration": duration,
                "start_image": image_file
            }
            
            try:
                # Using a synchronous call in an async function - this can be improved later
                print(f"Attempting to generate video with Kling v1.6-standard (async)")
                output = await asyncio.to_thread(
                    replicate.run,
                    "kwaivgi/kling-v1.6-standard",  # Use v1.6-standard instead of v1.6
                    input=input_data
                )
                
                # Download and save the video
                response = await asyncio.to_thread(requests.get, output)
                save_file(output_video_path, response.content)
                
                print(f"Video generated and saved to {output_video_path}")
                return output_video_path
            except Exception as e:
                print(f"Error with Kling v1.6-standard: {str(e)}")
                raise ValueError(f"Video generation failed: {str(e)}")
    except Exception as e:
        print(f"Video generation failed: {str(e)}")
        raise ValueError(f"Video generation failed: {str(e)}")

def generate_music(idea_or_prompt: str, output_music_path=None, tags=None, instrumental=True):
    """Generate music using Sonauto."""
    print(f"Step 4: Generating music using Sonauto with prompt: {idea_or_prompt[:50]}...")
    
    # Generate output path if not provided
    if output_music_path is None:
        timestamp = int(time.time())
        output_music_path = f"music/sonauto_music_{timestamp}.mp3"
    
    # Read music generation settings
    music_settings_text = read_file("prompts/music_gen.txt")
    
    # Set default values
    prompt_strength = 2.3
    
    # Extract prompt_strength if present in the settings
    if "prompt_strength" in music_settings_text:
        try:
            prompt_strength_line = [line for line in music_settings_text.split('\n') if "prompt_strength" in line][0]
            prompt_strength_str = prompt_strength_line.split(':', 1)[1].strip()
            prompt_strength_str = prompt_strength_str.split('(default:', 1)[1].split(')', 1)[0].strip() if '(default:' in prompt_strength_str else prompt_strength_str
            prompt_strength = float(prompt_strength_str)
        except:
            prompt_strength = 2.3
    
    # Use provided tags or default ones
    if tags is None:
        tags = ["ethereal", "chants", "folklore", "ancient", "spiritual", "ambient", "ritualistic"]
    
    # Prepare the request payload
    payload = {
        "prompt": idea_or_prompt,
        "tags": tags,
        "instrumental": instrumental,
        "prompt_strength": prompt_strength,
        "output_format": "mp3"
    }
    
    # Call Sonauto API
    headers = {
        "Authorization": f"Bearer {SONAUTO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Step 1: Start generation
    response = requests.post(
        "https://api.sonauto.ai/v1/generations",
        json=payload,
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"Error generating music: {response.text}")
        return None
    
    task_id = response.json()["task_id"]
    print(f"Music generation started with task ID: {task_id}")
    
    # Step 2: Wait for generation to complete
    status = ""
    while status != "SUCCESS":
        time.sleep(5)  # Wait 5 seconds between checks
        
        status_response = requests.get(
            f"https://api.sonauto.ai/v1/generations/status/{task_id}",
            headers=headers
        )
        
        if status_response.status_code != 200:
            print(f"Error checking music generation status: {status_response.text}")
            return None
        
        status = status_response.text.strip('"')
        print(f"Music generation status: {status}")
        
        if status == "FAILURE":
            print("Music generation failed")
            return None
        
        if status == "SUCCESS":
            # Get the generated music URL
            result_response = requests.get(
                f"https://api.sonauto.ai/v1/generations/{task_id}",
                headers=headers
            )
            
            if result_response.status_code != 200:
                print(f"Error getting music URL: {result_response.text}")
                return None
            
            song_url = result_response.json()["song_paths"][0]
            
            # Download the music file
            music_response = requests.get(song_url)
            save_file(output_music_path, music_response.content)
            
            print(f"Music generated and saved to {output_music_path}")
            break
    
    # Return the path only if generation was successful
    if status == "SUCCESS":
        return output_music_path
    else:
        return None

def generate_voice_dialog(idea: str, output_voice_path=None):
    """Generate a short dialog using OpenAI TTS and save to specified path."""
    print(f"Generating voice dialog for idea: {idea[:50]}...")
    
    # Generate output path if not provided
    if output_voice_path is None:
        timestamp = int(time.time())
        output_voice_path = f"voice/openai_voice_{timestamp}.mp3"
    
    # Read voice examples to use as references
    voice_examples = read_file("prompts/voice_examples.txt")
    
    # Check if the input is a direct narration text (shorter string) or an idea (longer string for generating dialog)
    is_direct_narration = len(idea) < 100 and ("join" in idea.lower() or "welcome" in idea.lower() or "September" in idea)
    
    if is_direct_narration:
        # Direct use of narration text
        dialog = idea
        print(f"Using provided narration text directly: '{dialog}'")
        
        # Create prompt for generating only voice instructions
        voice_prompt = f"""
        I need voice instructions for this promotional narration:
        
        "{dialog}"
        
        The narration will use this EXACT text. Just determine:
        1. If this should be spoken by a male voice (Ballad) or female voice (Shimmer)
        2. Provide detailed voice instructions for delivering this promotional line

        Here are some examples of good voice instructions:
        {voice_examples}
        
        Your response MUST follow this exact format:
        Voice: [Ballad or Shimmer]
        Instructions: [detailed speaking instructions including tone, emotion, pacing, emphasis, etc.]
        """
    else:
        # Original behavior for generating dialog from idea
        dialog_prompt = f"""
        Create a short, engaging single line of dialog question (maximum 15 words) for the following idea:

        Idea: 
        \n\n
        {idea}
        \n\n
        This short dialog question should be something a character might say when experiencing this scene.
        It should be brief, impactful, like the examples:
         "I wonder what happened here...?", "What could be over there...?", "I wonder where Queen Cleopatra is buried...?" or "What is that sound...?"

        In the dialog question, avoid cringe cliche terms like "secrets", "unveil", "moon", "breath etc. Please be creative and inspired by the idea.
        
        Also determine whether this dialog questions would best be spoken by a male voice (Ballad) or female voice (Shimmer) based on the archetype of the idea.
        
        IMPORTANT: You MUST provide detailed voice instructions that describe how the line should be delivered.
        
        Here are some examples of good voice instructions:

        {voice_examples}

        Create detailed voice instructions similar to these examples that fit the idea and the dialog.

        Your response MUST follow this exact format:
        Voice: [Ballad or Shimmer] (based on the archetype of the idea)
        Dialog: [the dialog question]
        Instructions: [detailed speaking instructions including tone, emotion, pacing, emphasis, etc.]
        """
        voice_prompt = dialog_prompt
    
    # Call OpenAI API
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": voice_prompt
            }
        ]
    )
    
    result = response.choices[0].message.content
    print(f"Raw result from GPT:\n{result}")  # Debug line
    
    # Parse the result with more robust handling
    voice = "onyx"  # Default male voice
    instructions = "Speak naturally with appropriate emotion."
    
    # For direct narration, we already have the dialog text
    if not is_direct_narration:
        dialog = ""
    
    # Extract values from the response with more robust handling
    lines = result.split('\n')
    for i, line in enumerate(lines):
        if line.lower().startswith("voice:"):
            voice_value = line.replace("Voice:", "", 1).strip().lower()
            # Only accept onyx or shimmer
            if "shimmer" in voice_value:
                voice = "shimmer"
                
        elif line.lower().startswith("dialog:") and not is_direct_narration:
            dialog = line.replace("Dialog:", "", 1).strip()
            # Remove extra quotes if present
            if dialog.startswith('"') and dialog.endswith('"'):
                dialog = dialog[1:-1]
                
        elif line.lower().startswith("instructions:"):
            # Grab the instructions part, which might span multiple lines
            instructions_parts = [line.replace("Instructions:", "", 1).strip()]
            
            # Check if there are more lines after "Instructions:" that are part of the instructions
            for j in range(i+1, len(lines)):
                next_line = lines[j].strip()
                # Stop if we hit a new section
                if next_line.lower().startswith("voice:") or next_line.lower().startswith("dialog:"):
                    break
                if next_line:  # Only add non-empty lines
                    instructions_parts.append(next_line)
                    
            instructions = " ".join(instructions_parts).strip()
    
    # Fallback if instructions are still empty
    if not instructions or instructions.strip() == "":
        print("Warning: No instructions detected. Using fallback instructions.")
        instructions = "Speak with emotion and emphasis appropriate to the scene, maintaining a natural cadence and clear articulation."
    
    print(f"Generated dialog: '{dialog}' with voice '{voice}'")
    print(f"Voice instructions: {instructions}")
    
    # Generate the speech using OpenAI TTS
    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=dialog,
        instructions=instructions
    )
    
    # Save the audio file
    try:
        response.stream_to_file(output_voice_path)
        print(f"Voice dialog generated and saved to {output_voice_path}")
        # Return both the path and other info (useful for server logging)
        return {
            "filename": output_voice_path, 
            "dialog": dialog, 
            "voice": voice, 
            "instructions": instructions
        }
    except Exception as e:
        print(f"Error saving generated voice file to {output_voice_path}: {e}")
        return None

def merge_videos(video_paths: List[str], music_path: Optional[str], voice_path: Optional[str] = None, output_file_path: Optional[str] = None) -> Optional[str]:
    """Merge videos with music and voice using FFMPEG."""
    print(f"Creating final video by merging {len(video_paths)} videos...")
    
    # Generate output path if not provided
    if output_file_path is None:
        timestamp = int(time.time())
        output_file_path = f"final_output_{timestamp}.mp4"
    
    # Create a temporary file for concatenation
    temp_list_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_list.txt")
    concat_output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_concat.mp4")
    
    with open(temp_list_path, "w") as f:
        for video_path in video_paths:
            # Ensure paths in the list file are correctly quoted for ffmpeg
            f.write(f"file '{os.path.abspath(video_path)}'\n")

    # First concatenate the videos
    concat_cmd = f'ffmpeg -y -f concat -safe 0 -i "{temp_list_path}" -c copy "{concat_output_path}"'

    print(f"Running video concatenation command: {concat_cmd}")
    concat_result = os.system(concat_cmd)
    
    if concat_result != 0:
        print(f"Error concatenating videos. Exit code: {concat_result}")
        return None
    
    # Now add music and optionally voice to the concatenated video
    # Check if voice_path is a dict or string
    voice_file_path = None
    if isinstance(voice_path, dict) and "filename" in voice_path:
        voice_file_path = voice_path["filename"]
    elif isinstance(voice_path, str):
        voice_file_path = voice_path
    
    # Prepare ffmpeg command based on available inputs
    if voice_file_path and os.path.exists(voice_file_path):
        # Add both music and voice
        ffmpeg_cmd = (
            f'ffmpeg -y -i "{concat_output_path}" -i "{music_path}" -i "{voice_file_path}" '
            f'-filter_complex "[1:a]volume=0.4[music];[2:a]adelay=1000|1000,volume=1.5[voice];[music][voice]amix=inputs=2:duration=longest[a]" '
            f'-map 0:v -map "[a]" -shortest -t 50 -c:v libx264 -c:a aac -b:a 192k "{output_file_path}"'
        )
    elif music_path and os.path.exists(music_path):
        # Just add music without voice
        ffmpeg_cmd = f'ffmpeg -y -i "{concat_output_path}" -i "{music_path}" -map 0:v -map 1:a -shortest -t 50 -c:v libx264 -c:a aac -b:a 192k "{output_file_path}"'
    else:
        # Just use the video with no audio
        ffmpeg_cmd = f'ffmpeg -y -i "{concat_output_path}" -c:v libx264 -c:a aac -t 50 "{output_file_path}"'
    
    # Print the command for debugging
    print(f"Running FFMPEG command: {ffmpeg_cmd}")
    
    # Execute FFMPEG command
    result = os.system(ffmpeg_cmd)
    
    # Clean up temporary files
    try:
        os.remove(temp_list_path)
        os.remove(concat_output_path)
    except:
        pass
    
    if result == 0:
        print(f"Final video created successfully: {output_file_path}")
        return output_file_path
    else:
        print(f"Error creating final video. Exit code: {result}")
        return None

def main():
    """Main function to run the full content generation pipeline."""
    try:
        # Ensure directories exist
        ensure_directories()
        print("Starting content generation pipeline...")
        
        # Generate an idea
        result = generate_idea()
        idea, prompt = result["idea"], result["prompt"]
        print(f"Generated idea: {idea}")
        print(f"Image prompt: {prompt}")
        
        # Generate an image using the prompt
        timestamp = int(time.time())
        image_path = generate_image(prompt, f"image/flux_image_{timestamp}.png")
        print(f"Generated image: {image_path}")
        
        # Generate a video from the image
        video_prompt = prompt
        video_path = generate_video(image_path, video_prompt)
        print(f"Generated video: {video_path}")
        
        # Extract last frame from the video
        second_image_path = f"image/last_frame_video1_{int(time.time())}.png"
        extract_last_frame(video_path, second_image_path)
        print(f"Extracted last frame: {second_image_path}")
        
        # Generate second video
        second_video_path = generate_video(second_image_path, video_prompt)
        print(f"Generated second video: {second_video_path}")
        
        # Generate music
        music_prompt = idea
        music_path = generate_music(music_prompt)
        print(f"Generated music: {music_path}")
        
        # Merge the videos with music
        final_video = merge_videos([video_path, second_video_path], music_path, None)
        
        print("\nContent Generation Pipeline Complete!")
        print(f"Generated Idea: {idea}")
        print(f"Generated Prompt: {prompt}")
        print(f"Generated Image: {image_path}")
        print(f"Extracted Image: {second_image_path}")
        print(f"Generated Videos: {video_path}, {second_video_path}")
        print(f"Generated Music: {music_path}")
        print(f"Final Output: {final_video}")
        
    except Exception as e:
        print(f"Error in content generation pipeline: {str(e)}")
        import traceback
        traceback.print_exc()
        print("Process failed. Please try running the script again.")

# Optional alternative main function for generating chain of videos
def main_chain():
    """Advanced main function to run content generation pipeline with video chaining."""
    try:
        # Ensure directories exist
        ensure_directories()
        print("Starting advanced content generation pipeline with video chaining...")
        
        # Step 1: Generate idea
        result = generate_idea()
        idea, prompt = result["idea"], result["prompt"]
        
        # Step 2: Generate the initial image
        first_image_path = generate_image(prompt)
        
        # Step 3: Generate voice dialog based on the idea
        voice_data = generate_voice_dialog(idea)
        
        # Step 4: Generate chain of videos, each using the last frame of the previous one
        print("Generating chain of connected videos...")
        
        video_count = 5  # Number of videos in the chain
        video_paths = []
        current_image_path = first_image_path
        
        for i in range(video_count):
            print(f"Generating video {i+1}/{video_count}...")
            
            # Generate video
            video_path = generate_video(current_image_path, prompt)
            video_paths.append(video_path)
            
            # Extract last frame for next video (except for the last one)
            if i < video_count - 1:
                next_image_path = f"image/last_frame_video{i+1}_{int(time.time())}.png"
                extract_last_frame(video_path, next_image_path)
                current_image_path = next_image_path
        
        # Step 5: Generate music using the idea
        music_path = generate_music(idea)
        
        # Step 6: Merge all videos with music and voice
        final_video = merge_videos(video_paths, music_path, voice_data)
        
        print("\nAdvanced Content Generation Pipeline Complete!")
        print(f"Generated Idea: {idea}")
        print(f"Generated Prompt: {prompt}")
        print(f"Generated Images: {first_image_path} and extracted frames")
        print(f"Generated Videos: {', '.join(video_paths)}")
        print(f"Generated Music: {music_path}")
        if voice_data:
            print(f"Generated Voice: {voice_data['filename']}")
            print(f"Voice Dialog: {voice_data['dialog']} (Voice: {voice_data['voice']})")
        print(f"Final Output: {final_video}")
        
    except Exception as e:
        print(f"Error in content generation pipeline: {str(e)}")
        import traceback
        traceback.print_exc()
        print("Process failed. Please try running the script again.")

if __name__ == "__main__":
    main()  # Use standard pipeline by default
    # To use the chained video generation, comment out main() and uncomment the next line
    # main_chain()