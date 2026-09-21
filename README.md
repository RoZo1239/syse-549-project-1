# Lab 1 — NIST SP 800-63-4 Figure 3, non-federated digital identity model

Four services, five steps, one subject moving through three roles, all inside a
single trust boundary. The model, the contract and the grading criteria are in
[`PROJECT_WORKFLOW.md`](PROJECT_WORKFLOW.md); this file is how to run it.

Python 3.8+. The Verifier, the Relying Party, the test suite and the scripts are
standard library only; the Subject agent and the CSP are FastAPI
(`requirements.txt`). No sudo, no system services.

## Services and ports

Ports are `LAB1_PORT_BLOCK` plus a fixed offset, so one setting moves all four.
Team `hayagreeva-jonathan` claimed **4100–4103** on the Canvas discussion, and
`team.json` and `.env.example` carry that block.

| Service | Offset | Port | Owner | What it does |
|---|---|---|---|---|
| Subject agent | +0 | 4100 | Partner A | Drives the five scenarios — `POST /run` |
| CSP | +1 | 4101 | Partner A | Proofing, enrollment, authenticator issuance (steps 1–2) |
| Verifier | +2 | 4102 | Partner B | Checks authenticator control, issues assertions (step 4) |
| Relying Party | +3 | 4103 | Partner B | Public + protected resource, sessions (steps 3, 5) |
| _frontend_ | — | 5173 | Partner A | React UI over the three browser-facing services. Not part of the graded contract. |

### Where the probe score stands

Two different measurements, and they do not agree yet:

| Where | Score | When |
|---|---|---|
| All four running on one host from this checkout | 24 of 24, 10.0/10 | this tree, `scripts/run_all.sh` then `conformance_probe.py` |
| The deployment on `daily-server` | 21 of 24 | last run against the live services |

A local pass is not a deployed pass, and only the deployed one is graded.
`result.json` in this archive must be the deployed run. The three checks that
fail there are a deployment difference, not a code difference — the same code
passes them on loopback — so they are chased with
[`docs/deployment.md`](docs/deployment.md) and `scripts/trace.py`, not by
editing services.

## Running it from a clean checkout

Step by step, including the server and the live demo:
**[`docs/deployment.md`](docs/deployment.md)**.

```bash
git clone <this repo> && cd syse-549-project-1
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # once per token
$EDITOR .env        # paste one token into each of the two token settings
pip install -r requirements.txt   # Partner A's two services only
```

One `.env` configures all four services: Partner A's read `TEAM`, `HOST` and
`<SERVICE>_PORT`, and Partner B's read the same names when the `LAB1_`-prefixed
form is unset.

Start all four at once, one log per service under `run/`:

```bash
sh scripts/run_all.sh                     # sh scripts/stop_all.sh to stop them
sh scripts/run_all.sh verifier rp         # or only the ones you name
sh scripts/run_all.sh subject csp verifier rp frontend   # + the React UI
```

Or one at a time, each in its own terminal:

```bash
python3 -m services.subject.main     # port block + 0   (Partner A)
python3 -m services.csp.main         # port block + 1   (Partner A)
python3 -m services.verifier         # port block + 2   (Partner B)
python3 -m services.rp               # port block + 3   (Partner B)
```

All four bind `0.0.0.0` by default. A service bound to `127.0.0.1` works on the
server and is invisible from campus, which is the second most common way to
fail the conformance probe.

## Watching it happen, one step at a time

`POST /run` does the whole flow in one call and reports only the verdict, which
is what the probe wants and the opposite of what a person needs. Two scripts
exist for the other job.

```bash
python3 scripts/walkthrough.py                  # happy_path, one step per screen
python3 scripts/walkthrough.py skip_verifier    # or any of the five scenarios
python3 scripts/walkthrough.py --all            # all five, in order
python3 scripts/walkthrough.py --no-pause       # don't wait for Enter
```

Each screen shows one Figure 3 step: the request that goes out, the status and
body that come back, the role transition it causes, and one sentence tying it
to SP 800-63-4 or RFC 9110. The authenticator secret is never printed — only
its length. It ends with the merged transcript for that run.

```bash
python3 scripts/trace.py                # every run, all four transcripts, merged
python3 scripts/trace.py --last         # just the most recent run
python3 scripts/trace.py <run_id>       # one run, e.g. a probe's
python3 scripts/trace.py --json         # the merged events, for a script

python3 scripts/diagnose.py result.json    # a failed probe check -> the next command
python3 scripts/diagnose.py --check H-ORD  # or look one up directly
```

`trace.py` sorts by `ts` exactly the way the probe's `H-ORD` check does, so the
table it prints is the order the probe will see rather than a tidier one. It
also restates `H-ORD`, `H-ROL` and `X-FLD` underneath in plain words.

What to actually say while it runs — the flow in plain words, the updated
diagram, and the three lines to land — is
[`docs/demo-script.md`](docs/demo-script.md).

The whole demo, in one command:

```bash
sh scripts/demo.sh            # start, happy path, three denials, probe

# rehearsing off campus? team.json's hostname only resolves there:
LAB1_PROBE_CONFIG=local.json sh scripts/demo.sh
```

## Tests

One command, all of it, never touching a running deployment:

```bash
python3 -m unittest discover -s tests -t .
```

88 tests. Every test named `test_denies_*` carries one sentence naming the
attack it defends against.

The cross-review tests for Partner A's services skip with a printed reason
while those services are not running. To include them, point them at a
deployment:

```bash
LAB1_SUBJECT_URL=http://host:4100 LAB1_CSP_URL=http://host:4101 \
    python3 -m unittest discover -s tests -t .
```

## Conformance probe

```bash
python3 conformance_probe.py --config team.json --verbose
python3 conformance_probe.py --config team.json --json result.json
```

`result.json` must come from a run against the **deployed** system.

## The API, beyond the frozen contract

Every service exposes `GET /health`, `GET /transcript` and `POST /reset`. The
endpoints below are the team's own design choices, recorded in
[`docs/decisions.md`](docs/decisions.md) — which also carries the full project
workflow: how a run travels end to end, how the two halves were built in
parallel, and the day-to-day loop.

**CSP** (port block + 1)

| Endpoint | Caller | Purpose |
|---|---|---|
| `POST /apply` | Applicant | Proofing and enrollment; returns the enrollment token (step 1) |
| `POST /subscribe` | Applicant | Redeem the token, bind the authenticator, push the record to the Verifier (step 2) |
| `GET /activate` | a human, from the emailed link | The same step 2, answered as HTML instead of JSON |

**Verifier** (port block + 2)

| Endpoint | Caller | Purpose |
|---|---|---|
| `POST /binding` | CSP, with `X-Lab1-Binding-Token` | Hand over the `identifier -> scrypt record` binding (step 2) |
| `POST /authenticate` | Claimant | Prove control of the authenticator; returns a single-use assertion handle (step 4) |
| `POST /introspect` | RP, with `X-Lab1-Introspect-Token` | Redeem an assertion handle for the subscriber identifier (step 5) |

**Relying Party** (port block + 3)

| Endpoint | Caller | Purpose |
|---|---|---|
| `GET /` | anyone | The public resource — no credential of any kind |
| `GET /protected` | Claimant / Subscriber | `401` + `WWW-Authenticate` without a session (step 3), `200` with one (step 5) |
| `POST /session` | Subject | Exchange an assertion for a session, after the RP validates it with the Verifier |
| `POST /logout` | Subscriber | Revoke the session |

Session credentials are presented as `Authorization: Lab1-Session <token>`. A
request that is part of a scripted run carries its `run_id` in the `X-Run-Id`
header (or a `?run_id=` query parameter) so that `GET /protected`, which has no
body, still lands in the transcript under the right run.

### Why the Relying Party never calls the CSP

Figure 3 has no arrow between them, and it is not an omission: an RP that could
ask the CSP about an account would be reaching into another service's data, and
the one question the code review cares most about is whether the RP can reach
an "authenticated" decision without the Verifier.

So the RP's public page and its `401` body each carry two URLs — `enroll_at`
(the CSP's `/apply`) and `authenticate_at` (the Verifier's `/authenticate`) —
and the RP issues no request to either. A subject who was never enrolled is
told where to go; the RP still learns nothing about them until the Verifier
says so. `tests/test_rp.py::test_the_rp_signposts_enrollment_without_ever_calling_the_csp`
pins both halves.

## Who built what

**Partner A** owns the enrollment side: the Subject agent (the scripted flow,
the Applicant → Subscriber → Claimant transitions, `POST /run` and the five
scenarios), the CSP (subscriber accounts, identity proofing policy,
authenticator issuance and secret hashing, the activation email) and the React
frontend. **Partner B** owns the authentication and access side: the Verifier
(checking authenticator control and issuing assertions) and the Relying Party
(the public and protected resources, the `401` challenge, and the session
lifecycle), plus the shared helpers in `shared/`, the walkthrough and trace
scripts, and the negative tests for Partner A's two services in
`tests/test_partner_a_negative.py`. Each partner wrote the negative tests for
the other's services, and both can explain all four.
