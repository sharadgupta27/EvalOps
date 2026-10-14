#!/usr/bin/env bash
# Operational drill: simulate a dead worker and record what the monitoring shows.
# Requires: docker compose -f docker-compose.yml -f ops/docker-compose.observability.yml up -d
set -u
OUT=security/ops-drill/drill-output.txt
C="docker compose -f docker-compose.yml -f ops/docker-compose.observability.yml"
q() { curl -s "localhost:9090/api/v1/query" --data-urlencode "query=$1"; echo; }
alerts() { curl -s localhost:9090/api/v1/alerts; echo; }
{
  echo "== $(date -u +%FT%TZ) drill start: stopping worker"
  $C stop worker
  TOKEN=$(curl -s -X POST localhost:5173/api/v1/auth/login -H 'Content-Type: application/json' \
    -d '{"email":"demo@evalops.dev","password":"evalops-demo-2026"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
  echo "== queue a run while the worker is down"
  curl -s -X POST localhost:5173/api/v1/projects/1/runs -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' -d '{"prompt_version_id":1,"dataset_id":1}'; echo
  for minute in 1 2 3 4 5 6 7 8; do
    sleep 60
    echo "== t+${minute}m"
    echo "-- up{job=evalops-worker}"; q 'up{job="evalops-worker"}'
    echo "-- queue age (api-side gauge is only updated by the worker, so use the DB via API below)"
    curl -s localhost:5173/api/v1/projects/1/runs -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;r=json.load(sys.stdin)[0];print('latest run', r['id'], r['status'], 'created', r['created_at'])"
    echo "-- alerts"; alerts
  done
  echo "== $(date -u +%FT%TZ) recovery: starting worker"
  $C start worker
  sleep 20
  curl -s localhost:5173/api/v1/projects/1/runs -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;r=json.load(sys.stdin)[0];print('latest run after recovery', r['id'], r['status'])"
  echo "-- alerts after recovery"; alerts
} > "$OUT" 2>&1
echo "drill written to $OUT"
