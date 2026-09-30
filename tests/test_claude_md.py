import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "runs", ".superpowers"}
MAX_LINES = 50


def _visible(p: Path) -> bool:
    return not (set(p.relative_to(ROOT).parts) & SKIP)


def test_every_directory_with_python_has_claude_md():
    dirs = {p.parent for p in ROOT.rglob("*.py") if _visible(p)}
    missing = sorted(str(d.relative_to(ROOT)) for d in dirs if not (d / "CLAUDE.md").exists())
    assert missing == [], f"folders without CLAUDE.md: {missing}"


def test_claude_md_files_are_at_most_50_lines():
    too_long = {str(f.relative_to(ROOT)): len(f.read_text(encoding="utf-8").splitlines())
                for f in ROOT.rglob("CLAUDE.md") if _visible(f)}
    too_long = {k: v for k, v in too_long.items() if v > MAX_LINES}
    assert too_long == {}, f"CLAUDE.md over {MAX_LINES} lines: {too_long}"


def test_root_claude_md_states_the_update_rule():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "CLAUDE.md" in text and "50" in text and "uv run pytest" in text


def test_folder_map_lines_are_paths_only():
    """`- sub/ → sub/CLAUDE.md` lines carry no description: that lives in the sub folder's file."""
    described = [f"{f.relative_to(ROOT)}: {line}"
                 for f in ROOT.rglob("CLAUDE.md") if _visible(f)
                 for line in f.read_text(encoding="utf-8").splitlines()
                 if re.match(r"^- \S+/ → \S+CLAUDE\.md", line) and " — " in line]
    assert described == [], f"folder-map lines with a description: {described}"
