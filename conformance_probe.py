#!/usr/bin/env python3
"""
Conformance Probe - Lab 1
NIST SP 800-63-4 Non-Federated Digital Identity Model (Figure 3)

Checks that a team's four services implement the five-step identity flow and
refuse the things they are supposed to refuse. Students run this to self-test;
the instructor runs the same script to score.

Standard library only. No pip install required.

Usage:
    python3 conformance_probe.py --config team.json
    python3 conformance_probe.py --config team.json --json result.json
    python3 conformance_probe.py --config team.json --verbose

team.json:
{
  "team": "team03",
  "endpoints": {
    "subject":  "http://daily-server.research.colostate.edu:4100",
    "csp":      "http://daily-server.research.colostate.edu:4101",
    "verifier": "http://daily-server.research.colostate.edu:4102",
    "rp":       "http://daily-server.research.colostate.edu:4103"
  }
}
"""

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid

TIMEOUT = 10
SERVICES = ["subject", "csp", "verifier", "rp"]
POINTS = 10  # this probe is worth 10 of the 50 lab points

STEP_NAMES = {
    1: "identity_proofing_and_enrollment",
    2: "authenticator_enrollment_issuance",
    3: "authentication_request",
    4: "authentication_process",
    5: "authenticated_session",
}


# --------------------------------------------------------------------------
# HTTP helper
# --------------------------------------------------------------------------

def http(method, url, body=None, headers=None, timeout=TIMEOUT):
    """Return (status, headers_dict, text). status is None on transport error."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    hdrs = {"Accept": "application/json", "User-Agent": "lab1-conformance-probe/1.0"}
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)

    # Self-signed certificates are acceptable in this lab.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", "replace")
        return e.code, {k.lower(): v for k, v in e.headers.items()}, body_text
    except Exception as e:  # timeout, DNS, refused, TLS, ...
        return None, {}, "TRANSPORT ERROR: %s" % e


def get_json(status, text):
    if status is None:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


# --------------------------------------------------------------------------
# Result plumbing
# --------------------------------------------------------------------------

class Probe:
    def __init__(self, endpoints, verbose=False):
        self.ep = endpoints
        self.verbose = verbose
        self.results = []
        self.transcripts = {}   # service -> list of events (all runs)

    def url(self, service, path):
        return self.ep[service].rstrip("/") + path

    def record(self, cid, desc, passed, detail=""):
        self.results.append({"id": cid, "check": desc, "passed": bool(passed), "detail": detail})
        if self.verbose:
            mark = "PASS" if passed else "FAIL"
            print("  [%s] %-6s %s%s" % (mark, cid, desc, (" - " + detail) if detail else ""))

    # ---------------- transcript helpers ----------------

    def fetch_transcript(self, service):
        status, _, text = http("GET", self.url(service, "/transcript"))
        payload = get_json(status, text)
        if status != 200 or not isinstance(payload, dict):
            return []
        events = payload.get("events")
        return events if isinstance(events, list) else []

    def refresh_transcripts(self):
        for s in SERVICES:
            self.transcripts[s] = self.fetch_transcript(s)

    def events_for(self, service, run_id):
        return [e for e in self.transcripts.get(service, [])
                if isinstance(e, dict) and e.get("run_id") == run_id]

    def has_step(self, service, run_id, step):
        return any(e.get("step") == step for e in self.events_for(service, run_id))

    def has_successful_step(self, service, run_id, step):
        return any(e.get("step") == step and str(e.get("outcome", "")).lower() == "success"
                   for e in self.events_for(service, run_id))

    def all_events(self, run_id):
        out = []
        for s in SERVICES:
            for e in self.events_for(s, run_id):
                e = dict(e)
                e["_service"] = s
                out.append(e)
        return out

    # ---------------- scenario driver ----------------

    def run_scenario(self, scenario, canary=None):
        run_id = "probe-%s-%s" % (scenario, uuid.uuid4().hex[:8])
        body = {"run_id": run_id, "scenario": scenario}
        if canary:
            body["canary"] = canary
        status, _, text = http("POST", self.url("subject", "/run"), body=body, timeout=30)
        payload = get_json(status, text) or {}
        time.sleep(0.4)  # let any async transcript writes land
        self.refresh_transcripts()
        return run_id, status, payload


# --------------------------------------------------------------------------
# Check groups
# --------------------------------------------------------------------------

def check_structure(p):
    """S - the four services exist, identify themselves, and can be reset."""
    for s in SERVICES:
        status, _, text = http("GET", p.url(s, "/health"))
        payload = get_json(status, text)
        ok = status == 200 and isinstance(payload, dict) and payload.get("service") == s
        detail = ""
        if status is None:
            detail = text
        elif status != 200:
            detail = "HTTP %s" % status
        elif not isinstance(payload, dict):
            detail = "body was not JSON"
        elif payload.get("service") != s:
            detail = "declared service=%r, expected %r" % (payload.get("service"), s)
        p.record("S-%s" % s[:4].upper(), "%s: GET /health identifies the service" % s, ok, detail)

    reset_ok = True
    failed = []
    for s in SERVICES:
        status, _, _ = http("POST", p.url(s, "/reset"), body={})
        if status not in (200, 204):
            reset_ok = False
            failed.append("%s=%s" % (s, status))
    p.record("S-RST", "all four services accept POST /reset", reset_ok, ", ".join(failed))


def check_public_and_denial(p):
    """P - the Relying Party serves the public resource and refuses the protected one."""
    status, _, text = http("GET", p.url("rp", "/"))
    p.record("P-PUB", "RP: GET / returns 200 with no credential",
             status == 200, "HTTP %s" % status if status != 200 else "")

    status, hdrs, text = http("GET", p.url("rp", "/protected"))
    p.record("P-401", "RP: GET /protected with no credential returns 401",
             status == 401, "got HTTP %s" % status if status != 401 else "")

    p.record("P-WWW", "RP: that 401 carries a WWW-Authenticate header (RFC 9110 15.5.2)",
             "www-authenticate" in hdrs,
             "headers present: %s" % ",".join(sorted(hdrs)) if "www-authenticate" not in hdrs else "")

    leaked = any(w in (text or "").lower() for w in ("traceback", "stack trace", "sqlite3.", "at line"))
    p.record("P-ERR", "RP: the 401 body does not leak an internal error trace", not leaked)


def check_happy_path(p, canary):
    """H - the five steps of Figure 3 actually happen, in order."""
    run_id, status, payload = p.run_scenario("happy_path", canary=canary)

    outcome = (payload or {}).get("outcome")
    p.record("H-RUN", "subject: POST /run happy_path reports success",
             status == 200 and outcome == "success",
             "HTTP %s outcome=%r" % (status, outcome) if outcome != "success" else "")

    expected = [
        ("H-ST1", "csp", 1, "step 1 identity proofing and enrollment recorded by CSP"),
        ("H-ST2", "csp", 2, "step 2 authenticator enrollment/issuance recorded by CSP"),
        ("H-ST3", "rp", 3, "step 3 authentication request recorded by RP"),
        ("H-ST4", "verifier", 4, "step 4 authentication process recorded by Verifier"),
        ("H-ST5", "rp", 5, "step 5 authenticated session recorded by RP"),
    ]
    for cid, service, step, desc in expected:
        p.record(cid, desc, p.has_step(service, run_id, step))

    # Ordering by timestamp across all four transcripts.
    evs = [e for e in p.all_events(run_id) if isinstance(e.get("step"), int) and e.get("ts")]
    evs.sort(key=lambda e: str(e["ts"]))
    seq = [e["step"] for e in evs]
    ordered = seq == sorted(seq) and len(set(seq)) >= 5
    p.record("H-ORD", "the five steps occur in ascending order by timestamp",
             ordered, "observed order: %s" % seq if not ordered else "")

    # The subject must pass through applicant -> subscriber -> claimant.
    actors = [str(e.get("actor", "")).lower() for e in evs]
    def first(a):
        return actors.index(a) if a in actors else -1
    ia, isb, ic = first("applicant"), first("subscriber"), first("claimant")
    roles_ok = ia >= 0 and isb > ia and ic > isb
    p.record("H-ROL", "subject moves Applicant -> Subscriber -> Claimant in that order",
             roles_ok, "actor sequence: %s" % actors if not roles_ok else "")

    return run_id


def check_negatives(p, canary):
    """N - the system refuses what it must refuse."""
    # (scenario, check id, description, must_have_no_successful_session)
    #
    # The replay scenario is the exception: a valid session is established first
    # and only then reused, so a successful step 5 is expected. What must fail is
    # the reuse. Every other negative case must never reach an authenticated
    # session at all.
    cases = [
        ("wrong_authenticator", "N-BAD",
         "wrong authenticator output is refused and no session is created", True),
        ("unenrolled_claimant", "N-ENR",
         "a claimant who never enrolled is refused", True),
        ("replay", "N-RPL",
         "a replayed or expired session credential is refused on reuse", False),
        ("skip_verifier", "N-SKP",
         "a subject presenting itself to the RP without the Verifier is refused", True),
    ]
    for scenario, cid, desc, no_session_required in cases:
        run_id, status, payload = p.run_scenario(scenario, canary=canary)
        outcome = (payload or {}).get("outcome")
        denied = outcome in ("denied", "refused", "failure")
        session_ok = True
        if no_session_required:
            session_ok = not p.has_successful_step("rp", run_id, 5)
        ok = denied and session_ok
        detail = ""
        if not denied:
            detail = "outcome=%r (expected denied)" % outcome
        elif not session_ok:
            detail = "RP recorded a successful step 5 for a run that should have failed"
        p.record(cid, desc, ok, detail)


def check_hygiene(p, canary):
    """X - secrets stay out of the transcript, and denial is durable."""
    p.refresh_transcripts()
    blob = json.dumps(p.transcripts).lower()
    leaked_canary = canary.lower() in blob
    p.record("X-CAN", "the authenticator secret does not appear in any transcript",
             not leaked_canary,
             "the canary value supplied by the probe was found in a transcript" if leaked_canary else "")

    risky = [w for w in ("password", "passwd", "private_key", "client_secret") if w in blob]
    p.record("X-FLD", "no obvious secret-bearing field names in transcripts",
             not risky, "found: %s" % ", ".join(risky) if risky else "")

    status, _, _ = http("GET", p.url("rp", "/protected"))
    p.record("X-DUR", "RP still refuses /protected after the failed runs",
             status == 401, "got HTTP %s" % status if status != 401 else "")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Lab 1 conformance probe (SP 800-63-4 Figure 3)")
    ap.add_argument("--config", required=True, help="path to team.json")
    ap.add_argument("--json", help="write machine-readable results here")
    ap.add_argument("--verbose", action="store_true", help="print each check as it runs")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = json.load(f)

    team = cfg.get("team", "unknown")
    endpoints = cfg.get("endpoints", {})
    missing = [s for s in SERVICES if s not in endpoints]
    if missing:
        print("config is missing endpoints for: %s" % ", ".join(missing))
        return 2

    print("=" * 68)
    print("Lab 1 Conformance Probe - SP 800-63-4 Non-Federated Identity Model")
    print("Team: %s" % team)
    print("=" * 68)
    for s in SERVICES:
        print("  %-9s %s" % (s + ":", endpoints[s]))
    print()

    canary = "CANARY-" + uuid.uuid4().hex[:12]
    p = Probe(endpoints, verbose=args.verbose)

    if args.verbose:
        print("Structure")
    check_structure(p)
    if args.verbose:
        print("Public access and denial")
    check_public_and_denial(p)
    if args.verbose:
        print("Happy path")
    check_happy_path(p, canary)
    if args.verbose:
        print("Negative scenarios")
    check_negatives(p, canary)
    if args.verbose:
        print("Hygiene")
    check_hygiene(p, canary)

    total = len(p.results)
    passed = sum(1 for r in p.results if r["passed"])
    score = round(POINTS * passed / total, 1) if total else 0.0

    print()
    print("-" * 68)
    for r in p.results:
        mark = "pass" if r["passed"] else "FAIL"
        line = "  %-4s %-7s %s" % (mark, r["id"], r["check"])
        print(line)
        if not r["passed"] and r["detail"]:
            print("           -> %s" % r["detail"])
    print("-" * 68)
    print("  %d of %d checks passed" % (passed, total))
    print("  Probe score: %.1f / %d" % (score, POINTS))
    print("-" * 68)

    if args.json:
        with open(args.json, "w") as f:
            json.dump({
                "team": team,
                "endpoints": endpoints,
                "checks_passed": passed,
                "checks_total": total,
                "probe_score": score,
                "probe_points_possible": POINTS,
                "results": p.results,
            }, f, indent=2)
        print("  Wrote %s" % args.json)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
