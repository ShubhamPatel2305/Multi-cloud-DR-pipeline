#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-aws-mumbai}"
ROUTER="${ROUTER:-http://localhost:8000}"

declare -A REGION_PORT=(
  ["aws-mumbai"]=8081
  ["aws-singapore"]=8082
  ["azure-secondary"]=8083
)

PORT="${REGION_PORT[$TARGET]:-}"
if [[ -z "$PORT" ]]; then
  echo "unknown target: $TARGET" >&2
  exit 1
fi

echo "→ Clearing injected failure on $TARGET"
curl -fsS -X POST "http://localhost:$PORT/admin/inject-failure" \
  -H 'content-type: application/json' \
  -d '{"mode":"none"}' | python3 -m json.tool

echo
echo "→ Waiting for $TARGET to be marked HEALTHY by the router..."
for _ in {1..20}; do
  state="$(curl -fsS "$ROUTER/admin/pool" | python3 -c "
import json, sys, os
target = os.environ['TARGET']
d = json.load(sys.stdin)
for o in d['origins']:
    if o['name'] == target:
        print(o['state']); break
" TARGET="$TARGET")"
  echo "    state=$state"
  [[ "$state" == "healthy" ]] && break
  sleep 2
done

echo
echo "→ Starting canary ramp on $TARGET (5% → 25% → 50% → 100%, gated on health)"
curl -fsS -X POST "$ROUTER/admin/canary/start" \
  -H 'content-type: application/json' \
  -d "{\"target\":\"$TARGET\"}" | python3 -m json.tool

echo
echo "→ Polling canary status (Ctrl+C to stop watching)"
while true; do
  status="$(curl -fsS "$ROUTER/admin/canary/status")"
  echo "$status" | python3 -m json.tool
  state="$(echo "$status" | python3 -c "import json,sys; print(json.load(sys.stdin).get('state','?'))")"
  if [[ "$state" == "completed" || "$state" == "rolled_back" ]]; then
    echo "→ Canary terminal state: $state"
    break
  fi
  sleep 5
done
