from datetime import datetime
from typing import List, Any
from pydantic import BaseModel

class Event(BaseModel):
    seq: int
    run_id: str
    step: int
    step_name: str
    actor: str
    peer: str
    outcome: str
    ts: datetime
    detail: Any

class EventsResponse(BaseModel):
    events: List[Event]
