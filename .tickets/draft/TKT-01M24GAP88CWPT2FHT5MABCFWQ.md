---
schema: 3
id: TKT-01M24GAP88CWPT2FHT5MABCFWQ
title: Tune duplicate-evidence hash threshold
type: spike
status: draft
status_reason: null
priority: normal
due_on: null
labels:
  - research
  - evidence
  - security
  - readiness
assignees: []
milestone: null
parent: TKT-01M24GA0PMGWEM80RBS502FGVY
origin: null
dependencies:
  - TKT-01M24G6DR9Z7WCWYYA79J5M5QX
blocks_on: none
references:
  - ref: follow-up:phash-threshold
    path: docs/progress.md
  - ref: implementation:phash-detector
    path: server/app/evidence.py
claim: null
archive: null
created_at: 2026-09-10T01:53:44Z
updated_at: 2026-09-10T17:29:06Z
created_by:
  id: agent:terva/mieli
  name: Mieli
updated_by:
  id: agent:terva/mieli
  name: Mieli
extensions: {}
---

## Description

The current cross-team duplicate detector flags near matches at Hamming distance <= 8 over the 64-bit perceptual hash. docs/progress.md explicitly defers false-positive tuning until representative party photos exist. This ticket turns that open follow-up into a measured decision.

## Acceptance criteria

- [ ] A representative fixture set covers same-photo recompression, resizing, lighting and viewpoint changes, and unrelated photos from different teams.
- [ ] Candidate Hamming thresholds have measured false-positive and false-negative results, with the selected threshold justified for party use.
- [ ] The selected threshold is reflected in code and regression tests, or the investigation records why the existing threshold remains unchanged.
- [ ] docs/progress.md records the chosen threshold and the test command passes.

## Definition of done

- [ ] The decision and its evidence are linked from this ticket.
- [ ] No player-uploaded photos or secrets enter Git.

## Implementation plan

Collect consented representative photos and controlled near-duplicate variants, measure false positives and false negatives at candidate thresholds, choose the threshold for party conditions, update the implementation and tests if needed, and record the result in docs/progress.md or a new ADR.
