import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

from _load import SKILL, slop

LEX = slop.load_lexikon()

BEISPIELE = {
    "modewoerter": "Wir bieten eine nahtlose Lösung für Ihr Team an.",
    "gespreizt": "Wir werden die neue Software im Mai implementieren.",
    "purple-prose": "Im Herzen der Altstadt entfaltet sich eine atemberaubende Kulisse.",
    "leere-adverbien": "Letztendlich hat der Kunde entschieden, das Angebot abzulehnen.",
    "fast-absicherung": "Die App läuft nahezu immer ohne Absturz.",
    "kopula-ausweichen": "Das alte Rathaus fungiert heute als Museum der Stadt.",
    "nominalstil": "Die Durchführung der Optimierung der Prozessgestaltung erfolgt unter Berücksichtigung der Anforderungen der Abteilung.",
    "anglizismen": "Das macht Sinn, wenn man den Preis vergleicht.",
    "epochen-eroeffnung": "In der heutigen schnelllebigen Welt zählt jede Minute.",
    "metaphern-kruecke": "Dieses Gesetz ist ein zweischneidiges Schwert für kleine Betriebe.",
    "bedeutungs-aufblaehung": "Die Eröffnung markiert einen Wendepunkt für den Stadtteil.",
    "konzept-label": "Viele Gründer unterschätzen das Vertrauensparadox im ersten Jahr.",
    "analogie-parade": "Er nannte Netflix, Spotify und Airbnb als Vorbilder für den Laden.",
    "correctio": "Es geht nicht um Geld, es geht um Respekt.",
    "negations-countdown": "Kein Abo. Keine Gebühren. Einfach fair.",
    "trikolon": "Unser Service ist schnell, einfach und sicher.",
    "gedankenstrich": "Der Preis — das wussten alle — war zu hoch.",
    "doppelpunkt-enthuellung": "Der Grund: Die meisten Teams messen ganz einfach das Falsche.\n\nDas Ergebnis: Niemand weiß am Ende noch, was eigentlich funktioniert.",
    "hypophora": "Was bedeutet das für dich? Du kannst ab Montag früher Feierabend machen.",
    "stakkato": "Wir hörten zu. Wir lernten. Wir wuchsen.",
    "anapher": "Wir glauben an Qualität im Detail. Wir glauben an ehrliche Preise. Wir glauben an gute Beratung.",
    "partizip-anhaengsel": "Der Umsatz stieg um acht Prozent, was die Stärke der Marke unterstreicht.",
    "absicherungs-stapel": "Das könnte möglicherweise unter Umständen etwas teurer werden.",
    "klammer-nuance": "Das klappt (zumindest in den meisten Fällen) ohne Probleme.",
    "kontrast-ueberfluss": "Im Gegensatz zu herkömmlichen Lösungen ist unsere Software einfach.",
    "scheinspanne": "Von kleinen Start-ups bis hin zu globalen Konzernen profitieren alle.",
    "gleichtakt": " ".join(["Der Bericht beschreibt heute die Lage der Firma im Jahr genau."] * 9),
    "meta-hinweis": "Es ist wichtig zu beachten, dass die Frist am Freitag endet.",
    "lehrer-modus": "Schauen wir uns das genauer an, bevor wir entscheiden.",
    "falsche-spannung": "Und jetzt kommt's: Die Software ist kostenlos.",
    "stell-dir-vor": "Stell dir vor, du könntest jeden Tag eine Stunde länger schlafen.",
    "vage-autoritaet": "Studien zeigen, dass Pausen die Arbeit verbessern.",
    "trotz-herausforderungen": "Trotz einiger Herausforderungen wurde das Projekt abgeschlossen.",
    "ausgewogenheits-reflex": "Homeoffice spart Zeit. Auf der anderen Seite fehlt der Austausch im Büro.",
    "gespielte-offenheit": "Ehrlich gesagt war ich am Anfang skeptisch.",
    "anbiederung": "Gute Frage! Die Antwort steht im Handbuch auf Seite vier.",
    "konnektoren-sucht": "Wir haben das Lager umgebaut.\n\nDarüber hinaus haben wir neue Regale gekauft.\n\nZudem gibt es jetzt eine Rampe.",
    "aufsatz-schluss": "Zusammenfassend lässt sich sagen, dass der Umzug gut lief.",
    "listen-reflex": "Das hilft:\n\n- früh anfangen\n- Pausen machen\n- Wasser trinken",
    "markdown-deko": "- **Tempo:** Alles geht schneller.\n- **Kosten:** Alles wird billiger.",
    "dramatisches-fragment": "Dann klingelte das Telefon, und der Auftrag war weg.\n\nEinfach so.\n\nWir haben am nächsten Tag neu angefangen.",
    "chatbot-floskeln": "Hier ist der Text für deine Webseite. Ich hoffe, das hilft!",
    "artefakte": "Mehr dazu auf https://example.com/seite?utm_source=chatgpt.com im Netz.",
}

SAUBER = (
    "Am Dienstag habe ich die Heizung im Keller selbst entlüftet. Der Installateur hätte frühestens in drei "
    "Wochen Zeit gehabt, und im Wohnzimmer waren es morgens nur noch 16 Grad.\n\n"
    "Das Ventil sitzt oben am Heizkörper, ein kleiner Vierkant. Ich hatte keinen passenden Schlüssel, also bin "
    "ich zum Baumarkt gefahren und habe für 2,49 Euro einen gekauft. Unter das Ventil kommt ein Lappen, sonst "
    "tropft es auf den Boden.\n\n"
    "Beim ersten Heizkörper kam erst Luft, dann ein dünner Strahl Wasser. Beim zweiten passierte gar nichts. "
    "Meine Nachbarin meinte, der Druck in der Anlage sei vermutlich zu niedrig, und sie hatte recht: Das "
    "Manometer stand bei 0,8 bar statt bei 1,5.\n\n"
    "Wasser nachfüllen war der unangenehme Teil. Der Schlauch muss vorher mit Wasser gefüllt sein, damit keine "
    "neue Luft ins System kommt, und das habe ich beim ersten Versuch natürlich vergessen. Danach lief es."
)

CLEAN_EN = (
    "We moved the office to the second floor in March. The old room had one window and the radiator clanked "
    "every morning at seven, so nobody was sad to leave.\n\n"
    "The move took two days instead of one because the freight elevator broke on the first afternoon. Sam "
    "carried the printer down the stairs, which he still brings up at lunch."
)


def ids(text, sprache="de"):
    return set(h["id"] for h in slop.analyse(text, LEX, sprache)["fundstellen"])


class Lexikon(unittest.TestCase):
    def test_achtundvierzig_formen(self):
        formen = LEX["formen"]
        self.assertEqual(len(formen), 48)
        self.assertEqual([f["nr"] for f in formen], list(range(1, 49)))
        self.assertEqual(len(set(f["id"] for f in formen)), 48)

    def test_jede_form_vollstaendig(self):
        for f in LEX["formen"]:
            for key in ("id", "name", "gruppe", "kurz"):
                self.assertTrue(f.get(key), "%s fehlt bei #%d" % (key, f["nr"]))

    def test_alle_muster_kompilieren(self):
        for f in LEX["formen"]:
            for lang in ("de", "en"):
                for p in f.get(lang, []):
                    re.compile(p, re.I)

    def test_erkennbar_oder_urteil(self):
        for f in LEX["formen"]:
            has = f.get("de") or f.get("en") or f.get("code")
            self.assertTrue(has or f.get("urteil"), "#%d hat weder Muster noch Urteil" % f["nr"])
            self.assertFalse(has and f.get("urteil"), "#%d ist beides" % f["nr"])

    def test_fuenf_urteilsformen(self):
        urteil = [f["nr"] for f in LEX["formen"] if f.get("urteil")]
        self.assertEqual(urteil, [9, 12, 28, 31, 46])


class Erkennen(unittest.TestCase):
    def test_beispiel_fuer_jede_erkennbare_form(self):
        erkennbar = set(f["id"] for f in LEX["formen"] if not f.get("urteil"))
        self.assertEqual(set(BEISPIELE), erkennbar)

    def test_beispiele_werden_gefunden(self):
        missed = [fid for fid, text in sorted(BEISPIELE.items()) if fid not in ids(text)]
        self.assertEqual(missed, [])

    def test_sauberer_text(self):
        self.assertLessEqual(len(slop.analyse(SAUBER, LEX, "de")["fundstellen"]), 1)

    def test_sauberer_englischer_text(self):
        res = slop.analyse(CLEAN_EN, LEX)
        self.assertEqual(res["sprache"], "en")
        self.assertEqual(res["fundstellen"], [])

    def test_englische_muster(self):
        text = ("It's not about the money, it's about trust. In today's fast-paced world, we delve into "
                "a seamless tapestry of ideas. I hope this helps!")
        found = ids(text, "en")
        for fid in ("correctio", "epochen-eroeffnung", "modewoerter", "chatbot-floskeln"):
            self.assertIn(fid, found)

    def test_sprache_erkennen(self):
        self.assertEqual(slop.detect_language(SAUBER), "de")
        self.assertEqual(slop.detect_language(CLEAN_EN), "en")

    def test_echte_dreiergruppe_bleibt(self):
        self.assertNotIn("trikolon", ids("Die Ampel zeigt Rot, Gelb und Grün."))

    def test_dreiergruppe_in_laengerer_liste(self):
        self.assertNotIn("trikolon", ids("Wir haben Äpfel, Birnen, Kirschen und Pflaumen gekauft."))

    def test_satzglieder_sind_kein_trikolon(self):
        self.assertNotIn("trikolon", ids("Was im Text fehlt, wird gestrichen oder nachgefragt."))

    def test_zeitspanne_ist_kein_gedankenstrich(self):
        self.assertNotIn("gedankenstrich", ids("Wir haben von 10–12 Uhr geöffnet."))

    def test_code_und_urls_ignoriert(self):
        text = "Der Befehl lautet `nicht nur X, sondern Y` und steht auf https://example.com/nahtlos-robust."
        self.assertEqual(ids(text), set())

    def test_zitate_ignoriert(self):
        text = "Er schrieb „Es ist wichtig zu beachten, dass alles nahtlos läuft“ in die Mail."
        self.assertEqual(ids(text), set())
        res = slop.analyse(text, LEX, "de", zitate=True)
        self.assertIn("meta-hinweis", set(h["id"] for h in res["fundstellen"]))

    def test_zeile_und_offsets(self):
        text = "Erste Zeile ohne Befund.\n\nIch hoffe, das hilft!"
        hit = [h for h in slop.analyse(text, LEX, "de")["fundstellen"] if h["id"] == "chatbot-floskeln"][0]
        self.assertEqual(hit["zeile"], 3)
        self.assertEqual(text[hit["start"]:hit["ende"]], hit["text"])

    def test_dichte(self):
        res = slop.analyse(BEISPIELE["correctio"], LEX, "de")
        self.assertGreater(res["dichte"], 0)
        self.assertEqual([f["nr"] for f in res["urteil_formen"]], [9, 12, 28, 31, 46])


class Bereinigen(unittest.TestCase):
    def test_unsichtbare_zeichen(self):
        self.assertEqual(slop.bereinigen("Hal\u200blo\u00ad Welt\ufeff"), "Hallo Welt")

    def test_zitier_artefakte(self):
        text = "Das stimmt.【4:0†source】 Siehe https://example.com/a?utm_source=chatgpt.com hier."
        out = slop.bereinigen(text)
        self.assertNotIn("source", out)
        self.assertIn("https://example.com/a", out)
        self.assertIn("Das stimmt.", out)

    def test_text_sonst_unveraendert(self):
        self.assertEqual(slop.bereinigen(SAUBER), SAUBER)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = slop.main(list(args))
        return code, buf.getvalue()

    def tmp(self, text):
        fd, path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_liste(self):
        code, out = self.run_cli("--liste")
        self.assertEqual(code, 0)
        self.assertIn("#48", out)
        self.assertIn("(Urteil)", out)

    def test_bericht(self):
        code, out = self.run_cli(self.tmp(BEISPIELE["correctio"]))
        self.assertEqual(code, 0)
        self.assertIn("Correctio", out)
        self.assertIn("kein Beweis", out)

    def test_json_und_formen(self):
        path = self.tmp(BEISPIELE["correctio"] + " " + BEISPIELE["meta-hinweis"])
        code, out = self.run_cli(path, "--json", "--formen", "16")
        data = json.loads(out)
        self.assertEqual(set(h["id"] for h in data["fundstellen"]), {"correctio"})

    def test_strikt(self):
        self.assertEqual(self.run_cli(self.tmp(BEISPIELE["correctio"]), "--strikt")[0], 1)
        self.assertEqual(self.run_cli(self.tmp(SAUBER[:200]), "--strikt", "--formen", "16")[0], 0)

    def test_vergleich(self):
        code, out = self.run_cli("--vergleich", self.tmp(BEISPIELE["correctio"]), self.tmp(SAUBER))
        self.assertEqual(code, 0)
        self.assertIn("Correctio", out)

    def test_bereinigen_datei(self):
        src = self.tmp("Hal\u200blo")
        dst = src + ".neu"
        self.addCleanup(lambda: os.path.exists(dst) and os.remove(dst))
        self.run_cli(src, "--bereinigen", "-o", dst)
        with open(dst, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "Hallo")

    def test_unbekannte_form(self):
        with redirect_stdout(io.StringIO()):
            err = io.StringIO()
            old, sys.stderr = sys.stderr, err
            try:
                code = slop.main([self.tmp("Text."), "--formen", "gibtsnicht"])
            finally:
                sys.stderr = old
        self.assertEqual(code, 2)

    def test_stdin(self):
        p = subprocess.run([sys.executable, os.path.join(SKILL, "slop.py"), "-"],
                           input="Ich hoffe, das hilft!".encode("utf-8"), stdout=subprocess.PIPE)
        self.assertEqual(p.returncode, 0)
        self.assertIn("Chatbot-Floskeln", p.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
