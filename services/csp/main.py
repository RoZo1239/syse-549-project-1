from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
import uvicorn
import secrets
from dotenv import load_dotenv

from shared.model import RunRequest, RunResponse, SubscriberResponse, Event, EventResponse, ApplicantRequest, ApplicantResponse, SubscriberRequest
from shared.user_database import UserDatabase

load_dotenv()

SERVICE = "csp"
TEAM = os.getenv("TEAM")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("CSP_PORT", "8000"))
BASE_URL = HOST + ":" + str(PORT)

events = EventResponse()

app = FastAPI(title=SERVICE)

user_db = UserDatabase()

@app.get("/health")
async def health():
    return { "service": SERVICE, "team": TEAM, "spec_version": "1.0" }

@app.get("/transcript")
async def transcript():
    return JSONResponse(status_code=200, content= Event())

@app.post("/reset")
async def reset():
    user_db.reset()
    events.reset()
    return JSONResponse(status_code=200, content={"status": "ok"})

@app.post("/apply")
async def run(body: ApplicantRequest):
    token=secrets.token_urlsafe(32)

    user_db.add_user(body.email, token)

    return ApplicantResponse(
        token=token
    )

@app.post("/subscribe")
async def run(body: SubscriberRequest):
    subscribed = user_db.subscribe_user(body.email, body.token)

    status_code = subscribed and 200 or 400
    response = SubscriberResponse(
        status = subscribed and "ok" or "error"
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump()
    )
    
if __name__ == "__main__":
    uvicorn.run(
        "services.csp.main:app",
        host=HOST,
        port=PORT,
        reload=True
    )
