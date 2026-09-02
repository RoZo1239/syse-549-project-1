#!/bin/sh
# Archive hygiene scan — run before building lab1-<teamname>.zip.
# A committed key, a real .env, or a live database file is an automatic deduction.
#
#   sh hygiene_scan.sh [path]
set -u

ROOT="${1:-.}"
PROBLEMS=0

hit()  { PROBLEMS=$((PROBLEMS+1)); printf '  PROBLEM  %s\n' "$1"; }
ok()   { printf '  ok       %s\n' "$1"; }

echo
echo "== secrets and live data ($ROOT) =="
FOUND=$(find "$ROOT" \
    -path '*/.git' -prune -o \
    \( -name '*.pem' -o -name '*.key' -o -name 'id_rsa*' -o -name '*.p12' \
       -o -name '*.pfx' -o -name '.env' -o -name '*.db' -o -name '*.sqlite' \
       -o -name '*.sqlite3' \) -print 2>/dev/null)
if [ -n "$FOUND" ]; then
    echo "$FOUND" | while read -r f; do hit "remove before zipping: $f"; done
    PROBLEMS=1
else
    ok "no keys, .env, or database files"
fi

KEYTEXT=$(grep -rl -- '-----BEGIN .*PRIVATE KEY-----' "$ROOT" \
    --exclude-dir=.git --exclude-dir=node_modules 2>/dev/null)
if [ -n "$KEYTEXT" ]; then
    echo "$KEYTEXT" | while read -r f; do hit "private key material inside: $f"; done
    PROBLEMS=1
else
    ok "no inline private key material"
fi

echo
echo "== bulk that should not ship =="
BULK=$(find "$ROOT" -path '*/.git' -prune -o \
    \( -name 'node_modules' -o -name 'venv' -o -name '.venv' -o -name '__pycache__' \
       -o -name '.pytest_cache' \) -print 2>/dev/null)
if [ -n "$BULK" ]; then
    echo "$BULK" | while read -r d; do hit "exclude from the archive: $d"; done
    PROBLEMS=1
else
    ok "no venv, node_modules, or caches"
fi

SIZE=$(du -sm "$ROOT" 2>/dev/null | cut -f1)
if [ -n "${SIZE:-}" ] && [ "$SIZE" -gt 25 ]; then
    hit "tree is ${SIZE}MB — the archive limit is 25MB"
else
    ok "size ${SIZE:-?}MB, under the 25MB limit"
fi

echo
echo "== required files =="
for f in README.md result.json .env.example .gitignore; do
    [ -e "$ROOT/$f" ] && ok "$f present" || hit "$f missing"
done

if [ -f "$ROOT/.gitignore" ]; then
    for pat in '.env' '*.db' 'venv' 'node_modules'; do
        grep -q -- "$pat" "$ROOT/.gitignore" 2>/dev/null \
            && ok ".gitignore covers $pat" \
            || hit ".gitignore does not mention $pat"
    done
fi

if [ -f "$ROOT/.env.example" ]; then
    if grep -qiE '(secret|key|token|password)[[:space:]]*=[[:space:]]*[A-Za-z0-9+/_-]{12,}' \
        "$ROOT/.env.example" 2>/dev/null; then
        hit ".env.example looks like it holds a real value, not a placeholder"
    else
        ok ".env.example holds placeholders"
    fi
fi

echo
if [ "$PROBLEMS" -eq 0 ]; then
    echo "hygiene clean"
else
    echo "$PROBLEMS problem area(s) above — fix before zipping"
fi
exit 0
