---
name: lab1-contract
description: The frozen HTTP contract for the NIST SP 800-63-4 Figure 3 lab — four services (Subject agent, CSP, Verifier, Relying Party), five steps, three roles. Use this whenever work touches /health, /transcript, /reset, POST /run, GET /protected, transcript event shape, run_id propagation, timestamps, the five Figure 3 steps, or the Applicant to Subscriber to Claimant transitions. Use it before writing ANY new service code for this lab, and also when the request sounds routine ("add an endpoint", "my transcript looks wrong", "the RP won't accept the session") — the contract is where those bugs come from. Do not guess these interfaces from memory; they are graded by an automated probe.
---

# Lab 1 contract — Figure 3, four services

The interfaces below are **required**. An automated harness talks to the system without knowing anything about how it was built, so any deviation is a failed check, not a style difference. Everything *not* in this file is a design choice the team makes and records in `docs/decisions.md`.

Full project workflow, including the design-choice register: `PROJECT_WORKFLOW.md`.

## The four services

| Service | `service` value | Port | Owns | Must never |
|---|---|---|---|---|
| Subject | `subject` | block+0 | The scripted flow and the three roles | Skip the Verifier in `happy_path` |
| CSP | `csp` | block+1 | Subscriber accounts, authenticator binding | Make the authentication decision |
| Verifier | `verifier` | block+2 | Authenticator check, assertion issuance | Serve the protected resource |
| RP | `rp` | block+3 | Public + protected resource, sessions | **Ever see the authenticator secret** |

That last cell is the point of the whole architecture. If any code path lets the RP handle the secret, or lets the RP decide "authenticated" without the Verifier having checked something, the design has failed — that is what the `skip_verifier` scenario tests.

## Every service exposes

```
GET  /health      -> 200 {"service":"csp","team":"<team>","spec_version":"1.0"}
GET  /transcript  -> 200 {"events":[ ... ]}     ordered
POST /reset       -> 200 or 204                 clears state, flow can run again
```

Transcript event:

```json
{"seq": 1,
 "run_id": "probe-happy_path-8f3a1c",
 "step": 1,
 "step_name": "identity_proofing_and_enrollment",
 "actor": "applicant",
 "peer": "csp",
 "outcome": "success",
 "ts": "2026-09-14T18:22:03.114Z",
 "detail": "evidence accepted"}
```

- `step` 1–5 · `actor` one of `applicant`, `subscriber`, `claimant`, `csp`, `verifier`, `rp` · `outcome` `success` or `denied`
- Only the step *numbers* are fixed. Use one snake_case `step_name` string per step and use the same string in all four services.

## The RP also exposes

```
GET /            -> 200, no credential of any kind (the public resource)
GET /protected   -> 401 + WWW-Authenticate header when no valid session
                 -> 200 + content when a valid session is presented
```

RFC 9110 §15.5.2 requires the `WWW-Authenticate` header on a 401. It is the single most forgotten line in this lab, and it is checked.

## The Subject agent also exposes

```
POST /run
  req  {"run_id":"...","scenario":"happy_path","canary":"CANARY-a1b2c3"}
  resp {"run_id":"...","scenario":"happy_path","outcome":"success",
        "detail":"protected resource returned HTTP 200"}
```

- `outcome` is `success` or `denied`.
- **`canary` is the string to use as the authenticator secret.** The harness then greps every transcript for it. If it appears anywhere, a secret was logged.
- Propagate the given `run_id` into every transcript event in **all four** services, so one run can be isolated.

Scenarios `POST /run` must support: `happy_path` (success) · `wrong_authenticator` · `unenrolled_claimant` · `replay` · `skip_verifier` (the last four all `denied`, with no successful step 5).

## The eight things that actually fail

1. **Whole-second timestamps.** Ordering across services is by `ts`; second granularity collides and the ordering check fails. Write one helper, use it everywhere:
   - Python: `datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")`
   - Node: `new Date().toISOString()`
2. **Binding to `127.0.0.1`.** Works on the server, invisible from campus. Bind `0.0.0.0`.
3. **Missing `WWW-Authenticate`** on the 401.
4. **`run_id` dropped** somewhere in the chain — usually the Verifier or RP, which receive it second-hand. Thread it through every call.
5. **The canary reaching a transcript**, usually via a well-meant `detail: "secret=..."` or an echoed request body. Log decisions, never inputs.
6. **`/reset` that half-resets**, leaving a session or a subscriber behind, so the next run passes for the wrong reason or fails mysteriously.
7. **The RP trusting the assertion it was handed** instead of validating it with the Verifier. This is `skip_verifier` and it is the check that separates teams.
8. **A `/health` `service` value that does not match the port's role** after a copy-paste.

## Before writing code

Check `shared/` first. The transcript writer, the timestamp helper, the HTTP client and the config loader belong there once, not four times. If a helper exists, use it; if a near-match exists, extend it rather than adding a sibling.

Build in this order, running the probe after each: `/health` on all four → RP `/` and `/protected` 401 → CSP enroll and bind → Verifier check and assert → RP session → Subject `POST /run` happy path → the four negative scenarios.

## Not in this lab

**No OAuth, OpenID Connect, or SAML** — those are federation technologies and this is explicitly the *non-federated* model; introducing them confuses both the design and the presentation. **No authorization roles** — no admin/viewer, no permission matrix. Applicant, Subscriber and Claimant are positions in the identity lifecycle, not privileges. The question this lab answers is only *can we tell who you are?*
