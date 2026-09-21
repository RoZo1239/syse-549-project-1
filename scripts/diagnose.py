#!/usr/bin/env python3
"""Turn a probe score into a list of things to go and do.

`conformance_probe.py` tells you *that* a check failed. This says what that
check was actually asking, what usually causes it, and the next command to
run. It is deliberately a lookup table rather than anything clever: the probe
only observes endpoints and transcripts, so the diagnosis is knowledge about
this system, not something that can be derived from the result file.

    python3 conformance_probe.py --config team.json --json result.json
    python3 scripts/diagnose.py result.json

    python3 scripts/diagnose.py --check H-ORD N-SKP    # without a result file
    python3 scripts/diagnose.py --all                  # the whole table
"""

import argparse
import json
import sys

# id -> (what it is asking, the usual cause, what to run next)
CHECKS = {
    "S-SUBJ": (
        "The Subject agent answers GET /health with service=\"subject\".",
        "The service is not running, is bound to 127.0.0.1 instead of 0.0.0.0, "
        "or something else is answering on that port.",
        "sh scripts/run_all.sh subject   then   curl -s <host>:4100/health",
    ),
    "S-CSP": (
        "The CSP answers GET /health with service=\"csp\".",
        "Same three causes as S-SUBJ. The CSP also refuses to start without "
        "LAB1_CSP_BINDING_TOKEN and DB_PATH in .env.",
        "sh scripts/run_all.sh csp   then   tail run/csp.log",
    ),
    "S-VERI": (
        "The Verifier answers GET /health with service=\"verifier\".",
        "Same three causes. The Verifier also refuses to start without "
        "LAB1_CSP_BINDING_TOKEN and LAB1_RP_INTROSPECT_TOKEN.",
        "sh scripts/run_all.sh verifier   then   tail run/verifier.log",
    ),
    "S-RP": (
        "The Relying Party answers GET /health with service=\"rp\".",
        "Same three causes.",
        "sh scripts/run_all.sh rp   then   tail run/rp.log",
    ),
    "S-RST": (
        "All four accept POST /reset.",
        "One service is down, or one returned something other than 200/204. "
        "A partial reset is worse than none: leftover state makes the next "
        "run pass or fail for the wrong reason.",
        "for p in 4100 4101 4102 4103; do curl -s -o /dev/null -w \"$p %{http_code}\\n\" "
        "-X POST <host>:$p/reset; done",
    ),
    "P-PUB": (
        "GET / on the RP returns 200 with no credential at all.",
        "The RP is down, or a proxy in front of it is answering first.",
        "curl -sS -D - <host>:4103/ -o /dev/null   # check the Server: header",
    ),
    "P-401": (
        "GET /protected with no credential returns 401.",
        "Anything other than 401 here - a 403, a redirect, a 200 - fails. A "
        "302 to a login page is the common one.",
        "curl -sS -D - <host>:4103/protected -o /dev/null",
    ),
    "P-WWW": (
        "That 401 carries a WWW-Authenticate header. RFC 9110 15.5.2.",
        "The RP sends it. If it is missing at the far end, something between "
        "the probe and the RP stripped it - an nginx proxy is the likely one, "
        "and the instructor kit flags exactly this.",
        "curl -sS -D - <host>:4103/protected -o /dev/null | grep -i www-auth\n"
        "     then the same against 127.0.0.1 ON the server, and compare",
    ),
    "P-ERR": (
        "The 401 body does not leak a traceback, a SQL error or a file path.",
        "A framework debug mode, or an exception handler that returns str(exc).",
        "curl -sS <host>:4103/protected",
    ),
    "H-RUN": (
        "POST /run with scenario=happy_path answers 200 and outcome=success.",
        "The Subject agent could not complete the flow. Which hop failed is "
        "in the transcripts, not in this answer.",
        "python3 scripts/walkthrough.py happy_path   # the same five steps, "
        "one at a time, showing every request and response",
    ),
    "H-ST1": (
        "The CSP recorded a step 1 event for that run_id.",
        "Enrollment never happened, or it happened under a different run_id. "
        "Every event has to be tagged with the run_id the probe supplied.",
        "python3 scripts/trace.py --last",
    ),
    "H-ST2": (
        "The CSP recorded a step 2 event for that run_id.",
        "Usually the binding POST to the Verifier failed: a wrong or missing "
        "X-Lab1-Binding-Token, or the CSP reaching the Verifier through the "
        "public campus URL instead of loopback and timing out.",
        "tail run/csp.log run/verifier.log   then   python3 scripts/trace.py --last",
    ),
    "H-ST3": (
        "The RP recorded a step 3 event for that run_id.",
        "GET /protected has no body, so the run_id has to arrive in the "
        "X-Run-Id header or a ?run_id= query parameter. If it does not, the "
        "event is written under the wrong run.",
        "python3 scripts/trace.py   # look for step 3 under a different run_id",
    ),
    "H-ST4": (
        "The Verifier recorded a step 4 event for that run_id.",
        "Authentication never reached the Verifier, or the binding from step 2 "
        "never arrived so there was nothing to check against.",
        "python3 scripts/walkthrough.py happy_path",
    ),
    "H-ST5": (
        "The RP recorded a step 5 event for that run_id.",
        "The assertion was not honoured: expired (LAB1_ASSERTION_TTL_SECONDS), "
        "already redeemed, or the RP could not reach the Verifier to "
        "introspect it.",
        "tail run/rp.log   then   python3 scripts/trace.py --last",
    ),
    "H-ORD": (
        "Sorting every event from all four transcripts by its ts string gives "
        "the steps in ascending order, with all five present.",
        "Whole-second or millisecond timestamps. The probe sorts by str(ts) "
        "with a STABLE sort, so two events sharing a timestamp keep collection "
        "order - which is service order, not time order. shared/timeutil.py "
        "uses microseconds for this reason.",
        "python3 scripts/trace.py --last   # the summary restates H-ORD\n"
        "     curl -s <host>:4102/transcript | head   # check the ts precision",
    ),
    "H-ROL": (
        "Applicant appears before Subscriber, which appears before Claimant, "
        "in the actor field across the merged transcripts.",
        "One of the three roles is never written. The CSP's step 1 event must "
        "carry actor=\"applicant\" and the RP's step 3 event actor="
        "\"subscriber\" - these are the only places two of the three appear.",
        "python3 scripts/trace.py --last   # the summary restates H-ROL",
    ),
    "N-BAD": (
        "A wrong authenticator output is refused, and no session is created.",
        "The Verifier accepted it, or the scenario reported success anyway.",
        "python3 scripts/walkthrough.py wrong_authenticator",
    ),
    "N-ENR": (
        "A claimant who never enrolled is refused.",
        "The Verifier answered for an identifier it holds no binding for.",
        "python3 scripts/walkthrough.py unenrolled_claimant",
    ),
    "N-RPL": (
        "A session credential reused after logout or expiry is refused.",
        "Logout did not actually revoke, or the RP checks expiry only at issue "
        "time. Note this scenario is allowed a successful step 5 first - what "
        "must fail is the reuse.",
        "python3 scripts/walkthrough.py replay",
    ),
    "N-SKP": (
        "A subject presenting itself to the RP with no Verifier involvement is "
        "refused. This is the check the whole lab is built around.",
        "The RP took an identifier from the request body instead of from the "
        "Verifier. If this fails, the architecture is decoration and the "
        "instructor is told to open the presentation with it.",
        "python3 scripts/walkthrough.py skip_verifier",
    ),
    "X-CAN": (
        "The canary the probe supplied as the authenticator secret does not "
        "appear anywhere in any transcript.",
        "A detail string built from the request, or an exception message "
        "echoed into a transcript event.",
        "python3 -m unittest tests.test_no_secret_logging   # AST scan of the "
        "sources\n     python3 scripts/trace.py --json | grep -i canary",
    ),
    "X-FLD": (
        "No obviously secret-bearing field name (password, passwd, "
        "private_key, client_secret) appears in a transcript.",
        "A detail string that names the field it rejected.",
        "python3 scripts/trace.py --last   # the summary restates X-FLD",
    ),
    "X-DUR": (
        "The RP still refuses /protected after all the failed runs.",
        "A failed run left a session behind, or POST /reset cleared sessions "
        "when it should not have, or the RP crashed partway through.",
        "curl -sS -D - <host>:4103/protected -o /dev/null",
    ),
}

GROUPS = {
    "S": "Structure - the four services exist and can be reset",
    "P": "Public access and denial - the RP's two resources",
    "H": "Happy path - the five Figure 3 steps, in order",
    "N": "Negative scenarios - what the system must refuse",
    "X": "Hygiene - secrets stay out, denial is durable",
}


def explain(check_id):
    entry = CHECKS.get(check_id)
    print()
    print("  %s" % check_id)
    if entry is None:
        print("     (not a check id this script knows about)")
        return
    asking, cause, do = entry
    print("     asks  : %s" % asking)
    print("     usually: %s" % cause)
    print("     run   : %s" % do)


def from_result(path):
    with open(path) as f:
        data = json.load(f)
    results = data.get("results", [])
    failed = [r for r in results if not r.get("passed")]
    passed = len(results) - len(failed)

    print()
    print("  %s" % path)
    print("  team     : %s" % data.get("team", "?"))
    print("  score    : %s of %s checks, %s / %s"
          % (passed, len(results), data.get("probe_score", "?"),
             data.get("probe_points_possible", 10)))
    for service, url in sorted((data.get("endpoints") or {}).items()):
        print("  %-9s %s" % (service + ":", url))

    if not failed:
        print()
        print("  Nothing failed. If this is the DEPLOYED run, it is the one that")
        print("  belongs in the archive as result.json.")
        return 0

    print()
    print("  %d failed:" % len(failed))
    for r in failed:
        print("    %-7s %s" % (r.get("id"), r.get("check")))
        if r.get("detail"):
            print("            -> %s" % r["detail"])

    print()
    print("  " + "-" * 68)
    print("  What each one is asking, and what to do about it")
    print("  " + "-" * 68)
    for r in failed:
        explain(r.get("id"))
    print()
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("result", nargs="?", help="a result.json written by --json")
    ap.add_argument("--check", nargs="+", metavar="ID",
                    help="explain these check ids directly, e.g. H-ORD N-SKP")
    ap.add_argument("--all", action="store_true", help="explain every check")
    args = ap.parse_args()

    if args.all:
        for prefix, title in GROUPS.items():
            print()
            print("  " + title)
            for check_id in CHECKS:
                if check_id.startswith(prefix + "-"):
                    explain(check_id)
        print()
        return 0

    if args.check:
        for check_id in args.check:
            explain(check_id.upper())
        print()
        return 0

    if args.result:
        return from_result(args.result)

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
