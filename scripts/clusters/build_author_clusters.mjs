// Group a lyric author's short poems into thematic collections, the way
// scripts/dickinson/, scripts/whitman/ and scripts/keats/ already do.
//
// Those three are near-identical 230-line copies of each other; Coleridge and
// Eliot would have made a fourth and a fifth, so the routine lives here once and
// the per-author differences (which works keep their own reading page) sit in
// CONFIG below. The older scripts are deliberately left alone: they have already
// been run, and re-running a cluster build is not idempotent (see the warning
// further down).
//
//   node scripts/clusters/build_author_clusters.mjs Coleridge           # dry run
//   node scripts/clusters/build_author_clusters.mjs Coleridge --write   # writes
//
// ONE SHOT. After --write the member notes point at Atomized/<slug>/ instead of
// _raw/, so a second run finds 0 members and prints an empty plan without
// complaining. The merge table can only be negotiated while the first run is
// still a dry run.
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const VAULT = path.resolve(ROOT, "..", "VaultEnglish");
const WORKS = path.join(VAULT, "Knowledge Graph", "Works");

const TAG_CAP = 28;
const MIN_MEMBERS = 7;

const CONFIG = {
  Coleridge: {
    fullName: "Samuel Taylor Coleridge",
    // Own reading page, so they stay out of the collections: the six plays and
    // the two long poems are already split under Plays/ and Long/, and the 41x
    // block is editorial apparatus (drafts, prose versions, prefaces) that would
    // swamp any collection it landed in.
    longWorks: [
      "P00_THE_FALL_OF_ROBESPIERRE.md",
      "P01_OSORIO.md",
      "P02_THE_PICCOLOMINI.md",
      "P03_THE_DEATH_OF_WALLENSTEIN.md",
      "P04_REMORSE.md",
      "P05_ZAPOLYA_A_CHRISTMAS_TALE_IN_TWO_PARTS.md",
      "137_THE_RIME_OF_THE_ANCIENT_MARINER.md",
      "142_CHRISTABEL.md",
      "108_RELIGIOUS_MUSINGS.md",
      "109_CHRISTIAN_RELIGION.md",
      "111_THE_DESTINY_OF_NATIONS_A_VISION.md",
      "153_FEARS_IN_SOLITUDE.md",
      "155_THE_THREE_GRAVES.md",
      "279_THE_IMPROVISATORE_OR_JOHN_ANDERSON_MY_JO_JOHN.md",
      "412_FIRST_DRAFTS_EARLY_VERSIONS_ETC.md",
      "413_I.md",
      "414_ALLEGORIC_VISION.md",
      "415_APOLOGETIC_PREFACE_TO_FIRE_FAMINE_AND_SLAUGHTER.md",
      "416_PROSE_VERSIONS_OF_POEMS_ETC.md",
    ],
  },
  Eliot: {
    fullName: "T. S. Eliot",
    // Three groups: the seven works already split under Long/ (plus the section
    // files that live inside those splits, which would otherwise be published a
    // second time inside a collection), the five plays, and the table-of-contents
    // stubs the EPUB extractor left behind as if they were poems.
    longWorks: [
      // already split under Long/
      "027_THE_WASTE_LAND_1922.md",
      "028_I_The_Burial_of_the_Dead.md",
      "029_II_A_Game_of_Chess.md",
      "030_III_The_Fire_Sermon.md",
      "031_IV_Death_by_Water.md",
      "032_V_What_the_Thunder_said.md",
      "033_Notes_on_the_Waste_Land.md",
      "034_THE_HOLLOW_MEN_1925.md",
      "035_ASH-WEDNESDAY_1930.md",
      "036_I_Because_I_do_not_hope_to_turn_again.md",
      "037_II_Lady_three_white_leopards_sat_under_a_juniper-tree.md",
      "038_III_At_the_first_turning_of_the_second_stair.md",
      "039_IV_Who_walked_between_the_violet_and_the_violet.md",
      "040_V_If_the_lost_word_is_lost_if_the_spent_word_is_spent.md",
      "041_VI_Although_I_do_not_hope_to_turn_again.md",
      "069_Burnt_Norton_1935.md",
      "070_East_Coker_1940.md",
      "071_The_Dry_Salvages_1941.md",
      "072_Little_Gidding.md",
      // plays
      "095_PLAYS.md",
      "096_MURDER_IN_THE_CATHEDRAL.md",
      "097_THE_FAMILY_REUNION.md",
      "098_THE_COCKTAIL_PARTY.md",
      "099_THE_CONFIDENTIAL_CLERK.md",
      "100_THE_ELDER_STATESMAN.md",
      "049_Sweeney_Agonistes.md",
      "048_UNFINISHED_POEMS.md",
      // container / listing pages, not poems
      "000_COLLECTED_POEMS_19091962.md",
      "001_PRUFROCK_and_Other_Observations_1917.md",
      "042_ARIEL_POEMS.md",
      "051_MINOR_POEMS.md",
      "057_CHORUSES_FROM_THE_ROCK_1934.md",
      "068_FOUR_QUARTETS.md",
      "073_OCCASIONAL_VERSES.md",
      "079_OLD_POSSUMS_BOOK_OF_PRACTICAL_CATS.md",
      "101_APPENDIX_POEMS_WRITTEN_IN_EARLY_YOUTH.md",
      "125_Also_by_T_S_Eliot.md",
    ],
  },
};

const AUTHOR = process.argv[2];
const WRITE = process.argv.includes("--write");
if (!CONFIG[AUTHOR]) {
  console.error(`uso: node ${path.relative(ROOT, fileURLToPath(import.meta.url))} <${Object.keys(CONFIG).join("|")}> [--write]`);
  process.exit(1);
}
const { fullName, longWorks } = CONFIG[AUTHOR];
const LONG_WORKS = new Set(longWorks);
const RAW = path.join(VAULT, "Authors", AUTHOR, "_raw");
const ATOMIZED = path.join(VAULT, "Authors", AUTHOR, "Atomized");
const MERGE_PATH = path.join(ROOT, "data", `${AUTHOR.toLowerCase()}_tail_merge.json`);
const MANIFEST = path.join(ROOT, "data", `${AUTHOR.toLowerCase()}_cluster_map.json`);

// Same slug shape as scripts/dickinson/build_cluster_map.mjs, so every author's
// Atomized/ dir reads alike.
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

const merge = fs.existsSync(MERGE_PATH) ? JSON.parse(fs.readFileSync(MERGE_PATH, "utf8")) : {};
for (const k of Object.keys(merge)) if (k.startsWith("_")) delete merge[k];

// --- collect the member notes ------------------------------------------------
const members = [];
const excluded = [];
const seenLong = new Set();
for (const f of fs.readdirSync(WORKS).sort()) {
  if (!f.endsWith(`(${AUTHOR}).md`)) continue;
  const notePath = path.join(WORKS, f);
  const text = fs.readFileSync(notePath, "utf8");
  const fm = readFrontmatter(text);
  if (!fm || fm.data.type !== "work") continue;
  const source = fm.data.source || "";
  const rawFile = path.basename(source);
  if (LONG_WORKS.has(rawFile)) {
    seenLong.add(rawFile);
    excluded.push({ noteFile: f, rawFile, title: fm.data.title });
    continue;
  }
  if (!fs.existsSync(path.join(RAW, rawFile))) {
    console.error(`  !! source mancante, salto: ${f} -> ${source}`);
    continue;
  }
  const srcCluster = fm.data.cluster;
  if (!srcCluster) {
    console.error(`  !! senza cluster, salto: ${f}`);
    continue;
  }
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

// A name in longWorks that matched nothing is a typo, and a typo silently drops
// an exclusion back into a collection.
for (const w of LONG_WORKS) if (!seenLong.has(w)) console.error(`  !! esclusione senza nota: ${w}`);

const byCluster = new Map();
for (const m of members) {
  if (!byCluster.has(m.finalLabel)) byCluster.set(m.finalLabel, []);
  byCluster.get(m.finalLabel).push(m);
}

console.log(`${AUTHOR}: note membro ${members.length} | opere con pagina propria ${excluded.length}`);
console.log(`cluster finali: ${byCluster.size}\n`);
let under = 0;
for (const [label, list] of [...byCluster].sort((a, b) => b[1].length - a[1].length)) {
  console.log(`  ${String(list.length).padStart(3)}  ${label}`);
  if (list.length < MIN_MEMBERS) under++;
}
if (under) console.log(`\n${under} cluster sotto la soglia di ${MIN_MEMBERS} membri`);

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
  m.atomRel = path.posix.join("Authors", AUTHOR, "Atomized", m.finalSlug, m.rawFile);
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
  const tags = ["graph/work", `author/${AUTHOR}`];
  for (const [t] of [...counts].sort((a, b) => b[1] - a[1])) {
    if (t === "graph/work" || t === `author/${AUTHOR}`) continue;
    if (tags.length >= TAG_CAP) break;
    tags.push(t);
  }
  const body = [
    "---",
    `title: "${label}"`,
    `author: "${AUTHOR}"`,
    "type: work",
    `cluster: "${label}"`,
    `source: "Authors/${AUTHOR}/Atomized/${slug}"`,
    "tags:",
    ...tags.map((t) => `  - ${t}`),
    "---",
    "",
    `# ${label}`,
    "",
    `Raccolta tematica di ${list.length} componimenti di ${fullName}.`,
    "",
    ...list.map((m) => `- [[${m.noteFile.replace(/\.md$/, "")}|${m.title}]]`),
    "",
  ].join("\n");
  fs.writeFileSync(path.join(WORKS, `${label.replace(/[\/:]/g, "-")} (${AUTHOR}).md`), body, "utf8");
  collections++;
}
console.log(`note collection scritte: ${collections}`);

fs.writeFileSync(
  MANIFEST,
  JSON.stringify(
    {
      generated: new Date().toISOString(),
      author: AUTHOR,
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
