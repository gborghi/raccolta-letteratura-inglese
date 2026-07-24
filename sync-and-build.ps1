# sync-and-build.ps1
# Regenerate vault-derived content, build the static Quartz site to quartz-eng-lit\public, and prep
# it for Cloudflare Pages. Everything stays IN PLACE inside the repo; content\ and public\ are both
# Dropbox-ignored so they never sync. Run from anywhere:
#   .\sync-and-build.ps1   # preprocess (SPA) -> plugin restore -> build -> search index -> slim /tags/ -> _headers
#
# This is the LOCAL Cloudflare Pages path (project `letteratura-inglese`, live at
# letteratura-inglese.pages.dev), mirroring the sibling Physics/Mathematics sites. GitHub Pages
# (gborghi.github.io/raccolta-letteratura-inglese) is kept as a BACKUP host and still deploys from
# CI on push to main (.github/workflows/deploy.yml) — this script does not touch it.
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$pub  = Join-Path $root "public"

Push-Location $root
try {
    # 1. Preprocess: wipe + regenerate content\ from the Obsidian vault (hardcoded VAULT/AUTHORS_DIR
    #    inside preprocess.mjs), emit generated pages + static\index.json + per-work chapter_related
    #    shards, then shell out to python scripts\make-author-pages.py. SPA=1 is REQUIRED — without
    #    it preprocess emits ~20k per-atom pages that blow Cloudflare's file cap. preprocess itself
    #    stamps content\ Dropbox-ignored. Dropbox must be RUNNING here so the vault reads hydrate.
    Write-Host "==> Preprocess (SPA=1): regenerating content\ from vault" -ForegroundColor Cyan
    $env:SPA = "1"
    node preprocess.mjs
    if ($LASTEXITCODE -ne 0) { Write-Error "preprocess.mjs failed"; exit 1 }
    Remove-Item Env:\SPA -ErrorAction SilentlyContinue

    # 2. Restore community plugins from quartz.lock.json into .quartz\ (gitignored). `npx quartz
    #    build` does NOT do this itself; needed after a clone or any lock change. Idempotent.
    Write-Host "==> Restoring Quartz community plugins" -ForegroundColor Cyan
    npx quartz plugin restore
    if ($LASTEXITCODE -ne 0) { Write-Error "quartz plugin restore failed"; exit 1 }

    # 3. Build to public\. ~7.8k pages under SPA; large enough to OOM Node at the default heap, so
    #    raise it. public\ is marked Dropbox-ignored right after Quartz recreates the dir.
    Write-Host "==> Building Quartz site -> $pub" -ForegroundColor Cyan
    $env:NODE_OPTIONS = "--max-old-space-size=14336"
    node quartz/bootstrap-cli.mjs build
    if ($LASTEXITCODE -ne 0) { Write-Error "quartz build failed"; exit 1 }
    Remove-Item Env:\NODE_OPTIONS -ErrorAction SilentlyContinue
    Set-Content -Path $pub -Stream com.dropbox.ignored -Value 1

    # 4. Post-build chain (same order as CI, .github/workflows/deploy.yml):
    #    a. Inject per-atom corpus search entries into the desktop index.
    Write-Host "==> Injecting atom search entries" -ForegroundColor Cyan
    node scripts/inject-atom-search.mjs
    if ($LASTEXITCODE -ne 0) { Write-Error "inject-atom-search failed"; exit 1 }

    #    b. TF-IDF-compress the 30MB+ desktop contentIndex.json (~11-12x) + build the master index,
    #       so the search button wires up in seconds, not tens of seconds.
    Write-Host "==> Compressing desktop index + building TF-IDF master" -ForegroundColor Cyan
    $env:NODE_OPTIONS = "--max-old-space-size=8192"
    node scripts/compress-search-index.mjs
    if ($LASTEXITCODE -ne 0) { Write-Error "compress-search-index failed"; exit 1 }
    Remove-Item Env:\NODE_OPTIONS -ErrorAction SilentlyContinue

    #    c. Derive the light contentIndexMobile.json from the full index.
    Write-Host "==> Building mobile index" -ForegroundColor Cyan
    node scripts/make-mobile-index.mjs
    if ($LASTEXITCODE -ne 0) { Write-Error "make-mobile-index failed"; exit 1 }

    #    d. Build the tiered (t0-t3) search shards from the TF-IDF master (progressive load).
    Write-Host "==> Building tiered search shards" -ForegroundColor Cyan
    node scripts/build-search-shards.mjs
    if ($LASTEXITCODE -ne 0) { Write-Error "build-search-shards failed"; exit 1 }

    #    e. Slim the tags-index page (server-rendered /tags/ can exceed Cloudflare's 25 MiB/file cap).
    Write-Host "==> Slimming tags index page" -ForegroundColor Cyan
    node scripts/gen-tags-table.mjs public
    if ($LASTEXITCODE -ne 0) { Write-Error "gen-tags-table failed"; exit 1 }

    # 5. Emit the Cloudflare Pages _headers file (immutable-asset caching). public\ is wiped every
    #    build, so re-create it here. Quartz emits index.css / *.js under STABLE names whose contents
    #    change every build, so they must NOT be immutable (a returning browser would keep a stale
    #    bundle for a week). Revalidate js/css; keep truly static fonts/images immutable.
    Write-Host "==> Writing Cloudflare _headers" -ForegroundColor Cyan
    $revalidateExts = "js","css"
    $immutableExts  = "woff2","svg","png","jpg","jpeg","webp","avif"
    $headerLines = @()
    foreach ($e in $revalidateExts) { $headerLines += "/*.$e"; $headerLines += "  Cache-Control: public, max-age=0, must-revalidate" }
    foreach ($e in $immutableExts)  { $headerLines += "/*.$e"; $headerLines += "  Cache-Control: public, max-age=604800, immutable" }
    Set-Content -Path (Join-Path $pub "_headers") -Value $headerLines -Encoding utf8

    # 6. robots.txt — allow all crawlers, point to the sitemap (Quartz emits /sitemap.xml).
    Write-Host "==> Writing robots.txt" -ForegroundColor Cyan
    $robots = "User-agent: *", "Allow: /", "", "Sitemap: https://letteratura-inglese.pages.dev/sitemap.xml"
    Set-Content -Path (Join-Path $pub "robots.txt") -Value $robots -Encoding utf8
}
finally {
    Pop-Location
}

Write-Host "==> Done. Output in $pub" -ForegroundColor Green
Write-Host "    Deploy to Cloudflare Pages:  npx wrangler pages deploy `"$pub`" --project-name letteratura-inglese --branch main" -ForegroundColor Green
