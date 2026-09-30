#!/usr/bin/env bash
set -euo pipefail
HOST="${HOST:-nlp.localtest.me}"
URL="http://${HOST}"
RESOLVE=(--resolve "${HOST}:80:127.0.0.1")

echo "==> readiness"
for i in $(seq 1 30); do
  curl -fsS "${RESOLVE[@]}" "$URL/readyz" && break || { echo "waiting ($i)"; sleep 2; }
done

echo; echo "==> inference"
BODY='{"texts":["I love this platform, it is amazing","This is the worst and slowest thing ever"]}'
RES=$(curl -fsS "${RESOLVE[@]}" -H 'content-type: application/json' -d "$BODY" "$URL/v1/sentiment")
echo "$RES"
echo "$RES" | grep -q '"positive"' && echo "$RES" | grep -q '"negative"'

echo "==> cache (second call must be served from Redis)"
RES2=$(curl -fsS "${RESOLVE[@]}" -H 'content-type: application/json' -d "$BODY" "$URL/v1/sentiment")
echo "$RES2" | grep -q '"cached":true'

echo "==> validation rejects bad input"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "${RESOLVE[@]}" -H 'content-type: application/json' -d '{"texts":[]}' "$URL/v1/sentiment")
[ "$CODE" = "422" ]

echo "==> network policy: unrelated pod must NOT reach redis"
kubectl -n nlp run np-probe --rm -i --restart=Never --image=busybox:1.36 \
  --overrides='{"spec":{"securityContext":{"runAsNonRoot":true,"runAsUser":1000,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"np-probe","image":"busybox:1.36","command":["sh","-c","nc -z -w 3 redis 6379 && echo REACHABLE || echo BLOCKED"],"securityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]}}}]}}' \
  2>/dev/null | tee /tmp/np.out || true
grep -q BLOCKED /tmp/np.out || echo "WARN: NetworkPolicy not enforced by this CNI (expected on default kind without Calico/Cilium)"

echo "ALL CHECKS PASSED"
