# Super Scholar Frontend V3.11.0

This is the Next.js client for Super Scholar V3.11.0. The repository-root `README.md` is the authoritative setup guide.

Current frontend capabilities include:

- local project/material workflow and evidence-grounded Research Profile;
- AI deep-understanding diagnostics, field-level salvage, Figure/Table evidence viewer and human-readable evidence chips;
- **系统连接与解析 → 学术数据源** settings for OpenAlex, Crossref and Semantic Scholar credentials plus DBLP enablement;
- real scholarly-source diagnostics rather than a single HTTP-success badge;
- backend-driven multi-source CS venue recommendation using OpenAlex Works/Sources, Semantic Scholar, DBLP, Crossref, local References, CCF and CCFDDL;
- persisted per-run data-source health (`Ready / Limited / Degraded`) and explicit Unknown/null evidence;
- Required/Preferred constraints, comparison and user venue selection.

The browser does not calculate authoritative venue facts or run a parallel recommendation algorithm. It submits the confirmed Research Profile/preferences and renders the persisted backend recommendation run.

After dependencies are installed:

```bash
npm run dev
```
