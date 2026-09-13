from datetime import datetime, timezone
from typing import List, Any
from pydantic import BaseModel

# Run
class RunRequest(BaseModel):
    run_id: str
    scenario: str
    canary: str

class RunResponse(BaseModel):
    run_id: str
    scenario: str
    outcome: str
    detail: str

# Applicant
class ApplicantRequest(BaseModel):
    email: str

class ApplicantResponse(BaseModel):
    token: str

# Subscriber
class SubscriberRequest(BaseModel):
    email: str
    token: str

class SubscriberResponse(BaseModel):
    status: str

# Event
class Event(BaseModel):
    seq: int
    run_id: str
    step: int
    step_name: str
    actor: str
    peer: str
    outcome: str
    ts: str
    detail: Any

    @staticmethod
    def get_timestamp() -> str:
        dt = datetime.now(timezone.utc)
        return dt.strftime('%Y-%m-%dT%H:%M:%S.') + f"{dt.microsecond // 1000:03d}Z"

class EventResponse(BaseModel):
    events: List[Event] = []

    def append(self, event: Event):
        self.events.append(event)

    def reset(self):
        self.events = []
