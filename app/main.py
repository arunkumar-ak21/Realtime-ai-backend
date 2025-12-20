from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import create_session, log_event
from app.llm import stream_chat
from app.tasks import process_session_summary
import json
import asyncio

app = FastAPI(title="AI Session Backend")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse('static/index.html')

@app.post("/sessions")
async def start_new_session():
    """Create a new session explicitly."""
    session_data = await create_session()
    return session_data

@app.get("/sessions/{session_id}/logs")
async def get_history(session_id: str):
    from app.database import get_session_logs
    try:
        logs = await get_session_logs(session_id)
        return logs
    except Exception as e:
        return []

@app.websocket("/ws/session/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    # Ensure session exists in DB so foreign keys don't fail
    from app.database import ensure_session_exists, get_session_logs
    await ensure_session_exists(session_id)
    
    # Load History
    db_logs = await get_session_logs(session_id)
    
    # Initialize history with System Prompt
    websocket.chat_history = [
        {"role": "system", "content": "You are a helpful AI assistant with access to tools. Use them when needed."}
    ]
    
    # 0. Populate context from DB
    for log in db_logs:
        role = log.get("role")
        content = log.get("content")
        # Ensure we only add valid roles for context
        if role in ["user", "assistant", "tool"]:
             msg = {"role": role, "content": content}
             
             # If it was a tool call by assistant, we need to reconstruct that structure
             # Our current DB schema is simple. For full tool reconstruction we need more fields.
             # but for this prototype, if we see 'tool_call_id' in log, we might need to handle it.
             # Implementation simplification: just treat text content for now unless complex.
             # To keep prototype simple: We will just load text content.
             # Improve: If log has `tool_call_id` and role is `assistant`, it was a call? 
             # Or if role is `tool`?
             
             # Let's keep it simple: content-based history.
             if content: 
                 websocket.chat_history.append(msg)
    
    try:
        # Initial greeting?
        # await websocket.send_text("Connected to session " + session_id)
        
        while True:
            data = await websocket.receive_text()
            
            # 1. Log User Message
            # We use asyncio.create_task to make it non-blocking logging
            asyncio.create_task(log_event(session_id, "user", content=data))
            
            # Prepare messages context
            
            # We already initialized websocket.chat_history above
            
            websocket.chat_history.append({"role": "user", "content": data})
            
            # 2. Stream LLM Response
            current_response = "" # Accumulator for the full response
            async for chunk in stream_chat(websocket.chat_history): # Use websocket.chat_history for context
                # chunk is {"type": "content"|"tool_result"|"info", ...}
                
                if chunk["type"] == "content":
                    content_chunk = chunk["content"]
                    current_response += content_chunk # Accumulate content
                    # Send JSON structure
                    payload = {"type": "chunk", "content": content_chunk}
                    await websocket.send_text(json.dumps(payload))
                elif chunk["type"] == "info":
                    # Optional: notify client about tool usage
                    pass 
                
            # Send End of Message signal
            await websocket.send_text(json.dumps({"type": "done"}))
            
            # 3. Log AI Response
            asyncio.create_task(log_event(session_id, "assistant", content=current_response))
            
            # Update history with full response
            websocket.chat_history.append({"role": "assistant", "content": current_response})
            
            # Send specific end-of-turn marker if custom protocol needed, 
            # or just rely on websocket mechanics.
            
    except WebSocketDisconnect:
        print(f"Client disconnected from session {session_id}")
        
        # 4. Trigger Post-Session Automation
        # We can't use BackgroundTasks directly in websocket handler nicely without the request scope,
        # but we can just spawn an asyncio task since we are still in event loop.
        asyncio.create_task(process_session_summary(session_id))
