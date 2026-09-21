#!/bin/sh
# Build the submission archive from the deployed, tested checkout.
#
#   sh scripts/package.sh
#
# The archive is built with `git archive`, which ships ONLY tracked files. That
# is the whole safety argument: .env, app.db, run/ and frontend/node_modules
# are gitignored and therefore untracked, so they cannot end up in the zip by
# being forgotten. Section 9.1 makes a committed credential an automatic
# deduction; this removes the chance to make that mistake rather than relying
# on a checklist.
#
# result.json is the one required file that is NOT built from the checkout -
# it has to come from a probe run against the deployed system - so it is added
# explicitly and its contents are checked before anything is packed.
set -u

cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
TEAM=$(python3 -c "import json;print(json.load(open('team.json'))['team'])" 2>/dev/null || echo "unknown")
ZIP="$ROOT/lab1-$TEAM.zip"
FAIL=0

say()  { printf "  %s\n" "$1"; }
bad()  { printf "  PROBLEM  %s\n" "$1"; FAIL=1; }
ok()   { printf "  ok       %s\n" "$1"; }

echo
echo "== 1. the checkout =="
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    bad "uncommitted changes - git archive ships COMMITTED files only, so"
    say "         anything not committed will be missing from the zip:"
    git status --porcelain | sed 's/^/           /'
    say "         commit them, then run this again"
else
    ok "working tree clean; HEAD is what will be packaged"
fi
say "         $(git log --oneline -1 2>/dev/null)"

echo
echo "== 2. result.json =="
if [ ! -f result.json ]; then
    bad "result.json missing - it is a required deliverable"
    say "         run the probe from a CAMPUS machine, not the server:"
    say "           python3 conformance_probe.py --config team.json --json result.json"
else
    python3 - <<'PY'
import json, sys
try:
    d = json.load(open("result.json"))
except Exception as exc:
    print("  PROBLEM  result.json is not valid JSON: %s" % exc); sys.exit(0)

eps = d.get("endpoints") or {}
loopback = [u for u in eps.values() if "127.0.0.1" in str(u) or "localhost" in str(u)]
passed, total = d.get("checks_passed"), d.get("checks_total")

print("  ok       %s of %s checks, score %s" % (passed, total, d.get("probe_score")))
for name, url in sorted(eps.items()):
    print("           %-9s %s" % (name + ":", url))

if loopback:
    print("  PROBLEM  these endpoints are loopback, so this run did NOT come from")
    print("           a machine other than the server. Section 9.1 wants the probe")
    print("           output from your DEPLOYED system - rerun it from campus.")
elif passed != total:
    print("           not 24 of 24. That is allowed - submit the honest number -")
    print("           but see what failed first:  python3 scripts/diagnose.py result.json")
PY
    grep -q "127.0.0.1\|localhost" result.json && FAIL=1
fi

echo
echo "== 3. required files, as git sees them =="
for f in README.md .env.example conformance_probe.py; do
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then ok "$f tracked"
    else bad "$f is not tracked - it will not be in the zip"; fi
done
n=$(git ls-files 'tests/*.py' | wc -l | tr -d ' ')
[ "$n" -gt 0 ] && ok "$n test files tracked" || bad "no tests tracked"
for d in services/subject services/csp services/verifier services/rp; do
    git ls-files "$d" | grep -q . && ok "$d tracked" || bad "$d not tracked"
done

echo
echo "== 4. nothing secret is tracked =="
SECRETS=$(git ls-files | grep -iE '(^|/)\.env$|\.pem$|\.key$|id_rsa|\.db$|\.sqlite3?$|node_modules/' || true)
if [ -n "$SECRETS" ]; then
    bad "these are TRACKED and would ship:"
    printf "%s\n" "$SECRETS" | sed 's/^/           /'
else
    ok "no .env, key, database or node_modules is tracked"
fi
if git ls-files .env.example | grep -q . ; then
    if git show HEAD:.env.example 2>/dev/null | grep -qE '^[A-Z_]*TOKEN=[A-Za-z0-9_-]{20,}'; then
        bad ".env.example appears to contain a REAL token, not a placeholder"
    else
        ok ".env.example holds placeholders only"
    fi
fi

echo
echo "== 5. building =="
if [ "$FAIL" -ne 0 ]; then
    echo
    echo "  Not building. Fix the problems above first."
    echo
    exit 1
fi

rm -f "$ZIP"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
PREFIX="lab1-$TEAM"

# Tracked files only. --prefix puts everything in one top-level directory, so
# the marker unzips into a folder rather than over their desktop.
git archive --format=tar --prefix="$PREFIX/" HEAD | (cd "$TMP" && tar xf -)
cp result.json "$TMP/$PREFIX/result.json"

# Belt and braces: the archive is built from tracked files, but assert it.
LEAKED=$(cd "$TMP" && find . \( -name ".env" -o -name "*.pem" -o -name "*.key" \
    -o -name "*.db" -o -name "*.sqlite*" -o -name "node_modules" -o -name "__pycache__" \) )
if [ -n "$LEAKED" ]; then
    echo "  PROBLEM  the staged tree contains things that must not ship:"
    printf "%s\n" "$LEAKED" | sed 's/^/           /'
    exit 1
fi
ok "staged tree is clean"

(cd "$TMP" && zip -qXr "$ZIP" "$PREFIX")

SIZE=$(du -k "$ZIP" | cut -f1)
COUNT=$(unzip -l "$ZIP" | tail -1 | awk '{print $2}')
echo
echo "== 6. done =="
ok "$ZIP"
ok "$COUNT files, $((SIZE / 1024 + 1)) MB (limit 25 MB)"
[ "$SIZE" -gt 25600 ] && bad "over the 25 MB limit"
echo
echo "  Check it yourself before submitting:"
echo "    unzip -l lab1-$TEAM.zip | head -40"
echo "    unzip -l lab1-$TEAM.zip | grep -iE 'env|\\.db|node_modules|pem|key'"
echo
