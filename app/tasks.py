import asyncio
from app.database import get_session_logs, update_session_summary
from app.llm import generate_session_summary

async def process_session_summary(session_id: str):
    """
    Background task to analyze logs and update session summary.
    """
    print(f"Starting background summarization for session {session_id}...")
    
    # 1. Fetch logs
    logs = await get_session_logs(session_id)
    
    # 2. Generate summary
    summary = await generate_session_summary(logs)
    
    # 3. Update session
    await update_session_summary(session_id, summary)
    
    print(f"Session {session_id} summary updated: {summary[:50]}...")
