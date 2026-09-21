#!/bin/sh
# Everything needed to work out why the dev server is not answering.
#
#   sh scripts/frontend_status.sh
#
# The frontend is the one piece of this project that is not standard library
# and not graded, and it has three independent ways to look broken while being
# fine: a stale pidfile, a port set in .env that a running process never saw,
# and a bind address that is not the one you are tunnelling to. This prints all
# three at once rather than making you guess which.
set -u

cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)

PORT=$(sed -n 's/^[[:space:]]*FRONTEND_PORT[[:space:]]*=[[:space:]]*\([0-9][0-9]*\).*/\1/p' \
    "$ROOT/.env" 2>/dev/null | tail -1)
PORT=${PORT:-5173}

echo
echo "== checkout =="
printf "  commit    "; git log --oneline -1 2>/dev/null || echo "(not a git checkout)"
printf "  branch    "; git rev-parse --abbrev-ref HEAD 2>/dev/null
if [ -d frontend/node_modules ]; then
    if [ -s frontend/node_modules/esbuild/bin/esbuild ]; then
        echo "  esbuild   binary present"
    else
        echo "  esbuild   MISSING - npm 11 blocked its postinstall and vite will"
        echo "            not start. Fix: cd frontend && npm rebuild esbuild"
    fi
else
    echo "  deps      frontend/node_modules absent - run 'npm install' in frontend/"
fi

echo
echo "== configured port =="
echo "  FRONTEND_PORT=$PORT   (from .env, default 5173)"

echo
echo "== process =="
pidfile="$ROOT/run/frontend.pid"
if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
        echo "  pid $pid is alive"
        echo "  NOTE: a running server keeps the port it started on. If you"
        echo "        changed FRONTEND_PORT since, stop it first:"
        echo "          sh scripts/stop_all.sh frontend"
    else
        echo "  pidfile names $pid, which is not running (stale)"
        echo "  Fix: sh scripts/stop_all.sh frontend   then start it again"
    fi
else
    echo "  no pidfile - the dev server was not started by run_all.sh"
    echo "  Start it:  sh scripts/run_all.sh frontend"
fi

echo
echo "== listening =="
if command -v ss >/dev/null 2>&1; then
    found=$(ss -tln 2>/dev/null | grep -E ":(${PORT}|5173|5174)[[:space:]]")
    if [ -n "$found" ]; then
        echo "$found" | sed 's/^/  /'
        echo
        echo "  Tunnel to the address on the left of the port. If it reads"
        echo "  [::1] rather than 127.0.0.1, that is IPv6 loopback and"
        echo "  'ssh -L $PORT:127.0.0.1:$PORT' will be refused - pull the"
        echo "  latest checkout, which pins 127.0.0.1."
    else
        echo "  nothing listening on $PORT, 5173 or 5174"
    fi
else
    echo "  (ss not available)"
fi

echo
echo "== reachable on loopback =="
for p in $(printf '%s\n' "$PORT" 5173 5174 | sort -un); do
    if command -v curl >/dev/null 2>&1; then
        code=$(curl -s -o /dev/null -m 3 -w "%{http_code}" "http://127.0.0.1:$p/" 2>/dev/null)
        [ "$code" = "000" ] && code="no answer"
        echo "  127.0.0.1:$p   $code"
    fi
done

echo
echo "== last 15 lines of run/frontend.log =="
if [ -f "$ROOT/run/frontend.log" ]; then
    sed 's/^/  /' "$ROOT/run/frontend.log" | tail -15
else
    echo "  (no log - it has never been started by run_all.sh)"
fi
echo
