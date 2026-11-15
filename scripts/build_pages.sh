#!/usr/bin/env bash
# Build the public GitHub Pages site into web/dist, with no market data.
#
#   PAGES_BASE=/<repo>/ scripts/build_pages.sh     for https://<owner>.github.io/<repo>/
#
# PAGES_BASE is required: the workflow sets it to the repository's name, so the site follows a rename.
#
# The site ships exactly three JSON files: evidence.json (the Explorer's results), the synthetic mock storm and
# web/pages/index.json (storm list and metrics, every storm marked withheld). Any other JSON in dist fails the build,
# so a real bundle left in web/public/bundles on a local machine can never be published. The GitHub workflow
# (.github/workflows/pages.yml) runs this same script.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${PAGES_BASE:?set PAGES_BASE to the Pages base path, e.g. /<repo>/ (the workflow sets it from the repository name)}"
case "$BASE" in
  /*/) ;;
  *) echo "pages: PAGES_BASE must start and end with /, got: $BASE" >&2; exit 1 ;;
esac
PY="$(command -v python3 || command -v python)"

"$PY" "$ROOT/scripts/build_pages_index.py" --check

cd "$ROOT/web"
VITE_API_BASE=off npx vite build --base "$BASE"   # no live server on Pages: no /api requests

# Bundles: only the synthetic mock storm and the sanitized index, whatever public/bundles held.
rm -rf dist/bundles
mkdir dist/bundles
cp public/bundles/mock_storm.json dist/bundles/mock_storm.json
cp pages/index.json dist/bundles/index.json

extra="$(cd dist && find . -name '*.json' ! -path ./evidence.json ! -path ./bundles/mock_storm.json ! -path ./bundles/index.json)"
if [ -n "$extra" ]; then
  echo "pages: refusing to publish these JSON files:" >&2
  echo "$extra" >&2
  exit 1
fi
"$PY" - "$ROOT/web/dist/bundles/mock_storm.json" <<'EOF'
import json, sys
b = json.load(open(sys.argv[1]))
assert b.get("source") == "synthetic", f"mock_storm.json is not labelled synthetic: source={b.get('source')!r}"
EOF
echo "pages: built web/dist for base $BASE (evidence.json, bundles/mock_storm.json, bundles/index.json; no market data)"
