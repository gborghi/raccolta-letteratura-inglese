// Group the Keats lyrics into thematic collections, the way scripts/dickinson/ does.
//
// Keats already carries the same `cluster:` vocabulary as Dickinson on every
// *(Keats).md work-note, but only 140 works against Dickinson's 1764, so
// Dickinson's ">=10 members is a big cluster" rule collapses everything into one
// bucket. data/keats_tail_merge.json therefore folds the 44 source clusters into
// 13 finals of >=7 members each, and lists the 6 long works that keep their own
// reading page instead of being buried in a collection.
//
// One script instead of Dickinson's four, because Keats needs no move step: each
// poem is a single _raw file, so the atoms are COPIED into Atomized/<slug>/ and
// _raw stays the untouched source of truth.
//
//   node scripts/keats/build_keats_clusters.mjs            # dry run, prints the plan
//   node scripts/keats/build_keats_clusters.mjs --write    # actually writes
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const VAULT = path.resolve(ROOT, "..", "VaultEnglish");
const WORKS = path.join(VAULT, "Knowledge Graph", "Works");
const RAW = path.join(VAULT, "Authors", "Keats", "_raw");
const ATOMIZED = path.join(VAULT, "Authors", "Keats", "Atomized");
const MERGE_PATH = path.join(ROOT, "data", "keats_tail_merge.json");
const MANIFEST = path.join(ROOT, "data", "keats_cluster_map.json");

const WRITE = process.argv.includes("--write");
const TAG_CAP = 28;

// Works that get their own reading page. Endymion / Hyperion / The_Fall_of_Hyperion /
// Lamia are already atomized under Long/; Otho_the_Great and The_Cap_and_Bells are
// long enough to swamp any collection they landed in.
const LONG_WORKS = new Set([
  "141_Endymion_-_A_Poetic_Romance.md",
  "142_Hyperion.md",
  "136_The_Fall_of_Hyperion.md",
  "140_Lamia.md",
  "143_Otho_the_Great.md",
  "137_The_Cap_and_Bells.md",
]);

// Same slug shape as scripts/dickinson/build_cluster_map.mjs, so the two authors'
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
for (const f of fs.readdirSync(WORKS).sort()) {
  if (!f.endsWith("(Keats).md")) continue;
  const notePath = path.join(WORKS, f);
  const text = fs.readFileSync(notePath, "utf8");
  const fm = readFrontmatter(text);
  if (!fm || fm.data.type !== "work") continue;
  const source = fm.data.source || "";
  const rawFile = path.basename(source);
  if (LONG_WORKS.has(rawFile)) {
    excluded.push({ noteFile: f, rawFile, title: fm.data.title });
    continue;
  }
  if (!fs.existsSync(path.join(RAW, rawFile))) {
    console.error(`  !! source mancante, salto: ${f} -> ${source}`);
    continue;
  }
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

console.log(`note membro: ${members.length} | opere lunghe escluse: ${excluded.length}`);
console.log(`cluster finali: ${byCluster.size}\n`);
for (const [label, list] of [...byCluster].sort((a, b) => b[1].length - a[1].length)) {
  console.log(`  ${String(list.length).padStart(3)}  ${slugify(label)}`);
  if (list.length < 7) console.log(`       ^^ sotto la soglia di 7 membri`);
}
console.log("\nescluse (pagina propria):");
for (const e of excluded) console.log(`   ${e.rawFile}  (${e.title})`);

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
  m.atomRel = path.posix.join("Authors", "Keats", "Atomized", m.finalSlug, m.rawFile);
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
  const tags = ["graph/work", "author/Keats"];
  for (const [t] of [...counts].sort((a, b) => b[1] - a[1])) {
    if (t === "graph/work" || t === "author/Keats") continue;
    if (tags.length >= TAG_CAP) break;
    tags.push(t);
  }
  const body = [
    "---",
    `title: "${label}"`,
    'author: "Keats"',
    "type: work",
    `cluster: "${label}"`,
    `source: "Authors/Keats/Atomized/${slug}"`,
    "tags:",
    ...tags.map((t) => `  - ${t}`),
    "---",
    "",
    `# ${label}`,
    "",
    `Raccolta tematica di ${list.length} componimenti di John Keats.`,
    "",
    ...list.map((m) => `- [[${m.noteFile.replace(/\.md$/, "")}|${m.title}]]`),
    "",
  ].join("\n");
  fs.writeFileSync(path.join(WORKS, `${label.replace(/[\/:]/g, "-")} (Keats).md`), body, "utf8");
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
    },
    null,
    2,
  ),
  "utf8",
);
console.log(`manifest: ${path.relative(ROOT, MANIFEST)}`);
