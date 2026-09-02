#!/bin/sh
# The adversarial hour, starter kit. Runs the five probes the lab names against
# YOUR OWN deployment, printing what was sent and what came back.
#
#   sh attack_curls.sh team.json
#
# Paths differ per team. Override any of these to match your API:
#   CSP_ENROLL=/enroll CSP_BIND=/authenticator VERIFY_PATH=/authenticate \
#   sh attack_curls.sh team.json
#
# SCOPE: only the endpoints in your own team.json. Probing another team's ports
# needs their written permission and the instructor's.
set -u

CONFIG="${1:-team.json}"
CSP_ENROLL="${CSP_ENROLL:-/enroll}"
CSP_BIND="${CSP_BIND:-/authenticator}"
VERIFY_PATH="${VERIFY_PATH:-/authenticate}"
SESSION_HEADER="${SESSION_HEADER:-Authorization}"

[ -f "$CONFIG" ] || { echo "config not found: $CONFIG"; exit 1; }

ENDPOINTS=$(python3 - "$CONFIG" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))["endpoints"]
for k in ("subject", "csp", "verifier", "rp"):
    print('%s_URL="%s"' % (k.upper(), cfg[k].rstrip("/")))
PY
) || exit 1
eval "$ENDPOINTS"

hdr() {
    echo
    echo "-------------------------------------------------------------"
    echo "$1"
    echo "  looking for: $2"
    echo "-------------------------------------------------------------"
}

show() {
    printf '  $ %s\n' "$1"
    shift
    # shellcheck disable=SC2068
    $@ 2>&1 | sed 's/^/  /'
}

hdr "1. Bearer a token nobody issued" \
   "401. A 200 means the RP trusts any string shaped like a session."
show "curl -i $RP_URL/protected -H '$SESSION_HEADER: Bearer not-a-real-token'" \
    curl -sS -m 10 -i "$RP_URL/protected" -H "$SESSION_HEADER: Bearer not-a-real-token"

hdr "2. Ask the Verifier about an identifier that was never issued" \
   "denied, and the SAME response as a wrong secret for a real account."
show "curl -i $VERIFIER_URL$VERIFY_PATH -d '{...ghost...}'" \
    curl -sS -m 10 -i -X POST "$VERIFIER_URL$VERIFY_PATH" \
        -H 'Content-Type: application/json' \
        -d '{"identifier":"ghost-account-that-does-not-exist","authenticator":"anything"}'

hdr "3. Bind an authenticator to somebody else's account" \
   "refused. If this succeeds, enrollment can be hijacked after the fact."
show "curl -i $CSP_URL$CSP_BIND -d '{...someone else...}'" \
    curl -sS -m 10 -i -X POST "$CSP_URL$CSP_BIND" \
        -H 'Content-Type: application/json' \
        -d '{"identifier":"victim","authenticator":"attacker-chosen-secret"}'

hdr "4. Enroll twice with the same identity" \
   "the second attempt refused. Duplicate identifiers make later attribution meaningless."
for i in 1 2; do
    show "curl -i $CSP_URL$CSP_ENROLL  (attempt $i)" \
        curl -sS -m 10 -i -X POST "$CSP_URL$CSP_ENROLL" \
            -H 'Content-Type: application/json' \
            -d '{"identifier":"dup-test-subject","evidence":"whatever your proofing takes"}'
done

hdr "5. Replay: reuse a session credential from a different client" \
   "401 after logout or expiry. Bearer credentials work for whoever holds them."
echo "  Manual step — the flow is team-specific:"
echo "    a. run happy_path, capture the session credential the RP issued"
echo "    b. call GET /protected with it from this shell   -> expect 200"
echo "    c. log out (or wait past expiry)"
echo "    d. call GET /protected with the same credential  -> expect 401"
echo "  If (d) returns 200, the replay scenario fails and so does check N-RPL."

echo
echo "-------------------------------------------------------------"
cat <<'NOTES'
Read the responses, not just the status codes:
  - do failures for a real account and a nonexistent one look identical?
  - any stack trace, file path, SQL fragment, or framework banner?
  - does an error echo back the secret that was sent?

Then attack the process, not the code. The cheapest real attack on step 1 is
usually social: work out who can cause an enrollment credential to be issued,
and what a plausible request to them would look like. Account recovery, if you
have one, is the front door with the weakest lock.

Every finding worth keeping becomes a denial test with one comment sentence
naming the attack it defends against.
NOTES
