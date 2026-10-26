# Contributing to SymptomPilot

Thanks for taking the time to contribute. This project is an educational triage
aid, so changes are judged on safety first and features second.

Everyone interacting here is expected to follow our
[Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
python -m symptompilot eval
python -m symptompilot serve
```

The app needs no API keys. If you want to test the model path, install
[Ollama](https://ollama.com) and run `ollama pull llama3.2`, or set
`SYMPTOMPILOT_OPENAI_API_KEY` and `SYMPTOMPILOT_LLM_PROVIDER=openai`.

## Before you open a pull request

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -m symptompilot eval
```

All four must pass. CI runs the same commands on Python 3.10, 3.11 and 3.12 and
also builds the Docker image.

## Ground rules for code changes

1. **Safety layer first.** `symptompilot/safety/redflags.py` must keep running
   before any model call. Nothing generated may raise or lower an urgency level.
2. **Evidence or silence.** Answers either cite retrieved passages with `[S#]`
   markers or explicitly abstain. Do not add fallback "general knowledge" prose.
3. **No clinical liability creep.** No dosages, no diagnoses, no "this rules out"
   wording, no advice to stop prescribed treatment.
4. **Small, typed, tested.** Prefer pure functions, type hints everywhere, and a
   unit test next to every behaviour change. Network calls stay behind a thin
   client so tests can fake them.
5. **No new heavy dependencies** without discussion. The project deliberately
   ships without a vector database, an orchestration framework or a JS build step.

## Adding a knowledge-base page

1. Copy the frontmatter shape from an existing file in [`knowledge/`](knowledge/).
2. Required fields: `id`, `title`, `topic`, `summary`, `tags`, `sources`.
3. Cite public-health or peer-reviewed sources; write the prose yourself rather
   than pasting copyrighted text.
4. Run `python -m symptompilot ingest` and confirm the page appears in
   `python -m symptompilot topics`.
5. Add at least one case to
   [`src/symptompilot/evaluation/cases.yaml`](src/symptompilot/evaluation/cases.yaml)
   so the new page is covered by the retrieval metric.

## Adding a red-flag rule

Add the rule to [`src/symptompilot/safety/rules.yaml`](src/symptompilot/safety/rules.yaml)
with `id`, `label`, `level`, `advice`, `patterns` (regular expressions) and,
where relevant, `all_of` for compound presentations and `docs` to point at the
knowledge-base page that explains it. Then add a parametrised case to
`tests/test_redflags.py`, including a **negated** phrasing so the rule does not
fire on "no chest pain".

Rules that could plausibly fire on a benign sentence need a negation test. A rule
that under-triages is a more serious bug than one that over-triages.

## Commit messages

Conventional-ish and imperative: `feat: add dehydration follow-up questions`,
`fix: stop negated chest pain from escalating`. Keep the subject under 72
characters and explain *why* in the body when the change is subtle.

## Reporting bugs and requesting features

Use the issue templates. Never include real patient data, credentials or
personally identifying health information in an issue, a test, or a fixture.
