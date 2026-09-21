#!/usr/bin/env python3
"""Merge the four services' transcripts into one ordered table.

Every service records only the Figure 3 steps it took part in, so no single
`/transcript` shows the flow. This fetches all four, sorts by `ts` the way the
conformance probe's H-ORD check does, and prints the result as one table.

    python3 scripts/trace.py                    every run, newest last
    python3 scripts/trace.py probe-happy_path-8f3a1c    one run
    python3 scripts/trace.py --last             only the most recent run
    python3 scripts/trace.py --json             the merged events, as JSON

Endpoints come from .env and team.json, the same as every other script here,
so this works against localhost and against the deployment without arguments.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import config  # noqa: E402
from shared.httpjson import ServiceUnreachable, get_json  # noqa: E402
from shared.transcript import STEP_NAMES  # noqa: E402

SERVICES = ("subject", "csp", "verifier", "rp")

# The Applicant -> Subscriber -> Claimant progression the probe checks (H-ROL).
LIFECYCLE_ROLES = ("applicant", "subscriber", "claimant")


def fetch(service):
    """Every event `service` has recorded, or [] with a note on stderr."""
    try:
        url = config.endpoint_for(service)
        status, body = get_json(url + "/transcript", timeout=5)
    except (ServiceUnreachable, config.ConfigError) as exc:
        print("  (%s unreachable: %s)" % (service, exc), file=sys.stderr)
        return []
    if status != 200 or not isinstance(body, dict):
        print("  (%s /transcript returned HTTP %s)" % (service, status), file=sys.stderr)
        return []
    events = body.get("events")
    return events if isinstance(events, list) else []


def merged(run_id=None):
    """All four transcripts in one list, sorted the way the probe sorts them."""
    out = []
    for service in SERVICES:
        for event in fetch(service):
            if not isinstance(event, dict):
                continue
            if run_id and event.get("run_id") != run_id:
                continue
            event = dict(event)
            event["_service"] = service
            out.append(event)
    # str(ts), stably, is exactly what conformance_probe.py does. Matching it
    # means this table shows the order the probe will see, not a nicer one.
    out.sort(key=lambda e: str(e.get("ts", "")))
    return out


def print_table(events):
    if not events:
        print("  (no events)")
        return
    header = ("%-4s %-9s %-5s %-34s %-24s %-8s %s"
              % ("#", "service", "step", "step_name", "actor -> peer", "outcome", "detail"))
    print(header)
    print("-" * len(header))
    for n, e in enumerate(events, 1):
        step = e.get("step")
        name = e.get("step_name") or STEP_NAMES.get(step, "?")
        hop = "%s -> %s" % (e.get("actor", "?"), e.get("peer", "?"))
        print("%-4d %-9s %-5s %-34s %-24s %-8s %s"
              % (n, e.get("_service", "?"), step, name, hop,
                 e.get("outcome", "?"), e.get("detail", "")))


def print_summary(events):
    """The two things the probe derives from this table, stated plainly.

    H-ORD and H-ROL are happy-path checks. On a denial run the flow stops
    early by design, so "NO" here is the expected answer, not a fault.
    """
    print()
    print("  (H-ORD and H-ROL below are happy-path checks: a denial run stops")
    print("   early on purpose, so an incomplete answer there is correct.)")
    steps = [e.get("step") for e in events if isinstance(e.get("step"), int)]
    ordered = steps == sorted(steps) and len(set(steps)) >= 5
    print("  step order observed : %s" % (steps or "none"))
    print("  ascending, all five : %s   (the probe's H-ORD check)"
          % ("yes" if ordered else "NO"))

    actors = [str(e.get("actor", "")).lower() for e in events]
    seen = [r for r in LIFECYCLE_ROLES if r in actors]
    positions = [actors.index(r) for r in seen]
    progression_ok = (len(seen) == 3 and positions == sorted(positions))
    print("  role progression    : %s   (the probe's H-ROL check)"
          % (" -> ".join(seen) if seen else "none"))
    if not progression_ok:
        print("                        NOT Applicant -> Subscriber -> Claimant in order")

    # A transcript is public. If a secret is in one, an attacker on the campus
    # network has it too - which is what the probe's X-CAN check is for.
    blob = json.dumps(events).lower()
    risky = [w for w in ("password", "passwd", "private_key", "client_secret") if w in blob]
    print("  secret-bearing names: %s   (the probe's X-FLD check)"
          % (", ".join(risky) if risky else "none"))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_id", nargs="?", help="show only this run")
    ap.add_argument("--last", action="store_true",
                    help="show only the most recent run_id")
    ap.add_argument("--json", action="store_true", help="print the merged events as JSON")
    args = ap.parse_args()

    events = merged(args.run_id)

    if args.last and events:
        last_run = events[-1].get("run_id")
        events = [e for e in events if e.get("run_id") == last_run]
        args.run_id = last_run

    if args.json:
        json.dump(events, sys.stdout, indent=2)
        print()
        return 0

    print()
    print("Merged transcript%s" % ((" for " + args.run_id) if args.run_id else " (all runs)"))
    print()
    print_table(events)
    if args.run_id or args.last:
        print_summary(events)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
