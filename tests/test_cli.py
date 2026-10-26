from __future__ import annotations

import json

from symptompilot.cli import main


def test_topics_command(tmp_path, knowledge_dir, capsys) -> None:
    code = main(["topics", "--kb", str(knowledge_dir), "--db", str(tmp_path / "cli.db")])
    assert code == 0
    assert "chest-pain" in capsys.readouterr().out


def test_ask_command_json(tmp_path, knowledge_dir, capsys) -> None:
    code = main(
        [
            "ask",
            "I have a mild headache",
            "--kb",
            str(knowledge_dir),
            "--db",
            str(tmp_path / "cli.db"),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["urgency"]["level"] == "routine"
    assert payload["citations"]


def test_ingest_command_json(tmp_path, knowledge_dir, capsys) -> None:
    code = main(["ingest", "--kb", str(knowledge_dir), "--db", str(tmp_path / "cli.db"), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["documents"] >= 14
    assert payload["chunks"] > 0


def test_eval_command_exit_code(tmp_path, knowledge_dir, capsys) -> None:
    code = main(["eval", "--kb", str(knowledge_dir), "--db", str(tmp_path / "cli.db")])
    assert code == 0
    assert "PASSED" in capsys.readouterr().out
