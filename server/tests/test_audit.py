"""The audit action enum is closed and documented: this test makes it
load-bearing by parsing docs/impl/audit-actions.md and asserting the two
lists cannot drift (enum doc: "every value here exists in code and every
code value is documented here")."""

import re
from pathlib import Path

from app.audit import Action

ENUM_DOC = Path(__file__).resolve().parents[2] / "docs" / "impl" / "audit-actions.md"


def _documented_actions() -> set[str]:
    """Extract action names from the enum tables' first column only.

    Matching all backticked `x.y` strings would also catch the
    "deliberately not an action" list (submission.claimed, …) and the
    `audit_event.action` schema reference — the tables' first column is
    the authoritative list."""
    text = ENUM_DOC.read_text(encoding="utf-8")
    return set(re.findall(r"^\| `([a-z_]+\.[a-z_]+)`", text, re.MULTILINE))


def test_enum_matches_documentation():
    documented = _documented_actions()
    coded = {str(a) for a in Action}
    missing_in_code = documented - coded
    missing_in_docs = coded - documented
    assert not missing_in_code, f"documented but not in Action: {missing_in_code}"
    assert not missing_in_docs, f"in Action but undocumented: {missing_in_docs}"
