// Group the Whitman lyrics into thematic collections, exactly as scripts/keats/ does.
//
// Whitman carries the same `cluster:` vocabulary as Dickinson and Keats on every
// *(Whitman).md work-note, but with 350 works the tail is long: 47 source
// clusters, 33 of them under 7 members (88 poems, six clusters of ONE).
// data/whitman_tail_merge.json folds that tail into the 14 clusters that already
// cleared the threshold, and lists the long works that stay out of the
// collections.
//
// This also unblocks translation: all 350 notes currently point into _raw/, which
// is unpublished, so today only 3 Whitman reading pages exist. Copying the poems
// into Atomized/<slug>/ is what makes them both publishable and translatable.
//
//   node scripts/whitman/build_whitman_clusters.mjs            # dry run, prints the plan
//   node scripts/whitman/build_whitman_clusters.mjs --write    # actually writes
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const VAULT = path.resolve(ROOT, "..", "VaultEnglish");
const WORKS = path.join(VAULT, "Knowledge Graph", "Works");
const RAW = path.join(VAULT, "Authors", "Whitman", "_raw");
const ATOMIZED = path.join(VAULT, "Authors", "Whitman", "Atomized");
const MERGE_PATH = path.join(ROOT, "data", "whitman_tail_merge.json");
const MANIFEST = path.join(ROOT, "data", "whitman_cluster_map.json");

const WRITE = process.argv.includes("--write");
const TAG_CAP = 28;
const RAW_PREFIX = "Authors/Whitman/_raw/";

// Works that stay out of the collections. Complete_Prose_Works and
// 025_Starting_from_Paumanok are already atomized under Atomized/;
// Leaves_of_Grass and Drum-Taps are CONTAINERS of the numbered poems and would
// duplicate the whole corpus inside a collection; 026_Song_of_Myself is 101 KB
// in 52 sections and deserves its own atomized page like the 025.
const LONG_WORKS = new Set([
  "Complete_Prose_Works.md",
  "Leaves_of_Grass.md",
  "Drum-Taps.md",
  "025_Starting_from_Paumanok.md",
  "026_Song_of_Myself.md",
]);

// Same slug shape as scripts/keats/ and scripts/dickinson/, so the authors'
// Atomized/ dirs read alike.
function slugify(s) {
  let out = s
    .toLowerCase()
    .replace(/[·’']/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (out.length > 60) {
    const cut = out.slice(0, 60);
    const i = cut.lastIndexOf("-");
    out = i > 30 ? cut.slice(0, i) : cut;
  }
  return out;
}

function readFrontmatter(text) {
  // Deliberately line-based, not a `\s*`-anchored regex: on a CRLF note a regex
  // swallows the CR into the value ("work\r") and the type gate then drops the
  // note silently. scripts/dickinson/rewrite_notes.mjs carries the same warning.
  const lines = text.split(/\r?\n/);
  if (lines[0] !== "---") return null;
  const end = lines.indexOf("---", 1);
  if (end < 0) return null;
  const data = {};
  const tags = [];
  let inTags = false;
  for (const line of lines.slice(1, end)) {
    const m = /^([A-Za-z_]+):\s*(.*)$/.exec(line);
    if (m) {
      inTags = m[1] === "tags";
      if (!inTags) data[m[1]] = m[2].replace(/^"(.*)"$/, "$1").trim();
      continue;
    }
    const t = /^\s*-\s+(.*)$/.exec(line);
    if (t && inTags) tags.push(t[1].trim());
  }
  return { data, tags, headEnd: end, lines };
}

const merge = JSON.parse(fs.readFileSync(MERGE_PATH, "utf8"));
for (const k of Object.keys(merge)) if (k.startsWith("_")) delete merge[k];

// --- collect the member notes ------------------------------------------------
const members = [];
const excluded = [];
const alreadyCollected = [];
const used = new Set();
for (const f of fs.readdirSync(WORKS).sort()) {
  if (!f.endsWith("(Whitman).md")) continue;
  const notePath = path.join(WORKS, f);
  const text = fs.readFileSync(notePath, "utf8");
  const fm = readFrontmatter(text);
  if (!fm || fm.data.type !== "work") continue;
  const source = fm.data.source || "";
  // A re-run must not eat its own output: the collection notes written below
  // point at Atomized/<slug>, not at _raw, so they drop out here.
  if (!source.startsWith(RAW_PREFIX)) {
    alreadyCollected.push({ noteFile: f, source });
    continue;
  }
  const rawFile = path.basename(source);
  if (LONG_WORKS.has(rawFile)) {
    excluded.push({ noteFile: f, rawFile, title: fm.data.title });
    used.add(rawFile);
    continue;
  }
  if (!fs.existsSync(path.join(RAW, rawFile))) {
    console.error(`  !! source mancante, salto: ${f} -> ${source}`);
    continue;
  }
  used.add(rawFile);
  const srcCluster = fm.data.cluster;
  const finalLabel = merge[srcCluster] || srcCluster;
  members.push({
    noteFile: f,
    notePath,
    title: fm.data.title,
    rawFile,
    srcCluster,
    finalLabel,
    finalSlug: slugify(finalLabel),
    tags: fm.tags,
    text,
    fm,
  });
}

const byCluster = new Map();
for (const m of members) {
  if (!byCluster.has(m.finalLabel)) byCluster.set(m.finalLabel, []);
  byCluster.get(m.finalLabel).push(m);
}

// _raw files nobody claims: they would be dropped in silence, so say so.
const orphans = fs
  .readdirSync(RAW)
  .filter((f) => f.endsWith(".md") && !used.has(f))
  .sort();

console.log(`note membro: ${members.length} | opere lunghe escluse: ${excluded.length}`);
if (alreadyCollected.length) console.log(`note collection preesistenti ignorate: ${alreadyCollected.length}`);
console.log(`cluster finali: ${byCluster.size}\n`);
for (const [label, list] of [...byCluster].sort((a, b) => b[1].length - a[1].length)) {
  console.log(`  ${String(list.length).padStart(3)}  ${slugify(label)}`);
  if (list.length < 7) console.log(`       ^^ sotto la soglia di 7 membri`);
}
console.log("\nescluse (pagina propria):");
for (const e of excluded) console.log(`   ${e.rawFile}  (${e.title})`);
console.log(`\n_raw senza nota-opera: ${orphans.length}`);
for (const o of orphans) {
  const kb = (fs.statSync(path.join(RAW, o)).size / 1024).toFixed(1);
  console.log(`   ${o}  (${kb} KB)`);
}

if (!WRITE) {
  console.log("\n--- dry run: rilancia con --write per scrivere ---");
  process.exit(0);
}

// --- 1. copy the atoms -------------------------------------------------------
let copied = 0;
for (const m of members) {
  const dir = path.join(ATOMIZED, m.finalSlug);
  fs.mkdirSync(dir, { recursive: true });
  const dest = path.join(dir, m.rawFile);
  if (!fs.existsSync(dest)) {
    fs.copyFileSync(path.join(RAW, m.rawFile), dest);
    copied++;
  }
  m.atomRel = path.posix.join("Authors", "Whitman", "Atomized", m.finalSlug, m.rawFile);
}
console.log(`\natomi copiati in Atomized/: ${copied}`);

// --- 2. member notes become page-less subwork nodes ---------------------------
let rewritten = 0;
for (const m of members) {
  const lines = [...m.fm.lines];
  let sawType = false;
  for (let i = 1; i < m.fm.headEnd; i++) {
    const line = lines[i];
    if (/^source:/.test(line)) lines[i] = `source: "${m.atomRel}"`;
    else if (/^cluster:/.test(line)) lines[i] = `cluster: "${m.finalLabel}"`;
    else if (/^type:/.test(line)) sawType = i;
  }
  if (sawType !== false && !lines.slice(1, m.fm.headEnd).some((l) => /^subwork:/.test(l))) {
    lines.splice(sawType + 1, 0, "subwork: true");
  }
  const out = lines.join("\n");
  if (out !== m.text) {
    fs.writeFileSync(m.notePath, out, "utf8");
    rewritten++;
  }
}
console.log(`note membro riscritte (subwork: true): ${rewritten}`);

// --- 3. one collection note per final cluster --------------------------------
let collections = 0;
for (const [label, list] of byCluster) {
  const slug = slugify(label);
  const counts = new Map();
  for (const m of list) for (const t of m.tags) counts.set(t, (counts.get(t) || 0) + 1);
  const tags = ["graph/work", "author/Whitman"];
  for (const [t] of [...counts].sort((a, b) => b[1] - a[1])) {
    if (t === "graph/work" || t === "author/Whitman") continue;
    if (tags.length >= TAG_CAP) break;
    tags.push(t);
  }
  const body = [
    "---",
    `title: "${label}"`,
    'author: "Whitman"',
    "type: work",
    `cluster: "${label}"`,
    `source: "Authors/Whitman/Atomized/${slug}"`,
    "tags:",
    ...tags.map((t) => `  - ${t}`),
    "---",
    "",
    `# ${label}`,
    "",
    `Raccolta tematica di ${list.length} componimenti di Walt Whitman.`,
    "",
    ...list.map((m) => `- [[${m.noteFile.replace(/\.md$/, "")}|${m.title}]]`),
    "",
  ].join("\n");
  fs.writeFileSync(path.join(WORKS, `${label.replace(/[\/:]/g, "-")} (Whitman).md`), body, "utf8");
  collections++;
}
console.log(`note collection scritte: ${collections}`);

fs.writeFileSync(
  MANIFEST,
  JSON.stringify(
    {
      generated: new Date().toISOString(),
      finals: [...byCluster].map(([label, list]) => ({
        label,
        slug: slugify(label),
        members: list.map((m) => ({ note: m.noteFile, title: m.title, atom: m.atomRel })),
      })),
      excluded,
      orphans,
    },
    null,
    2,
  ),
  "utf8",
);
console.log(`manifest: ${path.relative(ROOT, MANIFEST)}`);
