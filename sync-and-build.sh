#!/usr/bin/env bash
# sync-and-build.sh — macOS/Linux port of sync-and-build.ps1.
# Regenerate vault-derived content, build the static Quartz site to quartz-eng-lit/public, and prep
# it for Cloudflare Pages. Everything stays IN PLACE inside the repo; content/ + public/ are both
# cloud-sync-ignored so they never sync. Run from anywhere:  ./sync-and-build.sh
# (kept in sync with sync-and-build.ps1)
#
# This is the LOCAL Cloudflare Pages path (project `letteratura-inglese`, live at
# letteratura-inglese.pages.dev), mirroring the sibling Physics/Mathematics sites. GitHub Pages
# (gborghi.github.io/raccolta-letteratura-inglese) is kept as a BACKUP host and still deploys from
# CI on push to main (.github/workflows/deploy.yml) — this script does not touch it.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pub="$root/public"

is_mac=0; [[ "$(uname)" == "Darwin" ]] && is_mac=1

# Cloud-sync-ignore a path so its whole subtree stops syncing (and is never evicted to a cloud-only
# placeholder). macOS: stamp BOTH the modern File Provider flag `com.apple.fileprovider.ignore#P`
# (honored under ~/Library/CloudStorage/Dropbox) and the legacy `com.dropbox.ignored` xattr — the
# modern flag alone is a no-op on the old engine and vice-versa. Linux/legacy: com.dropbox.ignored.
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

cd "$root"

# 1. Preprocess: wipe + regenerate content/ from the Obsidian vault (hardcoded VAULT/AUTHORS_DIR
#    inside preprocess.mjs), emit generated pages + static/index.json + per-work chapter_related
#    shards, then shell out to python scripts/make-author-pages.py. SPA=1 is REQUIRED — without it
#    preprocess emits ~20k per-atom pages that blow Cloudflare's file cap. preprocess itself stamps
#    content/ cloud-ignored. Keep the sync client RUNNING so the vault reads hydrate.
echo "==> Preprocess (SPA=1): regenerating content/ from vault"
SPA=1 node preprocess.mjs

# 2. Restore community plugins from quartz.lock.json into .quartz/ (gitignored). `npx quartz build`
#    does NOT do this itself; needed after a clone or any lock change. Idempotent.
echo "==> Restoring Quartz community plugins"
npx quartz plugin restore

# 3. Build to public/. ~7.8k pages under SPA; large enough to OOM Node at the default heap.
echo "==> Building Quartz site -> $pub"
rm -rf "$pub"
NODE_OPTIONS="--max-old-space-size=14336" node quartz/bootstrap-cli.mjs build
dropbox_ignore "$pub"   # re-mark: Quartz rm's + recreates the output dir, dropping the xattr

# 4. Post-build chain (same order as CI, .github/workflows/deploy.yml):
echo "==> Injecting atom search entries"
node scripts/inject-atom-search.mjs

echo "==> Compressing desktop index + building TF-IDF master"
NODE_OPTIONS="--max-old-space-size=8192" node scripts/compress-search-index.mjs

echo "==> Building mobile index"
node scripts/make-mobile-index.mjs

echo "==> Building tiered search shards"
node scripts/build-search-shards.mjs

echo "==> Slimming tags index page"
node scripts/gen-tags-table.mjs public

# 5. Emit the Cloudflare Pages _headers file.
#    Quartz's index.css / *.js bundles use STABLE names but change contents every build, so they
#    must revalidate. Truly-static fonts/images stay immutable.
echo "==> Writing Cloudflare _headers"
: > "$pub/_headers"
for e in js css json; do
  printf '/*.%s\n  Cache-Control: public, max-age=0, must-revalidate\n' "$e" >> "$pub/_headers"
done
for e in woff2 svg png jpg jpeg webp avif; do
  printf '/*.%s\n  Cache-Control: public, max-age=604800, immutable\n' "$e" >> "$pub/_headers"
done

# 6. robots.txt — allow all crawlers, point to the sitemap (Quartz emits /sitemap.xml).
echo "==> Writing robots.txt"
printf 'User-agent: *\nAllow: /\n\nSitemap: https://letteratura-inglese.pages.dev/sitemap.xml\n' > "$pub/robots.txt"

echo "==> Done. Output in $pub"
echo "    Deploy to Cloudflare Pages:  npx wrangler pages deploy \"$pub\" --project-name letteratura-inglese --branch main"
