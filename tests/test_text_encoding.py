"""Guard against encoding damage in tracked text files.

Editing tools on Windows occasionally read UTF-8 as a legacy code page and write
it back doubled, turning one em dash into a three-character sequence of
punctuation. This test fails loudly if that happens again, instead of leaving
garbled text on the rendered README.
"""

from __future__ import annotations

from pathlib import Path

from symptompilot.config import PROJECT_ROOT

TEXT_SUFFIXES = {".md", ".toml", ".yaml", ".yml", ".py", ".js", ".css", ".html", ".example"}
EXTRA_NAMES = {".editorconfig", ".gitattributes"}
SKIP_DIRS = {".git", ".venv", "var", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}

# Fragments produced when UTF-8 bytes are decoded as windows-1252 and re-encoded.
MOJIBAKE_MARKERS = (
    "\u00e2\u20ac",  # em dash, curly quotes
    "\u00c3\u00a2",  # accented sequences
    "\u00e2\u201d",  # box drawing
    "\u00e2\u0153",  # check marks
    "\u00e2\u201a",  # arrows
)


def _text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in EXTRA_NAMES:
            files.append(path)
    return files


def test_text_files_are_utf8_without_mojibake() -> None:
    files = _text_files(PROJECT_ROOT)
    assert len(files) > 20, "expected to scan the whole repository"

    problems: list[str] = []
    for path in files:
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            problems.append(f"{path.relative_to(PROJECT_ROOT)}: not valid UTF-8 ({exc})")
            continue
        for marker in MOJIBAKE_MARKERS:
            if marker in text:
                problems.append(f"{path.relative_to(PROJECT_ROOT)}: mojibake {marker!r}")
                break

    assert not problems, "encoding problems found:\n" + "\n".join(problems)
