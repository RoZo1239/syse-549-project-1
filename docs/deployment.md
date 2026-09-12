# Deployment and test procedure

Every command below has been run from a clean clone. Where the result depends
on work that is not finished yet, the expected output says so.

Two things could not be run in the environment this was written in and are
therefore *not* verified here: `pip install -r requirements.txt` (no network),
and consequently Partner A's two services starting. Everything else below was
executed.

**Status this procedure was verified against:** the Verifier and RP are
complete; the Subject agent and CSP answer `/health`, `/transcript` and
`/reset` but have no `POST /run`, no enrollment and no binding. So the probe
scores **12 of 24** with all four running, and the end-to-end flow has to be
driven by hand (part 3 below) until `POST /run` exists.

---

## Part 1 — Local, on your own machine

### 1.1 Prerequisites

```bash
python3 --version      # 3.8 or newer
curl --version
```

Partner B's services (`verifier`, `rp`) and the whole test suite are standard
library only. Partner A's services (`subject`, `csp`) are FastAPI apps and need
four packages.

### 1.2 Clone and configure

```bash
git clone https://github.com/RoZo1239/syse-549-project-1.git
cd syse-549-project-1
cp .env.example .env
```

Generate the two shared tokens and paste one into each setting in `.env`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # LAB1_CSP_BINDING_TOKEN
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # LAB1_RP_INTROSPECT_TOKEN
```

Then set the rest of `.env`:

| Setting | Value | Why |
|---|---|---|
| `TEAM` | your team name | reported by all four `/health` endpoints |
| `HOST` | `0.0.0.0` | `127.0.0.1` works on the server and is invisible from campus |
| `SUBJECT_PORT` … `RP_PORT` | your claimed block, +0 +1 +2 +3 | must be four consecutive ports in **4100–4199** |

`.env` is gitignored and must stay that way — it holds both shared tokens.

### 1.3 Install Partner A's dependencies

```bash
pip install -r requirements.txt
```

Skip this and `subject` and `csp` will fail to start with
`ModuleNotFoundError: No module named 'fastapi'` in their log. Nothing else in
the project needs it.

### 1.4 Start everything

```bash
sh scripts/run_all.sh
```

One `nohup` process per service, pidfiles and logs under `run/`. The script
then reports which ones actually answer `/health`. Skipping step 1.3 looks
exactly like this:

```
== health ==
  subject   DOWN  <urlopen error [Errno 111] Connection refused>
            see run/subject.log
  csp       DOWN  <urlopen error [Errno 111] Connection refused>
            see run/csp.log
  verifier  ok    {"service": "verifier", "team": "...", "spec_version": "1.0"}
  rp        ok    {"service": "rp", ...}

2 of 4 not answering
```

`run/subject.log` then names the cause — `ModuleNotFoundError: No module named
'fastapi'`. With the dependencies installed all four report `ok` and the last
line reads `4 of 4 up: subject csp verifier rp`.

Start or stop one at a time by naming it: `sh scripts/run_all.sh rp`,
`sh scripts/stop_all.sh rp`.

### 1.5 Smoke test

```bash
cp team.json team.local.json      # then edit the four URLs to 127.0.0.1
sh .claude/skills/lab1-conformance/scripts/smoke.sh team.local.json
```

Ten seconds, and it separates a deployment problem from a model problem. It
checks the four `/health` values, that `GET /` is public, that `/protected`
returns `401` **with** `WWW-Authenticate`, and that every `/transcript` is
valid JSON with sub-second timestamps.

### 1.6 Unit tests

```bash
python3 -m unittest discover -s tests -t .
```

Expected: `Ran 69 tests ... OK (skipped=10)`. The ten skips are Partner B's
cross-review tests for Partner A's services; they run when those services are
up:

```bash
LAB1_SUBJECT_URL=http://127.0.0.1:4100 LAB1_CSP_URL=http://127.0.0.1:4101 \
    python3 -m unittest discover -s tests -t .
```

The suite never touches a running deployment — each test starts its own
services on ephemeral ports.

### 1.7 Conformance probe

```bash
python3 conformance_probe.py --config team.local.json --verbose
```

Expected **today**, with all four services running: `12 of 24 checks passed,
5.0 / 10`, with all seven `H-*` and all four `N-*` failing because `POST /run`
answers `404`. If Partner A's two are not running it is `9 of 24` instead —
the three `S-*`/`P-*` checks that need them fail as well. Once `POST /run`
exists and follows the sequence in
[`decisions.md`](decisions.md#what-post-run-has-to-do-scenario-by-scenario),
the same command scores 24 of 24 — that has been measured with a stand-in
driver, so the gap really is only `POST /run` plus the CSP's enrollment and
binding.

---

## Part 2 — On the lab server

No sudo. Everything runs from your home directory.

### 2.1 Deploy

```bash
ssh <you>@daily-server.research.colostate.edu
git clone https://github.com/RoZo1239/syse-549-project-1.git
cd syse-549-project-1
cp .env.example .env && $EDITOR .env      # tokens, TEAM, HOST=0.0.0.0, your ports
pip install --user -r requirements.txt
sh scripts/run_all.sh
```

`tmux` instead of `nohup` if you want to watch them:
`tmux new -s lab1` then a pane per service.

### 2.2 Confirm it is reachable

On the server:

```bash
for p in 4100 4101 4102 4103; do curl -s localhost:$p/health; echo; done
```

Then **from a different campus machine** — this is the step teams skip:

```bash
curl -s http://daily-server.research.colostate.edu:4102/health
```

Off campus, connect the VPN first.

| Symptom | Cause | Fix |
|---|---|---|
| Works on the server, refused from campus | bound to `127.0.0.1` | set `HOST=0.0.0.0` in `.env`, restart |
| Something answers but it is not your service; `Server:` says nginx | a reverse proxy is in front of your port | check course announcements before debugging your own code |
| `Address already in use` in `run/<service>.log` | another process, or a previous run | `sh scripts/stop_all.sh`, then check the port is really free |

### 2.3 Point the probe at the deployment and save the result

Edit `team.json` so the four URLs are the server's hostname and your claimed
ports, then:

```bash
python3 conformance_probe.py --config team.json --verbose
python3 conformance_probe.py --config team.json --json result.json
```

`result.json` from a run against the **deployed** system is a required
deliverable. Commit it.

---

## Part 3 — Driving the flow by hand

Until `POST /run` exists this is how to see all five steps, and it is also the
live demo. Run it from the repo so `shared.pwhash` is importable.

```bash
export V=http://127.0.0.1:4102 R=http://127.0.0.1:4103
export RUN=demo-happy_path-$(python3 -c "import secrets;print(secrets.token_hex(3))")
export CANARY=CANARY-demo01
export BIND_TOKEN=$(grep '^LAB1_CSP_BINDING_TOKEN=' .env | cut -d= -f2)
curl -sS -X POST $V/reset > /dev/null && curl -sS -X POST $R/reset > /dev/null
```

**Step 2 — the CSP binds the authenticator.** (Steps 1 and 2 are the CSP's;
this call is the half of step 2 that reaches the Verifier.)

```bash
curl -sS -X POST $V/binding -H 'Content-Type: application/json' \
  -H "X-Lab1-Binding-Token: $BIND_TOKEN" \
  -d "{\"run_id\":\"$RUN\",\"identifier\":\"alice\",\"verifier_record\":$(python3 -c "import json;from shared.pwhash import hash_secret;print(json.dumps(hash_secret('$CANARY')))")}"
# {"bound": true, "identifier": "alice"}
```

**Step 3 — the RP demands authentication.** Narrate RFC 9110 §15.5.2 here.

```bash
curl -sS -i -H "X-Run-Id: $RUN" $R/protected | grep -iE '^HTTP/|^WWW-Authenticate'
# HTTP/1.1 401 Unauthorized
# WWW-Authenticate: Lab1-Session realm="lab1-rp"
```

**Step 4 — the claimant proves control.**

```bash
export ASSERTION=$(curl -sS -X POST $V/authenticate -H 'Content-Type: application/json' \
  -d "{\"run_id\":\"$RUN\",\"identifier\":\"alice\",\"authenticator_output\":\"$CANARY\"}" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['assertion'])")
```

**Step 5 — the RP validates the assertion with the Verifier, then serves it.**

```bash
export SESSION=$(curl -sS -X POST $R/session -H 'Content-Type: application/json' \
  -d "{\"run_id\":\"$RUN\",\"assertion\":\"$ASSERTION\"}" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['session'])")
curl -sS -H "Authorization: Lab1-Session $SESSION" $R/protected
# {"resource": "protected", "subscriber": "alice", ...}
```

### The denials — pick two for the demo

```bash
# skip_verifier: a self-asserted identity, no Verifier involved
curl -sS -o /dev/null -w 'self-asserted identity     -> %{http_code}\n' \
  -X POST $R/session -H 'Content-Type: application/json' \
  -d "{\"run_id\":\"$RUN\",\"identifier\":\"alice\"}"

# replay: log out, then reuse the same credential
curl -sS -X POST $R/logout -H "Authorization: Lab1-Session $SESSION" -d '{}' > /dev/null
curl -sS -o /dev/null -w 'reused session credential  -> %{http_code}\n' \
  -H "Authorization: Lab1-Session $SESSION" $R/protected

# wrong authenticator, and an identifier that never existed - identical answers
curl -sS -X POST $V/authenticate -H 'Content-Type: application/json' \
  -d "{\"run_id\":\"$RUN\",\"identifier\":\"alice\",\"authenticator_output\":\"wrong\"}"
curl -sS -X POST $V/authenticate -H 'Content-Type: application/json' \
  -d "{\"run_id\":\"$RUN\",\"identifier\":\"ghost\",\"authenticator_output\":\"wrong\"}"
# both: 401 {"error": "authentication_failed"} - byte for byte the same
```

All four return `401`. Verified from a clean clone.

### Show the transcript

```bash
python3 - "$RUN" <<'PY'
import json, sys, urllib.request
run = sys.argv[1]; events = []
for name, port in (("csp", 4101), ("verifier", 4102), ("rp", 4103)):
    try:
        doc = json.load(urllib.request.urlopen("http://127.0.0.1:%d/transcript" % port))
    except Exception as exc:
        print("%-8s unreachable: %s" % (name, exc)); continue
    events += [dict(e, svc=name) for e in doc["events"] if e["run_id"] == run]
for e in sorted(events, key=lambda e: e["ts"]):
    print("%s  step %d  %-10s %-8s %s" % (e["ts"], e["step"], e["actor"], e["outcome"], e["svc"]))
PY
```

Observed, in timestamp order:

```
2026-09-12T02:14:46.255Z  step 2  csp        success  verifier
2026-09-12T02:14:46.262Z  step 3  subscriber success  rp
2026-09-12T02:14:46.339Z  step 4  claimant   success  verifier
2026-09-12T02:14:46.355Z  step 5  verifier   success  verifier
2026-09-12T02:14:46.356Z  step 5  rp         success  rp
2026-09-12T02:14:46.392Z  step 5  rp         success  rp
```

The last line is `/protected` being served; the one before it is the session
being established. That `actor` column is the
Applicant → Subscriber → Claimant progression the probe checks as `H-ROL`;
`applicant` appears once the CSP records step 1.

---

## Part 4 — Before the presentation

```bash
sh .claude/skills/lab1-adversary/scripts/attack_curls.sh team.json   # adversarial hour
sh .claude/skills/lab1-review/scripts/hygiene_scan.sh .              # before zipping
```

The hygiene scan will report two known items: `.env` on disk, which is
gitignored and must be excluded from the zip, and a "private key material"
hit on the scanner itself, which is the script matching its own search
pattern. `result.json` must be present from a **deployed** run.

Checklist for the slot itself:

- [ ] all four services already running before the slot begins
- [ ] reachable from a machine that is not the server
- [ ] `sh scripts/run_all.sh` output saved or on screen — it is the fastest proof they are up
- [ ] a fresh `run_id` for the live demo, and `/reset` sent first
- [ ] the probe run and `result.json` written
