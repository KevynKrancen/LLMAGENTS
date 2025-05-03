import os
import sys
import json
import re
import time
from mcp.server.fastmcp import FastMCP
import logging
from typing import Dict, List, Optional, Any
# from smolagents import LiteLLMModel # Removed unused import
from pydantic import Field
# import litellm # Removed
# from openai import OpenAI # Removed

# Import the video generation functionality
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from video_gen import (
    generate_idea,
    generate_image as vg_generate_image,
    generate_image_async as vg_generate_image_async,
    generate_video as vg_generate_video,
    generate_video_async as vg_generate_video_async,
    generate_voice_dialog,
    generate_music,
    merge_videos,
    extract_last_frame,
    ensure_directories
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GPT_MODEL = "gpt-4o-mini" # Removed
# openai_client = OpenAI() # Removed

# Initialize FastMCP server
mcp = FastMCP("video_generator_server")

# Remove explicit path defs and mkdirs - user's video_gen.py handles this
# with relative paths based on CWD set by os.chdir below.

class PromptManager:
    """Manages the prompt files and processes video requests using an LLM."""
    
    # Use absolute paths for prompt files now
    # Define prompt paths relative to the script's location
    PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
    IDEA_FILE = os.path.join(PROMPT_DIR, "idea_gen.txt")
    VIDEO_FILE = os.path.join(PROMPT_DIR, "video_gen.txt")
    MUSIC_FILE = os.path.join(PROMPT_DIR, "music_gen.txt")
    
    # Default values
    DEFAULT_DURATION = 10
    ALLOWED_DURATIONS = [10, 20, 30]  # These are target durations, actual API calls use 10-second segments
    
    @classmethod
    def _read_prompt_file(cls, file_path: str) -> str:
        """Internal helper to read a prompt file."""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Prompt file not found: {file_path}. Returning empty string.")
                # Optionally create default content here if needed
                return ""
            with open(file_path, 'r') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Error reading prompt file {file_path}: {str(e)}")
            return ""
    
    @classmethod
    def _write_prompt_file(cls, file_path: str, content: str) -> bool:
        """Internal helper to write content to a prompt file."""
        try:
            with open(file_path, 'w') as file:
                file.write(content)
            return True
        except Exception as e:
            logger.error(f"Error writing to prompt file {file_path}: {str(e)}")
            return False
    
    @classmethod
    def _update_video_prompt_content(cls, settings: Dict[str, Any]) -> bool:
        """Update the video generation prompt file content."""
        try:
            content = cls._read_prompt_file(cls.VIDEO_FILE)
            lines = content.strip().split('\n')
            updated_settings = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    updated_settings[key.strip()] = value.strip()
            
            # Update with new settings, ensuring duration is handled
            for key, value in settings.items():
                updated_settings[key] = value
            if 'duration' in updated_settings:
                try:
                    duration = int(updated_settings['duration'])
                    closest_duration = min(cls.ALLOWED_DURATIONS, key=lambda x: abs(x - duration))
                    updated_settings['duration'] = str(closest_duration)
                except:
                    updated_settings['duration'] = str(cls.DEFAULT_DURATION)
            
            new_content = "\n".join([f"{key}: {value}" for key, value in updated_settings.items()]) + "\n"
            return cls._write_prompt_file(cls.VIDEO_FILE, new_content)
            
        except Exception as e:
            logger.error(f"Error updating video prompt content: {str(e)}")
            return False
    
    @classmethod
    def _update_music_prompt_content(cls, settings: Dict[str, Any]) -> bool:
        """Update the music generation prompt file content."""
        try:
            content = cls._read_prompt_file(cls.MUSIC_FILE)
            lines = content.strip().split('\n')
            updated_settings = {}
            for line in lines:
                line = line.strip()
                if '"' in line and ':' in line:
                    match = re.search(r'"(.*?)"\s*:\s*"?(.*?)"?,?$', line)
                    if match:
                        key, value = match.groups()
                        if value.lower() == 'true': updated_settings[key] = True
                        elif value.lower() == 'false': updated_settings[key] = False
                        else: updated_settings[key] = value # Keep as string
            
            for key, value in settings.items():
                updated_settings[key] = value
            
            items = []
            for key, value in updated_settings.items():
                if isinstance(value, bool):
                    items.append(f'  "{key}": {str(value).lower()},') # JSON boolean
                elif isinstance(value, (int, float)):
                     items.append(f'  "{key}": "{value}",') # Keep numeric as string based on original format
                else:
                    # Ensure strings are properly quoted and escaped if necessary
                    # Use json.dumps to handle string escaping correctly for JSON format
                    items.append(f'  "{key}": {json.dumps(str(value))},')
            
            # Remove trailing comma from the last item if present
            if items and items[-1].endswith(','):
                 items[-1] = items[-1][:-1]

            new_content = "{\n" + "\n".join(items) + "\n}" # Format as JSON object
            return cls._write_prompt_file(cls.MUSIC_FILE, new_content)
            
        except Exception as e:
            logger.error(f"Error updating music prompt content: {str(e)}")
            return False
    
    @classmethod
    def _extract_parameters_simple(cls, request: str) -> Dict[str, Any]:
        """Extracts parameters using simple regex and keyword matching (No LLM)."""
        logger.info(f"Attempting simple parameter extraction from request: {request}")
        parameters = cls._get_default_params(request) # Start with defaults

        # 1. Extract Duration (10, 20, 30)
        duration_match = re.search(r'\b(10|20|30)\s*(?:seconds?|sec)\b', request, re.IGNORECASE)
        if not duration_match: # Try just the number
            duration_match = re.search(r'\b(10|20|30)\b', request)

        if duration_match:
            try:
                parameters["duration"] = int(duration_match.group(1))
                logger.info(f"Extracted duration: {parameters['duration']}")
            except ValueError:
                 logger.warning(f"Found duration-like text '{duration_match.group(1)}' but failed to parse as int. Using default.")
                 parameters["duration"] = cls.DEFAULT_DURATION # Fallback
        else:
            logger.info("No explicit duration found, using default.")
            parameters["duration"] = cls.DEFAULT_DURATION # Default if not found

        # 2. Extract Style Keywords (simple examples)
        style_keywords = ['cinematic', 'cartoon', 'realistic', 'futuristic', 'anime', 'documentary', 'vintage']
        style_found = None
        for keyword in style_keywords:
            if re.search(r'\b' + keyword + r'\b', request, re.IGNORECASE):
                style_found = keyword
                logger.info(f"Extracted style keyword: {style_found}")
                break # Take the first one found
        if style_found:
             parameters["style"] = style_found
        else:
             logger.info("No specific style keyword found, using default.")
             # Keep default style from _get_default_params if nothing found

        # 3. Extract Music Type Keywords (simple examples)
        music_keywords = ['electronic', 'piano', 'orchestral', 'upbeat', 'calm', 'rock', 'jazz', 'ambient', 'epic']
        music_found = None
        for keyword in music_keywords:
             if re.search(r'\b' + keyword + r'(?:\s+music)?\b', request, re.IGNORECASE):
                 music_found = keyword
                 logger.info(f"Extracted music keyword: {music_found}")
                 break # Take the first one found
        if music_found:
              parameters["music_type"] = music_found
        else:
             logger.info("No specific music keyword found, using default.")
             # Keep default music_type from _get_default_params

        # 4. Extract Narration (basic: look for quoted text)
        narration_match = re.search(r'["\'](.+?)["\']', request)
        if narration_match:
            parameters["narration"] = narration_match.group(1).strip()
            logger.info(f"Extracted potential narration from quotes: {parameters['narration']}")
        else:
            logger.info("No quoted text found for narration, using default.")
             # Keep default narration from _get_default_params

        # Theme and Mood are harder with simple regex, rely on defaults initialized earlier
        # The theme defaults to the full request, which is reasonable
        logger.info(f"Final parameters after simple extraction: {parameters}")
        return parameters

    @classmethod
    def _get_default_params(cls, request: str) -> Dict[str, Any]:
        """Provides a default parameter structure based on the request."""
        logger.warning(f"Using default parameters based on request: {request}")
        return {
            "theme": request, # Use the raw request as theme if nothing else
            "style": "cinematic, professional",
            "music_type": "upbeat background music",
            "duration": cls.DEFAULT_DURATION,
            "narration": f"An engaging look at {request}. Discover more now!",
            "mood": "professional, informative"
        }

    @classmethod
    def _verify_and_fill_parameters(cls, parameters: Dict[str, Any], original_request: str) -> Dict[str, Any]:
        """Checks for missing parameters and fills them using defaults or LLM inference (optional)."""
        required_keys = ["theme", "style", "music_type", "duration", "narration", "mood"]
        missing_keys = [key for key in required_keys if key not in parameters or not parameters[key]]
        
        if not missing_keys:
            logger.info("All required parameters present.")
            # Final duration check even if all keys present
            parameters["duration"] = cls._validate_duration(parameters.get("duration"))
            return parameters

        logger.warning(f"Missing or empty parameters detected: {missing_keys}. Filling defaults.")
        defaults = cls._get_default_params(original_request)
        
        for key in missing_keys:
            parameters[key] = defaults[key]
            logger.info(f"Filled missing/empty parameter '{key}': '{parameters[key]}'")
        
        # Final duration check after filling defaults
        parameters["duration"] = cls._validate_duration(parameters.get("duration"))
        logger.info(f"Parameters after verification and filling: {parameters}")
        return parameters
    
    @classmethod
    def _validate_duration(cls, duration_value: Any) -> int:
        """Validates the duration parameter, returning a valid value (10, 20, or 30)."""
        try:
            duration = int(duration_value)
            # Use class-defined allowed durations
            if duration in cls.ALLOWED_DURATIONS:
                return duration
            else:
                # Find the closest allowed duration
                closest_duration = min(cls.ALLOWED_DURATIONS, key=lambda x: abs(x - duration))
                logger.warning(f"Invalid duration {duration}. Using closest allowed value: {closest_duration}")
                return closest_duration
        except (ValueError, TypeError): 
            logger.warning(f"Invalid or missing duration value '{duration_value}'. Using default: {cls.DEFAULT_DURATION}")
            return cls.DEFAULT_DURATION

    @classmethod
    def process_request_and_update_prompts(cls, request: str) -> Dict[str, Any]:
        """Main method: Extracts, verifies, fills parameters, updates prompt files, and returns final parameters."""
        # 1. Extract parameters using simple keyword/regex matching
        extracted_params = cls._extract_parameters_simple(request)
        
        # 2. Verify and fill any missing parameters
        final_params = cls._verify_and_fill_parameters(extracted_params, request)
        
        # 3. Update prompt files based on final parameters
        video_settings = {
            "prompt": f"{final_params.get('theme', 'video topic')}, {final_params.get('style', 'cinematic style')}",
            "negative_prompt": "blurry, deformed, text, words, low quality, noisy, watermark",
            "aspect_ratio": "9:16",
            "cfg_scale": "0.5",
            "duration": str(final_params.get("duration", cls.DEFAULT_DURATION)) # Use validated duration
        }
        if cls._update_video_prompt_content(video_settings):
             logger.info("Successfully updated video prompt file.")
        else:
             logger.error("Failed to update video prompt file.")

        music_settings = {
            "prompt": f"{final_params.get('music_type', 'background music')}, {final_params.get('mood', 'neutral mood')}",
            "instrumental": True,
            "prompt_strength": "2.3"
        }
        if cls._update_music_prompt_content(music_settings):
            logger.info("Successfully updated music prompt file.")
        else:
            logger.error("Failed to update music prompt file.")
            
        # Return the final, complete parameters used for generation
        return final_params

@mcp.tool()
async def create_custom_video(
    request: str = Field(..., description="Detailed natural language description of the video you want to generate. E.g., 'Make a 20 second video about a futuristic programming school for kids with rock background music saying Join us!'. The system will extract details like duration, style, narration text, and music type."),
) -> Dict[str, Any]:
    """Processes a natural language request, extracts all parameters, and generates a customized video."""
    try:
        logger.info(f"Received video generation request: '{request}'")
        start_time = time.time()

        # Ensure directories exist
        ensure_directories()

        # ----- Enhanced Request Parsing -----
        # Extract duration (if specified)
        duration_match = re.search(r'(\d+)\s*(?:second|sec)', request, re.IGNORECASE)
        custom_duration = None
        if duration_match:
            custom_duration = int(duration_match.group(1))
            logger.info(f"Extracted custom duration: {custom_duration} seconds")
        
        # Extract narration text (text in quotes or after "saying")
        narration_text = None
        narration_match = re.search(r'saying\s+["\']?([^"\'!?.]+)[!?.]?["\']?', request, re.IGNORECASE)
        if not narration_match:
            narration_match = re.search(r'["\']([^"\']+)["\']', request)
        if narration_match:
            narration_text = narration_match.group(1).strip()
            logger.info(f"Extracted narration text: '{narration_text}'")
        
        # Extract music style (before "music" or "background")
        music_style = None
        music_match = re.search(r'(\w+)\s+(?:music|background)', request, re.IGNORECASE)
        if music_match:
            music_style = music_match.group(1).strip()
            logger.info(f"Extracted music style: {music_style}")

        # Process the request using the PromptManager to get final params and update files
        logger.info("Processing request and updating prompts using PromptManager...")
        final_params = PromptManager.process_request_and_update_prompts(request)
        
        # Preserve the user's raw creative input
        user_theme = final_params.get('theme', request)
        logger.info(f"Using user theme directly: {user_theme}")
        
        # Override with extracted values if found
        if custom_duration:
            final_params["duration"] = custom_duration
            # Update the video prompt file with the base duration (always 10 seconds per segment)
            video_settings = {
                "duration": "10"  # Always use 10 for API calls
            }
            PromptManager._update_video_prompt_content(video_settings)
            
        if narration_text:
            final_params["narration"] = narration_text
            
        if music_style:
            final_params["music_type"] = f"{music_style} music"
            # Update the music prompt file with the custom style
            music_settings = {
                "prompt": f"{music_style} music, {user_theme}"
            }
            PromptManager._update_music_prompt_content(music_settings)
            
        # Generate idea directly using user's abstract input as theme
        logger.info(f"Generating idea based on user theme: {user_theme}")
        idea_result = generate_idea(theme=user_theme)
        idea, image_prompt = idea_result["idea"], idea_result["prompt"]
        logger.info(f"Generated idea: {idea}")
        
        # Preserve aspects of user's original request in the image prompt
        enhanced_prompt = f"{image_prompt} {user_theme}"
        logger.info(f"Enhanced image prompt with user input: {enhanced_prompt}")
        
        # Update video prompt to include user's creative input
        video_prompt_update = {
            "prompt": f"{user_theme}, {image_prompt}"
        }
        PromptManager._update_video_prompt_content(video_prompt_update)
        logger.info("Updated video prompt with user's creative input")

        # Generate initial image
        logger.info("Generating initial image...")
        image_filename = f"image/flux_image_{int(time.time())}.png"
        
        # Try multiple times to generate an image with Replicate API
        image_generation_attempts = 0
        max_attempts = 3
        image_path = None
        
        while image_generation_attempts < max_attempts and not image_path:
            image_generation_attempts += 1
            logger.info(f"Image generation attempt {image_generation_attempts}/{max_attempts}")
            
            try:
                # First try async generation
                image_path = await vg_generate_image_async(enhanced_prompt, image_filename)
                if image_path and os.path.exists(image_path):
                    logger.info(f"Successfully generated image on attempt {image_generation_attempts}: {image_path}")
                    break
            except Exception as e:
                logger.warning(f"Async image generation failed on attempt {image_generation_attempts}: {e}")
                
                # Try sync generation as fallback
                try:
                    logger.info("Trying synchronous image generation...")
                    image_path = vg_generate_image(enhanced_prompt, image_filename)
                    if image_path and os.path.exists(image_path):
                        logger.info(f"Successfully generated image with sync method: {image_path}")
                        break
                except Exception as sync_e:
                    logger.warning(f"Sync image generation also failed: {sync_e}")
            
            # If we get here, both methods failed
            if image_generation_attempts < max_attempts:
                logger.info(f"Retrying with simplified prompt...")
                # Try with a simpler prompt but keep user themes
                simpler_prompt = f"{user_theme}, high quality, detailed"
                enhanced_prompt = simpler_prompt
        
        if not image_path or not os.path.exists(image_path):
            logger.error("All image generation attempts failed")
            return {
                "status": "error", 
                "error": "Failed to generate an image after multiple attempts. Please try again with a different description."
            }
        
        logger.info(f"Image ready at: {image_path}")
        
        # Generate voice dialog with the custom narration
        logger.info("Generating voice dialog...")
        voice_filename = f"voice/openai_voice_{int(time.time())}.mp3"
        voice_text = final_params["narration"] 
        # Better narration text extraction
        if narration_text:
            voice_text = narration_text
            
        logger.info(f"Using voice narration text: '{voice_text}'")
        voice_data = generate_voice_dialog(voice_text, voice_filename)
        if voice_data:
            logger.info(f"Generated voice dialog: {voice_data['filename']}")
        else:
            logger.warning("Voice dialog generation failed or did not return a valid path.")

        # Calculate how many video segments we need based on duration
        # Each segment is 10 seconds, so a 30 second video needs 3 segments
        total_segments = max(1, round(final_params["duration"] / 10))
        logger.info(f"Generating {total_segments} video segments to create a {final_params['duration']} second video")
        
        # Create a simplified video prompt that the API can handle
        simple_video_prompt = f"futuristic, {user_theme.split(',')[0]}"
        # Ensure the prompt isn't too long
        if len(simple_video_prompt) > 100:
            simple_video_prompt = simple_video_prompt[:100]
        
        logger.info(f"Using simplified video prompt: {simple_video_prompt}")
        
        # Generate chain of videos
        video_paths = []
        current_image_path = image_path
        
        for i in range(total_segments):
            logger.info(f"Generating video segment {i+1}/{total_segments}...")
            video_filename = f"video/kling_video_{i+1}_{int(time.time())}.mp4"
            
            try:
                # Generate video from current image
                video_path = vg_generate_video(current_image_path, simple_video_prompt, video_filename)
                if not video_path or not os.path.exists(video_path):
                    logger.error(f"Failed to generate video segment {i+1}.")
                    return {
                        "status": "error", 
                        "error": f"Failed to generate video segment {i+1}. Please try again."
                    }
                
                logger.info(f"Generated video segment {i+1}: {video_path}")
                video_paths.append(video_path)
                
                # If not the last segment, extract last frame for next video
                if i < total_segments - 1:
                    next_image_path = f"image/last_frame_video{i+1}_{int(time.time())}.png"
                    if extract_last_frame(video_path, next_image_path):
                        current_image_path = next_image_path
                        logger.info(f"Extracted last frame for next video: {next_image_path}")
                    else:
                        logger.error(f"Failed to extract last frame from video {i+1}.")
                        # Continue with the original image if extraction fails
                        current_image_path = image_path
            except Exception as e:
                logger.error(f"Error generating video segment {i+1}: {e}")
                # Continue with remaining segments if one fails
                if not video_paths:
                    return {
                        "status": "error", 
                        "error": f"Failed to generate any video segments. Error: {str(e)}"
                    }
                break

        # Generate music with custom style and user theme
        logger.info("Generating music...")
        music_filename = f"music/sonauto_music_{int(time.time())}.mp3"
        # Combine music style with user theme for better context
        music_prompt = f"{final_params.get('music_type', 'background music')}, {user_theme}"
        if music_style:
            music_prompt = f"{music_style} music, {user_theme}"
        
        music_path = generate_music(music_prompt, music_filename)

        if not music_path or not os.path.exists(music_path):
            logger.warning(f"Music generation failed. Proceeding without music.")
            music_path = None
        else:
            logger.info(f"Generated music: {music_path}")

        # Merge all video segments with music and voice
        logger.info(f"Creating final video by merging {len(video_paths)} segments...")
        final_video_path = merge_videos(video_paths, music_path, voice_data, os.path.join(os.getcwd(), f"final_output_{int(time.time())}.mp4"))

        # Check if final video creation was successful
        if not final_video_path or not os.path.exists(final_video_path):
            logger.error("Final video creation failed.")
            return {
                "status": "error", 
                "error": "Failed to create the final video file."
            }

        total_time = time.time() - start_time
        logger.info(f"Video generation completed successfully: {final_video_path} (Total time: {total_time:.2f}s)")
        
        # Build the result
        voice_info = None
        if voice_data and isinstance(voice_data, dict):
            voice_info = {
                "filename": voice_data.get("filename"),
                "dialog": voice_data.get("dialog"),
                "voice": voice_data.get("voice")
            }
        
        result = {
            "status": "success",
            "request": request,
            "final_parameters": final_params,
            "idea": idea,
            "image_prompt": image_prompt,
            "final_video_path": final_video_path,
            "narration_generated": narration_text or final_params["narration"],
            "voice_audio": voice_info,
            "initial_image_path": image_path,
            "video_segments": video_paths,
            "segment_count": len(video_paths),
            "music_path": music_path,
            "duration_seconds": final_params["duration"],
            "total_generation_time_seconds": round(total_time, 2)
        }
        return result
        
    except Exception as e:
        logger.error(f"Error in create_custom_video: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": f"An unexpected error occurred: {str(e)}"
        }

@mcp.tool()
async def create_chain_video(
    request: str = Field(..., description="Detailed natural language description of the video chain you want to generate. The system will create multiple connected videos that transition from one to another."),
    video_count: int = Field(5, description="Number of video segments to generate in the chain (default: 5, max: 10).")
) -> Dict[str, Any]:
    """Processes a request and generates a chain of connected videos where each segment uses the last frame of the previous one."""
    try:
        logger.info(f"Received chain video generation request: '{request}' with {video_count} segments")
        start_time = time.time()

        # Validate video count (limit to reasonable range)
        if video_count < 1:
            video_count = 1
        elif video_count > 10:
            video_count = 10
            
        # Ensure directories exist
        ensure_directories()

        # Process the request using the PromptManager
        logger.info("Processing request and updating prompts...")
        final_params = PromptManager.process_request_and_update_prompts(request)
        logger.info(f"Final parameters determined: {json.dumps(final_params)}")
        
        # Generate idea based on theme
        logger.info(f"Generating idea based on theme: {final_params.get('theme')}")
        idea_result = generate_idea(theme=final_params.get('theme', request))
        idea, image_prompt = idea_result["idea"], idea_result["prompt"]
        logger.info(f"Generated idea: {idea}")
        logger.info(f"Generated image prompt: {image_prompt}")
        
        # Generate initial image
        logger.info("Generating initial image...")
        image_filename = f"image/flux_image_{int(time.time())}.png"
        # Use async image generation
        image_path = await vg_generate_image_async(image_prompt, image_filename)
        logger.info(f"Generated initial image: {image_path}")
        
        # Generate voice dialog
        logger.info("Generating voice dialog...")
        voice_filename = f"voice/openai_voice_{int(time.time())}.mp3"
        voice_data = generate_voice_dialog(final_params["narration"], voice_filename)
        if voice_data:
            logger.info(f"Generated voice dialog: {voice_data['filename']}")
        else:
            logger.warning("Voice dialog generation failed or didn't return valid data.")
        
        # Generate chain of videos
        logger.info(f"Generating chain of {video_count} connected videos...")
        video_paths = []
        current_image_path = image_path
        image_paths = [image_path]  # Track all generated images
        
        for i in range(video_count):
            logger.info(f"Generating video segment {i+1}/{video_count}...")
            video_filename = f"video/kling_video_{i+1}_{int(time.time())}.mp4"
            # Use async video generation
            video_path = await vg_generate_video_async(current_image_path, image_prompt, video_filename)
            
            if not video_path or not os.path.exists(video_path):
                logger.error(f"Failed to generate video segment {i+1}. Stopping chain.")
                break
                
            logger.info(f"Generated video segment {i+1}: {video_path}")
            video_paths.append(video_path)
            
            # Extract last frame for next video (unless this is the last one)
            if i < video_count - 1:
                next_image_path = f"image/last_frame_video{i+1}_{int(time.time())}.png"
                if extract_last_frame(video_path, next_image_path):
                    current_image_path = next_image_path
                    image_paths.append(next_image_path)
                    logger.info(f"Extracted last frame for next video: {next_image_path}")
                else:
                    logger.error(f"Failed to extract last frame from video {i+1}. Stopping chain.")
                    break
        
        # Generate music
        logger.info("Generating music...")
        music_filename = f"music/sonauto_music_{int(time.time())}.mp3"
        music_path = generate_music(idea, music_filename)
        
        if not music_path or not os.path.exists(music_path):
            logger.warning("Music generation failed. Proceeding without music.")
            music_path = None
        else:
            logger.info(f"Generated music: {music_path}")
        
        # Create final video by merging all segments
        if not video_paths:
            logger.error("No video segments were successfully generated.")
            return {"status": "error", "error": "Failed to generate any video segments."}
            
        logger.info(f"Merging {len(video_paths)} video segments...")
        final_video_path = merge_videos(video_paths, music_path, voice_data, os.path.join(os.getcwd(), f"final_output_{int(time.time())}.mp4"))
        
        if not final_video_path or not os.path.exists(final_video_path):
            logger.error("Failed to create final merged video.")
            return {"status": "error", "error": "Failed to merge video segments."}
            
        total_time = time.time() - start_time
        logger.info(f"Chain video generation completed successfully: {final_video_path} (Total time: {total_time:.2f}s)")
        
        # Build the result
        voice_info = None
        if voice_data and isinstance(voice_data, dict):
            voice_info = {
                "filename": voice_data.get("filename"),
                "dialog": voice_data.get("dialog"),
                "voice": voice_data.get("voice")
            }
            
        result = {
            "status": "success",
            "request": request,
            "final_parameters": final_params,
            "idea": idea,
            "image_prompt": image_prompt,
            "final_video_path": final_video_path,
            "narration_generated": final_params["narration"],
            "voice_audio": voice_info,
            "initial_image_path": image_path,
            "image_paths": image_paths,
            "video_segments": video_paths,
            "segments_count": len(video_paths),
            "music_path": music_path,
            "duration_seconds": final_params["duration"] * len(video_paths),
            "total_generation_time_seconds": round(total_time, 2)
        }
        return result
        
    except Exception as e:
        logger.error(f"Error in create_chain_video: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": f"An unexpected error occurred: {str(e)}"
        }

@mcp.tool()
async def get_video_info() -> Dict[str, Any]:
    """Get information about the most recently generated video file (final_output.mp4)."""
    try:
        # Search for the latest final_output_*.mp4 in the CWD (step1/video_gen/)
        output_dir = os.getcwd() # Should be step1/video_gen/ due to os.chdir
        potential_files = [f for f in os.listdir(output_dir) if f.startswith("final_output_") and f.endswith(".mp4")]
        if not potential_files:
             return {"status": "error", "error": f"No final_output_*.mp4 files found in {output_dir}"}
        # Get the latest one based on timestamp in filename or modification time
        latest_file = max(potential_files, key=lambda f: os.path.getmtime(os.path.join(output_dir, f)))
        output_file = os.path.join(output_dir, latest_file)

        if not os.path.exists(output_file):
            return {"status": "error", "error": f"Video file not found: {output_file}"}
        
        stat_info = os.stat(output_file)
        video_info = {
            "status": "success",
            "final_video_path": os.path.abspath(output_file),
            "file_size_mb": round(stat_info.st_size / (1024 * 1024), 2),
            "last_modified_timestamp": stat_info.st_mtime
        }
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ideas_file = os.path.join(script_dir, "last_ideas.json")
        if os.path.exists(ideas_file):
            try:
                with open(ideas_file, "r") as f: video_info["previous_ideas"] = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load previous ideas from {ideas_file}: {e}")
        
        return video_info
        
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}", exc_info=True)
        return {"status": "error", "error": f"Failed to get video info: {str(e)}"}

if __name__ == "__main__":
    logger.info("Starting Video Generation MCP Server")
    # Change to the script's directory to ensure relative paths work
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    logger.info(f"Working directory changed to: {os.getcwd()}")
    
    # Ensure output directories exist
    ensure_directories()
    logger.info("Ensured output directories exist")
    
    mcp.run() # Use default transport (stdio) 