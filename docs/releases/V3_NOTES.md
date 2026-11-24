# Super Scholar V3 release notes

## Research Understanding Engine

- Added durable `research_analysis_runs` database model and Alembic migration `20260826_0002`.
- Added PyMuPDF PDF parsing: text, tables, embedded images, page renders and selective OCR.
- Added python-docx structured text/table/media extraction.
- Added structured spreadsheet parsing.
- Added source-ZIP filtering, notebook-cell extraction, repository summaries and common-secret redaction.
- Added visual artifact serving and inspection.
- Added OpenAI Responses multimodal structured analysis with explicit consent, `store=false`, temporary PDF file uploads and evidence-ID validation.
- Added distinction between claimed novelty and literature-verified novelty.
- Kept the deterministic local profile as an explicitly labelled fallback when AI is not configured.

## UI fixes

- Conference-only comparisons no longer show JCR/Impact Factor/APC rows.
- Comparison action buttons use stable columns and no-wrap labels.

## Verification

- Backend: 18 tests passed.
- Alembic: V3 migration reaches `20260826_0002 (head)`.
- Frontend: 34 TS/TSX files passed syntax transpilation; all local aliases resolved.
- Full npm dependency installation/build was not completed in the packaging environment because package-network access timed out.
