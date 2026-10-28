import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "remove-slop-skill")
sys.path.insert(0, SKILL)

import slop  # noqa: E402
