#!/usr/bin/env python3
"""Compare the two shared tokens with a partner, without revealing them.

LAB1_CSP_BINDING_TOKEN and LAB1_RP_INTROSPECT_TOKEN are shared secrets between
two services each. When the partners run their halves from their own home
directories there are two .env files, and .env.example tells each of them to
generate a fresh random value — so generating independently guarantees a
mismatch, and the symptom is a 502 at step 2 that looks like a code fault.

Checking by pasting the tokens to each other would put them in a chat log, on
a shared machine, for a system whose whole subject is secret handling. This
prints a short fingerprint instead: a truncated SHA-256, which is safe to send
and still differs whenever the tokens differ.

    python3 scripts/check_tokens.py

Send your partner the output. Same fingerprint, same token.
"""

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SHARED = (
    ("LAB1_CSP_BINDING_TOKEN", "CSP -> Verifier, on POST /binding  (step 2)"),
    ("LAB1_RP_INTROSPECT_TOKEN", "RP  -> Verifier, on POST /introspect (step 5)"),
)

PLACEHOLDERS = ("<paste", "changeme", "your-token", "xxx")


def env_values(path):
    """Every KEY=VALUE in a .env, without importing anything or executing it."""
    values = {}
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return None
    return values


def fingerprint(value):
    """Twelve hex characters of SHA-256. Safe to send; still unique per token."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, ".env")
    values = env_values(path)

    if values is None:
        print("\n  no .env found at %s" % path)
        print("  cp .env.example .env, then fill in both tokens\n")
        return 2

    print()
    print("  Shared-token fingerprints — send these two lines to your partner.")
    print("  Same fingerprint means same token. They must match.")
    print()

    problems = 0
    for name, who in SHARED:
        value = values.get(name, "")
        if not value:
            print("  %-26s NOT SET" % name)
            print("  %-26s %s" % ("", who))
            problems += 1
        elif any(p in value.lower() for p in PLACEHOLDERS):
            print("  %-26s STILL A PLACEHOLDER" % name)
            print("  %-26s %s" % ("", who))
            problems += 1
        else:
            print("  %-26s %s" % (name, fingerprint(value)))
            print("  %-26s %s" % ("", who))
        print()

    if problems:
        print("  Generate a value for each one that is missing, ONCE, and put the")
        print("  same value in both partners' .env:")
        print()
        print('    python3 -c "import secrets; print(secrets.token_urlsafe(32))"')
        print()
        return 1

    print("  Both set. If a fingerprint differs from your partner's, one of you")
    print("  overwrites theirs with the other's value and you both restart:")
    print()
    print("    sh scripts/stop_all.sh && sh scripts/run_all.sh")
    print()
    print("  Then confirm end to end:")
    print()
    print("    python3 scripts/walkthrough.py --no-pause happy_path")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
