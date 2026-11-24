# Changelog

All notable development milestones of **Super Scholar** are recorded here.

Detailed historical implementation notes are archived under
[`docs/releases/`](docs/releases/).

## Current — V3.9.1

### Research understanding

- Evidence-grounded research-profile generation.
- Text-first provider pipeline with bounded requests.
- Optional visual evidence analysis.
- Figure/Table reconstruction from PDF pages.
- Human-readable evidence references and source viewer.
- Local deterministic fallback when final AI synthesis fails.

### Scholarly data connections

- Configurable OpenAlex, Semantic Scholar, Crossref and DBLP integrations.
- Per-source diagnostics and explicit health states.
- Encrypted persistence for scholarly API credentials.
- `Ready`, `Limited`, `Degraded`, `Error`, `Disabled` and `N/A` are treated differently.

### Venue recommendation

- OpenAlex semantic Works retrieval.
- Candidate Venue → OpenAlex Source resolution.
- OpenAlex Source-topic evidence.
- Independent Semantic Scholar publication-Venue evidence.
- DBLP conference identity normalization.
- Crossref journal identity verification.
- Manuscript References community prior.
- CCF / CCFDDL ranking and conference metadata.
- Missing evidence stays Unknown instead of being fabricated as zero or pass.

### AI provider configuration

- OpenAI, DeepSeek and Custom providers keep independent configurations.
- Base URL, model, protocol, output mode, capabilities and encrypted API keys persist separately.
- Switching providers no longer destroys the Custom configuration.
- Unsaved provider drafts are retained while switching inside the settings page.

---

## Historical releases

| Release | Main milestone |
|---|---|
| V3.9.1 | Candidate Source resolution and independent AI-provider profiles |
| V3.9 | Scholarly-source configuration and multi-source recommendation evidence |
| V3.8 | Hybrid CS venue recommendation |
| V3.7.1 | Evidence viewer and improved PDF visual evidence |
| V3.7 | OpenAlex + CCF/CCFDDL venue recommendation |
| V3.6.1 | Provider-output salvage and reliability improvements |
| V3.6 | Text-first provider architecture |
| V3.5 | Research-understanding pipeline improvements |
| V3.4 | Research evidence and parsing improvements |
| V3.3 | Research-profile iteration |
| V3.2 | Material-processing improvements |
| V3.1 | Early research-understanding workflow |
| V3 | Major application restructuring |
| V2.1 | Earlier prototype milestone |

See [`docs/releases/`](docs/releases/) for the original detailed notes.
