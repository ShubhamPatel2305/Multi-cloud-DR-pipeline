#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-aws-mumbai}"
MODE="${2:-deep}"

declare -A REGION_PORT=(
  ["aws-mumbai"]=8081
  ["aws-singapore"]=8082
  ["azure-secondary"]=8083
)

PORT="${REGION_PORT[$TARGET]:-}"
if [[ -z "$PORT" ]]; then
  echo "unknown target: $TARGET (expected aws-mumbai | aws-singapore | azure-secondary)" >&2
  exit 1
fi

echo "→ Injecting '$MODE' failure on $TARGET (port $PORT)"
curl -fsS -X POST "http://localhost:$PORT/admin/inject-failure" \
  -H 'content-type: application/json' \
  -d "{\"mode\":\"$MODE\"}" | python3 -m json.tool

echo
echo "→ Waiting for the router to detect the outage (unhealthy_threshold × poll_interval)..."
sleep 8

echo
echo "→ Pool state after failure"
ROUTER="${ROUTER:-http://localhost:8000}" bash "$(dirname "$0")/health-check.sh"
