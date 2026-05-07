#!/usr/bin/env bash
set -euo pipefail

ROUTER="${ROUTER:-http://localhost:8000}"

echo "→ Pool state at $(date -u +%FT%TZ)"
curl -fsS "$ROUTER/admin/pool" \
  | python3 -c '
import json, sys
d = json.load(sys.stdin)
fmt = "{:<18} {:<8} {:<7} {:<10} {:<12} {:<10}"
print(fmt.format("origin","prio","weight","state","probe_ms","status"))
print("-" * 70)
for o in d["origins"]:
    print(fmt.format(
        o["name"], o["priority"], o["weight"], o["state"],
        str(o.get("last_probe_ms") or "-"),
        str(o.get("last_status_code") or o.get("last_error") or "-"),
    ))
'

echo
echo "→ Routing 5 sample requests through the router"
for _ in {1..5}; do
  curl -sS -o /dev/null -D - "$ROUTER/proxy/api/courses" | grep -i "x-routed-to:" || true
done
