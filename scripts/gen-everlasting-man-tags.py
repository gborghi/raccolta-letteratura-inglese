# -*- coding: utf-8 -*-
"""Generate chapter_tags.json entries for the re-atomised Everlasting Man (19 chapters).

The re-atomisation gave every chapter a new URL, orphaning the 3 old (broken-chapter) tag entries
that drove the "suggested works" cards. This authors fresh entries -- grounded in each chapter's
actually-referenced figures/concepts -- keyed by the REAL atom slug (some are truncated by the
atomiser's 30-char slug cap, so we read the filenames rather than idealise them), and drops the
stale everlasting_man/the_everlasting_man keys.
"""
import os, re, glob, json

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ATOMS = os.path.join(ROOT, "..", "VaultEnglish", "Authors", "Chesterton", "Atomized", "everlasting_man")
TAGS = os.path.join(ROOT, "data", "chapter_tags.json")

# Tags by chapter NUMBER. characters = figures/entities the chapter actually invokes; themes = its
# argument; plot = one-sentence precis of the essay's move. Grounded in the chapter texts.
BY_NUM = {
    1:  {"characters": ["G.K. Chesterton"],
         "themes": ["scope of the book", "history vs theology", "the amateur and the specialist"],
         "plot": "Chesterton states that the book treats Christ and Christianity historically rather than devotionally, arguing the amateur has a right to weigh the facts the specialists supply."},
    2:  {"characters": ["the Catholic Church", "the Twelve Apostles"],
         "themes": ["seeing the familiar from outside", "the outsider's clear sight", "Christendom as strange"],
         "plot": "He proposes that both Christianity and man himself can only be judged truly by stepping outside them, as a traveller sees a country the native cannot."},
    3:  {"characters": ["prehistoric man", "the cave artist"],
         "themes": ["cave art and the uniqueness of man", "art as the mark of the soul", "the gulf between man and beast"],
         "plot": "Examining the painted caves, Chesterton argues the earliest man is revealed as an artist, and that this creative power sets a difference in kind, not degree, between man and the animals."},
    4:  {"characters": ["Pithecanthropus", "the Missing Link", "the professors"],
         "themes": ["the myth of prehistoric science", "conjecture dressed as fact", "evolutionary storytelling"],
         "plot": "He mocks the confident reconstructions of 'prehistoric man' from a few bones, arguing the professors invent a Missing Link and a savage past the evidence cannot support."},
    5:  {"characters": ["Babylon", "Egypt", "Troy", "the Nile civilisations"],
         "themes": ["antiquity of civilisation", "civilisation not primitive", "the ancient East"],
         "plot": "Chesterton argues that the oldest recorded civilisations are already mature and complex, so barbarism is a decline rather than the natural origin of humanity."},
    6:  {"characters": ["Israel", "the Jews", "Jupiter", "Apollo"],
         "themes": ["hidden monotheism behind paganism", "the God behind the gods", "Israel's witness"],
         "plot": "Behind the crowd of pagan gods he finds a buried memory of one God, kept alive chiefly by Israel, whom the nations half-remembered and mostly forgot."},
    7:  {"characters": ["Apollo", "Adonis", "Thor", "the Greek poets"],
         "themes": ["mythology as imagination", "the poetry of paganism", "myth vs philosophy"],
         "plot": "He reads the myths as works of the human imagination -- a search for God through beauty and story -- neither true religion nor mere error, but poetry seeking something real."},
    8:  {"characters": ["Buddha", "Confucius", "the philosophers of Asia", "Rome"],
         "themes": ["the philosophers vs the demons", "eastern wisdom", "paganism's two moods"],
         "plot": "Alongside the poets he sets the philosophers and the darker cults, contrasting the calm sages of Asia with the demon-worship whose cruelty culminates in Carthage."},
    9:  {"characters": ["Rome", "Carthage", "Hannibal", "Moloch"],
         "themes": ["Rome versus Carthage", "the war of gods and demons", "child-sacrifice and civilisation"],
         "plot": "The Punic Wars become a battle between the human paganism of Rome and the demonic child-sacrificing cult of Carthage, whose defeat Chesterton reads as the survival of humanity itself."},
    10: {"characters": ["Virgil", "Rome", "Carthage"],
         "themes": ["exhaustion of paganism", "the end of the old world", "waiting for something new"],
         "plot": "With paganism grown weary and its imagination spent, the ancient world reaches a quiet dead end, and Chesterton depicts a civilisation waiting, without knowing it, for a birth."},
    11: {"characters": ["Christ", "Bethlehem", "Confucius", "Aristotle"],
         "themes": ["the Nativity", "God in the cave", "revolution hidden in a stable"],
         "plot": "At Bethlehem the two strands -- the God behind the gods and the man in the cave -- meet, as the divine enters history in a cave and quietly overturns the ancient world."},
    12: {"characters": ["Christ", "the Gospel", "the Galilean"],
         "themes": ["the strangeness of the Gospels", "the unexpected Christ", "riddles of the sayings"],
         "plot": "He argues the Christ of the Gospels is not the mild teacher of modern imagination but a startling, riddling figure whose words no invented sage would have dared to speak."},
    13: {"characters": ["Jesus", "Socrates", "Buddha", "Peter", "Nazareth"],
         "themes": ["the uniqueness of the story", "the claim to be God", "comparison with the sages"],
         "plot": "Comparing Christ with Socrates and Buddha, Chesterton contends the central story -- a man who was also God, who died and rose -- is unlike anything else told of the founders of religions."},
    14: {"characters": ["the Church", "the Manicheans", "the Roman Empire"],
         "themes": ["the witness of the heretics", "orthodoxy defined against error", "the Church holding the balance"],
         "plot": "The early heresies, by their very one-sidedness, testify to the fullness the Church defended, keeping a difficult balance the Empire and the sects kept losing."},
    15: {"characters": ["Christendom", "Islam", "the East"],
         "themes": ["escape from the cycle of paganism", "Christendom as a breakout", "West and East"],
         "plot": "Where the older religions turned in endless cycles, Chesterton sees Christendom as an escape into something linear and new, distinct even from the later simplifications of Islam."},
    16: {"characters": ["the Faith", "Julian the Apostate", "the Renaissance"],
         "themes": ["the recurring death and revival of the Faith", "five deaths of Christianity", "resurrection as pattern"],
         "plot": "Tracing five moments when the Faith seemed dead -- from Julian to the Renaissance -- he argues that Christianity's repeated, improbable revivals are its most distinctive historical mark."},
    17: {"characters": ["Christ", "the Catholic Church"],
         "themes": ["the pattern of the whole book", "the God who returns", "history as unfinished"],
         "plot": "Chesterton draws the threads together, presenting the story of Christ and His Church as a drama that keeps ending and beginning again, still unconcluded."},
    18: {"characters": [],
         "themes": ["on prehistoric man", "limits of the evidence", "appendix"],
         "plot": "A short appendix returning to prehistoric man, cautioning again against building confident histories on fragmentary remains."},
    19: {"characters": [],
         "themes": ["on authority and accuracy", "sources and method", "appendix"],
         "plot": "A closing appendix on authority and accuracy, defending the book's use of sources and its historical method."},
}


def main():
    # map chapter number -> real slug from filenames
    num2slug = {}
    for p in glob.glob(os.path.join(ATOMS, "Chapter_*.md")):
        b = os.path.basename(p)
        if b.endswith(".it.md"):
            continue
        m = re.match(r"Chapter_(\d+)", b)
        if m:
            num2slug[int(m.group(1))] = b[:-3].lower()
    assert len(num2slug) == 19, f"expected 19 chapters, got {len(num2slug)}"

    tags = json.load(open(TAGS, encoding="utf-8"))
    # drop the stale keys (broken-chapter and old re-atomisation leftovers)
    stale = [k for k in tags if re.search(r"/(the_)?everlasting_man/", k)]
    for k in stale:
        del tags[k]
    # add fresh entries
    for num, slug in num2slug.items():
        key = f"testi/chesterton/atomized/everlasting_man/{slug}"
        tags[key] = BY_NUM[num]
    json.dump(tags, open(TAGS, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"removed {len(stale)} stale keys, added {len(num2slug)} fresh chapter entries")
    print("sample:")
    for num in (3, 9, 11):
        print(f"  ch{num}: {num2slug[num]}")


if __name__ == "__main__":
    main()
