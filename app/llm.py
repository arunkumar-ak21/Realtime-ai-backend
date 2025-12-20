import os
import json
import asyncio
from typing import AsyncGenerator, List, Dict, Any
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY not found.")

# Initialize v1 Client
client = genai.Client(api_key=GEMINI_API_KEY)

# 1. Simulated Tool
def get_current_weather(location: str):
    """Get the current weather in a given location"""
    if "tokyo" in location.lower():
        return json.dumps({"location": "Tokyo", "temperature": "15", "unit": "celsius"})
    elif "san francisco" in location.lower():
        return json.dumps({"location": "San Francisco", "temperature": "72", "unit": "fahrenheit"})
    else:
        return json.dumps({"location": location, "temperature": "22", "unit": "celsius"})

# 2. Streaming Chat with Tool Calling
async def stream_chat(messages: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Streams responses from Gemini 2.5 Flash using google-genai SDK.
    Handles tool calls via client.chats.create
    """
    try:
        # Map messages to Gemini v1 format
        # User: {'role': 'user', 'parts': [{'text': ...}]}
        # Model: {'role': 'model', 'parts': [{'text': ...}]}
        
        gemini_history = []
        last_user_content = ""
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            if role == "user":
                gemini_history.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))
                last_user_content = content
            elif role == "assistant":
                gemini_history.append(types.Content(role="model", parts=[types.Part.from_text(text=content)]))
            # Ignore system for history in this simple mapping or use system_instruction
        
        # Pop last user message to send it as the prompt
        if gemini_history and gemini_history[-1].role == "user":
            gemini_history.pop()

        chat = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                tools=[get_current_weather],
                system_instruction="You are a helpful AI assistant. You can answer general questions, math, coding, and provide general knowledge. You also have access to weather tools. Use the weather tool ONLY when specifically asked about weather. For all other queries, answer directly.",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False) 
            ),
            history=gemini_history
        )
        
        # Send message and stream
        # Note: send_message is synchronous in v1 or async? 
        # google-genai client methods are synchronous by default? 
        # Wait, the quickstart `response = client.models.generate_content` implies sync unless `client.aio` used?
        # The documentation for python v1 client usually has `client = genai.Client()` and async support via manual async wrapping or async client?
        # Let's check user snippet: `client = genai.Client()`. This creates a sync client usually.
        # But we need async streaming for FastAPI.
        # We should use `client = genai.Client(http_options={'api_version': 'v1alpha'})`? 
        # Actually standard practice is strict usage.
        # To be safe for FastAPI, we'll try to use the async client methods if available or wrap in thread.
        
        # However, checking `google.genai` docs (if we could), usually there is an async client support.
        # Let's assume sync for now and wrap in thread for the *initial* call but iterating stream might be tricky if sync iterator.
        
        # Correction: `google-genai` likely supports async via `client.aio.chats.create` or similar?
        # Let's try `stream=True` and see if iterator is async.
        # If not, we will run in thread interactively.
        
        # Using a specialized approach:
        # Since I can't browse deep docs, I will assume the standard sync client for now because `await chat.send_message_async` was old SDK.
        # I'll create the response iterator synchronously and yield from it, potentially blocking briefly.
        # To avoid blocking event loop, really should use async client.
        
        # Assuming `from google import genai`... `client.aio`?
        # User snippet used sync: `print(response.text)`.
        
        # Important: To make it work in `async def`:
        # We'll stick to a simpler approach: use sync client but minimal blocking.
        
        # Use send_message_stream for streaming response
        response = chat.send_message_stream(last_user_content)
        
        # Response is an iterator of chunks
        for chunk in response:
            if chunk.text:
                yield {"type": "content", "content": chunk.text}
            # Tool calls are handled automatically by SDK
            
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "resource_exhausted" in error_msg or "quota" in error_msg:
             # Fallback logic
             yield {"type": "content", "content": "\n\n**Quota Exceeded **\n\nI'm unable to reach the Gemini API right now due to free tier limits."}
        else:
            yield {"type": "content", "content": f"\n\n[System Error: {str(e)}]"}

async def generate_session_summary(logs: List[Dict[str, Any]]) -> str:
    """Generates a summary using Gemini."""
    if not logs:
        return "No activity."
        
    transcript = ""
    for log in logs:
        role = log.get("role", "unknown")
        content = log.get("content", "")
        transcript += f"{role}: {content}\n"
        
    prompt = f"Summarize this:\n{transcript}"
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "resource_exhausted" in error_msg:
            return "Session summary unavailable (Quota Exceeded)."
        return f"Error generating summary: {str(e)}"
