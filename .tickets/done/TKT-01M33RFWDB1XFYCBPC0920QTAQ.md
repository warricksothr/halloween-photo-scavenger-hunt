---
schema: 3
id: TKT-01M33RFWDB1XFYCBPC0920QTAQ
title: Harden the backend and evidence pipeline
type: epic
status: done
status_reason: null
priority: high
due_on: null
labels:
  - backend
  - security
  - quality
assignees: []
milestone: null
parent: null
origin: null
dependencies: []
blocks_on: none
references: []
claim: null
archive: null
created_at: 2026-09-22T05:12:50Z
updated_at: 2026-09-23T13:38:22Z
created_by:
  id: agent:opencode/review-system-design
  name: ""
updated_by:
  id: agent:opencode/t3code-0691bbb1
  name: ""
extensions: {}
---

## Description

The review found one urgent correctness hole in the shared SQLite connection and a cluster of evidence/security gaps around it. This epic collects the backend fixes that protect the audit invariant, the upload path, and the unauthenticated surface.

## Summary

All eleven children are merged and closed: RFWG7 (shared connection),
X80N (join route), RFWH1, RFWHX, RFWJN, RFWKK (evidence and unauthenticated
surface), RFWMFMPB3 (audit-actions drift), RFWN88Y57BZ (session TTL),
RFWP28QSFGVNPKJ3EY6SS (atomic migrations), RFWPVZG68H8JFWRK6JK70 (upload
free-space floor), and RFWQM9HYPK702FCAXGWNX (blocking work off the event
loop). The audit invariant, upload path, and unauthenticated surface are
hardened and covered by regression tests.
