#!/usr/bin/env python3
"""Walk one scenario through the four services, one step at a time.

This is the presentation tool. `POST /run` on the Subject agent does the same
five steps, but it does them in one call and reports only the verdict — which
is what the conformance probe wants and the opposite of what an audience
needs. Here every hop is its own screen: the request that goes out, the status
and body that come back, the transcript line it produced, and one sentence
tying it to SP 800-63-4 or RFC 9110.

    python3 scripts/walkthrough.py                     # happy_path, pausing
    python3 scripts/walkthrough.py wrong_authenticator
    python3 scripts/walkthrough.py --all               # all five, in order
    python3 scripts/walkthrough.py --no-pause          # don't wait for Enter

Scenarios: happy_path, wrong_authenticator, unenrolled_claimant, replay,
skip_verifier — the same five the probe drives, defined in
services/subject/flow.py.

The authenticator secret is never printed. It is shown as its length, which
is the only thing about it an audience needs to see.
"""

import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import config  # noqa: E402
from shared.validate import MIN_OUTPUT_LEN  # noqa: E402
from scripts import trace  # noqa: E402

SESSION_SCHEME = "Lab1-Session"
SCENARIOS = ("happy_path", "wrong_authenticator", "unenrolled_claimant",
             "replay", "skip_verifier")

# Never printed, only measured. A demo that puts the secret on a projector has
# already failed the hygiene check it is about to claim to pass.
SECRET_FIELDS = ("plaintext", "authenticator_output", "canary", "password")

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
GREEN, RED, YELLOW = "\033[32m", "\033[31m", "\033[33m"


def colour(text, code):
    return text if os.environ.get("NO_COLOR") else code + text + RESET


class Walkthrough:
    def __init__(self, pause=True):
        self.pause = pause
        self.csp = config.endpoint_for("csp")
        self.verifier = config.endpoint_for("verifier")
        self.rp = config.endpoint_for("rp")
        self.run_id = None
        self.step_no = 0

    # -- presentation -------------------------------------------------------
    def banner(self, title, hop, why):
        self.step_no += 1
        line = "=" * 74
        print()
        print(colour(line, BOLD))
        print(colour(" %s" % title, BOLD))
        print(colour(" %s" % hop, DIM))
        print(colour(line, BOLD))
        print(" %s" % why)

    def wait(self):
        if not self.pause:
            return
        try:
            input(colour("\n   [Enter] to continue ", DIM))
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0)

    def show_request(self, method, url, payload=None, headers=None):
        print()
        print("   %s %s %s" % (colour("-->", YELLOW), method, url))
        for key, value in sorted((headers or {}).items()):
            if key.lower() == "authorization":
                scheme, _, token = value.partition(" ")
                value = "%s %s...%s" % (scheme, token[:6], token[-4:])
            print("       %s: %s" % (key, value))
        if payload is not None:
            print("       %s" % json.dumps(self.redact(payload)))

    def show_response(self, status, headers, body):
        mark = GREEN if 200 <= status < 300 else RED if status >= 400 else YELLOW
        print("   %s HTTP %s" % (colour("<--", mark), colour(str(status), mark)))
        for name in ("WWW-Authenticate",):
            if name.lower() in headers:
                print("       %s: %s" % (name, headers[name.lower()]))
        if body:
            print("       %s" % json.dumps(self.redact(body))[:400])

    @staticmethod
    def redact(obj):
        """Replace every secret-bearing value with its length. Never its content."""
        if not isinstance(obj, dict):
            return obj
        out = {}
        for key, value in obj.items():
            if key in SECRET_FIELDS and isinstance(value, str):
                out[key] = "<redacted, %d chars>" % len(value)
            elif key in ("session", "assertion", "token") and isinstance(value, str):
                # Not secrets in the 800-63 sense, but long and unreadable on a
                # projector; the first characters are enough to follow one.
                out[key] = value[:8] + "..." if len(value) > 12 else value
            else:
                out[key] = value
        return out

    def note(self, text):
        print("   %s %s" % (colour("note:", DIM), text))

    # -- HTTP ---------------------------------------------------------------
    def call(self, method, url, payload=None, headers=None, show=True):
        """One request, printed both ways. Returns (status, headers, body)."""
        if show:
            self.show_request(method, url, payload, headers)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        hdrs = {"Accept": "application/json"}
        if data is not None:
            hdrs["Content-Type"] = "application/json"
        hdrs.update(headers or {})
        request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=10) as response:
                status, raw = response.status, response.read()
                head = {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
            head = {k.lower(): v for k, v in exc.headers.items()}
        except (urllib.error.URLError, OSError) as exc:
            print("   %s %s is not answering (%s)"
                  % (colour("<--", RED), url, getattr(exc, "reason", exc)))
            raise SystemExit(
                "\nStart the services first:  sh scripts/run_all.sh\n")
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            body = {}
        if show:
            self.show_response(status, head, body if isinstance(body, dict) else {})
        return status, head, body if isinstance(body, dict) else {}

    # -- the steps ----------------------------------------------------------
    def step1_apply(self, identifier, secret):
        self.banner(
            "STEP 1 - Identity proofing and enrollment",
            "Applicant  ->  CSP      (SP 800-63-4 Figure 3, step 1)",
            "The applicant presents evidence and the CSP creates a subscriber\n"
            " account. Nobody is authenticated yet: proofing answers \"is this a\n"
            " real person we can reach?\", not \"is this them right now?\".",
        )
        status, _, body = self.call(
            "POST", self.csp + "/apply",
            {"run_id": self.run_id, "email": identifier, "plaintext": secret},
        )
        self.note("proofing here is control of an email address - IAL1, "
                  "self-asserted with a confirmable address.")
        self.note("the secret was hashed with scrypt on arrival (shared/pwhash.py) "
                  "and is not stored in the clear anywhere.")
        self.wait()
        return body.get("token") if status == 201 else None

    def step2_subscribe(self, identifier, token):
        self.banner(
            "STEP 2 - Authenticator enrollment and issuance",
            "CSP  ->  Subscriber     (SP 800-63-4 Figure 3, step 2)",
            "Presenting the enrollment token is what turns the Applicant into a\n"
            " Subscriber. The CSP then pushes the salted digest to the Verifier,\n"
            " so the Verifier can check the authenticator without the CSP ever\n"
            " being asked \"is this password right?\".",
        )
        status, _, body = self.call(
            "POST", self.csp + "/subscribe",
            {"run_id": self.run_id, "email": identifier, "token": token},
        )
        self.note("ROLE CHANGE: Applicant -> Subscriber.")
        self.note("what crossed to the Verifier was the scrypt record, never the secret.")
        self.wait()
        return status == 200

    def step3_demand(self):
        self.banner(
            "STEP 3 - Authentication request",
            "RP  ->  Claimant        (SP 800-63-4 Figure 3, step 3)",
            "The subscriber asks for the protected resource with no session. The\n"
            " Relying Party refuses and says where to authenticate. RFC 9110\n"
            " 15.5.2 requires the WWW-Authenticate header on that 401 - it is the\n"
            " single most commonly omitted line in this whole lab.",
        )
        status, head, body = self.call(
            "GET", self.rp + "/protected", headers={"X-Run-Id": self.run_id})
        self.note("ROLE CHANGE: Subscriber -> Claimant. The 401 is what makes it.")
        if "enroll_at" in body:
            self.note("the 401 names the CSP (enroll_at) but the RP never calls it - "
                      "Figure 3 has no RP -> CSP arrow, so that is a signpost, "
                      "not a connection.")
        self.wait()
        return status == 401

    def step4_authenticate(self, identifier, secret, label="the enrolled secret"):
        self.banner(
            "STEP 4 - Authentication process",
            "Claimant  <->  Verifier (SP 800-63-4 Figure 3, step 4)",
            "The claimant proves control of the authenticator and the VERIFIER\n"
            " decides - not the CSP, and not the Relying Party. What comes back is\n"
            " an opaque, single-use handle that means nothing on its own.",
        )
        print("   %s presenting %s" % (colour("::", DIM), label))
        status, _, body = self.call(
            "POST", self.verifier + "/authenticate",
            {"run_id": self.run_id, "identifier": identifier,
             "authenticator_output": secret},
        )
        if status != 200:
            self.note("one denial body for every way of failing: wrong secret and "
                      "unknown identifier are indistinguishable from out here, so "
                      "this is not an account-enumeration oracle.")
        self.wait()
        return body.get("assertion") if status == 200 else None

    def step5_session(self, assertion, label="the Verifier's assertion"):
        self.banner(
            "STEP 5 - Authenticated session",
            "Verifier  ->  RP         (SP 800-63-4 Figure 3, step 5)",
            "SP 800-63B-4: on success the verifier asserts the subscriber's\n"
            " identifier to the RP. Here the RP redeems the handle by calling the\n"
            " Verifier's /introspect - so the identifier comes from the Verifier,\n"
            " never from the request body. That is why skip_verifier cannot work.",
        )
        print("   %s presenting %s" % (colour("::", DIM), label))
        status, _, body = self.call(
            "POST", self.rp + "/session",
            {"run_id": self.run_id, "assertion": assertion},
        )
        self.wait()
        return body.get("session") if status == 201 else None

    def read_protected(self, session, title="Reading the protected resource"):
        self.banner(
            title,
            "Subscriber  ->  RP       (the resource they wanted all along)",
            "The RP is the policy enforcement point in SP 800-207 terms: it\n"
            " enforces the decision, the Verifier made it.",
        )
        status, _, body = self.call(
            "GET", self.rp + "/protected",
            headers={"Authorization": "%s %s" % (SESSION_SCHEME, session),
                     "X-Run-Id": self.run_id})
        self.wait()
        return status

    def logout(self, session):
        self.banner(
            "Logout - revoking the session",
            "Subscriber  ->  RP",
            "Logout answers the same way whether or not the credential was real.\n"
            " A logout that said \"no such session\" would be a free oracle for\n"
            " testing stolen tokens.",
        )
        self.call("POST", self.rp + "/logout", {"run_id": self.run_id},
                  headers={"Authorization": "%s %s" % (SESSION_SCHEME, session)})
        self.wait()

    # -- scenarios ----------------------------------------------------------
    def run(self, scenario):
        self.run_id = "demo-%s-%s" % (scenario, secrets.token_hex(4))
        self.step_no = 0
        identifier = "demo-%s@example.test" % secrets.token_hex(4)
        # A real 800-63B-4 3.1.1.2 password: 15 characters minimum, no second
        # factor anywhere in this system.
        secret = "demo-secret-" + secrets.token_hex(8)
        assert len(secret) >= MIN_OUTPUT_LEN

        print()
        print(colour("#" * 74, BOLD))
        print(colour("#  scenario: %s" % scenario, BOLD))
        print(colour("#  run_id:   %s" % self.run_id, BOLD))
        print(colour("#" * 74, BOLD))

        verdict = getattr(self, "_" + scenario)(identifier, secret)

        print()
        print(colour("=" * 74, BOLD))
        expected = "success" if scenario == "happy_path" else "denied"
        mark = GREEN if verdict == expected else RED
        print(" verdict: %s   (expected %s)"
              % (colour(verdict.upper(), mark), expected))
        print(colour("=" * 74, BOLD))

        self.wait()
        print()
        print(colour(" The same run, as the four transcripts record it:", BOLD))
        events = trace.merged(self.run_id)
        trace.print_table(events)
        if scenario == "happy_path":
            trace.print_summary(events)
        return verdict == expected

    def _happy_path(self, identifier, secret):
        token = self.step1_apply(identifier, secret)
        if not token or not self.step2_subscribe(identifier, token):
            return "denied"
        if not self.step3_demand():
            return "denied"
        assertion = self.step4_authenticate(identifier, secret)
        if assertion is None:
            return "denied"
        session = self.step5_session(assertion)
        if session is None:
            return "denied"
        return "success" if self.read_protected(session) == 200 else "denied"

    def _wrong_authenticator(self, identifier, secret):
        token = self.step1_apply(identifier, secret)
        self.step2_subscribe(identifier, token)
        self.step3_demand()
        assertion = self.step4_authenticate(
            identifier, "not-the-authenticator-at-all",
            label=colour("the WRONG secret", RED))
        if assertion is not None:
            return "success"
        self.note("no assertion, so there is nothing to present at step 5 - the "
                  "run stops here and the RP is never involved.")
        return "denied"

    def _unenrolled_claimant(self, identifier, secret):
        self.banner(
            "No enrollment at all",
            "(steps 1 and 2 deliberately skipped)",
            "This identifier has no subscriber account and no binding at the\n"
            " Verifier. Watch the denial be identical to the wrong-secret one.",
        )
        self.wait()
        self.step3_demand()
        assertion = self.step4_authenticate(
            identifier, secret, label=colour("a secret for an account that does not exist", RED))
        if assertion is not None:
            return "success"
        self.note("byte-for-byte the same refusal as wrong_authenticator: nothing "
                  "here tells an attacker which email addresses are enrolled.")
        return "denied"

    def _replay(self, identifier, secret):
        token = self.step1_apply(identifier, secret)
        self.step2_subscribe(identifier, token)
        self.step3_demand()
        assertion = self.step4_authenticate(identifier, secret)
        if assertion is None:
            return "denied"
        session = self.step5_session(assertion)
        if session is None:
            return "denied"
        if self.read_protected(session, "The session works - once") != 200:
            return "denied"
        self.logout(session)
        status = self.read_protected(
            session, "Replaying the SAME credential after logout")
        if status == 200:
            return "success"
        self.note("a bearer credential is only as good as its revocation: this one "
                  "is dead the moment logout is called, and the reuse is a 401.")
        return "denied"

    def _skip_verifier(self, identifier, secret):
        token = self.step1_apply(identifier, secret)
        self.step2_subscribe(identifier, token)
        self.step3_demand()
        self.banner(
            "SKIPPING STEP 4 - straight to the RP with a made-up assertion",
            "Claimant  ->  RP         (no Verifier anywhere in this request)",
            "This is the check the whole lab is built around. A real subscriber,\n"
            " correctly enrolled, presenting a handle no Verifier ever issued.\n"
            " If the RP takes the identifier from the request body, it is a\n"
            " self-asserted login and the architecture is decoration.",
        )
        forged = secrets.token_urlsafe(32)
        status, _, body = self.call(
            "POST", self.rp + "/session",
            {"run_id": self.run_id, "identifier": identifier, "assertion": forged},
        )
        if status == 201 and body.get("session"):
            return "success"
        self.note("the RP asked the Verifier to introspect the handle, the Verifier "
                  "had never issued it, and the RP has no other way to learn an "
                  "identifier - so this is refused by construction, not by a check.")
        self.wait()
        return "denied"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenario", nargs="?", default="happy_path", choices=SCENARIOS)
    ap.add_argument("--all", action="store_true", help="run all five, in order")
    ap.add_argument("--no-pause", action="store_true",
                    help="do not wait for Enter between steps")
    args = ap.parse_args()

    walk = Walkthrough(pause=not args.no_pause)
    scenarios = SCENARIOS if args.all else (args.scenario,)

    results = [(s, walk.run(s)) for s in scenarios]

    if len(results) > 1:
        print()
        print(colour("=" * 74, BOLD))
        for scenario, ok in results:
            print("  %-22s %s" % (scenario,
                                  colour("as expected", GREEN) if ok
                                  else colour("NOT as expected", RED)))
        print(colour("=" * 74, BOLD))
    print()
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
