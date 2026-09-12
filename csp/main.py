from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
import uvicorn
from dotenv import load_dotenv

from event import Event

TEAM = os.getenv("TEAM")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("CSP_PORT", "8000"))
SERVICE = "csp"

load_dotenv()

app = FastAPI(title=SERVICE)

@app.get("/health")
async def health():
    return { "service": SERVICE, "team": TEAM, "spec_version": "1.0" }

@app.get("/transcript")
async def transcript():
    return JSONResponse(status_code=200, content= Event())

@app.post("/reset")
async def reset():
    return JSONResponse(status_code=200, content={"status": "ok"})

if __name__ == "__main__":
    uvicorn.run(
        "csp.main:app",
        host=HOST,
        port=PORT,
        reload=True
    )
