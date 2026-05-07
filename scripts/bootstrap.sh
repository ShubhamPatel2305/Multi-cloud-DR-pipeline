#!/usr/bin/env bash
set -euo pipefail

ROUTER="${ROUTER:-http://localhost:8000}"

echo "→ Building & starting the stack"
docker compose up -d --build

echo
echo "→ Waiting for the router to be reachable"
for _ in {1..30}; do
  if curl -fsS "$ROUTER/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo
echo "→ Initial pool state"
bash "$(dirname "$0")/health-check.sh"

echo
echo "→ Seeding two sample courses"
curl -fsS -X POST "$ROUTER/proxy/api/courses" \
  -H 'content-type: application/json' \
  -d '{"code":"CS101","title":"Intro to CS","instructor":"Dr. Iyer","seats":120}' \
  | python3 -m json.tool

curl -fsS -X POST "$ROUTER/proxy/api/courses" \
  -H 'content-type: application/json' \
  -d '{"code":"DS200","title":"Data Structures","instructor":"Prof. Khanna","seats":80}' \
  | python3 -m json.tool

echo
echo "→ Stack is ready."
echo "    Router:        $ROUTER"
echo "    Mumbai:        http://localhost:8081"
echo "    Singapore:     http://localhost:8082"
echo "    Azure:         http://localhost:8083"
echo
echo "Try:  bash scripts/simulate-failure.sh aws-mumbai"
echo "Then: bash scripts/canary-failback.sh aws-mumbai"
