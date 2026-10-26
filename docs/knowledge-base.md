# Knowledge base

The knowledge base is a directory of markdown pages (`knowledge/` by default).
Pages are human-readable on GitHub, parsed into chunks at startup, and cited by
title and section.

## Page format

```markdown
---
id: chest-pain
title: Chest pain, pressure and tightness
topic: Cardiovascular
summary: One or two sentences used in listings and topic cards.
tags: [chest, pain, pressure, heart attack]
sources:
  - title: Heart attack symptoms
    url: https://www.cdc.gov/heart-disease/about/heart-attack.html
    publisher: Centers for Disease Control and Prevention
---

## Overview

Prose, in your own words.
```

| Field | Required | Notes |
| --- | --- | --- |
| `id` | recommended | Stable slug; defaults to the file name. Duplicates are rejected at load time |
| `title` | recommended | Used in citations and the UI |
| `topic` | recommended | Grouping label shown in the topic list |
| `summary` | recommended | Kept short; surfaced in `/api/topics` |
| `tags` | optional | Indexed alongside the body, so lay synonyms help |
| `sources` | **required in practice** | At least one public reference; the first one is linked in evidence cards |

## How pages become passages

1. `##`/`###` headings split the page into sections. Prose before the first
   heading becomes "Overview".
2. Each section is packed into chunks of about 900 characters with a 140-character
   overlap, never splitting mid-sentence unless a single paragraph is oversized.
3. Chunk ids are `doc_id#n`, and every chunk inherits the page's title, section,
   tags and sources — that is what makes `[S1] Cold, flu and sore throat ›
   Warning signs` possible.

Because headings become citation labels, write headings that read well as a
citation suffix ("Warning signs", "What may help now", not "Section 2").

## Writing guidance

- **Write it yourself.** Summarise public guidance in your own words; do not paste
  copyrighted text.
- **Stay descriptive.** "Chest pain can be a heart attack" is fine. "You have
  angina" is not: the assistant must never diagnose.
- **No dosages.** Refer to "a pharmacist or clinician" instead of numbers.
- **Say when to escalate.** Every page should have a "Warning signs" or "When to
  seek care" section, because those sentences are what the composer quotes.
- **Name the uncertainty.** A closing "Limits of this guidance" section keeps
  answers honest and gives the composer something to cite when a question is
  borderline.
- **Use the words patients use.** Include both "urine" and "pee", "abdomen" and
  "tummy". The retriever expands many synonyms, but matching the corpus directly
  is always better.

## Rebuilding the index

```bash
python -m symptompilot ingest            # sync SQLite with knowledge/
python -m symptompilot ingest --embed    # also store dense vectors via Ollama
python -m symptompilot topics            # confirm what is indexed
```

Ingestion is idempotent and checksum-driven: unchanged pages are skipped, changed
pages are re-chunked, deleted pages are removed together with any orphaned
vectors. The server also syncs at startup, so editing a page and restarting is
enough during development.

## Adding a page checklist

- [ ] Frontmatter complete, `id` unique.
- [ ] At least one `sources` entry with a real URL.
- [ ] Every section heading reads as a citation suffix.
- [ ] Includes warning signs and an explicit limits paragraph.
- [ ] No dosages, no diagnosis language, no copied text.
- [ ] `python -m symptompilot ingest` succeeds and `topics` lists it.
- [ ] At least one evaluation case references the new `id` in `expect_docs`.
