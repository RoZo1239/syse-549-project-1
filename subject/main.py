from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv

from shared import config
from shared.transcript import Transcript

# Before any os.getenv call below: a .env read after them has no effect, which
# is why /health used to report team=null and the service came up on port 8000.
load_dotenv()

SERVICE = "subject"
TEAM = config.team_name()
# Bind every interface: 127.0.0.1 works on the server and is invisible from
# campus, which is the second most common way to fail the conformance probe.
HOST = config.bind_host()
PORT = config.port_for(SERVICE)
RELOAD = config.bool_setting("LAB1_UVICORN_RELOAD", False)

# The transcript writer, the event shape and the sub-second UTC timestamp
# helper are shared with the other two services (PROJECT_WORKFLOW.md section 10:
# one place, reused, not re-implemented per service).
transcript = Transcript()

app = FastAPI(title=SERVICE)

@app.get("/health")
async def health():
    return { "service": SERVICE, "team": TEAM, "spec_version": "1.0" }

@app.get("/transcript")
async def get_transcript():
    return JSONResponse(status_code=200, content={"events": transcript.events()})

@app.post("/reset")
async def reset():
    # Total, not partial: a half-reset leaves state behind and the next run
    # passes for the wrong reason.
    transcript.reset()
    return JSONResponse(status_code=200, content={"status": "ok"})

if __name__ == "__main__":
    uvicorn.run(
        "subject.main:app",
        host=HOST,
        port=PORT,
        reload=RELOAD
    )
