// Adopt the 33 Whitman poems in _raw/ that never got a work note.
//
// build_whitman_clusters.mjs collects members by reading the *(Whitman).md work
// notes, so a _raw poem with no note is invisible to it: 33 short pieces (the
// "By the Roadside" epigrams, the Thought/Thoughts sequences, the late Sands at
// Seventy fragments) would stay out of every collection and off the site forever.
// This gives each one a note, copies its atom into the right collection dir and
// splices it into that collection's list.
//
// The cluster assignments below are editorial and were made poem by poem from the
// texts; ASSIGN is the whole decision, everything else is mechanical.
//
//   node scripts/whitman/add_orphan_poems.mjs            # dry run, prints the plan
//   node scripts/whitman/add_orphan_poems.mjs --write    # actually writes
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const VAULT = path.resolve(ROOT, "..", "VaultEnglish");
const WORKS = path.join(VAULT, "Knowledge Graph", "Works");
const RAW = path.join(VAULT, "Authors", "Whitman", "_raw");
const ATOMIZED = path.join(VAULT, "Authors", "Whitman", "Atomized");
const MANIFEST = path.join(ROOT, "data", "whitman_cluster_map.json");

const WRITE = process.argv.includes("--write");

const NATION = "Nationalism and Patriotism · Democracy · Liberty Political Freedom";
const IDENTITY = "Identity · Free Verse · Eternal Return";
const COMRADE = "Comradeship · Union · Hands Hand in Hand";
const SELFKNOW = "Self-Knowledge · Immortality · Self-Reliance";
const MORTALITY = "Mortality · Grave · Memento Mori";
const WONDER = "Wonder and Gratitude · Sublime · Storm";
const JOURNEY = "Journey · Ship";
const STARS = "Stars · Night · Military Camp";
const NATURE = "Nature · Book of Nature · Natural Order";
const WAR = "War and its Cost · American Civil War · Battlefield";
const GRIEF = "Grief and Loss · Elegy · Clothing and Costume";
const HEROISM = "Heroism · Hero · Last Stand";

const ASSIGN = {
  "004_To_Foreign_Lands.md": NATION, //          "to define America, her athletic Democracy"
  "023_To_You.md": COMRADE, //                   the stranger addressed in the street
  "024_Thou_Reader.md": IDENTITY, //             "thou reader throbbest life ... the same as I"
  "037_I_Am_He_That_Aches_with_Love.md": COMRADE, // Children of Adam, amorous love as gravitation
  "067_Here_the_Frailest_Leaves_of_Me.md": COMRADE, // Calamus, the hidden leaves that expose him
  "120_Perfections.md": SELFKNOW, //             "as souls only understand souls"
  "127_A_Farm_Picture.md": NATURE, //            the barn door, the sunlit pasture
  "128_A_Child_s_Amaze.md": WONDER, //           the boy amazed at the preacher's God
  "130_Beautiful_Women.md": MORTALITY, //        "the old are more beautiful than the young"
  "131_Mother_and_Babe.md": WONDER, //           the hush'd contemplation of mother and child
  "132_Thought.md": NATION, //                   masses following those who do not believe in men
  "133_Visor_d.md": SELFKNOW, //                 the perpetual mask, appearance against reality
  "134_Thought.md": NATION, //                   of justice, and the natural judges
  "135_Gliding_O_er_all.md": JOURNEY, //         "as a ship on the waters advancing"
  "137_Thought.md": NATION, //                   of Equality
  "138_To_Old_Age.md": MORTALITY, //             the estuary pouring into the great sea
  "140_Offerings.md": COMRADE, //                the cluster of friends gathered round each
  "249_Thought.md": MORTALITY, //                the wreck at sea: "are souls drown'd so?"
  "252_Pensive_and_Faltering.md": MORTALITY, //  "the words the Dead I write"
  "265_Thoughts.md": NATION, //                  public opinion, the Democracies resplendent
  "280_Thoughts.md": NATION, //                  the years of America, the Union welded in blood
  "289_The_Untold_Want.md": JOURNEY, //          "now voyager sail thou forth"
  "290_Portals.md": MORTALITY, //                "what are those of life but for death?"
  "291_These_Carols.md": IDENTITY, //            his own songs dedicated to the Invisible World
  "294_Mannahatta.md": NATION, //                the city's aboriginal name resumed
  "299_The_Bravest_Soldiers.md": WAR, //         the bravest fell unnamed, unknown
  "307_Memories.md": GRIEF, //                   "how sweet the silent backward tracings"
  "310_Abraham_Lincoln_Born_Feb_12_1809.md": HEROISM, // the birthday breath of prayer
  "332_Life_and_Death.md": MORTALITY, //         the two old problems, insoluble, passed on
  "341_Twilight.md": STARS, //                   "a haze--nirwana--rest and night--oblivion"
  "348_An_Evening_Lull.md": STARS, //            the calm that comes toward the ending day
  "356_Apparitions.md": MORTALITY, //            solid things as apparitions, non-realities
  "358_An_Ended_Day.md": WONDER, //              "now triumph! transformation! jubilate!"
};

// Eight of these poems share a title with a Whitman poem that already has a note
// (there are five "Thought"s and two "Thoughts" in Leaves of Grass, two
// "Mannahatta"s, two "To You"s) — which is very likely why they never got one:
// the note filename is <Title> (Whitman).md and would have collided. They are
// disambiguated the way editions cite them, by first line.
const RETITLE = {
  "023_To_You.md": "To You (Stranger, if you passing meet me)",
  "132_Thought.md": "Thought (Of obedience, faith, adhesiveness)",
  "134_Thought.md": "Thought (Of justice)",
  "137_Thought.md": "Thought (Of Equality)",
  "249_Thought.md": "Thought (As I sit with others at a great feast)",
  "265_Thoughts.md": "Thoughts (Of public opinion)",
  "280_Thoughts.md": "Thoughts (Of these years I sing)",
  "294_Mannahatta.md": "Mannahatta (My city’s fit and noble name resumed)",
};

// Same slug shape as build_whitman_clusters.mjs.
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

// The _raw files are linkified, so the H1 can read "# A [[Child]]'s Amaze".
function unwrap(s) {
  return s
    .replace(/\[\[([^\[\]|]+)\|([^\[\]|]+)\]\]/g, "$2")
    .replace(/\[\[([^\[\]|]+)\]\]/g, "$1");
}

const plan = [];
for (const [rawFile, label] of Object.entries(ASSIGN)) {
  const rawPath = path.join(RAW, rawFile);
  if (!fs.existsSync(rawPath)) {
    console.error(`  !! _raw mancante, salto: ${rawFile}`);
    continue;
  }
  const text = fs.readFileSync(rawPath, "utf8");
  const m = /^#\s+(.*)$/m.exec(text);
  const title = RETITLE[rawFile] || unwrap(m ? m[1].trim() : path.basename(rawFile, ".md"));
  const noteFile = `${title.replace(/[\/:]/g, "-")} (Whitman).md`;
  const slug = slugify(label);
  plan.push({
    rawFile,
    label,
    slug,
    title,
    noteFile,
    atomRel: path.posix.join("Authors", "Whitman", "Atomized", slug, rawFile),
    exists: fs.existsSync(path.join(WORKS, noteFile)),
  });
}

const byCluster = new Map();
for (const p of plan) {
  if (!byCluster.has(p.label)) byCluster.set(p.label, []);
  byCluster.get(p.label).push(p);
}

console.log(`poesie adottate: ${plan.length}\n`);
for (const [label, list] of [...byCluster].sort((a, b) => b[1].length - a[1].length)) {
  console.log(`  ${String(list.length).padStart(2)}  ${slugify(label)}`);
  for (const p of list) console.log(`        ${p.title}${p.exists ? "   (nota GIA' esistente!)" : ""}`);
}

const clash = plan.filter((p) => p.exists);
if (clash.length) {
  console.error(`\n!! ${clash.length} note esistono gia': interrompo, andrebbero sovrascritte.`);
  process.exit(1);
}

if (!WRITE) {
  console.log("\n--- dry run: rilancia con --write per scrivere ---");
  process.exit(0);
}

// --- 1. atom + work note ------------------------------------------------------
for (const p of plan) {
  fs.mkdirSync(path.join(ATOMIZED, p.slug), { recursive: true });
  fs.copyFileSync(path.join(RAW, p.rawFile), path.join(ATOMIZED, p.slug, p.rawFile));
  const note = [
    "---",
    `title: "${p.title.replace(/"/g, "'")}"`,
    'author: "Whitman"',
    "type: work",
    "subwork: true",
    `cluster: "${p.label}"`,
    `source: "${p.atomRel}"`,
    "tags:",
    "  - graph/work",
    "  - author/Whitman",
    "---",
    "",
    `# ${p.title}`,
    "",
    `*by Whitman*  ·  **Cluster:** [[${p.label}]]`,
    "",
  ].join("\n");
  fs.writeFileSync(path.join(WORKS, p.noteFile), note, "utf8");
}
console.log(`\nnote scritte: ${plan.length} | atomi copiati: ${plan.length}`);

// --- 2. splice into the collection notes --------------------------------------
let touched = 0;
for (const [label, list] of byCluster) {
  const collPath = path.join(WORKS, `${label.replace(/[\/:]/g, "-")} (Whitman).md`);
  if (!fs.existsSync(collPath)) {
    console.error(`  !! collection mancante: ${path.basename(collPath)}`);
    continue;
  }
  const lines = fs.readFileSync(collPath, "utf8").split("\n");
  const rows = lines.filter((l) => l.startsWith("- [["));
  const first = lines.findIndex((l) => l.startsWith("- [["));
  const merged = [...rows, ...list.map((p) => `- [[${p.noteFile.replace(/\.md$/, "")}|${p.title}]]`)].sort(
    (a, b) => a.localeCompare(b, "en"),
  );
  const out = [
    ...lines.slice(0, first).map((l) =>
      /^Raccolta tematica di \d+ componimenti/.test(l)
        ? `Raccolta tematica di ${merged.length} componimenti di Walt Whitman.`
        : l,
    ),
    ...merged,
    "",
  ].join("\n");
  fs.writeFileSync(collPath, out, "utf8");
  touched++;
}
console.log(`note collection aggiornate: ${touched}`);

// --- 3. keep the manifest honest ----------------------------------------------
if (fs.existsSync(MANIFEST)) {
  const man = JSON.parse(fs.readFileSync(MANIFEST, "utf8"));
  for (const f of man.finals) {
    for (const p of byCluster.get(f.label) || []) {
      f.members.push({ note: p.noteFile, title: p.title, atom: p.atomRel });
    }
    f.members.sort((a, b) => a.note.localeCompare(b.note, "en"));
  }
  man.orphans = (man.orphans || []).filter((o) => !(o in ASSIGN));
  man.adopted = plan.map((p) => ({ note: p.noteFile, title: p.title, cluster: p.label }));
  fs.writeFileSync(MANIFEST, JSON.stringify(man, null, 2), "utf8");
  console.log(`manifest aggiornato: ${path.relative(ROOT, MANIFEST)}`);
}
