# Super Scholar Frontend data-source notes

V3.11 preserves the V3.10 Academic Fit / Current Actionability split, adds truthful journal metadata enrichment (OpenAlex public OA/APC + optional Clarivate JIF/JCR/WoS), and exposes complete returned evidence through expand-all viewers. CCF `U` is unknown/unverified and is distinct from verified `N`.

# Frontend data behavior — V3.9

The frontend is a presentation/configuration client; scholarly ranking and source verification run in FastAPI.

- `/app/settings` stores AI-provider settings separately from scholarly-data settings. Secret values are sent only when the user enters/replaces them; GET responses contain masked hints, never decrypted keys.
- The scholarly panel can configure/test OpenAlex, Crossref and Semantic Scholar and enable/disable DBLP. CCF/CCFDDL/local References are managed no-key sources.
- Recommendation runs come from `POST /api/v1/projects/{project_id}/recommendations`. The frontend does not recreate ranking locally.
- `dataSourceHealth` controls the recommendation status badge. Anonymous OpenAlex can be `Limited`; failed enrichers are displayed as `Degraded`; the UI does not call them verified.
- Missing evidence is rendered as `—` / Unknown rather than `0` unless the backend actually computed a zero from available evidence.
- Research Match is labelled as fit evidence, never acceptance probability.
- Raw evidence UUIDs remain internal grounding keys; the profile UI renders human-readable source labels and interactive evidence viewers.

See repository-root `DATA_SOURCES.md` for source roles, provenance and privacy behavior.


V3.9.1 separates OpenAlex semantic Works/Source hydration from candidate Venue → Source resolution and links Semantic Scholar directly to the official API-key request form.
