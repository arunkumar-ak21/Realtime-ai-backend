from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class SessionCreate(BaseModel):
    summary: Optional[str] = None

class SessionUpdate(BaseModel):
    summary: Optional[str] = None

class Session(SessionCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class EventLogCreate(BaseModel):
    session_id: UUID
    role: str
    content: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None

class EventLog(EventLogCreate):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

# Schemas for LLM interaction
class ToolCall(BaseModel):
    id: str
    function: Dict[str, Any] # {name: str, arguments: str}
    type: str = "function"

class Message(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
