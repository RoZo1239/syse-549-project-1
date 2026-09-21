#!/bin/sh
# The presentation runbook, in one command.
#
#   sh scripts/demo.sh              pause between steps (what to use live)
#   sh scripts/demo.sh --no-pause   run straight through (rehearsal, CI)
#
# Covers the demo segment of the lab: the five Figure 3 steps live, then three
# denial scenarios, then the conformance probe. The lab asks for at least two
# denials; this shows three, because skip_verifier is the one the whole
# architecture exists to fail.
set -u

cd "$(dirname "$0")/.." || exit 1

PAUSE_FLAG=""
[ "${1:-}" = "--no-pause" ] && PAUSE_FLAG="--no-pause"

rule() {
    echo
    echo "############################################################"
    echo "#  $1"
    echo "############################################################"
}

hold() {
    [ -n "$PAUSE_FLAG" ] && return 0
    printf "\n   [Enter] for the next part "
    read -r _ignored || exit 0
}

rule "0. Are the four services up?"
sh scripts/run_all.sh || exit 1
hold

rule "1. The happy path - all five steps, one screen each"
python3 scripts/walkthrough.py $PAUSE_FLAG happy_path || exit 1
hold

rule "2. Denial: the wrong authenticator output"
python3 scripts/walkthrough.py $PAUSE_FLAG wrong_authenticator || exit 1
hold

rule "3. Denial: a claimant who was never enrolled"
echo "   Watch this refusal against the last one. They are identical, so"
echo "   neither tells an attacker which addresses are enrolled."
python3 scripts/walkthrough.py $PAUSE_FLAG unenrolled_claimant || exit 1
hold

rule "4. Denial: skipping the Verifier entirely"
echo "   The check the lab is built around: will the RP accept an identity"
echo "   no Verifier ever checked?"
python3 scripts/walkthrough.py $PAUSE_FLAG skip_verifier || exit 1
hold

rule "5. The conformance probe - the same script the instructor runs"
# team.json names the campus hostname, which only resolves from campus. Point
# this at a loopback config when rehearsing off the server, or the probe will
# report 3 of 24 for a system that is running perfectly in front of you.
PROBE_CONFIG=${LAB1_PROBE_CONFIG:-team.json}
echo "   config: $PROBE_CONFIG   (override with LAB1_PROBE_CONFIG=...)"
exec python3 conformance_probe.py --config "$PROBE_CONFIG" --verbose
