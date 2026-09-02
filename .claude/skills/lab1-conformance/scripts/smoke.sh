#!/bin/sh
# Smoke-test the four Lab 1 services before spending time on conformance_probe.py.
# Read-only by default. Pass --full to also reset, run happy_path, and grep the
# transcripts for the canary.
#
#   sh smoke.sh team.json
#   sh smoke.sh team.json --full
set -u

CONFIG="${1:-team.json}"
MODE="${2:-quick}"
PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); printf '  ok    %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; }
note() { printf '        %s\n' "$1"; }

[ -f "$CONFIG" ] || { echo "config not found: $CONFIG"; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl not found"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; exit 1; }

ENDPOINTS=$(python3 - "$CONFIG" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))["endpoints"]
for k in ("subject", "csp", "verifier", "rp"):
    print('%s_URL="%s"' % (k.upper(), cfg[k].rstrip("/")))
PY
) || { echo "could not read endpoints from $CONFIG"; exit 1; }
eval "$ENDPOINTS"

echo
echo "== /health =="
for s in subject csp verifier rp; do
    case $s in
        subject)  url=$SUBJECT_URL ;;
        csp)      url=$CSP_URL ;;
        verifier) url=$VERIFIER_URL ;;
        rp)       url=$RP_URL ;;
    esac
    body=$(curl -sS -m 5 "$url/health" 2>&1)
    if [ $? -ne 0 ]; then
        bad "$s unreachable at $url"
        note "$body"
        note "bound to 127.0.0.1 instead of 0.0.0.0? or nginx in front of the port?"
        continue
    fi
    if printf '%s' "$body" | grep -q "\"service\"[[:space:]]*:[[:space:]]*\"$s\""; then
        ok "$s /health"
    else
        bad "$s /health did not report service=\"$s\""
        note "$body"
    fi
done

echo
echo "== RP public and protected =="
code=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "$RP_URL/" 2>/dev/null)
[ "$code" = "200" ] && ok "GET / is public (200)" || bad "GET / returned $code, expected 200"

hdrs=$(curl -sS -m 5 -D - -o /dev/null "$RP_URL/protected" 2>/dev/null)
if printf '%s' "$hdrs" | head -1 | grep -q ' 401'; then
    ok "GET /protected returns 401 without a session"
else
    bad "GET /protected did not return 401"
    note "$(printf '%s' "$hdrs" | head -1)"
fi
if printf '%s' "$hdrs" | grep -qi '^www-authenticate:'; then
    ok "401 carries WWW-Authenticate (RFC 9110 15.5.2)"
else
    bad "401 is missing the WWW-Authenticate header"
    note "this is check P-WWW and it is the most commonly forgotten line in the lab"
fi

echo
echo "== transcript shape =="
for s in subject csp verifier rp; do
    case $s in
        subject)  url=$SUBJECT_URL ;;
        csp)      url=$CSP_URL ;;
        verifier) url=$VERIFIER_URL ;;
        rp)       url=$RP_URL ;;
    esac
    out=$(curl -sS -m 5 "$url/transcript" 2>/dev/null | python3 - "$s" <<'PY'
import json, re, sys
svc = sys.argv[1]
raw = sys.stdin.read()
try:
    doc = json.loads(raw)
except Exception as e:
    print("BAD invalid JSON from /transcript (%s)" % e); raise SystemExit
events = doc.get("events")
if events is None:
    print("BAD response has no 'events' key"); raise SystemExit
if not events:
    print("OK valid JSON, no events yet"); raise SystemExit
required = {"seq", "run_id", "step", "step_name", "actor", "peer", "outcome", "ts"}
problems = []
for i, e in enumerate(events):
    missing = required - set(e)
    if missing:
        problems.append("event %d missing %s" % (i, sorted(missing)))
    ts = str(e.get("ts", ""))
    if not re.search(r"\.\d+", ts):
        problems.append("event %d has whole-second ts %r (H-ORD will fail)" % (i, ts))
    if e.get("outcome") not in ("success", "denied"):
        problems.append("event %d outcome %r not success/denied" % (i, e.get("outcome")))
if problems:
    print("BAD " + "; ".join(problems[:3]))
else:
    print("OK %d events, sub-second timestamps" % len(events))
PY
)
    case "$out" in
        OK*)  ok "$s /transcript ${out#OK }" ;;
        *)    bad "$s /transcript ${out#BAD }" ;;
    esac
done

if [ "$MODE" = "--full" ]; then
    echo
    echo "== full run: reset, happy_path, canary check =="
    for u in "$SUBJECT_URL" "$CSP_URL" "$VERIFIER_URL" "$RP_URL"; do
        curl -sS -m 5 -X POST "$u/reset" -o /dev/null -w '' 2>/dev/null
    done
    ok "reset sent to all four services"

    CANARY=$(python3 -c "import secrets;print('CANARY-'+secrets.token_hex(3))")
    RUN_ID="smoke-happy_path-$(python3 -c "import secrets;print(secrets.token_hex(3))")"
    body=$(curl -sS -m 30 -X POST -H 'Content-Type: application/json' \
        -d "{\"run_id\":\"$RUN_ID\",\"scenario\":\"happy_path\",\"canary\":\"$CANARY\"}" \
        "$SUBJECT_URL/run" 2>&1)
    printf '        %s\n' "$body"
    if printf '%s' "$body" | grep -q '"outcome"[[:space:]]*:[[:space:]]*"success"'; then
        ok "happy_path returned success"
    else
        bad "happy_path did not return success"
    fi

    steps=""
    leaked=0
    for u in "$SUBJECT_URL" "$CSP_URL" "$VERIFIER_URL" "$RP_URL"; do
        t=$(curl -sS -m 5 "$u/transcript" 2>/dev/null)
        printf '%s' "$t" | grep -q "$CANARY" && leaked=1
        s=$(printf '%s' "$t" | python3 - "$RUN_ID" <<'PY'
import json, sys
try:
    doc = json.load(sys.stdin)
except Exception:
    raise SystemExit
print(" ".join(str(e.get("step")) for e in doc.get("events", [])
                if e.get("run_id") == sys.argv[1]))
PY
)
        steps="$steps $s"
    done
    missing=""
    for n in 1 2 3 4 5; do
        case " $steps " in *" $n "*) ;; *) missing="$missing $n" ;; esac
    done
    [ -z "$missing" ] && ok "all five steps present for $RUN_ID" \
        || bad "steps missing for $RUN_ID:$missing"
    [ "$leaked" -eq 0 ] && ok "canary absent from every transcript (X-CAN)" \
        || bad "CANARY FOUND IN A TRANSCRIPT — a secret was logged (X-CAN fails)"
fi

echo
echo "passed $PASS, failed $FAIL"
[ "$FAIL" -eq 0 ] && echo "smoke clean — now run: python3 conformance_probe.py --config $CONFIG --verbose"
exit 0
