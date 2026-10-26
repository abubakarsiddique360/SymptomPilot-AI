## What does this change do?

<!-- One or two sentences. Link the issue: "Closes #12". -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Knowledge-base content
- [ ] Documentation
- [ ] Refactor / tooling

## Safety checklist

- [ ] The deterministic screener still runs **before** any model call.
- [ ] No change lets generated text lower an urgency level.
- [ ] New or changed answers keep inline `[S#]` evidence markers.
- [ ] I did not add dosages, diagnoses, or "rules out" language.

## Validation

- [ ] `python -m ruff check .` passes
- [ ] `python -m ruff format --check .` passes
- [ ] `python -m pytest` passes
- [ ] `python -m symptompilot eval` passes (paste metrics below)

```
level_accuracy / retrieval_hit_rate / emergency_recall
```

## Notes for reviewers

<!-- Anything subtle: scoring changes, threshold changes, new rules, migration steps. -->
