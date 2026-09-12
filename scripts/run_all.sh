#!/bin/sh
# Start all four Lab 1 services in the background, one log file each.
#
#   sh scripts/run_all.sh            start every service
#   sh scripts/run_all.sh verifier rp   start only the ones named
#
# No sudo, no systemd: nohup from the home directory, which is all the lab
# server allows. Ports and the bind address come from .env.
set -u

cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
RUN_DIR="$ROOT/run"
mkdir -p "$RUN_DIR"

[ -f .env ] || { echo "no .env - copy .env.example to .env and fill it in first"; exit 1; }

# Partner A's services are FastAPI modules; Partner B's are packages under services/.
module_for() {
    case "$1" in
        subject)  echo "subject.main" ;;
        csp)      echo "csp.main" ;;
        verifier) echo "services.verifier" ;;
        rp)       echo "services.rp" ;;
    esac
}

WANTED=${*:-"subject csp verifier rp"}

for s in $WANTED; do
    mod=$(module_for "$s")
    [ -n "$mod" ] || { echo "unknown service: $s"; continue; }
    pidfile="$RUN_DIR/$s.pid"
    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        echo "  $s already running (pid $(cat "$pidfile"))"
        continue
    fi
    nohup python3 -m "$mod" > "$RUN_DIR/$s.log" 2>&1 &
    echo $! > "$pidfile"
    echo "  started $s (pid $!) -> run/$s.log"
done

# Give them a moment, then say which ones actually answer.
sleep 2
echo
echo "== health =="
python3 - "$WANTED" <<'PY'
import json, sys, urllib.request
sys.path.insert(0, ".")
from shared import config
wanted = sys.argv[1].split()
failed = 0
for name in wanted:
    url = "http://127.0.0.1:%d/health" % config.port_for(name)
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            body = json.load(r)
        ok = body.get("service") == name
        print("  %-9s %s  %s" % (name, "ok  " if ok else "WRONG", json.dumps(body)))
        failed += 0 if ok else 1
    except Exception as exc:
        print("  %-9s DOWN  %s" % (name, exc))
        print("            see run/%s.log" % name)
        failed += 1
print()
if failed:
    print("%d of %d not answering" % (failed, len(wanted)))
else:
    print("%d of %d up: %s" % (len(wanted), len(wanted), " ".join(wanted)))
PY
