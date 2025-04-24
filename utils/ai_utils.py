import os
import asyncio
import google.generativeai as genai
import logging

_instructions = ""
logger = logging.getLogger(__name__)

def load_instructions():
    global _instructions
    try:
        with open('instructions.txt', 'r', encoding='utf-8') as f:
            _instructions = f.read().strip()
        if not _instructions:
            logger.warning("instructions.txt is empty or contains only whitespace.")
        else:
            logger.info("Instructions loaded from instructions.txt")
    except FileNotFoundError:
        logger.error("instructions.txt not found. Using basic AI fallback prompt.")
        _instructions = "You are a helpful AI assistant."
    except Exception as e:
        logger.exception(f"Error loading instructions.txt: {e}")
        _instructions = "You are a helpful AI assistant."

async def get_ai_response(user_message: str) -> str:
    google_api_key_value = os.getenv("GOOGLE_GEMINI_API_KEY")
    logger.debug(f"Inside get_ai_response: Value of os.getenv('GOOGLE_GEMINI_API_KEY') = '{google_api_key_value}'")

    if not google_api_key_value:
        logger.error("GOOGLE_GEMINI_API_KEY is not configured or found in environment.")
        return "Error: GOOGLE_GEMINI_API_KEY is not configured."

    if not _instructions:
        load_instructions()

    current_instructions = _instructions if _instructions else "You are a helpful AI assistant."

    combined_prompt = f"{current_instructions}\n\nUser Query: {user_message}"
    logger.debug(f"Combined prompt starts with: '{combined_prompt[:100]}...'")

    try:
        genai.configure(api_key=google_api_key_value)
        model = genai.GenerativeModel("gemini-1.5-flash-latest")

        response = await asyncio.to_thread(
            model.generate_content,
            contents=combined_prompt
        )
        logger.debug("Received response from Gemini API.")

        if response.parts:
            ai_text = "".join(part.text for part in response.parts)
            logger.debug(f"AI Response Text (first 100 chars): '{ai_text[:100]}...'")
            return ai_text
        elif response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason
            block_details = response.prompt_feedback.block_reason_message or "No details provided."
            logger.warning(f"AI content blocked. Reason: {block_reason}. Details: {block_details}")
            return f"My response was blocked due to safety settings ({block_reason}). Please rephrase your request or contact support if this seems incorrect."
        else:
            logger.warning(f"Received an empty or unexpected response structure from AI: {response}")
            return "Error: Received an empty or unexpected response from the AI."

    except Exception as e:
        error_type = type(e).__name__
        error_str = str(e)
        logger.exception(f"Gemini API Error ({error_type}) during generation: {error_str}")

        if '429' in error_str or 'rate limit' in error_str.lower():
            return "AI Rate Limit Reached. Please try again later."
        elif 'api key not valid' in error_str.lower():
             return "Error: The provided GOOGLE_GEMINI_API_KEY is invalid. Please check your .env file."
        else:
            return f"An error occurred while contacting the AI ({error_type}). Please try again later."

load_instructions()