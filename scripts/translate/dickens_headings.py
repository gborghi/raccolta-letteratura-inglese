# -*- coding: utf-8 -*-
"""Deterministic, link-preserving Italian translation of Dickens chapter-title headings.

WHY: Tower mangles headings — it mistranslates ("SPECTRO" for spettro) and drops/renames the
concept wikilinks embedded in a title ("MARLEY'S [[Ghost|GHOST]]" -> a bare invented [[Fantasma]]),
which both reads wrong on the page AND trips the emitter's invented-target guard (REJECT).

STRATEGY (chosen with the user):
- WORK TITLES are rendered with their CANONICAL Italian title, authored by hand, links preserved
  (WORK_HEAD). One distinct work-part form per work, so this is a clean deterministic substitution.
- The 26 chapter titles that embed a CONCEPT link (Ghost, Home, Journey, Water, Shadow, Road,
  Poverty, Castle, ...) are hand-curated in full (TITLE_OVERRIDE): exact Italian, every link placed
  on the right word, every target identical to the source (so nothing is invented or dropped).
- Everything else is  "# <work> — Chapter N: <plain descriptive subtitle>"  with NO link in the
  subtitle: the work + section are deterministic, and only the link-free subtitle goes to Tower
  (strict title prompt -> good Italian, and it CAN'T invent a link because there is none to place).

Guarantee: targets(IT heading) is always a subset of targets(EN heading) -> the invented-target
REJECT can never fire from a heading again.
"""
import re

SECTION = {"Chapter": "Capitolo", "Stave": "Strofa", "Book": "Libro", "Part": "Parte"}

# EN work-part (segment before the em dash, verbatim) -> canonical Italian, links preserved.
WORK_HEAD = {
    "# [[Great Expectations]]":                             "# [[Great Expectations|Grandi aspettative]]",
    "# [[Oliver Twist]]":                                   "# [[Oliver Twist]]",
    "# A Christmas [[carol|Carol]]":                        "# [[carol|Canto]] di Natale",
    "# A Tale of Two Cities":                               "# Racconto di due città",
    "# Hard Times":                                         "# Tempi difficili",
    "# The Chimes":                                         "# Le campane",
    "# The Cricket on the Hearth":                          "# Il grillo del focolare",
    "# The Battle of Life":                                 "# La battaglia della vita",
    "# The Haunted Man and the [[Ghost]]'s Bargain":        "# L'uomo perseguitato e il patto del [[Ghost|fantasma]]",
    "# The Old Curiosity Shop":                             "# La bottega dell'antiquario",
    "# [[Nicholas Nickleby]]":                              "# [[Nicholas Nickleby]]",
    "# [[David Copperfield]]":                              "# [[David Copperfield]]",
    "# Bleak [[house|House]]":                              "# [[house|Casa]] desolata",
    "# Little Dorrit":                                      "# La piccola Dorrit",
    "# Dombey and Son":                                     "# Dombey e Figlio",
    "# Our Mutual Friend":                                  "# Il nostro comune amico",
    "# [[Martin Chuzzlewit]]":                              "# [[Martin Chuzzlewit]]",
    "# [[Barnaby Rudge]]":                                  "# [[Barnaby Rudge]]",
    "# The [[Pickwick]] Papers":                            "# Il Circolo [[Pickwick]]",
    "# The Mystery of [[Edwin Drood]]":                     "# Il mistero di [[Edwin Drood]]",
    "# Sketches by Boz":                                    "# Bozzetti di Boz",
    "# American Notes":                                     "# Note americane",
    "# A [[Child]]'s [[history|History]] of England":       "# [[history|Storia]] d'Inghilterra per [[Child|ragazzi]]",
}

# Full curated headings for chapter titles that embed a concept link. Keys are the EN heading with
# the "(part N)" suffix stripped; the caller re-appends " (parte N)".
TITLE_OVERRIDE = {
    "# A Christmas [[carol|Carol]] — Stave 1: MARLEY'S [[Ghost|GHOST]]":
        "# [[carol|Canto]] di Natale — Strofa 1: IL [[Ghost|FANTASMA]] DI MARLEY",
    "# A Christmas [[carol|Carol]] — Stave 2: THE FIRST OF THE THREE SPIRITS":
        "# [[carol|Canto]] di Natale — Strofa 2: IL PRIMO DEI TRE SPIRITI",
    "# A Christmas [[carol|Carol]] — Stave 3: THE SECOND OF THE THREE SPIRITS":
        "# [[carol|Canto]] di Natale — Strofa 3: IL SECONDO DEI TRE SPIRITI",
    "# A Christmas [[carol|Carol]] — Stave 4: THE LAST OF THE SPIRITS":
        "# [[carol|Canto]] di Natale — Strofa 4: L'ULTIMO DEGLI SPIRITI",
    "# A Christmas [[carol|Carol]] — Stave 5: THE END OF IT":
        "# [[carol|Canto]] di Natale — Strofa 5: LA CONCLUSIONE",

    "# [[David Copperfield]] — Chapter 7: MY ‘FIRST HALF’ AT SALEM [[house|HOUSE]]":
        "# [[David Copperfield]] — Capitolo 7: IL MIO ‘PRIMO SEMESTRE’ A [[house|SALEM HOUSE]]",
    "# [[David Copperfield]] — Chapter 20: STEERFORTH’S [[Home|HOME]]":
        "# [[David Copperfield]] — Capitolo 20: LA [[Home|CASA]] DI STEERFORTH",
    "# [[David Copperfield]] — Chapter 29: I VISIT STEERFORTH AT HIS [[Home|HOME]], AGAIN":
        "# [[David Copperfield]] — Capitolo 29: TORNO A FAR VISITA A STEERFORTH A [[Home|CASA]] SUA",
    "# [[David Copperfield]] — Chapter 5: I AM SENT AWAY FROM [[Home|HOME]]":
        "# [[David Copperfield]] — Capitolo 5: VENGO MANDATO VIA DA [[Home|CASA]]",
    "# [[David Copperfield]] — Chapter 37: A LITTLE COLD [[Water|WATER]]":
        "# [[David Copperfield]] — Capitolo 37: UN PO’ D’[[Water|ACQUA]] FREDDA",
    "# [[David Copperfield]] — Chapter 51: THE BEGINNING OF A LONGER [[Journey|JOURNEY]]":
        "# [[David Copperfield]] — Capitolo 51: L’INIZIO DI UN [[Journey|VIAGGIO]] PIÙ LUNGO",
    "# [[David Copperfield]] — Chapter 32: THE BEGINNING OF A LONG [[Journey|JOURNEY]]":
        "# [[David Copperfield]] — Capitolo 32: L’INIZIO DI UN LUNGO [[Journey|VIAGGIO]]",

    "# Our Mutual Friend — Book 2: [[Birds|BIRDS]] OF A FEATHER":
        "# Il nostro comune amico — Libro 2: [[Birds|UCCELLI]] DELLO STESSO PIUMAGGIO",

    "# Little Dorrit — Chapter 10: The [[Dreams]] of Mrs Flintwinch thicken":
        "# La piccola Dorrit — Capitolo 10: I [[Dreams|sogni]] della signora Flintwinch si infittiscono",
    "# Little Dorrit — Chapter 10: Containing the whole Science of [[government|Government]]":
        "# La piccola Dorrit — Capitolo 10: Che contiene l’intera Scienza del [[government|Governo]]",
    "# Little Dorrit — Chapter 3: On the [[Road]]":
        "# La piccola Dorrit — Capitolo 3: Sulla [[Road|strada]]",
    "# Little Dorrit — Chapter 21: The [[history|History]] of a [[Self]]-Tormentor":
        "# La piccola Dorrit — Capitolo 21: La [[history|storia]] di chi tormenta [[Self|sé stesso]]",
    "# Little Dorrit — Chapter 3: [[Home]]":
        "# La piccola Dorrit — Capitolo 3: [[Home|Casa]]",
    "# Little Dorrit — Chapter 21: [[Mr Merdle]]’s Complaint":
        "# La piccola Dorrit — Capitolo 21: Il disturbo del [[Mr Merdle|signor Merdle]]",
    "# Little Dorrit — Chapter 19: The Storming of the [[Castle]] in the Air":
        "# La piccola Dorrit — Capitolo 19: L’assalto al [[Castle|castello]] in aria",
    "# Little Dorrit — Book 1: [[Poverty|POVERTY]]":
        "# La piccola Dorrit — Libro 1: [[Poverty|POVERTÀ]]",
    "# Little Dorrit — Chapter 22: Who passes by this [[Road]] so late?":
        "# La piccola Dorrit — Capitolo 22: Chi passa per questa [[Road|strada]] così tardi?",
    "# Little Dorrit — Chapter 18: Little Dorrit’s [[Lover]]":
        "# La piccola Dorrit — Capitolo 18: L’[[Lover|innamorato]] della piccola Dorrit",
    "# Little Dorrit — Chapter 1: Sun and [[Shadow]]":
        "# La piccola Dorrit — Capitolo 1: Sole e [[Shadow|ombra]]",
    "# Little Dorrit — Chapter 7: The [[Child]] of the Marshalsea":
        "# La piccola Dorrit — Capitolo 7: La [[Child|bambina]] della Marshalsea",
    "# Little Dorrit — Chapter 4: Mrs Flintwinch has [[A Dream|a Dream]]":
        "# La piccola Dorrit — Capitolo 4: La signora Flintwinch fa [[A Dream|un sogno]]",
    "# Little Dorrit — Chapter 35: What was behind [[Mr Pancks]] on Little Dorrit’s Hand":
        "# La piccola Dorrit — Capitolo 35: Cosa si celava dietro [[Mr Pancks|il signor Pancks]] sulla mano della piccola Dorrit",
    "# Little Dorrit — Chapter 36: The Marshalsea becomes an [[Orphan]]":
        "# La piccola Dorrit — Capitolo 36: La Marshalsea diventa [[Orphan|orfana]]",
    "# Little Dorrit — Chapter 18: A [[Castle]] in the Air":
        "# La piccola Dorrit — Capitolo 18: Un [[Castle|castello]] in aria",

    "# Dombey and Son — Chapter 30: The interval before the [[Marriage]]":
        "# Dombey e Figlio — Capitolo 30: L’intervallo prima del [[Marriage|matrimonio]]",
}

PART_RE = re.compile(r"\s*\(part (\d+)\)\s*$")
DASH_RE = re.compile(r"^(.*?)(?:\s+[—-]\s+)(.*)$")
SEC_RE = re.compile(r"^(Chapter|Stave|Book|Part)\s+(\d+)\s*(?::\s*(.*))?$", re.S)
WIKI_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")


def _targets(text):
    return sorted(m.group(1) for m in WIKI_RE.finditer(text))


def is_heading_block(block):
    """A block the emitter treats as an H1/H2 title: starts with '#'. One-line by construction."""
    return block.lstrip().startswith("#")


def translate_heading(heading, translate_plain):
    """Return (it_heading, unknown) for a '#'-heading block.

    translate_plain(str)->str renders a LINK-FREE subtitle to Italian (the only piece that needs a
    model). `unknown` is True when the work-part isn't in WORK_HEAD (caller should fall back).
    Never introduces a wikilink target absent from the source.
    """
    m = PART_RE.search(heading)
    suffix = f" (parte {m.group(1)})" if m else ""
    base = PART_RE.sub("", heading).rstrip()

    if base in TITLE_OVERRIDE:
        return TITLE_OVERRIDE[base] + suffix, False

    dm = DASH_RE.match(base)
    work_part = dm.group(1) if dm else base
    rest = dm.group(2) if dm else None

    it_work = WORK_HEAD.get(work_part.strip())
    if it_work is None:
        return heading, True                       # unknown work: let caller fall back to Tower

    if not rest:
        return it_work + suffix, False

    sm = SEC_RE.match(rest)
    if sm:
        sec = SECTION.get(sm.group(1), sm.group(1))
        num = sm.group(2)
        desc = (sm.group(3) or "").strip()
        out = f"{it_work} — {sec} {num}"
        if desc:
            out += f": {translate_plain(desc)}"
    else:
        out = f"{it_work} — {translate_plain(rest.strip())}"

    # Safety net: a heading must never contribute a target the source lacks.
    src = set(_targets(heading))
    for t in _targets(out):
        if t not in src:
            return heading, True                   # unexpected -> fall back rather than publish a bad link
    return out + suffix, False
