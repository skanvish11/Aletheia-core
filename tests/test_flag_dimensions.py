import re
from pathlib import Path
from typing import get_args

from aletheia.research_contracts import Dimension

README = Path(__file__).resolve().parents[1] / "README.md"


def test_dimensions_match_readme():
    # Flags with an unlisted dimension are dropped, so the code must accept every documented one.
    line = next(
        line
        for line in README.read_text(encoding="utf-8").splitlines()
        if line.startswith("- `dimension` names what differs:")
    )
    documented = re.findall(r"`([a-z_]+)`", line.split(":", 1)[1])
    assert list(get_args(Dimension)) == documented
