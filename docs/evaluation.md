# Evaluation

The evaluation suite is offline, deterministic and fast (well under a second).
It exists so that changes to rules, scoring or content cannot silently degrade
screening or retrieval.

## Running it

```bash
python -m symptompilot eval          # human-readable table
python -m symptompilot eval --json   # machine-readable report
```

Exit code is `0` when every threshold is met and `1` otherwise, which is what CI
checks.

## Metrics

| Metric | Definition | Threshold |
| --- | --- | --- |
| `level_accuracy` | Share of cases where the screener's urgency equals `expect_level` | ≥ 0.90 |
| `retrieval_hit_rate` | Share of cases where any `expect_docs` page appears in the top 3 passages | ≥ 0.80 |
| `emergency_recall` | Share of emergency cases actually classified `emergency` | = 1.00 |
| `abstain_accuracy` | Share of cases where `abstained` matches `expect_abstain` | reported, not gated |

`emergency_recall` has no tolerance: a single missed emergency fails the build.
Over-triage is annoying; under-triage is dangerous.

Screening and retrieval are measured separately on purpose. If retrieval quality
falls while screening stays correct, the failure shows up in its own column
instead of being averaged away.

## Current results

| Metric | Value |
| --- | --- |
| `level_accuracy` | 1.00 |
| `retrieval_hit_rate` | 1.00 |
| `emergency_recall` | 1.00 |
| `abstain_accuracy` | 1.00 |

18 cases cover 8 emergencies, 4 urgent presentations, 6 routine ones (including a
negated emergency) and one out-of-domain question. These numbers describe a small
curated set, not clinical validity — treat them as regression protection, not
evidence of accuracy on real patients.

## Case format

```yaml
- id: cardiac-emergency
  message: I have crushing chest pain spreading to my left arm and I am sweating
  expect_level: emergency      # emergency | urgent | routine | unknown
  expect_docs: [chest-pain]    # optional; must appear in the top 3
  expect_abstain: false        # optional; asserts the abstain flag
```

Guidance for new cases:

- Write the way a patient would speak, not in clinical shorthand. Lay phrasing is
  what exercises the vocabulary expansion.
- One behaviour per case. A case that tests two things makes failures ambiguous.
- Include the negated form of every dangerous pattern you add.
- Prefer a realistic sentence over a keyword list; keyword lists hide ranking bugs.

## Inspecting a single case

```bash
python -m symptompilot ask "I have had a high fever for four days" --json
```

The JSON payload contains `urgency`, `red_flags`, `citations`, `verification` and
`latency_ms`, which is usually enough to see whether a failure is screening,
retrieval, composition or verification.

## What is not measured

- Factual correctness of knowledge-base prose (reviewed by humans).
- Whether a model-generated answer would be safe with a hostile prompt; only the
  deterministic parts are covered by tests.
- Latency under load. `latency_ms` in the report is single-request time in
  extractive mode.
