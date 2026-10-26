# Safety model

SymptomPilot is an educational triage aid. It is **not** a medical device, does
not diagnose, and cannot rule out illness. This document explains how the
software behaves, what it deliberately refuses to do, and where the boundaries
of its safety claims are.

## Three independent layers

1. **Deterministic screening** (`safety/rules.yaml`). Regex rules over a
   normalised message produce a red-flag list and an urgency level. No model is
   involved, so no prompt or retrieved passage can change the outcome.
2. **Grounded composition** (`agent/composer.py`, `agent/prompts.py`). Clinical
   statements come from retrieved knowledge-base passages, each carrying a `[S#]`
   marker. Without evidence, the assistant abstains instead of free-styling.
3. **Verification** (`agent/verifier.py`). Markers that do not map to a supplied
   passage are stripped, the emergency statement is prepended if missing, and the
   response records what was supplied versus what was cited in
   `verification.notes`.

Because layer 1 runs first and layer 3 runs last, an emergency message still
produces an emergency answer when retrieval finds nothing and when the model is
unreachable.

## Urgency levels

| Level | Meaning | Typical trigger |
| --- | --- | --- |
| `emergency` | Contact emergency services now | Chest pain, stroke signs, severe breathlessness, anaphylaxis, suicidal intent, infant fever, seizure |
| `urgent` | Same-day assessment | High or persistent fever, dehydration, urinary infection, worsening abdominal pain |
| `routine` | Often manageable with monitoring | Cold symptoms, mild headache, mild back pain, anxiety symptoms |
| `unknown` | Not enough signal | Out-of-domain questions, vague messages |

The level is the maximum over matched rules, so a routine symptom cannot mask an
emergency sign in the same message.

## Negation handling

"no chest pain, just a runny nose" must not trigger the chest-pain rule. The
screener inspects the three tokens before a match for negators (`no`, `not`,
`without`, `denies`, `never`, `none`, `negative`, `free`). A conjunction inside
that window (`but`, `however`, `though`, `except`, `although`, `just`, `only`,
`apart`) cancels the negation, so "no fever **but** crushing chest pain" still
escalates. A bare "not" followed by hedging words (`sure`, `if`, `whether`,
`think`, `know`, `certain`) is treated as uncertainty rather than denial.

Limitations: negation is lexical, not syntactic. Very long sentences, double
negatives and sarcasm can defeat it. Under-triage is treated as the more serious
direction of error, so patterns lean toward firing.

## Compound rules

Some presentations are only alarming together. `all_of` requires every listed
pattern to match, for example:

- fever **and** a stiff neck / non-blanching rash → `emergency` (meningitis, sepsis)
- hit head **and** vomiting / drowsiness → `emergency`
- back pain **and** groin numbness **and** loss of bladder control → `emergency`

## Abstention

If the best passage scores below `SYMPTOMPILOT_ABSTAIN_THRESHOLD` (default
`0.15`), the response sets `abstained: true`, drops citations, and says plainly
that the knowledge base does not cover the question. The urgency banner still
appears: an out-of-corpus question from someone describing chest pain is still an
emergency.

## What the assistant will not do

- Name a diagnosis or say a condition has been ruled out.
- Give drug names with doses, or advise stopping prescribed treatment.
- Interpret an image or a test result.
- Answer from general knowledge when evidence is missing.
- Contradict or downgrade the deterministic urgency level.

These rules are enforced in the system prompt **and** in the offline composer, so
they hold in every mode.

## Prompt-injection resistance

Retrieved text is untrusted input: a knowledge-base page could contain "ignore
your rules". Mitigations:

- The screener never reads retrieved text, so urgency cannot be manipulated.
- The prompt tells the model that evidence is data, not instructions, and that the
  urgency line is fixed.
- Answers are only accepted with `[S#]` markers that map to real passages.
- A hostile page cannot invent a citation, because markers are validated against
  the passages actually supplied.

Residual risk: a hostile page inside `knowledge/` can still poison *content*
(what the assistant asserts) even though it cannot change urgency. Review
knowledge-base changes as carefully as code.

## Known limitations

- No authentication, no rate limiting, no audit log. Self-host behind a proxy if
  it is reachable by anyone else.
- Not validated on real patients; the rules encode public first-aid guidance, not
  a triage protocol validated in a clinical trial.
- English only. Lay vocabulary expansion covers common phrasing, not dialects.
- Cannot detect emergencies described only with metaphor, or signs not in the rule
  set.
- The emergency number guidance lists generic examples (911, 112, 999, 108) and
  cannot know the user's country.

## If you find a safety bug

Under-triage (a missing escalation) and prompt-injection paths that lower urgency
are security-relevant. Report them privately as described in
[SECURITY.md](../SECURITY.md). Please include the exact message, the urgency you
expected, and the urgency returned.
