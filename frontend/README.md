# frontend

A React UI for the RP's public/protected resource and the full subscriber
journey: sign up (CSP), log in (Verifier + RP), view the protected resource
(RP). Not part of the graded contract — the four backend services are pure
JSON and are what the conformance probe talks to. This is a browsable client
on top of them.

## Run it

Requires Node.js (not installed in the environment this was scaffolded in —
install it on your own machine first: https://nodejs.org).

```
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173. The backend services must already be running
on their default ports (csp: 4101, verifier: 4102, rp: 4103) — the dev server
proxies `/api/csp`, `/api/verifier`, `/api/rp` to them (see
`vite.config.js`), so the browser never calls those origins directly and never
hits their CORS/OPTIONS gap.

To drive the deployment instead of a local copy — which is also what puts the
traffic on a real network interface for packet capture:

```
VITE_API_HOST=daily-server.research.colostate.edu npm run dev
VITE_PORT_BLOCK=4100 npm run dev                    # if the block ever moves
```

## The five steps, and which page does which

| Step | Page | Request |
|---|---|---|
| **3** authentication request | landing on `/` with no session | `GET /api/rp/protected` → `401` + `WWW-Authenticate` |
| **1** proofing and enrollment | Sign up | `POST /api/csp/apply` |
| **2** authenticator issuance | the activation link | `GET /api/csp/activate` |
| **4** authentication process | Log in | `POST /api/verifier/authenticate` |
| **5** authenticated session | after logging in | `POST /api/rp/session`, then `GET /api/rp/protected` |

Step 3 comes first because a person hits the wall before they have an account.
The probe's Subject agent runs them in numbered order because it is a script.
Both are recorded truthfully, which is what the transcripts are for.

The landing page asks the RP even when it holds no session, deliberately. An
earlier version short-circuited to the login form in the browser, which meant
the *client* decided who was authenticated — a small version of the mistake
`skip_verifier` exists to catch — and it left step 3 out of the browser flow
entirely.

## Why a proxy, not CORS headers on the services

The backend services are deliberately a minimal `http.server` subclass
(`shared/service.py`) with no OPTIONS handling. Adding CORS support there
would mean modifying code the automated probe grades. Routing through Vite's
dev proxy keeps the backend untouched and the browser same-origin.
