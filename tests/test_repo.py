import ast
import json
import os
import re
import unittest

from _load import ROOT, SKILL, slop

LEX = slop.load_lexikon()


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


class Repo(unittest.TestCase):
    def test_layout(self):
        for rel in ("README.md", "LICENSE", ".gitignore", ".claude-plugin/plugin.json",
                    ".claude-plugin/marketplace.json", "skills/remove-slop-skill/SKILL.md",
                    "skills/remove-slop-skill/slop.py", "skills/remove-slop-skill/lexikon.json",
                    "skills/remove-slop-skill/formen.md"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)), rel)
        self.assertEqual(os.listdir(os.path.join(ROOT, "skills")), ["remove-slop-skill"])

    def test_frontmatter(self):
        text = read(SKILL, "SKILL.md")
        m = re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", text)
        self.assertTrue(m)
        self.assertEqual(m.group(1), "remove-slop-skill")
        self.assertLess(len(m.group(2)), 1024)
        for phrase in ("KI-Slop", "remove AI slop", "Correctio", "Trikolon", "Purple Prose"):
            self.assertIn(phrase, m.group(2))

    def test_formen_md_passt_zum_lexikon(self):
        heads = re.findall(r"^### (\d+)\. (.+?) \(`([a-z-]+)`\)", read(SKILL, "formen.md"), re.M)
        self.assertEqual([(int(n), i) for n, _, i in heads], [(f["nr"], f["id"]) for f in LEX["formen"]])
        groups = re.findall(r"^## (.+)$", read(SKILL, "formen.md"), re.M)
        order = []
        for f in LEX["formen"]:
            if f["gruppe"] not in order:
                order.append(f["gruppe"])
        self.assertEqual(groups, order)

    def test_jede_form_hat_beispiel(self):
        sections = re.split(r"^### ", read(SKILL, "formen.md"), flags=re.M)[1:]
        self.assertEqual(len(sections), 48)
        for sec in sections:
            self.assertIn("Vorher:", sec, sec[:40])
            self.assertIn("Nachher:", sec, sec[:40])

    def test_readme_nennt_alle_formen(self):
        readme = read(ROOT, "README.md")
        for f in LEX["formen"]:
            self.assertIn("%d %s" % (f["nr"], f["name"].split(" (")[0]), readme)
        self.assertIn("github.com/Ultra-Smashed/remove-slop-skill", readme)
        self.assertIn("thanisch.co", readme)

    def test_kein_gedankenstrich_in_doku(self):
        for rel in ("README.md", "skills/remove-slop-skill/SKILL.md"):
            self.assertNotIn("\u2014", read(ROOT, rel), rel)

    def test_plugin_json(self):
        plugin = json.loads(read(ROOT, ".claude-plugin", "plugin.json"))
        market = json.loads(read(ROOT, ".claude-plugin", "marketplace.json"))
        self.assertEqual(plugin["name"], "remove-slop-skill")
        self.assertEqual(market["plugins"][0]["name"], "remove-slop-skill")
        self.assertEqual(plugin["author"]["url"], "https://thanisch.co")

    def test_python38_syntax(self):
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(base, f)
                src = read(path)
                ast.parse(src, path, feature_version=(3, 8))
                if f == "test_repo.py":
                    continue
                for bad in ("removeprefix", "removesuffix", "zoneinfo", "match ", "list[", "dict["):
                    if bad == "match ":
                        self.assertIsNone(re.search(r"^\s*match \w+:", src, re.M), path)
                    else:
                        self.assertNotIn(bad, src, "%s in %s" % (bad, path))


if __name__ == "__main__":
    unittest.main()
