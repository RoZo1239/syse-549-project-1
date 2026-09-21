"""The Credential Service Provider — Figure 3, port block + 1. Partner A.

Owns the subscriber accounts and the authenticator. Two steps of the five:

  1. identity proofing and enrollment — POST /apply
  2. authenticator issuance and binding — POST /subscribe

Proofing here is control of an email address: an applicant supplies one and
gets back a token, and presenting that token is the evidence that makes them a
Subscriber. The authenticator secret is hashed with scrypt on arrival and never
stored in the clear; what crosses the boundary to the Verifier is that salted
digest, never the secret.

The CSP deliberately does NOT decide who is authenticated. That is the
Verifier's job, and keeping it there is what the skip_verifier scenario tests.
"""

import os
from html import escape

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import secrets
from dotenv import load_dotenv

# Before any configuration is read: a .env loaded afterwards has no effect.
load_dotenv()

from shared import config
from shared.httpjson import ServiceUnreachable, post_json
from shared.model import ApplicantRequest, ApplicantResponse, SubscriberRequest, SubscriberResponse
from shared.pwhash import hash_secret
from shared.transcript import Transcript
from shared.user_database import UserDatabase
from shared.validate import (
    MAX_OUTPUT_LEN,
    MIN_OUTPUT_LEN,
    normalize_identifier,
    valid_authenticator_output,
)
from services.csp.email_service import EmailService

SERVICE = "csp"
TEAM = config.team_name()
HOST = config.bind_host()
PORT = config.port_for(SERVICE)

VERIFIER_URL = config.internal_endpoint_for("verifier")
BINDING_TOKEN = config.require_secret("LAB1_CSP_BINDING_TOKEN")
# The link mailed to an applicant has to resolve for them, not for us: the
# bind host is 0.0.0.0 on the wire but means nothing in a browser.
PUBLIC_URL = config.endpoint_for(SERVICE)
# The frontend isn't one of the four graded services (shared/config.py's
# SERVICES), so it has no port-block entry of its own - just Vite's fixed dev
# port. Same host-resolution reasoning as PUBLIC_URL above: a concrete HOST
# means "dial this everywhere", and 0.0.0.0 falls back to loopback since the
# frontend never runs in production either.
# The port was hardcoded to 5173 here, so the "Log in" link on the activation
# page pointed at 5173 however the dev server was actually configured - and
# the subscriber landed on a dead URL immediately after the one step that just
# succeeded. It reads FRONTEND_PORT now, the same setting run_all.sh and
# vite.config.js use, so all three agree.
FRONTEND_PORT = config.int_setting("LAB1_FRONTEND_PORT", 5173)
FRONTEND_URL = "http://%s:%d" % (
    HOST if HOST not in ("0.0.0.0", "::", "") else "127.0.0.1", FRONTEND_PORT,
)
ACTIVATION_PAGE_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "templates", "activation_page.html",
)

transcript = Transcript()

app = FastAPI(title=SERVICE)

user_db = UserDatabase()
email_service = EmailService(PUBLIC_URL)

@app.get("/health")
def health():
    return { "service": SERVICE, "team": TEAM, "spec_version": "1.0" }

@app.get("/transcript")
def get_transcript():
    return JSONResponse(status_code=200, content={"events": transcript.events()})

@app.post("/reset")
def reset():
    # Total, not partial: a half reset leaves an account behind and the next
    # run passes for the wrong reason.
    user_db.reset()
    transcript.reset()
    return JSONResponse(status_code=200, content={"status": "ok"})

@app.post("/apply")
def apply(body: ApplicantRequest):
    """Step 1. Create the subscriber account and issue the enrollment token."""
    identifier = normalize_identifier(body.email)
    if identifier is None:
        transcript.record(
            run_id=body.run_id, step=1, actor="applicant", peer="csp",
            outcome="denied", detail="enrollment refused: malformed application",
        )
        return JSONResponse(status_code=400, content={"error": "invalid_request"})

    if not valid_authenticator_output(body.plaintext):
        # Rejected here, at the point of choice, so nobody enrolls with a
        # password that /authenticate would then never accept.
        transcript.record(
            run_id=body.run_id, step=1, actor="applicant", peer="csp",
            outcome="denied", detail="enrollment refused: password length not accepted",
        )
        return JSONResponse(status_code=400, content={
            "error": "invalid_password",
            "min_length": MIN_OUTPUT_LEN,
            "max_length": MAX_OUTPUT_LEN,
        })

    if user_db.user_exists(identifier):
        # Any existing account, activated or not. Refusing only the *activated*
        # ones was an account-takeover path, and the cross-review test in
        # tests/test_partner_a_negative.py caught it:
        #
        #   1. Alice applies. A row is created with her password hash and a
        #      token is mailed to her. She has not clicked it yet.
        #   2. Mallory applies for alice@example.com with a password of
        #      Mallory's choosing. The row is overwritten - Mallory's hash now,
        #      a fresh token - and that token is mailed to Alice.
        #   3. Alice clicks the link that arrives in her own mailbox and
        #      activates an account whose password belongs to Mallory.
        #
        # Every step looks legitimate from inside the system, and no
        # cryptography is involved. See docs/decisions.md.
        transcript.record(
            run_id=body.run_id, step=1, actor="applicant", peer="csp",
            outcome="denied", detail="enrollment refused: identifier already claimed",
        )
        return JSONResponse(status_code=409, content={"error": "already_enrolled"})

    token = secrets.token_urlsafe(32)
    user_db.add_user(identifier, token, hash_secret(body.plaintext))
    email_sent = email_service.send_activation(identifier, token, body.run_id)

    # actor="applicant" is load bearing: the probe reads the Applicant ->
    # Subscriber -> Claimant progression off this field, and this is the only
    # event that carries the first of the three.
    transcript.record(
        run_id=body.run_id, step=1, actor="applicant", peer="csp",
        outcome="success", detail="evidence accepted, subscriber account created",
    )
    return JSONResponse(
        status_code=201,
        content=ApplicantResponse(token=token, email_sent=bool(email_sent)).model_dump(),
    )

def _complete_subscription(identifier, token, run_id):
    """Step 2. The applicant becomes a Subscriber and the authenticator is bound.

    Shared by the machine-facing POST /subscribe and the human-facing
    GET /activate below, so there is exactly one code path that ever finishes
    enrollment, whichever way a subscriber reaches it.
    """
    # Check the token WITHOUT spending it. The account is marked subscribed at
    # the bottom, only once the Verifier has the binding: doing it here instead
    # spent the token before the binding was attempted, so a single failed
    # binding left the account subscribed-but-unbound and the activation link
    # dead, with every retry reporting "invalid or already used".
    if identifier is None or not user_db.token_matches(identifier, token):
        transcript.record(
            run_id=run_id, step=2, actor="csp", peer="applicant",
            outcome="denied", detail="issuance refused: enrollment token not accepted",
        )
        return "invalid_token"

    record = user_db.verifier_record(identifier)
    try:
        status, _ = post_json(
            VERIFIER_URL + "/binding",
            {"run_id": run_id, "identifier": identifier, "verifier_record": record},
            headers={"X-Lab1-Binding-Token": BINDING_TOKEN},
        )
    except ServiceUnreachable:
        # A CSP that cannot reach the Verifier has issued nothing usable.
        transcript.record(
            run_id=run_id, step=2, actor="csp", peer="verifier",
            outcome="denied", detail="issuance incomplete: verifier unreachable",
        )
        return "verifier_unreachable"

    bound = status == 201
    if bound:
        # Only now is the applicant a Subscriber. Before this line the account
        # is still pending and the activation link still works, so a Verifier
        # that was briefly unhappy costs a retry rather than the account.
        user_db.subscribe_user(identifier, token)
    # One detail string for both outcomes used to put "authenticator issued and
    # bound" next to outcome="denied", which is a transcript that contradicts
    # itself - and the transcript is the evidence a grader reads.
    transcript.record(
        run_id=run_id, step=2, actor="csp", peer="subscriber",
        outcome="success" if bound else "denied",
        detail=("authenticator issued and bound to the subscriber account"
                if bound else
                "issuance incomplete: verifier did not accept the binding"),
    )
    return "ok" if bound else "not_bound"

@app.post("/subscribe")
def subscribe(body: SubscriberRequest):
    """Step 2, for the Subject agent: JSON in, JSON out."""
    identifier = normalize_identifier(body.email)
    result = _complete_subscription(identifier, body.token, body.run_id)
    status_code = {
        "ok": 200, "invalid_token": 400,
        "verifier_unreachable": 503, "not_bound": 502,
    }[result]
    return JSONResponse(
        status_code=status_code,
        content=SubscriberResponse(status="ok" if result == "ok" else "error").model_dump(),
    )

def _activation_page(title: str, message: str) -> str:
    # Styled HTML lives in templates/activation_page.html (same convention as
    # email_service.py's activation_email.html) rather than built inline here.
    with open(ACTIVATION_PAGE_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()
    return (
        template
        .replace("{{TITLE}}", escape(title))
        .replace("{{MESSAGE}}", escape(message))
        .replace("{{LOGIN_URL}}", escape(FRONTEND_URL + "/login"))
    )

@app.get("/activate", response_class=HTMLResponse)
def activate(email: str, token: str, run_id: str = ""):
    """Step 2, for a human: the link mailed by /apply, answered with a page.

    Not part of the machine contract — the Subject agent drives step 2
    through the JSON POST /subscribe above, not this endpoint.

    `run_id` is optional and carried through so that a browser-driven signup
    still lands its step 2 under the same run as its step 1. Without it the
    activation click was recorded as UNATTRIBUTED, and a run traced from the
    UI was missing one of the five arrows. A malformed or absent value is
    handled by shared.transcript.clean_run_id, not here.
    """
    identifier = normalize_identifier(email)
    result = _complete_subscription(identifier, token, run_id)
    if result == "ok":
        return HTMLResponse(_activation_page(
            "Account activated",
            "Your account is active. You can now log in with your email and password.",
        ))
    if result == "verifier_unreachable":
        return HTMLResponse(_activation_page(
            "Activation incomplete",
            "We could not finish setting up your account. Please try the link again shortly.",
        ), status_code=503)
    if result == "not_bound":
        # Distinct from invalid_token on purpose. Blaming the link for a
        # Verifier that refused the binding sends the subscriber to re-enrol,
        # which cannot help, and hides the actual fault - usually
        # LAB1_CSP_BINDING_TOKEN differing between the CSP and the Verifier.
        return HTMLResponse(_activation_page(
            "Activation incomplete",
            "Your link is valid, but we could not finish setting up your "
            "account. Nothing has been used up - try the same link again "
            "shortly, or contact whoever runs this service.",
        ), status_code=502)
    return HTMLResponse(_activation_page(
        "Activation failed",
        "This activation link is invalid or has already been used.",
    ), status_code=400)

if __name__ == "__main__":
    uvicorn.run(
        "services.csp.main:app",
        host=HOST,
        port=PORT,
    )
