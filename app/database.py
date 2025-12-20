import os
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not found in environment variables.")
    # In a real app we might raise an error, but for setup we'll warn.

_supabase: Client = None

def get_supabase_client() -> Client:
    global _supabase
    if _supabase is None:
        if SUPABASE_URL and SUPABASE_KEY:
            _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        else:
            raise ValueError("Supabase credentials not set.")
    return _supabase

async def create_session() -> dict:
    client = get_supabase_client()
    result = await asyncio.to_thread(client.table("sessions").insert({}).execute)
    return result.data[0]

async def ensure_session_exists(session_id: str):
    """Checks if session exists, if not creates it with the given ID."""
    client = get_supabase_client()
    
    # 1. Check if exists
    result = await asyncio.to_thread(
        client.table("sessions").select("id").eq("id", session_id).execute
    )
    
    if not result.data:
        # 2. Create if not exists (upsert-like behavior but simple insert logic)
        try:
            await asyncio.to_thread(
                client.table("sessions").insert({"id": session_id}).execute
            )
            print(f"Created new session {session_id}")
        except Exception as e:
            print(f"Error ensuring session exists: {e}")
            # Could be race condition, ignore if it now exists

async def update_session_summary(session_id: str, summary: str):
    client = get_supabase_client()
    await asyncio.to_thread(
        client.table("sessions").update({"summary": summary}).eq("id", session_id).execute
    )

async def log_event(session_id: str, role: str, content: str = None, tool_call_id: str = None, tool_name: str = None):
    client = get_supabase_client()
    data = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "tool_call_id": tool_call_id,
        "tool_name": tool_name
    }
    # Filter out None values to let DB defaults or nulls handle it cleanly if needed, 
    # though here we want explicit nulls for optional fields.
    await asyncio.to_thread(client.table("event_logs").insert(data).execute)

async def get_session_logs(session_id: str) -> list:
    client = get_supabase_client()
    result = await asyncio.to_thread(
        client.table("event_logs")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at")
        .execute
    )
    return result.data
