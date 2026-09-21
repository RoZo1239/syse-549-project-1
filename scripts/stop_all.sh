#!/bin/sh
# Stop the services started by run_all.sh.
#
#   sh scripts/stop_all.sh           stop the four services
#   sh scripts/stop_all.sh rp        stop only the ones named
#   sh scripts/stop_all.sh frontend  stop the React dev server too
#   sh scripts/stop_all.sh --force   also kill orphans with no pidfile
#
# The default list is the four contract services, matching run_all.sh: the
# frontend is opt-in on the way up, so it is opt-in on the way down.
#
# --force exists because a pidfile is not the whole truth. A service started by
# hand, or one left behind when a pidfile was deleted or overwritten, keeps its
# port and nothing here knows its pid - so every restart then fails on a port
# that is "already in use" by a process the tooling cannot see. --force matches
# on the module name instead, scoped to THIS user's processes: it will never
# touch another team's services on the shared server.
set -u

FORCE=no
ARGS=""
for arg in "$@"; do
    if [ "$arg" = "--force" ]; then
        FORCE=yes
    else
        ARGS="$ARGS $arg"
    fi
done

cd "$(dirname "$0")/.." || exit 1
RUN_DIR="$(pwd)/run"

# What to match for each service when --force is on. These are the module paths
# run_all.sh launches, so they identify our own processes precisely.
pattern_for() {
    case "$1" in
        subject)  echo "services.subject.main" ;;
        csp)      echo "services.csp.main" ;;
        verifier) echo "services\.verifier" ;;
        rp)       echo "services\.rp" ;;
        frontend) echo "vite" ;;
    esac
}

# shellcheck disable=SC2086
WANTED=${ARGS:-"subject csp verifier rp"}

for s in $WANTED; do
    pidfile="$RUN_DIR/$s.pid"
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill "$pid" 2>/dev/null; then
            echo "  stopped $s (pid $pid)"
        else
            echo "  $s was not running (stale pid $pid)"
        fi
        rm -f "$pidfile"
    else
        echo "  $s not started by run_all.sh"
    fi

    [ "$FORCE" = "yes" ] || continue

    pattern=$(pattern_for "$s")
    [ -n "$pattern" ] || continue
    # -u $(id -u) is the safety rail: only our own processes, never another
    # team's copy of the same service on this host.
    orphans=$(ps -u "$(id -u)" -o pid=,args= 2>/dev/null \
        | grep -E "$pattern" | grep -v grep | awk '{print $1}')
    for pid in $orphans; do
        [ "$pid" = "$$" ] && continue
        if kill "$pid" 2>/dev/null; then
            echo "  stopped $s orphan (pid $pid)"
        fi
    done
done

if [ "$FORCE" = "yes" ]; then
    echo
    echo "  --force also cleared processes with no pidfile. Ports should be free:"
    echo "    sh scripts/run_all.sh"
fi
