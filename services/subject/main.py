"""The Subject agent — Figure 3, port block + 0. Partner A.

Stands in for the human in the diagram: a program, so the flow is scriptable
and the role transitions are visible in code. `POST /run` drives one scenario
end to end and reports success or denial.

The scenarios themselves live in services/subject/flow.py, which is standard
library only and tested directly against the Verifier and the Relying Party.
This file is the HTTP surface and nothing more.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv

# Before any configuration is read: a .env loaded afterwards has no effect.
load_dotenv()

from shared import config
from shared.model import RunRequest
from shared.transcript import Transcript
from services.subject.flow import Flow

SERVICE = "subject"
TEAM = config.team_name()
HOST = config.bind_host()
PORT = config.port_for(SERVICE)
RELOAD = config.bool_setting("LAB1_UVICORN_RELOAD", False)

# One writer, one timestamp helper, shared with the other three services.
transcript = Transcript()
flow = Flow(transcript)

app = FastAPI(title=SERVICE)

@app.get("/health")
async def health():
    return JSONResponse(status_code=200, content={ "service": SERVICE, "team": TEAM, "spec_version": "1.0" })

@app.get("/transcript")
async def get_transcript():
    return JSONResponse(status_code=200, content={"events": transcript.events()})

@app.post("/reset")
async def reset():
    transcript.reset()
    return JSONResponse(status_code=200, content={"status": "ok"})

@app.post("/run")
async def run(body: RunRequest):
    """Drive one scenario. Always answers 200 with the contract's four fields.

    A denial is a result, not an error: the four negative scenarios are
    supposed to end in `outcome: "denied"`, and a 500 would be indistinguishable
    from a broken service.
    """
    return JSONResponse(
        status_code=200,
        content=flow.run(body.run_id, body.scenario, body.canary),
    )

if __name__ == "__main__":
    uvicorn.run(
        "services.subject.main:app",
        host=HOST,
        port=PORT,
        reload=RELOAD
    )
