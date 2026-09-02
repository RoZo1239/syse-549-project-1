---
name: lab1-conformance
description: Run and interpret conformance_probe.py for the NIST SP 800-63-4 Figure 3 lab, and fix the checks it fails. Use whenever the probe, its 24 checks, or any check ID (S-*, P-*, H-*, N-*, X-*, H-ORD, N-SKP, P-WWW, X-CAN) comes up; when a service is reachable on the server but not from campus; when a scenario returns the wrong outcome; or when someone asks "why is my score not 24/24". Also use before any checkpoint or the presentation, to smoke-test the deployment first. Reach for this instead of guessing at probe behavior from the score alone.
---

# Conformance probe — run it, then read it correctly

The probe is a **conformance check, not a security assessment**. 24/24 means the system does what Figure 3 says; it says nothing about whether the system is safe. It also cannot see inside the implementation — it observes endpoints and transcripts only, exactly like an attacker on the campus network.

Run it early and often, not at the end.

## Running it

```bash
python3 conformance_probe.py --config team.json --verbose
```

```bash
python3 conformance_probe.py --config team.json --json result.json
```

`result.json` from a run against the **deployed** system is a required deliverable. Standard-library Python; nothing to install.

`team.json`:

```json
{"team":"ada-grace",
 "endpoints":{
   "subject":"http://daily-server.research.colostate.edu:4112",
   "csp":"http://daily-server.research.colostate.edu:4113",
   "verifier":"http://daily-server.research.colostate.edu:4114",
   "rp":"http://daily-server.research.colostate.edu:4115"}}
```

Before the probe, run the quick smoke test in this skill — it isolates deployment problems from model problems in about ten seconds:

```bash
sh .claude/skills/lab1-conformance/scripts/smoke.sh team.json
```

## The five check groups

| Group | Checks | Establishes | Difficulty |
|---|---|---|---|
| `S-*` | 5 | Four services exist, identify themselves, can be reset | near-universal |
| `P-*` | 4 | Public resource open; protected returns 401 with `WWW-Authenticate`, no error trace | near-universal |
| `H-*` | 7 | All five steps occur, in timestamp order, with Applicant → Subscriber → Claimant visible | `H-ORD` catches many teams |
| `N-*` | 4 | Wrong authenticator, unenrolled claimant, replay, verifier-bypass all refused | the real objective |
| `X-*` | 3 | No secret in transcripts, no secret-bearing field names, denial persists after failed runs | `X-CAN` separates teams |

`S-*` and `P-*` are 9 of the 24, so four `/health` endpoints, a public page and a 401 already score a few points without implementing any of the identity model. Do not read a passing-looking score as a working system — `N-SKP` and `X-CAN` are the checks that mean something.

## Failure → cause → fix

| Symptom | Almost always | Fix |
|---|---|---|
| Service unreachable from campus, fine on the server | bound to `127.0.0.1` | bind `0.0.0.0` |
| Something answers but it is not your code; `Server:` header names nginx | reverse proxy intercepting the port | check course announcements before debugging your own code |
| `H-ORD` fails, everything else in `H-*` passes | whole-second timestamps colliding | one shared helper, sub-second ISO 8601 UTC |
| `H-*` steps missing entirely | a service is not writing transcript events, or dropped the `run_id` | thread `run_id` through every hop |
| `P-WWW` fails | 401 returned without `WWW-Authenticate` | add the header (RFC 9110 §15.5.2) |
| `P-*` complains about an error trace | framework debug mode on | disable debug; return a plain JSON error |
| `N-SKP` fails | the RP accepts a self-asserted session — no real verification | the RP must validate the assertion with the Verifier before establishing a session |
| `N-RPL` fails | session credential still valid after logout/expiry | revoke on logout, check expiry on every request |
| `X-CAN` fails | the canary reached a transcript | log decisions, never inputs; grep transcripts for the canary before submitting |
| `X-*` persistence fails | `/reset` leaves state behind, or a failed run leaves a usable session | make reset total |
| Wrong `service` value | copy-paste between services | check all four `/health` responses |

## When N-SKP fails

Do not patch around it. Trace the exact lines where the RP decides someone is authenticated and ask whether that decision can be reached without the Verifier having actually checked an authenticator. If it can, the architecture — not the endpoint — needs the fix. The simplest structural answer is an opaque, single-use assertion handle that the RP introspects by calling the Verifier, which makes the bypass impossible rather than merely rejected.

Expect this to be the first thing asked about in the presentation if it fails.

## Before a checkpoint or the demo

- All four `/health` responses correct and reachable **from another campus machine**, not just localhost
- Transcripts return valid JSON with sub-second `ts`
- `happy_path` completes; all four negative scenarios return `denied`
- Canary absent from every transcript
- Services already running before the slot begins
