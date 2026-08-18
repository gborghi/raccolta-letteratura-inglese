#!/usr/bin/env bash
# Rebuild public/ with a larger heap + run the post-build chain (steps 3-6 of sync-and-build.sh).
# Preprocess + plugin-restore already done; content/ carries the Dickinson poetic-head fix.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pub="$root/public"
cd "$root"

is_mac=0; [[ "$(uname)" == "Darwin" ]] && is_mac=1
dropbox_ignore() {
  local target="$1"
  [[ -e "$target" ]] || return 0
  if [[ "$is_mac" == 1 ]]; then
    xattr -w 'com.apple.fileprovider.ignore#P' 1 "$target" 2>/dev/null || true
    xattr -w com.dropbox.ignored 1 "$target" 2>/dev/null || true
  else
    attr -s com.dropbox.ignored -V 1 "$target" >/dev/null 2>&1 || \
      setfattr -n user.com.dropbox.ignored -v 1 "$target" 2>/dev/null || true
  fi
}

echo "==> [1/8] Build (heap 20480)"
rm -rf "$pub"
NODE_OPTIONS="--max-old-space-size=20480" node quartz/bootstrap-cli.mjs build
dropbox_ignore "$pub"

echo "==> [2/8] inject-atom-search"
node scripts/inject-atom-search.mjs

echo "==> [3/8] compress-search-index"
NODE_OPTIONS="--max-old-space-size=8192" node scripts/compress-search-index.mjs

echo "==> [4/8] make-mobile-index"
node scripts/make-mobile-index.mjs

echo "==> [5/8] build-search-shards"
node scripts/build-search-shards.mjs

echo "==> [6/8] gen-tags-table"
node scripts/gen-tags-table.mjs public

echo "==> [7/8] _headers"
: > "$pub/_headers"
for e in js css json; do
  printf '/*.%s\n  Cache-Control: public, max-age=0, must-revalidate\n' "$e" >> "$pub/_headers"
done
for e in woff2 svg png jpg jpeg webp avif; do
  printf '/*.%s\n  Cache-Control: public, max-age=604800, immutable\n' "$e" >> "$pub/_headers"
done

echo "==> [8/8] robots.txt"
printf 'User-agent: *\nAllow: /\n\nSitemap: https://letteratura-inglese.pages.dev/sitemap.xml\n' > "$pub/robots.txt"

echo "==> ALL DONE. Deploy: npx wrangler pages deploy \"$pub\" --project-name letteratura-inglese --branch main"
