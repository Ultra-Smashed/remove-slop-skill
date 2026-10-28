#!/usr/bin/env python3
"""remove-slop-skill: findet die 48 Formen von KI-Slop in einem Text (Deutsch und Englisch).

    python3 slop.py entwurf.md                  Bericht
    python3 slop.py entwurf.md --json           Bericht als JSON
    python3 slop.py --vergleich alt.md neu.md   vorher und nachher
    python3 slop.py entwurf.md --bereinigen -o sauber.md
                                                entfernt nur unsichtbare Zeichen und Zitier-Artefakte

Ein Befund ist ein Hinweis, kein Urteil über die Herkunft des Texts.
Nur Standardbibliothek, Python 3.8 oder neuer.
"""

import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEXIKON = os.path.join(HERE, "lexikon.json")

WORD = re.compile(r"[A-Za-zÄÖÜäöüßéèàç0-9]+(?:['’\-][A-Za-zÄÖÜäöüßéèàç0-9]+)*")
LIST_ITEM = re.compile(r"^\s*(?:[-*+•]|\d{1,2}[.)])\s+")
HEADING = re.compile(r"^\s*#{1,6}\s")
INVISIBLE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad\u202a-\u202e\u2066-\u2069]")
CITATION = re.compile(
    r"【[^】\n]{0,60}】"
    r"|:?contentReference\[oaicite:\d+\](?:\{[^}\n]*\})?"
    r"|\[oaicite:\d+\]"
    r"|\bturn\d+(?:search|news|view|fetch)\d+\b"
    r"|[?&]utm_source=(?:chatgpt\.com|openai|copilot\.com|perplexity(?:\.ai)?|gemini)[^\s)\]\"'>]*")
ARROWS = re.compile("[→⇒➜➔➡⟶↳]")
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2705]")
EM_DASH = re.compile("\u2014")
SPACED_DASH = re.compile(r"(?<=\w)[ \u00a0](?:\u2013|-{1,2})[ \u00a0](?=\w)")
BOLD = re.compile(r"\*\*[^*\n]+\*\*|__[^_\n]+__")
BOLD_BULLET = re.compile(r"^\s*(?:[-*+•]|\d{1,2}[.)])\s+(?:\*\*[^*\n]+\*\*|__[^_\n]+__)\s*:?")
PAREN = re.compile(r"\(([^()\n]{3,140})\)")
NOMINAL = re.compile(r"\b[A-ZÄÖÜ][a-zäöüß]{3,}(?:ung|heit|keit|ion|ität|ierung|ismus|nahme)(?:en)?\b")
ABBREV = re.compile(r"(?:\b(?:z|d|u|o|v|s|bzw|ca|usw|etc|vgl|Dr|Nr|Abs|Prof|St|Mio|Mrd|evtl|ggf|inkl|zzgl|bspw|e|i|vs|Jh|Tel|Str)\.|\b[A-ZÄÖÜa-z]\.|\d+\.)$")
SENT_END = re.compile(r"(?<=[.!?…])[\"“”»«)\]]*\s+")

DE_HINTS = {"der", "die", "das", "und", "ist", "nicht", "ich", "wir", "mit", "für", "auf", "ein", "eine", "auch", "sich",
            "du", "sie", "es", "zu", "den", "dem", "von", "dass", "wie", "aber", "oder", "noch", "nur"}
EN_HINTS = {"the", "and", "is", "not", "with", "for", "you", "we", "this", "that", "are", "it", "of", "to", "a", "in",
            "on", "be", "but", "or", "your", "our", "was", "have"}
NEGATION_START = {"kein", "keine", "keinen", "keiner", "keines", "nicht", "ohne", "no", "not", "never", "nie"}
PARTIKELN = {"aus", "an", "auf", "ab", "bei", "durch", "für", "gegen", "in", "mit", "nach", "ohne", "über", "um",
             "unter", "von", "vor", "zu", "dann", "auch", "noch", "nur", "so", "da", "hier", "dort", "the", "a", "an",
             "to", "of", "in", "on", "with", "for", "it", "is", "so", "then", "too", "also"}


class SlopError(Exception):
    pass


def load_lexikon(path=LEXIKON):
    with open(path, encoding="utf-8") as fh:
        lex = json.load(fh)
    for f in lex["formen"]:
        for lang in ("de", "en"):
            f["_re_" + lang] = [re.compile(p, re.IGNORECASE) for p in f.get(lang, [])]
    lex["_by_id"] = {f["id"]: f for f in lex["formen"]}
    return lex


def mask(text, zitate=False):
    """Code, URLs und (ohne zitate) Zitate in „…“ und »…« durch Leerzeichen gleicher Länge ersetzen."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    out = re.sub(r"\A---\n.*?\n---\n", blank, text, flags=re.S)
    out = re.sub(r"```.*?```", blank, out, flags=re.S)
    out = re.sub(r"`[^`\n]+`", blank, out)
    out = re.sub(r"https?://\S+|www\.\S+", blank, out)
    if not zitate:
        out = re.sub(r"„[^“”„\n]{1,300}[“”]|»[^«»\n]{1,300}«", blank, out)
    return out


def detect_language(text):
    words = [w.lower() for w in WORD.findall(text)]
    de = sum(1 for w in words if w in DE_HINTS)
    en = sum(1 for w in words if w in EN_HINTS)
    return "en" if en > de else "de"


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def blocks(text):
    """Absätze als (start, ende, text, art). art: prosa, liste, ueberschrift."""
    out = []
    for m in re.finditer(r"(?:[^\n]+\n?)+", text):
        chunk = m.group(0).rstrip("\n")
        if not chunk.strip():
            continue
        lines = chunk.split("\n")
        if all(LIST_ITEM.match(l) or not l.strip() for l in lines):
            kind = "liste"
        elif len(lines) == 1 and HEADING.match(chunk):
            kind = "ueberschrift"
        else:
            kind = "prosa"
        out.append((m.start(), m.start() + len(chunk), chunk, kind))
    return out


def sentences(text):
    """Sätze als (start, ende, text) aus Prosa-Absätzen; Listenpunkte und Überschriften zählen je als ein Satz."""
    out = []
    for start, end, chunk, kind in blocks(text):
        if kind != "prosa":
            pos = start
            for line in chunk.split("\n"):
                if line.strip():
                    out.append((pos, pos + len(line), line, kind))
                pos += len(line) + 1
            continue
        pos = 0
        pieces = []
        for m in SENT_END.finditer(chunk):
            pieces.append((pos, m.start()))
            pos = m.end()
        pieces.append((pos, len(chunk)))
        merged = []
        for a, b in pieces:
            if merged and ABBREV.search(chunk[merged[-1][0]:merged[-1][1]].rstrip()):
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))
        for a, b in merged:
            s = chunk[a:b].strip()
            if s:
                lead = len(chunk[a:b]) - len(chunk[a:b].lstrip())
                out.append((start + a + lead, start + a + lead + len(s), s, "prosa"))
    return out


def words(s):
    return WORD.findall(s)


class Finder(object):
    def __init__(self, text, lex, lang, zitate=False):
        self.raw = text
        self.text = mask(text, zitate)
        self.lex = lex
        self.lang = lang
        self.langs = ["de", "en"] if lang == "beide" else [lang]
        self.hits = []
        self.sents = sentences(self.text)

    def add(self, fid, start, end, note=None):
        f = self.lex["_by_id"][fid]
        snippet = self.raw[start:end].replace("\n", " ")
        if len(snippet) > 110:
            snippet = snippet[:107] + "..."
        self.hits.append({"nr": f["nr"], "id": fid, "name": f["name"], "zeile": line_of(self.raw, start),
                          "start": start, "ende": end, "text": snippet, "hinweis": note})

    def run(self):
        for f in self.lex["formen"]:
            for lang in self.langs:
                src = self.raw if f["id"] == "artefakte" else self.text
                for rx in f["_re_" + lang]:
                    for m in rx.finditer(src):
                        if m.end() > m.start():
                            self.add(f["id"], m.start(), m.end())
        for name in dir(self):
            if name.startswith("rule_"):
                getattr(self, name)()
        return self.dedupe()

    def dedupe(self):
        self.hits.sort(key=lambda h: (h["nr"], h["start"], -(h["ende"] - h["start"])))
        out = []
        for h in self.hits:
            if out and out[-1]["id"] == h["id"] and h["start"] < out[-1]["ende"]:
                continue
            out.append(h)
        out.sort(key=lambda h: (h["nr"], h["start"]))
        return out

    def prose(self):
        return [s for s in self.sents if s[3] == "prosa"]

    def runs(self, pred, minimum):
        """Folgen benachbarter Prosa-Sätze, für die pred gilt."""
        out, cur = [], []
        prev_end = None
        for s in self.prose():
            gap = self.text[prev_end:s[0]] if prev_end is not None else ""
            if pred(s) and (not cur or "\n\n" not in gap):
                cur.append(s)
            else:
                if len(cur) >= minimum:
                    out.append(cur)
                cur = [s] if pred(s) else []
            prev_end = s[1]
        if len(cur) >= minimum:
            out.append(cur)
        return out

    # ------------------------------------------------------------ Satzbau

    def rule_trikolon(self):
        exceptions = set(w.lower() for w in self.lex.get("trikolon_ausnahmen", []))
        item = r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß-]*(?: [\wÄÖÜäöüß-]+){0,2}?"
        rx = re.compile(r"(?<![\w-])(%s), (%s),? (?:und|oder|sowie|and|or) (%s)(?![\w-])" % (item, item, item))
        for s in self.prose():
            for m in rx.finditer(s[2]):
                parts = [m.group(i) for i in (1, 2, 3)]
                start = m.start()
                if " " not in parts[1] and " " not in parts[2] and " " in parts[0]:
                    start = m.start(1) + parts[0].rindex(" ") + 1
                    parts[0] = parts[0].rsplit(" ", 1)[1]
                if any(re.search(r"\d", p) for p in parts):
                    continue
                if sum(1 for p in parts if p.lower() in exceptions) >= 2:
                    continue
                if re.match(r"\s*,\s*\S", s[2][m.end():]) or re.search(r",\s*$", s[2][:start]):
                    continue
                if not self.same_shape(parts):
                    continue
                self.add("trikolon", s[0] + start, s[0] + m.end())

    def same_shape(self, parts):
        if any(p.lower() in PARTIKELN for p in parts):
            return False
        if self.lang == "en":
            return all(len(p.split()) <= 2 for p in parts)
        last_caps = [p.split()[-1][:1].isupper() for p in parts]
        if all(last_caps):
            return True
        return all(" " not in p for p in parts) and not any(last_caps)

    def rule_gedankenstrich(self):
        for rx in (EM_DASH, SPACED_DASH):
            for m in rx.finditer(self.text):
                a = max(0, m.start() - 25)
                b = min(len(self.text), m.end() + 25)
                self.add("gedankenstrich", a, b)

    def rule_doppelpunkt(self):
        cands = []
        for s in self.prose():
            m = re.match(r"^((?:\S+\s+){0,4}\S+?):\s+(.+)$", s[2])
            if not m or re.search(r"\d:\d", s[2][:m.end(1) + 2]):
                continue
            if len(words(m.group(2))) >= 6:
                cands.append(s)
        if len(cands) >= 2:
            for s in cands:
                self.add("doppelpunkt-enthuellung", s[0], s[1])

    def rule_hypophora(self):
        ps = self.prose()
        for i, s in enumerate(ps[:-1]):
            nxt = ps[i + 1]
            if not s[2].endswith("?") or nxt[2].endswith("?"):
                continue
            if "\n\n" in self.text[s[1]:nxt[0]]:
                continue
            if len(words(s[2])) <= 8:
                self.add("hypophora", s[0], nxt[1])

    def rule_stakkato(self):
        for run in self.runs(lambda s: 0 < len(words(s[2])) <= 5 and not s[2].endswith("?"), 3):
            self.add("stakkato", run[0][0], run[-1][1], "%d kurze Sätze in Folge" % len(run))

    def rule_anapher(self):
        def opener(s):
            w = [x.lower() for x in words(s[2])[:2]]
            return " ".join(w) if len(w) == 2 else None
        ps = self.prose()
        i = 0
        while i < len(ps):
            o = opener(ps[i])
            j = i
            while o and j + 1 < len(ps) and opener(ps[j + 1]) == o:
                j += 1
            if o and j - i + 1 >= 3:
                self.add("anapher", ps[i][0], ps[j][1], "%d Sätze beginnen mit „%s“" % (j - i + 1, o))
            i = j + 1

    def rule_negations_countdown(self):
        def neg(s):
            w = words(s[2])
            return bool(w) and w[0].lower() in NEGATION_START and len(w) <= 10
        for run in self.runs(neg, 2):
            self.add("negations-countdown", run[0][0], run[-1][1])

    def _terms_in(self, sentence, terms):
        low = " %s " % " ".join(words(sentence.lower()))
        return sum(low.count(" %s " % t.lower()) for t in terms)

    def rule_absicherungs_stapel(self):
        terms = []
        for lang in self.langs:
            terms += self.lex["absicherung"].get(lang, [])
        for s in self.prose():
            if self._terms_in(s[2], terms) >= 3:
                self.add("absicherungs-stapel", s[0], s[1])

    def rule_klammer_nuance(self):
        terms = []
        for lang in self.langs:
            terms += self.lex["klammer_qualifier"].get(lang, [])
        for m in PAREN.finditer(self.text):
            if self._terms_in(m.group(1), terms):
                self.add("klammer-nuance", m.start(), m.end())

    def rule_nominalstil(self):
        if "de" not in self.langs:
            return
        for s in self.prose():
            n = len(NOMINAL.findall(s[2]))
            w = len(words(s[2]))
            if n >= 4 and n / float(max(w, 1)) >= 0.2:
                self.add("nominalstil", s[0], s[1], "%d Substantive auf -ung/-heit/-keit/-ion" % n)

    def rule_gleichtakt(self):
        lens = [len(words(s[2])) for s in self.prose() if len(words(s[2])) >= 3]
        if len(lens) >= 8:
            mean = statistics.mean(lens)
            cv = statistics.pstdev(lens) / mean if mean else 1
            if cv < 0.3:
                self.add("gleichtakt", 0, min(len(self.raw), 60),
                         "Satzlängen fast gleich: Mittel %.1f Wörter, Streuung %.0f %%" % (mean, cv * 100))
        paras = [len(words(c)) for _, _, c, k in blocks(self.text) if k == "prosa" and len(words(c)) >= 15]
        if len(paras) >= 4:
            mean = statistics.mean(paras)
            cv = statistics.pstdev(paras) / mean if mean else 1
            if cv < 0.15:
                self.add("gleichtakt", 0, min(len(self.raw), 60),
                         "Absätze fast gleich lang: Mittel %.0f Wörter, Streuung %.0f %%" % (mean, cv * 100))

    # ------------------------------------------------------------ Rahmung

    def rule_analogie_parade(self):
        brands = self.lex.get("marken", [])
        for s in self.prose():
            found = set(b for b in brands if re.search(r"\b%s\b" % re.escape(b), s[2]))
            if len(found) >= 3:
                self.add("analogie-parade", s[0], s[1], ", ".join(sorted(found)))

    # ------------------------------------------------------------ Struktur

    def rule_konnektoren_sucht(self):
        conns = []
        for lang in self.langs:
            conns += self.lex["konnektoren"].get(lang, [])
        rx = re.compile(r"^(?:%s)\b[ ,]" % "|".join(re.escape(c) for c in sorted(conns, key=len, reverse=True)))
        cands = [s for s in self.prose() if rx.match(s[2])]
        if len(cands) >= 2:
            for s in cands:
                self.add("konnektoren-sucht", s[0], s[0] + min(len(s[2]), 60))

    def rule_listen_reflex(self):
        lines = self.text.split("\n")
        pos, run = 0, []
        offsets = []
        for line in lines:
            offsets.append(pos)
            pos += len(line) + 1
        i = 0
        while i < len(lines):
            if LIST_ITEM.match(lines[i]):
                indent = len(lines[i]) - len(lines[i].lstrip())
                j = i
                count = 0
                while j < len(lines) and (LIST_ITEM.match(lines[j]) or (lines[j].startswith(" " * (indent + 2)) and lines[j].strip())):
                    if LIST_ITEM.match(lines[j]) and len(lines[j]) - len(lines[j].lstrip()) == indent:
                        count += 1
                    j += 1
                sizes = [len(words(l)) for l in lines[i:j] if LIST_ITEM.match(l)]
                even = sizes and min(sizes) > 0 and max(sizes) <= 1.5 * min(sizes)
                if count in (3, 5, 7, 10) and even:
                    self.add("listen-reflex", offsets[i], offsets[j - 1] + len(lines[j - 1]),
                             "Liste mit genau %d Punkten" % count)
                i = j
            else:
                i += 1
        for a, b in ((r"\bErstens\b", r"\bZweitens\b"), (r"\bFirst(?:ly)?,", r"\bSecond(?:ly)?,"),
                     (r"\b(?:Der|Die|Das) erste\b", r"\b(?:Der|Die|Das) zweite\b"),
                     (r"\bThe first\b", r"\bThe second\b")):
            ma = re.search(a, self.text)
            mb = re.search(b, self.text)
            if ma and mb and ma.start() < mb.start():
                self.add("listen-reflex", ma.start(), mb.end() if mb.end() - ma.start() < 200 else ma.end(),
                         "Liste in Prosa verkleidet")

    def rule_markdown_deko(self):
        pos, run = 0, []
        for line in self.raw.split("\n") + [""]:
            if BOLD_BULLET.match(line):
                run.append((pos, pos + len(line)))
            else:
                if len(run) >= 2:
                    self.add("markdown-deko", run[0][0], run[-1][1], "%d fette Listenköpfe" % len(run))
                run = []
            if EMOJI.search(line[:4]) or (HEADING.match(line) and EMOJI.search(line)):
                self.add("markdown-deko", pos, pos + len(line), "Emoji als Gliederung")
            pos += len(line) + 1
        for m in ARROWS.finditer(self.text):
            self.add("markdown-deko", max(0, m.start() - 20), min(len(self.text), m.end() + 20), "Pfeil im Text")
        for start, end, chunk, kind in blocks(self.raw):
            if kind == "prosa" and len(BOLD.findall(chunk)) >= 3:
                self.add("markdown-deko", start, end, "%d Fettungen in einem Absatz" % len(BOLD.findall(chunk)))

    def rule_dramatisches_fragment(self):
        bl = blocks(self.text)
        for idx, (start, end, chunk, kind) in enumerate(bl):
            if kind != "prosa" or "\n" in chunk.strip():
                continue
            w = words(chunk)
            if 0 < len(w) <= 4 and re.search(r"[.!?…]\s*$", chunk.strip()) and idx not in (0,):
                self.add("dramatisches-fragment", start, end)

    def rule_artefakte(self):
        for m in INVISIBLE.finditer(self.raw):
            self.add("artefakte", m.start(), m.end(), "unsichtbares Zeichen U+%04X" % ord(m.group(0)))
        for m in CITATION.finditer(self.raw):
            self.add("artefakte", m.start(), m.end(), "Zitier- oder Tracking-Artefakt")


def analyse(text, lex=None, sprache="auto", zitate=False):
    lex = lex or load_lexikon()
    lang = detect_language(text) if sprache == "auto" else sprache
    hits = Finder(text, lex, lang, zitate).run()
    n_words = len(words(mask(text, True)))
    counts = {}
    for h in hits:
        counts[h["id"]] = counts.get(h["id"], 0) + 1
    return {
        "sprache": lang,
        "woerter": n_words,
        "fundstellen": hits,
        "formen": counts,
        "anzahl": len(hits),
        "dichte": round(len(hits) * 100.0 / n_words, 1) if n_words else 0.0,
        "urteil_formen": [{"nr": f["nr"], "id": f["id"], "name": f["name"]} for f in lex["formen"] if f.get("urteil")],
    }


def bereinigen(text):
    """Nur das mechanisch Sichere: unsichtbare Zeichen und Zitier-/Tracking-Artefakte entfernen."""
    out = INVISIBLE.sub("", text)
    out = re.sub(r"[ \t]?(?:%s)" % CITATION.pattern, "", out)
    out = re.sub(r"[ \t]+\n", "\n", out)
    return out


def num(x):
    return ("%.1f" % x).replace(".", ",")


def report(res, name, lex):
    by_id = lex["_by_id"]
    lines = ["remove-slop-skill: %s, %d Wörter, Sprache %s" % (name, res["woerter"], res["sprache"])]
    lines.append("%d Fundstellen in %d von 48 Formen (%s je 100 Wörter)"
                 % (res["anzahl"], len(res["formen"]), num(res["dichte"])))
    current = None
    for h in res["fundstellen"]:
        if h["id"] != current:
            current = h["id"]
            f = by_id[current]
            lines.append("")
            lines.append("#%d %s (%d): %s" % (f["nr"], f["name"], res["formen"][current], f["kurz"]))
        extra = " [%s]" % h["hinweis"] if h["hinweis"] else ""
        lines.append("  Z. %d: „%s“%s" % (h["zeile"], h["text"].strip(), extra))
    lines.append("")
    lines.append("Ohne Muster, beim Lesen prüfen: " + ", ".join("#%d %s" % (f["nr"], f["name"]) for f in res["urteil_formen"]))
    lines.append("Ein Befund ist ein Hinweis, kein Beweis für KI. Prüfe jede Stelle im Zusammenhang.")
    return "\n".join(lines)


def compare(a, b, lex):
    lines = ["%-34s %7s %7s" % ("Form", "vorher", "nachher")]
    for f in lex["formen"]:
        x, y = a["formen"].get(f["id"], 0), b["formen"].get(f["id"], 0)
        if x or y:
            lines.append("%-34s %7d %7d" % ("#%d %s" % (f["nr"], f["name"]), x, y))
    lines.append("%-34s %7d %7d" % ("Summe", a["anzahl"], b["anzahl"]))
    lines.append("%-34s %7s %7s" % ("je 100 Wörter", num(a["dichte"]), num(b["dichte"])))
    lines.append("%-34s %7d %7d" % ("Wörter", a["woerter"], b["woerter"]))
    return "\n".join(lines)


def read(path):
    if path == "-":
        return sys.stdin.read()
    if not os.path.isfile(path):
        raise SlopError("Datei nicht gefunden: %s" % path)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv=None):
    p = argparse.ArgumentParser(description="Findet die 48 Formen von KI-Slop in einem Text.")
    p.add_argument("datei", nargs="?", help="Textdatei (oder - für stdin)")
    p.add_argument("--vergleich", nargs=2, metavar=("ALT", "NEU"), help="zwei Fassungen vergleichen")
    p.add_argument("--sprache", choices=["auto", "de", "en", "beide"], default="auto")
    p.add_argument("--formen", help="nur diese Formen, z. B. 16,18,19 oder correctio,trikolon")
    p.add_argument("--json", action="store_true", help="JSON statt Bericht")
    p.add_argument("--bereinigen", action="store_true", help="unsichtbare Zeichen und Zitier-Artefakte entfernen")
    p.add_argument("-o", "--out", help="Zieldatei für --bereinigen (sonst stdout)")
    p.add_argument("--strikt", action="store_true", help="Exit-Code 1, wenn etwas gefunden wurde")
    p.add_argument("--liste", action="store_true", help="die 48 Formen auflisten")
    p.add_argument("--mit-zitaten", action="store_true", help="auch Text in „…“ und »…« prüfen")
    a = p.parse_args(argv)
    try:
        lex = load_lexikon()
        if a.liste:
            group = None
            for f in lex["formen"]:
                if f["gruppe"] != group:
                    group = f["gruppe"]
                    print("\n" + group)
                tag = " (Urteil)" if f.get("urteil") else ""
                print("  #%-2d %-34s %s%s" % (f["nr"], f["name"], f["kurz"], tag))
            return 0
        if a.vergleich:
            ra = analyse(read(a.vergleich[0]), lex, a.sprache, a.mit_zitaten)
            rb = analyse(read(a.vergleich[1]), lex, a.sprache, a.mit_zitaten)
            if a.json:
                print(json.dumps({"vorher": ra, "nachher": rb}, ensure_ascii=False, indent=2))
            else:
                print(compare(ra, rb, lex))
            return 1 if a.strikt and rb["anzahl"] else 0
        if not a.datei:
            raise SlopError("gib eine Datei an, - für stdin, oder --vergleich ALT NEU")
        text = read(a.datei)
        if a.bereinigen:
            clean = bereinigen(text)
            if a.out:
                with open(a.out, "w", encoding="utf-8") as fh:
                    fh.write(clean)
                print("%s geschrieben (%d Zeichen entfernt)." % (a.out, len(text) - len(clean)))
            else:
                sys.stdout.write(clean)
            return 0
        res = analyse(text, lex, a.sprache, a.mit_zitaten)
        if a.formen:
            want = set(x.strip() for x in a.formen.split(","))
            keep = set(f["id"] for f in lex["formen"] if f["id"] in want or str(f["nr"]) in want)
            if not keep:
                raise SlopError("keine bekannte Form in --formen: %s" % a.formen)
            res["fundstellen"] = [h for h in res["fundstellen"] if h["id"] in keep]
            res["formen"] = dict((k, v) for k, v in res["formen"].items() if k in keep)
            res["anzahl"] = len(res["fundstellen"])
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(report(res, a.datei, lex))
        return 1 if a.strikt and res["anzahl"] else 0
    except SlopError as e:
        print("slop.py: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
