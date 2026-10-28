# remove-ai-slop

Ein Claude-Skill, der KI-Slop aus Texten entfernt. Er findet 48 typische Muster, von „Das ist nicht X, das ist Y“ über das ewige Dreierpaket „schnell, einfach und sicher“ bis zu „Ich hoffe, das hilft!“, und schreibt den Text so um, dass der Inhalt bleibt und die Floskeln verschwinden. Gebaut für Deutsch, Englisch geht auch.

Ein Python-Detektor markiert die Stellen mit Zeilennummer, Claude prüft sie im Zusammenhang und überarbeitet. Danach vergleicht der Detektor beide Fassungen. Nichts wird erfunden: Wo eine Floskel eine Quelle oder Zahl bräuchte, die im Text fehlt, wird gestrichen oder nachgefragt.

## Installation

Füg das in Claude ein:

```
https://github.com/Ultra-Smashed/remove-ai-slop

installiere den Skill
```

Oder als Plugin in Claude Code:

```
/plugin marketplace add Ultra-Smashed/remove-ai-slop
/plugin install remove-ai-slop@remove-ai-slop
```

Oder den Ordner direkt kopieren:

```bash
git clone https://github.com/Ultra-Smashed/remove-ai-slop.git
cp -r remove-ai-slop/skills/remove-ai-slop ~/.claude/skills/
```

Ohne Claude Code kannst du `SKILL.md` und `formen.md` in einen Chat einfügen. Claude arbeitet dann nach derselben Methode, nur ohne Detektor.

Der Detektor braucht Python 3.8 oder neuer und keine Pakete.

## Benutzung

Sag Claude etwa „Entferne den KI-Slop aus diesem Text“, „Das klingt nach ChatGPT, mach es menschlicher“ oder „remove AI slop“. Drei Modi:

- **gründlich** (Standard): alle 48 Formen, auch Satzbau und Struktur
- **vorsichtig**: Floskeln und klare Fälle, der Satzbau bleibt
- **minimal**: nur Artefakte, Chatbot-Reste und Meta-Hinweise

Du bekommst den überarbeiteten Text und darunter eine kurze Liste: was entfernt wurde, was bewusst stehen blieb und wo der Autor noch etwas ergänzen muss.

Der Detektor geht auch allein:

```bash
cd skills/remove-ai-slop
python3 slop.py text.md                      # Bericht
python3 slop.py text.md --json               # als JSON
python3 slop.py text.md --formen 16,18,19    # nur Correctio, Trikolon, Gedankenstrich
python3 slop.py --vergleich alt.md neu.md    # vorher und nachher
python3 slop.py text.md --bereinigen -o neu.md   # unsichtbare Zeichen und Zitier-Reste entfernen
python3 slop.py --liste                      # alle 48 Formen
```

Mit `--strikt` endet der Aufruf mit Exit-Code 1, sobald etwas gefunden wird. Das passt in eine CI-Pipeline für Doku oder Blog.

## Die 48 Formen

**Wortwahl:** 1 Modewörter, 2 Gespreiztes Register, 3 Purple Prose, 4 Leere Adverbien, 5 „Fast“-Absicherung, 6 Kopula-Ausweichen („fungiert als“ statt „ist“), 7 Nominalstil, 8 Lehnübersetzungen („macht Sinn“), 9 Synonym-Karussell

**Rahmung und Bilder:** 10 Epochen-Eröffnung („In der heutigen schnelllebigen Welt“), 11 Metaphern-Krücke, 12 Wiederkehrendes Bild, 13 Bedeutungs-Aufblähung, 14 Erfundenes Konzeptlabel, 15 Analogie-Parade (Netflix, Uber, Airbnb)

**Satzbau:** 16 Correctio („nicht X, sondern Y“), 17 Negations-Countdown, 18 Trikolon, 19 Gedankenstrich-Inflation, 20 Doppelpunkt-Enthüllung, 21 Hypophora, 22 Stakkato, 23 Anapher, 24 Partizip-Anhängsel, 25 Absicherungs-Stapel, 26 Klammer-Nuance, 27 Überflüssiger Kontrast, 28 Nachklapp, 29 Scheinspanne („von Start-ups bis zu Konzernen“), 30 Gleichtakt

**Rhetorik:** 31 Räuspern, 32 Meta-Hinweis („Es ist wichtig zu beachten“), 33 Lehrer-Modus, 34 Falsche Spannung, 35 „Stell dir vor“, 36 Vage Autorität („Studien zeigen“), 37 „Trotz aller Herausforderungen“, 38 Ausgewogenheits-Reflex, 39 Gespielte Offenheit, 40 Anbiederung und Empathie-Theater

**Struktur und Format:** 41 Konnektoren-Sucht, 42 Aufsatz-Schluss, 43 Listen-Reflex, 44 Markdown-Deko, 45 Dramatisches Fragment, 46 Ein-Punkt-Verwässerung

**Chatbot-Reste:** 47 Chatbot-Floskeln, 48 Technische Artefakte (unsichtbare Zeichen, `oaicite`, `utm_source=chatgpt.com`)

Jede Form steht mit Erkennungszeichen, Vorher-Nachher-Beispiel und Ausnahmen in [`formen.md`](skills/remove-ai-slop/formen.md). 43 Formen findet der Detektor über Muster. Fünf (9, 12, 28, 31, 46) erkennt nur, wer den ganzen Text liest, dafür sorgt die Anleitung in `SKILL.md`.

## Eigene Floskeln ergänzen

Alle Muster stehen in [`lexikon.json`](skills/remove-ai-slop/lexikon.json), getrennt nach `de` und `en`. Jede Form hat eine Liste regulärer Ausdrücke, Groß- und Kleinschreibung spielt keine Rolle. Neue Floskel eintragen, `python3 -m unittest discover -s tests` laufen lassen, fertig. Ausnahmen für echte Dreiergruppen („Rot, Gelb und Grün“) stehen unter `trikolon_ausnahmen`.

## Grenzen

Das ist kein KI-Detektor. Menschen schreiben auch Trikolons, Gedankenstriche und „darüber hinaus“. Ein Befund heißt „schau dir diese Stelle an“, nicht „das hat eine Maschine geschrieben“. Muster finden Formen, keinen Stil: Ein Text ohne Befund kann trotzdem leer sein, und ein guter Text darf eine bewusst gesetzte Anapher haben.

## Quellen

- [slop-cop](https://github.com/awnist/slop-cop) von awnist und der [Go-Port](https://github.com/yasyf/slop-cop) von yasyf (beide MIT): der Regelkatalog, auf dem die 48 Formen aufbauen. Für Deutsch angepasst und um Nominalstil, Lehnübersetzungen, Purple Prose, Chatbot-Floskeln und Artefakte ergänzt.
- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing): Vokabular, Kopula-Ausweichen, Bedeutungs-Aufblähung, Zitier-Artefakte.
- humanizer-de: deutsche Muster und Beispiele.

## Lizenz

MIT, siehe [LICENSE](LICENSE). Von [Christopher Thanisch](https://thanisch.co).
