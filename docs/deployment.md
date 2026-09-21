# Deployment and test procedure

Every command below has been run from a clean clone with all four services up.
Where a result depends on something not finished yet, the expected output says
so.

**Status this procedure was last verified against:** all four services
complete, all five scenarios working, `85 tests ... OK` and **24 of 24 checks,
10.0 / 10** from the probe with the four running on one host. The deployment on
`daily-server` last scored **21 of 24** — same code, so that gap is a
deployment difference and part 2 is where it gets chased, not the services.

---

## Where each part runs

There is no build step: the services run from the checkout, so nothing is
produced locally and copied up. **You can do all of this on the server.**

| | Where | Why |
|---|---|---|
| Part 1 | your machine, **optional** | faster to iterate while writing code; skip it if you just want the system up |
| Part 2.0 first half | the server | is the port free |
| Part 2.0 second half | **your laptop, on campus or VPN** | proving a port is reachable *from elsewhere* cannot be done from the server itself |
| Part 2.1 | the server | clone, configure, start |
| Part 2.2 | both | `localhost` on the server, then the hostname from your laptop |
| Part 2.3, the probe | **your laptop** | a probe run on the server can pass while the firewall blocks everyone else; `result.json` should come from the path a grader would use |
| Part 3, the flow by hand | the server | it calls `127.0.0.1` and imports `shared.pwhash` |
| Part 4 | the server, then your laptop for the demo | |
| The frontend | wherever you are demoing from | it is a dev server on `:5173` that proxies to the four; it is **not** part of the graded contract |

The probe and the tests are standard-library Python, so your laptop needs a
clone of the repo and nothing else installed.

---

## Part 1 — Local, on your own machine (optional)

### 1.1 Prerequisites

```bash
python3 --version      # 3.8 or newer
curl --version
```

Partner B's services (`verifier`, `rp`), the whole test suite and every script
in `scripts/` are standard library only. Partner A's services (`subject`,
`csp`) are FastAPI apps and need four packages. The React frontend needs
Node.js, and only if you want it — nothing graded depends on it.

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
chmod 600 .env
```

The `chmod` matters on the lab server: it is a shared machine, and the default
umask leaves new files readable by every other account on it. `.env` holds both
shared tokens, and anyone who can read the binding token can bind an
authenticator to any identifier — which is to say, become any subscriber.

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

The script prints a `== next ==` block pointing at the three scripts in 1.5.

### 1.4b The React frontend (optional, and never graded)

```bash
cd frontend && npm install && cd ..
sh scripts/run_all.sh subject csp verifier rp frontend
```

Then open <http://localhost:5173>. Sign up (CSP), log in (Verifier then RP),
read the protected resource (RP) — the same five steps a browser-shaped way.

Two things to know before demoing it. Vite proxies `/api/csp`,
`/api/verifier` and `/api/rp` to `127.0.0.1:4101-4103`
(`frontend/vite.config.js`), so the browser stays same-origin and never hits
the backends' missing `OPTIONS` handling; and `frontend` is deliberately **not**
in the default set, so `sh scripts/run_all.sh` on its own still prints exactly
`4 of 4 up: subject csp verifier rp`, which is the line worth screenshotting.

Without `npm install` the script says so and starts the other four anyway:

```
  frontend NOT started - run 'npm install' in frontend/ first
```

### 1.4c Running the frontend *on the server*

Two things bite here and neither is obvious from the npm output.

**Port 5173 is not a port we claimed.** The lab's ground rules say to bind
only the four ports on our Discussion post, and 5173 is outside 4100–4103.
Vite's dev server binds `localhost` by default, which is exactly right on a
shared machine: nothing unclaimed is exposed. **Do not add `--host`.** Reach
it over an SSH tunnel from your own machine instead:

You need **two terminals**: `ssh -N` gives you no shell, so nothing can be
started in the tunnel's window.

```bash
# terminal 1, ON THE SERVER
cd ~/syse-549-project-1
sh scripts/run_all.sh frontend               # port from .env
#   frontend  ok    http://127.0.0.1:5173      <- tunnel to THIS

# terminal 2, on your laptop
ssh -N -L 5173:127.0.0.1:5173 <you>@daily-server.research.colostate.edu
```

**Setting the port.** `FRONTEND_PORT` in your `.env` is the durable place;
`VITE_PORT=... sh scripts/run_all.sh frontend` overrides it for one run.
`run_all.sh` prints the URL it actually bound, so tunnel to that rather than
to what you assumed.

**Why the default sits outside 4100–4199.** We claimed four ports and all four
are in use by the four services — there is no spare inside our block. Any
other port in the lab's range belongs to the team that claimed that block, and
§4.4 is explicit: *"Do not bind to ports you did not claim. Doing so will
break another team's demonstration."* Outside the range there is no claim to
collide with. If you want one in-range, claim a fifth on the Discussion board
first and then set `FRONTEND_PORT` to it — the machinery does not care which
number it is.

**Pick a different one per person.** Loopback on a shared host is not
per-user: if both partners run a dev server, the second one collides with the
first, and a tunnel aimed at 5173 reaches whichever one won — silently, and
possibly the other person's. Agree on one each (5173 and 5174, say) and tunnel
to your own. The config sets `strictPort`, so a collision is a startup error
rather than Vite quietly moving to the next port and binding something else
you did not claim.

#### `channel N: open failed: connect failed: Connection refused`

The tunnel is fine — SSH connected and opened the channel. That message comes
from the *server* end, and it means nothing is listening on `127.0.0.1:<port>`
there. In order of likelihood:

```bash
# on the server
tail -20 ~/syse-549-project-1/run/frontend.log   # did it start, or fail?
ss -tln | grep 517                               # is anything listening?
```

- **It never started.** `ssh -N` has no shell; the dev server has to be
  launched from a separate session.
- **It failed on startup.** Almost always esbuild's blocked postinstall —
  `npm rebuild esbuild`, then start it again.
- **It is on a different port.** With `strictPort` it now errors instead, but
  an older checkout would have moved to 5174 and said so in a line that is
  easy to miss. `tail` the log and tunnel to what it actually printed.

A partner already holding the port does *not* produce this error: you would
reach their page instead of a refusal.

Then open <http://localhost:5173> on your laptop. The browser is yours, the
services are the server's, and no extra port is published on a machine other
teams are sharing.

The alternative — run the frontend on your laptop and point it at the
server's four services — is in 1.4b:
`VITE_API_HOST=daily-server.research.colostate.edu npm run dev`. That one puts
the traffic on a real interface for packet capture; the tunnel keeps it on
loopback. Pick by which you need.

**npm 11 blocks esbuild's postinstall.** The install prints:

```
npm warn install-scripts   esbuild@0.21.5 (postinstall: node install.js)
```

That postinstall is what puts esbuild's platform binary in place, and Vite
will not start without it. Approve it once:

```bash
npm install-scripts approve esbuild   # npm 11+
npm rebuild esbuild                   # or this, on any npm
```

Then `npm run dev` again. If it was already fine, both are harmless no-ops.

**On `npm audit`.** `npm install` reports advisories against dev
dependencies — the bundler and its transitive packages. Do **not** run
`npm audit fix --force`: it upgrades Vite across a major version and will
break the proxy config this UI depends on. Nothing in the graded contract
ships any of it; the dev server is a local tool, not a deployed service. That
is a defensible answer and a better one than a broken build, but say it out
loud rather than leaving it unmentioned.

### 1.5 Watch it actually run

Three scripts, in the order you will reach for them.

**`walkthrough.py` — one Figure 3 step per screen.** This is the one to use
live. `POST /run` does all five steps in one call and answers with a verdict,
which is what the probe wants and the opposite of what an audience or a
debugger needs.

```bash
python3 scripts/walkthrough.py                  # happy_path, pausing at each step
python3 scripts/walkthrough.py skip_verifier    # or any of the five scenarios
python3 scripts/walkthrough.py --all            # all five, in order
python3 scripts/walkthrough.py --no-pause       # straight through
```

Each screen shows the request that goes out, the status and body that come
back, the role transition it causes, and one sentence tying it to SP 800-63-4
or RFC 9110 — which is the "tied to authoritative guidance" the Live Demo row
of the rubric asks for. The authenticator secret is never printed, only its
length. It ends with the merged transcript for that run.

**`trace.py` — all four transcripts, merged.** No single `/transcript` shows
the flow, because each service records only the steps it took part in.

```bash
python3 scripts/trace.py --last         # the most recent run
python3 scripts/trace.py <run_id>       # one run, e.g. one the probe drove
python3 scripts/trace.py --json         # the merged events, for a script
```

It sorts by `ts` exactly the way the probe's `H-ORD` check does, so the table
is the order that gets graded rather than a tidier one, and it restates
`H-ORD`, `H-ROL` and `X-FLD` underneath in plain words.

**`diagnose.py` — a failed check, turned into the next command.**

```bash
python3 scripts/diagnose.py result.json       # explain everything that failed
python3 scripts/diagnose.py --check H-ORD     # or look one up directly
python3 scripts/diagnose.py --all             # the whole table of 24
```

### 1.5b Driving the five steps from the browser, and capturing them

The React UI walks the same five steps a person would walk. It is worth
knowing exactly which request produces which arrow, because a browser does
them in a different order than the probe does.

| Figure 3 step | Where in the UI | Request the browser sends |
|---|---|---|
| **3** authentication request | landing on `/` with no session | `GET /api/rp/protected`, no credential → `401` + `WWW-Authenticate` |
| **1** proofing and enrollment | the Sign up form | `POST /api/csp/apply` |
| **2** authenticator issuance | clicking the activation link | `GET /api/csp/activate?…` → the CSP then `POST`s `/binding` to the Verifier |
| **4** authentication process | the Log in form | `POST /api/verifier/authenticate` |
| **5** authenticated session | immediately after, and on the page that follows | `POST /api/rp/session`, then `GET /api/rp/protected` with the session |

**Step 3 comes first, not third.** The probe's Subject agent runs the steps in
their numbered order because it is a script. A human hits the wall before they
have an account, which is why `scripts/trace.py` on a browser run shows
`[3, 1, 2, 2, 4, 5, 5, 5]` and reports `H-ORD: NO`. That is correct for a
person and would be a failure for the probe — the two drive the system
differently and the transcript records what actually happened, which is the
point of having one. Say this out loud if you trace a browser run in the demo.

**If no mail server is configured**, step 2 is not a dead end: the CSP returns
the enrollment token in the `/apply` response as well as mailing it, and the
Sign up page offers the activation link directly. That is deliberate — the
graded contract is machine-to-machine and must not need a working SMTP
account.

**Correlating the browser with the transcripts.** The Sign up and Protected
pages both print the `run_id` they used. Copy it:

```bash
python3 scripts/trace.py web-8f3a1c2e-...
```

#### Packet capture

The lab server deliberately serves cleartext HTTP so this works. Three things
decide whether you actually see anything.

**1. Point the frontend at the server, not at loopback.** By default the Vite
proxy targets `127.0.0.1`, so every request — browser to Vite, Vite to the
services — is loopback traffic. Wireshark can only see that on the loopback
interface (`lo` on Linux, `lo0` on macOS, and on Windows only if Npcap was
installed with "support loopback traffic capture" ticked). To put the five
steps on a real interface instead:

```bash
cd frontend
VITE_API_HOST=daily-server.research.colostate.edu npm run dev
```

Now browser → Vite is still loopback, but Vite → the four services crosses the
network in cleartext and captures normally.

**2. Two hops are loopback whichever way you do it**, by design:

- CSP → Verifier `POST /binding` (step 2)
- RP → Verifier `POST /introspect` (step 5)

Both go over `127.0.0.1` on the server, because
`shared/config.py::internal_endpoint_for()` sends them there on purpose — the
assertion has no business crossing the campus network. To see them you have to
capture on the server's loopback interface:

```bash
# on the server
tcpdump -i lo -s0 -w lab1-internal.pcap 'tcp port 4102'
```

Then open `lab1-internal.pcap` in Wireshark. It is worth doing once: the
`/introspect` exchange is the single most important pair of packets in the
whole system, because it is the reason `skip_verifier` fails.

**3. Useful Wireshark display filters:**

```
http                                     # everything
tcp.port >= 4100 && tcp.port <= 4103     # just the four services
http.request.uri contains "authenticate" # step 4
http.response.code == 401                # every refusal, including step 3
http.www_authenticate                    # the RFC 9110 15.5.2 challenge
```

**What you will see in the clear, and should say so:** the password, on
`POST /apply` and `POST /authenticate`. The assertion handle. The session
token. All of it, because this is port-80 HTTP with no TLS — which the server
notes ask for, so the traffic is readable. It is also the honest answer to
"what is the weakest point in your system": everything below the application
layer. `docs/analysis.md` §3 says this at more length, and a capture on screen
is the most convincing way to make the point.

### 1.5c Smoke test

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

Expected: `Ran 85 tests ... OK (skipped=10)`. The ten skips are Partner B's
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

Expected with all four services running on one host: `24 of 24 checks passed,
10.0 / 10`. If Partner A's two are not running it drops to `9 of 24` — the
`S-*` and `P-*` checks that do not need them still pass, and everything that
drives a scenario fails.

Anything in between means a specific check is unhappy, and the answer is not to
start editing services:

```bash
python3 conformance_probe.py --config team.local.json --json result.json
python3 scripts/diagnose.py result.json
```

That names what each failed check was asking and the command to run next. The
five scenarios and the two easy-to-miss ordering constraints are in
[`decisions.md`](decisions.md#the-five-scenarios-as-sequences).

---

## Part 2 — On the lab server

No sudo. Everything runs from your home directory.

### 2.0 Claim the ports, and prove they are usable

There is no way to reserve a port on the machine — the server notes say the
per-user assignments are "a convention, not something the operating system
enforces". Claiming is three things: the post on the Canvas discussion, this
check, and then binding the ports by leaving your services running.

**Team hayagreeva-jonathan claims 4100–4103** (subject 4100, CSP 4101,
verifier 4102, RP 4103).

First, confirm nothing already holds them:

```bash
ss -tln | awk '{print $4}' | grep -E ':(4100|4101|4102|4103)$' || echo "all four free"
```

Then the check that actually matters, because the server's firewall rule
admits campus traffic to `4000:4009` only, and says nothing about 4100–4199.
On the server:

```bash
mkdir -p ~/port-check && cd ~/port-check
python3 -m http.server 4100 --bind 0.0.0.0
```

From a **different campus machine** (or over the VPN):

```bash
curl -sv --max-time 8 http://daily-server.research.colostate.edu:4100/
```

| What comes back | Meaning | Next |
|---|---|---|
| A directory listing | the port is open from campus | stop the listener, go to 2.1 |
| `Connection timed out` or `refused` | the firewall does not admit this range | ask the server admin for the rule below |
| An nginx page or `Server: nginx` | nginx is answering on the port first | check course announcements |

Repeat for 4103 — it confirms the whole block, not just one port.

If the range is blocked, the admin needs one rule, matching the shape of the
one already in place for 4000–4009:

```bash
sudo ufw allow from 129.82.0.0/16 to any port 4100:4103 proto tcp
```

Until that exists, the alternative is to serve all four behind the path
already assigned to you and give the probe path-based endpoint URLs — the
probe accepts any URL, not just `host:port`. Confirm which the instructor
wants before building it.

### 2.1 Deploy

If you cloned before this branch was merged, your checkout is on `main`, which
still carries a committed `.env` with the wrong host and the 4000-4003 ports.
Switching branches will refuse while that file has local edits. Keep a copy,
drop the tracked one, then switch:

```bash
cp .env ~/lab1-env.backup && chmod 600 ~/lab1-env.backup
git checkout -- .env
git checkout claude/clever-archimedes-wzp85q
cp .env.example .env && chmod 600 .env
```

On this branch `.env` is untracked, so it will not come back on the next pull
and must never be added.


```bash
ssh <you>@daily-server.research.colostate.edu
git clone https://github.com/RoZo1239/syse-549-project-1.git
cd syse-549-project-1
cp .env.example .env && $EDITOR .env      # tokens, TEAM, HOST=0.0.0.0, your ports
pip install --user -r requirements.txt
sh scripts/run_all.sh
```

Expect `4 of 4 up: subject csp verifier rp`, then the `== next ==` block. If a
service is DOWN, the line under it names the reason and `run/<service>.log` has
the rest — a missing token, a port already held, a missing package.

Prove the model works on the server before worrying about the network:

```bash
python3 scripts/walkthrough.py --no-pause --all
```

All five scenarios, every request and response on screen. If those pass on
loopback and the probe still scores low from your laptop, the problem is 2.2,
not the code.

`tmux` instead of `nohup` if you want to watch them:
`tmux new -s lab1` then a pane per service.

The frontend is not deployed to the server. It is a Vite dev server that
proxies to `127.0.0.1`, so run it wherever you are demoing from, against a
local copy of the four services — or skip it. Nothing graded touches it.

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

If it is not 24 of 24, do not start editing services — the same code scores 24
of 24 on one host, so a lower number here is a deployment difference. Ask the
result file what is wrong:

```bash
python3 scripts/diagnose.py result.json
```

It prints, for each failed check, what that check was actually asking, what
usually causes it, and the next command to run. `P-WWW` failing only from off
host is the signature of a proxy stripping the header; `H-ORD` is timestamp
precision; anything in `H-ST*` is usually the `run_id` not being threaded
through.

---

## Part 3 — Driving the flow by hand

**Read this second.** The live demo is `scripts/walkthrough.py` (1.5 above) or
`sh scripts/demo.sh`, which run the same five steps with the request, the
response and the NIST or RFC line on screen for each one, and without putting
the authenticator secret on a projector.

What follows is the same flow with no tooling at all — raw `curl`, one call at
a time. Keep it for two reasons: it is what you fall back to if a script
misbehaves in front of the room, and it is the honest answer when someone asks
"is the script doing something clever?" It is not. Run it from the repo so
`shared.pwhash` is importable.

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

(Or run `python3 scripts/walkthrough.py wrong_authenticator` and friends, which
show the same thing with the reasoning on screen. The raw calls are below.)

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
python3 scripts/trace.py "$RUN"
```

Observed, in timestamp order:

```
#    service   step  step_name                          actor -> peer          outcome  detail
1    csp       1     identity_proofing_and_enrollment   applicant -> csp       success  evidence accepted, subscriber account created
2    verifier  2     authenticator_enrollment_issuance  csp -> verifier        success  binding record accepted, authenticator bound...
3    csp       2     authenticator_enrollment_issuance  csp -> subscriber      success  authenticator issued and bound to the subscriber account
4    rp        3     authentication_request             subscriber -> rp       success  no session presented, authentication demanded
5    verifier  4     authentication_process             claimant -> verifier    success  authenticator control proven, single-use assertion issued
6    verifier  5     authenticated_session              verifier -> rp         success  subscriber identifier asserted to the relying party
7    rp        5     authenticated_session              rp -> verifier         success  verifier asserted the identifier, session established
8    rp        5     authenticated_session              rp -> subscriber       success  protected resource served to an authenticated session

  step order observed : [1, 2, 2, 3, 4, 5, 5, 5]
  ascending, all five : yes   (the probe's H-ORD check)
  role progression    : applicant -> subscriber -> claimant   (the probe's H-ROL check)
  secret-bearing names: none   (the probe's X-FLD check)
```

Line 8 is `/protected` being served; line 7 is the session being established.
That `actor` column is the Applicant → Subscriber → Claimant progression the
probe checks as `H-ROL`, and the three lines underneath are the probe's own
`H-ORD`, `H-ROL` and `X-FLD` restated in words. If any of them reads wrong
here, it will read wrong in the grader's run too.

Timestamps carry **microseconds**. At millisecond precision the CSP's step 2
and the Subject's step 3 tie, the probe's stable sort breaks the tie by
collection order rather than time, and `H-ORD` fails. See
[`decisions.md`](decisions.md#a5-on-timestamp-precision).

---

## Part 4 — Before the presentation

### The rehearsal

```bash
sh scripts/demo.sh
```

The whole demo segment in order: the four services up, the happy path one step
per screen, three denial scenarios, then the probe. It pauses between steps;
`sh scripts/demo.sh --no-pause` runs it straight through for a timing check.

Off campus, `team.json`'s hostname will not resolve and the probe at the end
reports 3 of 24 for a system running perfectly in front of you. Point it at a
loopback config instead:

```bash
LAB1_PROBE_CONFIG=team.local.json sh scripts/demo.sh
```

The lab asks for at least two denials; `demo.sh` shows three, because
`skip_verifier` is the one the whole architecture exists to fail, and because
`wrong_authenticator` and `unenrolled_claimant` back to back are the clearest
way to show the two refusals are identical.

### The checks

```bash
sh .claude/skills/lab1-adversary/scripts/attack_curls.sh team.json   # adversarial hour
sh .claude/skills/lab1-review/scripts/hygiene_scan.sh .              # before zipping
```

The hygiene scan will report known items that are not problems: `.env` on disk,
which is gitignored and must be excluded from the zip; `__pycache__`
directories, likewise gitignored; and a "private key material" hit on the
scanner itself, which is the script matching its own search pattern.
`result.json` must be present, from a **deployed** run.

### Checklist for the slot itself

- [ ] all four services already running before the slot begins
- [ ] reachable from a machine that is not the server
- [ ] `sh scripts/run_all.sh` output saved or on screen — the fastest proof they are up
- [ ] `sh scripts/demo.sh` rehearsed end to end, against the deployment
- [ ] a fresh `run_id` for the live demo, and `/reset` sent first
- [ ] the probe run and `result.json` written
- [ ] the frontend started too, if you are demoing it (`sh scripts/run_all.sh subject csp verifier rp frontend`)
- [ ] each partner has walked through the *other* partner's two services once

The last row is the one the rubric scores off-script, and it is the cheapest
seven points on the sheet.
