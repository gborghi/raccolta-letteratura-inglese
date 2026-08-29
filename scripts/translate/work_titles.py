# -*- coding: utf-8 -*-
"""Italian headings for the book-level aggregates whose chapters can't supply one.

assemble_aggregates derives a parent's title from its children and refuses to invent one. That
works for every chapter (its parts all repeat the chapter title) and for most books (their
chapters share a "Work — Chapter n" prefix). It cannot work for a collection of essays, where
each chapter carries only its own essay title and the book's name appears nowhere below it --
Belloc's "On Anything", Chesterton's "The Defendant", and the like.

For those the title is authored here by hand, keyed by the aggregate's vault path, in the spirit
of dickens_headings.WORK_HEAD: one deterministic substitution per work, decided once by a human,
rather than a guess made per build. Keys are the ENGLISH aggregate's path; the comment on each
line is its English H1, so the two can be checked against each other at a glance.

Wikilink targets are preserved exactly -- the alias is translated, never the target -- because
the emitter rejects a page whose heading introduces a target its source lacks.

Anything absent from this table stays untranslated and is reported by assemble_aggregates as
"senza titolo derivabile dai figli": add the work here rather than loosening the derivation.
"""

TITLES = {
    # --- Belloc: essay and verse collections, chapters carry only the piece's own title
    "Authors/Belloc/Atomized/Europe_and_the_Faith/Europe_and_the_Faith.md":
        "L'Europa e la Fede",                                   # Europe and the Faith
    "Authors/Belloc/Atomized/The_Path_to_Rome/The_Path_to_Rome.md":
        "Il cammino verso Roma",                                # The Path to Rome
    "Authors/Belloc/Atomized/The_Bad_Childs_Book_of_Beasts/The_Bad_Childs_Book_of_Beasts.md":
        "Il libro delle bestie del bambino cattivo",            # The Bad Child's Book of Beasts
    "Authors/Belloc/Atomized/But_Soft_We_Are_Observed/But_Soft_We_Are_Observed.md":
        "Ma piano: siamo osservati!",                           # But Soft: We Are Observed!
    "Authors/Belloc/Atomized/On_Nothing_and_Kindred_Subjects/On_Nothing_and_Kindred_Subjects.md":
        "Su nulla e argomenti affini",                          # On Nothing and Kindred Subjects
    "Authors/Belloc/Atomized/Hills_and_the_Sea/Hills_and_the_Sea.md":
        "Le colline e il mare",                                 # Hills and the Sea
    "Authors/Belloc/Atomized/On_Anything/On_Anything.md":
        "Su qualunque cosa",                                    # On Anything
    "Authors/Belloc/Atomized/Mr_Belloc_Still_Objects_to_Mr_Wellss_Outline_of_Hi/"
    "Mr_Belloc_Still_Objects_to_Mr_Wellss_Outline_of_Hi.md":
        "Il signor Belloc obietta ancora al «Profilo della storia» del signor Wells",
    "Authors/Belloc/Atomized/First_and_Last/First_and_Last.md":
        "Il primo e l'ultimo",                                  # First and Last
    "Authors/Belloc/Atomized/This_and_That_and_the_Other/This_and_That_and_the_Other.md":
        "Questo, quello e l'altro",                             # This and That and the Other
    "Authors/Belloc/Atomized/Economics_for_Helen/Economics_for_Helen.md":
        "Economia per Elena",                                   # Economics for Helen
    "Authors/Belloc/Atomized/Essays_of_a_Catholic/Essays_of_a_Catholic.md":
        "Saggi di un cattolico",                                # Essays of a Catholic
    "Authors/Belloc/Atomized/More_Beasts_for_Worse_Children/More_Beasts_for_Worse_Children.md":
        "Altre bestie per bambini peggiori",                    # More Beasts for Worse Children
    "Authors/Belloc/Atomized/Cautionary_Tales_for_Children/Cautionary_Tales_for_Children.md":
        "Racconti ammonitori per bambini",                      # Cautionary Tales for Children
    "Authors/Belloc/Atomized/Danton_A_Study/Danton_A_Study.md":
        "Danton: uno studio",                                   # Danton: A Study
    "Authors/Belloc/Atomized/The_Servile_State/The_Servile_State.md":
        "Lo Stato servile",                                     # The Servile State
    "Authors/Belloc/Atomized/More_Peers/More_Peers.md":
        "Altri Pari",                                           # More Peers
    "Authors/Belloc/Atomized/Sonnets_and_Verse/Sonnets_and_Verse.md":
        "Sonetti e versi",                                      # Sonnets and Verse
    "Authors/Belloc/Atomized/The_Two_Maps_of_Europe/The_Two_Maps_of_Europe.md":
        "Le due carte d'Europa",                                # The Two Maps of Europe
    "Authors/Belloc/Atomized/The_Mercy_of_Allah/The_Mercy_of_Allah.md":
        "La misericordia di Allah",                             # The Mercy of Allah
    "Authors/Belloc/Atomized/Calibans_Guide_to_Letters/Calibans_Guide_to_Letters.md":
        "La guida di Calibano alle lettere",                    # Caliban's Guide to Letters
    "Authors/Belloc/Atomized/The_Great_Inquiry/The_Great_Inquiry.md":
        "La grande inchiesta",                                  # The Great Inquiry
    "Authors/Belloc/Atomized/On/On.md":
        "Su",                                                   # On
    "Authors/Belloc/Atomized/On_Something/On_Something.md":
        "Su qualcosa",                                          # On Something

    # --- Chesterton: some of these carry the atomizer's slug as their English H1, so the
    # Italian is the work's real title rather than a rendering of the slug
    "Authors/Chesterton/Atomized/secret_Fr_Brown/secret_Fr_Brown.md":
        "Il segreto di padre Brown",                            # secret Fr Brown
    "Authors/Chesterton/Atomized/misc/misc.md":
        "[[misc|Scritti vari]]",                                # [[misc]]
    "Authors/Chesterton/Atomized/The_Defendant/The_Defendant.md":
        "L'imputato",                                           # (nessun H1 nell'originale)
    "Authors/Chesterton/Atomized/Wild_Ducks/Wild_Ducks.md":
        "Anatre selvatiche",                                    # Wild Ducks
    "Authors/Chesterton/Atomized/whats_wrong/whats_wrong.md":
        "Che cosa c'è che non va nel mondo",                     # whats wrong
    "Authors/Chesterton/Atomized/debate/debate.md":
        "[[debate|Dibattito]]",                                 # [[debate]]
    "Authors/Chesterton/Atomized/Napoleon_of_Notting_Hill/Napoleon_of_Notting_Hill.md":
        "Il Napoleone di Notting [[Hill]]",                     # Napoleon of Notting [[Hill]]
    "Authors/Chesterton/Atomized/trees_of_pride/trees_of_pride.md":
        "Gli alberi dell'[[Pride|orgoglio]]",                   # trees of [[Pride|pride]]

    # --- Conan Doyle
    "Authors/Conan_Doyle/Atomized/A_VISIT_TO_THREE_FRONTS_JUNE_1916/"
    "A_VISIT_TO_THREE_FRONTS_JUNE_1916.md":
        "UNA VISITA A TRE FRONTI. GIUGNO 1916",

    # --- Chapters whose own parts translated the title differently ("LA FESTA DELLO SCHIAVO"
    # against "LA VACANZA DELLO SCHIAVO"), with no majority to settle it. One of the readings
    # is chosen here; the part before the em dash follows the work's prevailing spelling so the
    # chapter doesn't announce itself differently from the rest of its book.
    "Authors/Belloc/Atomized/On_Something/Story_07_ON_A_VAN_TROMP.md":
        "Su qualcosa — SU UN VAN TROMP",
    "Authors/Chesterton/Atomized/longbow2/Chapter_05.md":
        "[[longbow2]] — Capitolo 5",
    "Authors/Chesterton/Atomized/ball_and_cross/Story_01_A_Discussion_Somewhat_in_the_Air.md":
        "palla e [[Cross|croce]] — Una discussione un po' campata in aria",
    "Authors/Chesterton/Atomized/ball_and_cross/Story_02_The_Religion_of_the_Stipendiary_Magistra.md":
        "palla e [[Cross|croce]] — La religione del magistrato stipendiato",
    "Authors/Chesterton/Atomized/trees_of_pride/Story_03_THE_TALE_OF_THE_PEACOCK_TREES.md":
        "alberi dell'[[Pride|orgoglio]] — IL RACCONTO DEGLI ALBERI DEL PAVONE",
    "Authors/Chesterton/Atomized/Twelve_Types/Story_09_tolstoy_TOLSTOY_AND_THE_CULT_OF_SIMPLICI.md":
        "Dodici tipi — [[tolstoy|TOLSTOJ]] E IL CULTO DELLA SEMPLICITÀ",
    "Authors/Chesterton/Atomized/Sanity/Story_03_ON_A_SENSE_OF_PROPORTION.md":
        "[[Sanity]] — SUL SENSO DELLA PROPORZIONE",
    "Authors/Chesterton/Atomized/Sanity/Story_11_THE_Wheel_WHEEL_OF_FATE.md":
        "[[Sanity]] — LA [[Wheel|RUOTA]] DEL DESTINO",
    "Authors/Chesterton/Atomized/Sanity/Story_13_THE_HOLIDAY_OF_THE_SLAVE.md":
        "[[Sanity]] — LA VACANZA DELLO SCHIAVO",
    "Authors/Chesterton/Atomized/TheAppOfTyranny/Chapter_05.md":
        "[[TheAppOfTyranny|L'appetito della tirannia]] — Capitolo 4",   # l'originale dice 4
    "Authors/Chesterton/Atomized/The_Glass_Walking_Stick/Story_02_History_In_Stone.md":
        "Il bastone da passeggio di vetro — La storia nella pietra",
    "Authors/Chesterton/Atomized/The_Glass_Walking_Stick/Story_03_Playing_With_An_Idea.md":
        "Il bastone da passeggio di vetro — Giocare con un'idea",
    "Authors/Chesterton/Atomized/The_Thing/Story_10_THE_EARLY_BIRD_IN_history_HISTORY.md":
        "La cosa — L'UCCELLO MATTINIERO NELLA [[history|STORIA]]",
    "Authors/Chesterton/Atomized/The_Flying_Inn/Chapter_01_A_SERMON_ON_INNS.md":
        "La Locanda Volante — Capitolo 1: UN SERMONE SULLE LOCANDE",
    "Authors/Chesterton/Atomized/The_Flying_Inn/Chapter_03_THE_SIGN_OF_THE_OLD_Ship_SHIP.md":
        "La Locanda Volante — Capitolo 3: L'INSEGNA DELLA «VECCHIA [[Ship|NAVE]]»",
    "Authors/Chesterton/Atomized/The_Flying_Inn/Chapter_07_THE_SOCIETY_OF_SIMPLE_SOULS.md":
        "La Locanda Volante — Capitolo 7: LA SOCIETÀ DELLE ANIME SEMPLICI",
    "Authors/Chesterton/Atomized/The_Flying_Inn/Chapter_12_VEGETARIANISM_IN_THE_FOREST.md":
        "La Locanda Volante — Capitolo 12: IL VEGETARIANISMO NELLA FORESTA",
    "Authors/Chesterton/Atomized/The_Flying_Inn/Chapter_15_THE_songs_SONGS_OF_THE_CAR_CLU.md":
        "La Locanda Volante — Capitolo 15: LE [[songs|CANZONI]] DEL CAR CLUB",
    "Authors/Chesterton/Atomized/Spice_Of_Life/Chapter_02_LITERATURE_IN_GENERAL.md":
        "Il sale della vita — Parte 1: LA LETTERATURA IN GENERALE",
    "Authors/Chesterton/Atomized/Spice_Of_Life/Chapter_04_THOUGHT_AND_BELIEF.md":
        "Il sale della vita — Parte 3: PENSIERO E FEDE",
    # I due che seguono NON sono titoli nuovi: estendono una scelta gia' fatta qui sopra.
    # I figli di questi aggregati rendono il nome dell'opera in modi discordi (The Flying Inn /
    # La locanda volante; Spice Of Life / Il sale della vita), percio' la derivazione dai figli
    # fallisce e il libro intero resta non assemblato -- Chapter_22 bloccava da solo tutto
    # The_Flying_Inn (1 figlio su 25).
    "Authors/Chesterton/Atomized/The_Flying_Inn/Chapter_22_THE_CHEMISTRY_OF_MR_CROOKE.md":
        "La Locanda Volante — Capitolo 22: LA CHIMICA DEL SIGNOR CROOKE",
    "Authors/Chesterton/Atomized/Spice_Of_Life/Spice_Of_Life.md":
        "Il sale della vita",                                   # Spice Of Life

    # --- Gli ultimi quattro libri di Chesterton che restavano non assemblati. Nessuno dei
    # quattro ha una maggioranza fra i suoi figli: le foglie rendono il nome dell'opera in
    # sei modi diversi (Well_And_Shallows) o non lo traducono affatto (GKC_Come_to_Think),
    # percio' la derivazione dai figli si rifiuta -- giustamente -- di inventare il titolo.
    # Dove una resa prevale nettamente e' quella che vince; dove non prevale nulla il titolo
    # e' scelto qui.
    "Authors/Chesterton/Atomized/Well_And_Shallows/Well_And_Shallows.md":
        "[[Well|Il pozzo]] e le secche",                        # [[Well]] And Shallows
    "Authors/Chesterton/Atomized/Poet_and_Lunatics/Poet_and_Lunatics.md":
        "Il poeta e i lunatici",                                # Poet and Lunatics
    "Authors/Chesterton/Atomized/Tremendous_Trifles/Tremendous_Trifles.md":
        "Tremende inezie",                                      # Tremendous Trifles
    # Come Spice_Of_Life e misc: l'H1 inglese e' lo slug dell'atomizzatore, non un titolo, e
    # tutti e 53 i figli lo ricopiano tale e quale. L'opera e' "Come to Think of It" (1930).
    "Authors/Chesterton/Atomized/GKC_Come_to_Think/GKC_Come_to_Think.md":
        "A pensarci bene",                                      # GKC Come to Think

    # --- Due titoli che la derivazione dai figli perde perche' il titolo del libro non e'
    # il titolo di nessuna sua parte. In entrambi i casi l'italiano esistente e' migliore
    # dell'assemblato e va conservato: e' l'assemblaggio che deve adeguarsi, non il titolo.
    # Endymion: il sottotitolo sta solo nell'H1 del file-libro ("A Poetic Romance"), le
    # sezioni si chiamano Book I..IV, quindi l'assemblatore ricostruiva il solo "Endymion".
    "Authors/Keats/Long/Endymion/Endymion.md":
        "[[Endymion]] — Un [[Romance|romanzo]] poetico",        # Endymion - A Poetic Romance
    # La Rima: l'H1 inglese e' in maiuscolo, e in maiuscolo sta l'italiano gia' pubblicato;
    # derivandolo dai figli usciva in minuscolo e divergeva a ogni riassemblaggio.
    "Authors/Coleridge/Long/The_Rime_of_the_Ancient_Mariner/The_Rime_of_the_Ancient_Mariner.md":
        "LA RIMA DEL [[Ancient Mariner|VECCHIO MARINAIO]]",     # THE RIME OF THE ANCIENT MARINER

    # --- Gli ultimi ventidue aggregati rimasti senza titolo derivabile. Le cause sono sempre
    # le stesse tre: la raccolta di racconti, i cui capitoli portano solo il titolo del singolo
    # racconto (tutto Conan Doyle qui sotto, e On Everything); il romanzo i cui capitoli si
    # limitano a numerarsi; e l'H1 che e' lo slug dell'atomizzatore invece di un titolo (i
    # quattro saggi di Chesterton). La convenzione di casing e' quella gia' in uso per Conan
    # Doyle -- maiuscole inglesi rese in tondo italiano ("Il cane dei Baskerville", "Il segno
    # dei quattro"): il maiuscolo di A_STUDY_IN_SCARLET resta l'unica eccezione, non il modello.
    "Authors/Belloc/Atomized/On_Everything/On_Everything.md":
        "Su tutto",                                             # On Everything
    # Agnes Grey e' un nome proprio: il titolo italiano corrente lo lascia tale e quale, e i
    # capitoli gia' tradotti scrivono "[[Agnes Grey]] — Capitolo n". Serve solo per il libro.
    "Authors/Bronte/Atomized/Agnes_Grey/Agnes_Grey.md":
        "[[Agnes Grey]]",                                       # [[Agnes Grey]]

    # --- Chesterton: quattro saggi in cui l'H1 e' lo slug e il titolo vero sta nel corpo
    # ("COCKNEYS AND THEIR JOKES", "LOGIC AND LAWN TENNIS", "The Shop of Ghosts", "Women in
    # the Workplace - and at Home"). Il bersaglio del wikilink e' lo slug e va conservato, cosi'
    # l'intero titolo italiano entra nell'alias -- uniforme per tutti e quattro.
    "Authors/Chesterton/Atomized/cockneys/cockneys.md":
        "[[cockneys|I cockney e le loro battute]]",             # [[cockneys]]
    "Authors/Chesterton/Atomized/logic/logic.md":
        "[[logic|La logica e il tennis su prato]]",             # [[logic]]
    "Authors/Chesterton/Atomized/shop-of-ghosts/shop-of-ghosts.md":
        "[[shop-of-ghosts|La bottega dei fantasmi]]",           # [[shop-of-ghosts]]
    "Authors/Chesterton/Atomized/Women_in_the_Workplace/Women_in_the_Workplace.md":
        "[[Women_in_the_Workplace|Le donne al lavoro e in casa]]",  # [[Women_in_the_Workplace]]

    # --- Conan Doyle: le quattordici raccolte e i romanzi rimasti. Dove esiste un titolo
    # italiano storico e' quello (His Last Bow circola da sempre come "L'ultimo saluto di
    # Sherlock Holmes", che nomina Holmes dove l'inglese non lo fa); altrove la resa e' letterale.
    "Authors/Conan_Doyle/Atomized/HIS_LAST_BOW/HIS_LAST_BOW.md":
        "L'ultimo saluto di Sherlock Holmes",                   # HIS LAST BOW
    "Authors/Conan_Doyle/Atomized/MY_FRIEND_THE_MURDERER_AND_OTHER_MYSTERIES_AND_ADV/"
    "MY_FRIEND_THE_MURDERER_AND_OTHER_MYSTERIES_AND_ADV.md":
        "Il mio amico l'assassino e altri misteri e avventure",  # MY FRIEND THE MURDERER AND OTHER MYSTERIES AND ADVENTURES
    "Authors/Conan_Doyle/Atomized/ROUND_THE_FIRE_STORIES/ROUND_THE_FIRE_STORIES.md":
        "Racconti attorno al fuoco",                            # ROUND THE FIRE STORIES
    "Authors/Conan_Doyle/Atomized/SIR_NIGEL/SIR_NIGEL.md":
        "Sir Nigel",                                            # SIR NIGEL
    "Authors/Conan_Doyle/Atomized/THE_ADVENTURES_OF_GERARD/THE_ADVENTURES_OF_GERARD.md":
        "Le avventure di Gerard",                               # THE ADVENTURES OF GERARD
    "Authors/Conan_Doyle/Atomized/THE_ADVENTURES_OF_SHERLOCK_HOLMES/THE_ADVENTURES_OF_SHERLOCK_HOLMES.md":
        "Le avventure di Sherlock Holmes",                      # THE ADVENTURES OF SHERLOCK HOLMES
    "Authors/Conan_Doyle/Atomized/THE_CAPTAIN_OF_THE_POLESTAR_AND_OTHER_TALES/"
    "THE_CAPTAIN_OF_THE_POLESTAR_AND_OTHER_TALES.md":
        "Il capitano della Polestar e altri racconti",          # THE CAPTAIN OF THE POLESTAR AND OTHER TALES.
    "Authors/Conan_Doyle/Atomized/THE_CASE_OF_MR_GEORGE_EDALJI/THE_CASE_OF_MR_GEORGE_EDALJI.md":
        "Il caso del signor George Edalji",                     # THE CASE OF MR. GEORGE EDALJI
    "Authors/Conan_Doyle/Atomized/THE_EXPLOITS_OF_BRIGADIER_GERARD/THE_EXPLOITS_OF_BRIGADIER_GERARD.md":
        "Le imprese del brigadiere Gerard",                     # THE EXPLOITS OF BRIGADIER GERARD
    "Authors/Conan_Doyle/Atomized/THE_GREEN_FLAG_AND_OTHER_STORIES/THE_GREEN_FLAG_AND_OTHER_STORIES.md":
        "La bandiera verde e altri racconti",                   # THE GREEN FLAG AND OTHER STORIES
    "Authors/Conan_Doyle/Atomized/THE_LAND_OF_MIST/THE_LAND_OF_MIST.md":
        "La terra della nebbia",                                # THE LAND OF MIST
    "Authors/Conan_Doyle/Atomized/THE_LAST_GALLEY/THE_LAST_GALLEY.md":
        "L'ultima galea",                                       # THE LAST GALLEY
    "Authors/Conan_Doyle/Atomized/THE_MAN_FROM_ARCHANGEL_AND_OTHER_TALES_OF_ADVENTUR/"
    "THE_MAN_FROM_ARCHANGEL_AND_OTHER_TALES_OF_ADVENTUR.md":
        "L'uomo di Arcangelo e altri racconti d'avventura",     # THE MAN FROM ARCHANGEL AND OTHER TALES OF ADVENTURE
    "Authors/Conan_Doyle/Atomized/THE_RETURN_OF_SHERLOCK_HOLMES/THE_RETURN_OF_SHERLOCK_HOLMES.md":
        "Il ritorno di Sherlock Holmes",                        # THE RETURN OF SHERLOCK HOLMES

    # --- Due titoli storici in cui il bersaglio del wikilink va conservato e tradotto l'alias.
    "Authors/Dickens/Atomized/A_Christmas_Carol/A_Christmas_Carol.md":
        "[[carol|Canto]] di Natale",                            # A Christmas [[carol|Carol]]
    "Authors/Poe/Atomized/The_Thousand_And_Second_Tale_of_Scheherazade/"
    "The_Thousand_And_Second_Tale_of_Scheherazade.md":
        "[[The Thousand-And-Second Tale of Scheherazade|Il millesimosecondo racconto di Sheherazade]]",
}
