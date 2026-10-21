#!/usr/bin/env bash
# shellcheck disable=SC2015  # `test && pass || fail`: pass only echoes, so fail never runs after a pass
# Start the built Docker image the way Render does (production settings, migrations on start) and check what a
# deploy depends on: the health check, the app shell and its security headers, sign-in that is closed to
# development logins, the packaged docs and every page in the sitemap, and the SEO files built from PUBLIC_URL.
#
#   docker build -t agentsec-dashboard:ci .
#   scripts/smoke_test_image.sh agentsec-dashboard:ci
#
# Needs only docker, curl and grep. Uses SQLite inside the container, so no database service is required.
set -euo pipefail

IMAGE="${1:?usage: scripts/smoke_test_image.sh IMAGE}"
PORT="${SMOKE_PORT:-18000}"
PUBLIC_URL="https://smoke-test.invalid"        # never resolved: only compared against the URLs the pages print
NAME="agentsec-smoke-$$"
BASE="http://127.0.0.1:${PORT}"
failures=0

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

pass() { echo "ok   $1"; }
fail() {
  echo "FAIL $1"
  [ -n "${GITHUB_ACTIONS:-}" ] && echo "::error title=Docker smoke test::$1"
  failures=$((failures + 1))
}
check() {   # check "description" command...
  local what="$1"; shift
  if "$@" >/dev/null 2>&1; then pass "$what"; else fail "$what"; fi
}

docker run -d --name "$NAME" -p "127.0.0.1:${PORT}:8000" \
  -e AGENTSEC_ENV=production \
  -e SECRET_KEY="smoke-test-only-$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')" \
  -e DATABASE_URL="sqlite:////tmp/smoke.db" \
  -e PUBLIC_URL="$PUBLIC_URL" \
  -e GITHUB_CLIENT_ID=smoke-test-client -e GITHUB_CLIENT_SECRET=smoke-test-secret \
  "$IMAGE" >/dev/null

for _ in $(seq 1 60); do
  curl -fsS "$BASE/healthz" >/dev/null 2>&1 && break
  if [ "$(docker inspect -f '{{.State.Running}}' "$NAME")" != "true" ]; then break; fi
  sleep 1
done
if ! curl -fsS "$BASE/healthz" >/dev/null 2>&1; then
  echo "The container did not become healthy. Its log:"
  docker logs "$NAME" 2>&1 | tail -40
  [ -n "${GITHUB_ACTIONS:-}" ] && echo "::error title=Docker smoke test::the image did not start; see the log above"
  exit 1
fi

TMP="$(mktemp -d)"
get() { curl -sS -o "$TMP/body" -D "$TMP/headers" -w '%{http_code}' "$BASE$1"; }
has_header() { grep -qi "^$1" "$TMP/headers"; }
has_body() { grep -q -- "$1" "$TMP/body"; }

[ "$(docker exec "$NAME" id -u)" != "0" ] && pass "runs as a non-root user" || fail "runs as a non-root user"
check "migrations ran on start (alembic_version exists)" \
  docker exec "$NAME" python -c "import sqlite3; sqlite3.connect('/tmp/smoke.db').execute('select * from alembic_version').fetchone()[0]"

[ "$(get /healthz)" = 200 ] && has_body '"ok":true' && pass "/healthz" || fail "/healthz"
[ "$(get /)" = 200 ] && has_body '/static/app.js' && pass "/ serves the app shell" || fail "/ serves the app shell"
has_header "content-security-policy: default-src 'none'" && pass "strict Content-Security-Policy" \
  || fail "strict Content-Security-Policy"
has_header "x-frame-options: DENY" && pass "X-Frame-Options" || fail "X-Frame-Options"
[ "$(get /static/app.js)" = 200 ] && pass "/static/app.js" || fail "/static/app.js"
[ "$(get /api/me)" = 401 ] && pass "/api/me needs a session" || fail "/api/me needs a session"
# Sent from the site's own origin, so the cross-site write guard lets it through to the route itself.
code="$(curl -sS -o /dev/null -w '%{http_code}' -X POST -H "Origin: $PUBLIC_URL" -H 'Content-Type: application/json' \
  -d '{"login":"x"}' "$BASE/auth/dev-login")"
[ "$code" = 404 ] && pass "development sign-in is off in production" || fail "development sign-in is off in production (got $code)"
code="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE/auth/github")"
[ "$code" = 302 ] && pass "GitHub sign-in redirects" || fail "GitHub sign-in redirects (got $code)"

[ "$(get /docs)" = 200 ] && has_body "<link rel=\"canonical\" href=\"$PUBLIC_URL/docs\">" \
  && pass "/docs canonical URL uses PUBLIC_URL" || fail "/docs canonical URL uses PUBLIC_URL"
has_body 'application/ld+json' && pass "/docs has structured data" || fail "/docs has structured data"
! has_header "set-cookie" && pass "/docs sets no cookie" || fail "/docs sets no cookie"
[ "$(get /robots.txt)" = 200 ] && has_body "Sitemap: $PUBLIC_URL/docs/sitemap.xml" && has_body "Disallow: /api/" \
  && pass "/robots.txt" || fail "/robots.txt"
[ "$(get /docs/search?q=token)" = 200 ] && has_header "x-robots-tag: noindex" \
  && pass "/docs/search is noindex" || fail "/docs/search is noindex"
[ "$(get /docs/no-such-page)" = 404 ] && has_header "x-robots-tag: noindex" \
  && pass "unknown docs pages are 404 and noindex" || fail "unknown docs pages are 404 and noindex"
[ "$(get /static/social-card.png)" = 200 ] && has_header "content-type: image/png" \
  && pass "social card image" || fail "social card image"

# Every URL in the sitemap must be absolute on PUBLIC_URL and served by this image (the docs are package data).
[ "$(get /sitemap.xml)" = 200 ] && pass "/sitemap.xml" || fail "/sitemap.xml"
grep -o '<loc>[^<]*</loc>' "$TMP/body" | sed 's/<loc>//; s/<\/loc>//' > "$TMP/locs"
count="$(wc -l < "$TMP/locs" | tr -d ' ')"
[ "$count" -ge 10 ] && pass "sitemap lists $count pages" || fail "sitemap lists only $count pages"
bad=0
while read -r loc; do
  case "$loc" in "$PUBLIC_URL"/docs*) ;; *) fail "sitemap URL not on PUBLIC_URL: $loc"; bad=1; continue ;; esac
  path="${loc#"$PUBLIC_URL"}"
  code="$(get "$path")"
  if [ "$code" != 200 ] || ! has_body "<link rel=\"canonical\" href=\"$loc\">"; then
    fail "sitemap page $path (HTTP $code, or its canonical URL is not its sitemap URL)"; bad=1
  fi
done < "$TMP/locs"
[ "$bad" = 0 ] && pass "every sitemap page is served with a matching canonical URL"

rm -rf "$TMP"
if [ "$failures" -gt 0 ]; then
  echo "$failures smoke check(s) failed. Container log:"
  docker logs "$NAME" 2>&1 | tail -40
  exit 1
fi
echo "All smoke checks passed."
