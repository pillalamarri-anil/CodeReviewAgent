# AI Code Review Agent (P0)

Reviews real GitHub pull requests on a Java Spring Boot repo with a real LLM, posts
inline + summary findings on the PR, and drives a quality gate (exit 0/1).

Implements **P0** of `coderepo/PRD.md`. One Python app, config-driven, GitHub +
OpenAI. `mock` provider exists for tests / offline only.

```
diff  ->  Java context  ->  LLM (1 call / changed file)  ->  validate  ->  dedup
      ->  risk score + gate  ->  publish (PR comments + commit status)  ->  review-report.json
```

## Quick start (clean -> CLI result, < 10 min)

```bash
cd implementation
python3 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

# offline smoke test -- mock provider, no network
pytest -q

# dry run against the sample repo (writes a report, posts nothing)
LLM_PROVIDER=mock python -m review_agent \
  --repo ../coderepo/BookMyShow \
  --base main --head fix/booking-repository-missing-import \
  --overlay ./overlay --no-publish --report /tmp/review-report.json
```

For a **real** review, copy `.env.example` to `.env` and fill in the OpenAI +
GitHub values, then:

```bash
python -m review_agent --repo ../coderepo/BookMyShow --pr 3 \
  --base main --head my-feature-branch --commit <sha> --overlay ./overlay --publish
```

Exit code: `0` = PASS, `1` = CHANGES REQUESTED (or every file failed LLM review),
`2` = the agent itself errored.

## CLI

| flag | meaning |
|------|---------|
| `--repo` | local checkout to review (default `.`) |
| `--pr` | PR number — enables GitHub diff fetch + publishing |
| `--base` / `--head` | refs for the local `git diff base...head` fallback |
| `--commit` | head SHA for the commit status |
| `--overlay` | dir of `review-rules.yaml` + `docs/` to layer over the repo |
| `--report` | output path (default `review-report.json`, always written) |
| `--publish` / `--no-publish` | post to the PR, or write the report only (default) |

## Configuration (env / `.env`, see `.env.example`)

`LLM_PROVIDER` (`openai` \| `mock`), `OPENAI_API_KEY` / `_MODEL` / `_BASE_URL`,
`GITHUB_TOKEN`, `GITHUB_REPOSITORY`,
`MIN_CONFIDENCE` (0.75), `MAX_CONTEXT_TOKENS` (8000),
`MAX_CRITICAL` / `MAX_HIGH` / `MAX_MEDIUM` (0 / 0 / 5). Secrets come only from the
environment and are never logged.

## Quality gate (PRD §7)

Penalty per finding: CRITICAL 40, HIGH 20, MEDIUM 8, LOW 2.
`score = clamp(100 - Σ, 0, 100)`. The gate fails (exit 1) when any of
`CRITICAL > MAX_CRITICAL`, `HIGH > MAX_HIGH`, `MEDIUM > MAX_MEDIUM`.

## Finding validation (PRD §4.5) — false-positive control

A finding is kept only if its file is in the changed set, its line is inside a changed
hunk, its `evidence` snippet appears verbatim in the model input, and its
`confidence ≥ MIN_CONFIDENCE`. CRITICAL / SECURITY findings are never dropped on
confidence alone. Survivors are de-duplicated on
`file + line-bucket + category + normalized-title`.

## CI (GitHub Actions)

`.github/workflows/ai-review.yml` is written for the **sample repo**, not this one.
Copy it into `BookMyShow/.github/workflows/`, then in that repo set:

- secrets: `OPENAI_API_KEY` (optionally `OPENAI_MODEL`, `OPENAI_BASE_URL`)
- variables: `AI_REVIEW_AGENT_REPO` (this repo's `owner/name`), `AI_REVIEW_AGENT_REF`

It triggers on `pull_request`, runs the agent against the PR diff, posts comments +
commit status, and archives `review-report.json`.

`Jenkinsfile` is intentionally **not** provided — the PRD's Jenkins step is replaced by
GitHub Actions to match the sample repo's existing setup.

## Knowledge overlay

The sample repo does not yet ship review knowledge, so `overlay/` provides
`review-rules.yaml` and `docs/{ARCHITECTURE,schema,persistence}.md`. Commit these into
`BookMyShow` to make them "real", or keep passing `--overlay ./overlay`.

## Layout

```
src/review_agent/
  cli.py  config.py  models.py  pipeline.py  git_ops.py  logging.py
  context/   diff parse, Java brace-scanner extraction, doc/rule selection, budgeted assembly, render
  llm/       provider protocol, openai_provider, mock, strict-JSON contract + 1 repair retry
  review/    validator, dedup, scoring + gate
  publish/   github_client (sole GitHub API surface), comment formatter
  report/    review-report.json writer
  prompts/   system.txt, java_review.txt  (version-controlled)
overlay/     review-rules.yaml + docs for BookMyShow
tests/       offline, mock-only; fixtures under tests/fixtures/
```

The `context/` package is ported from the deterministic prototype in
`coderepo/ContextPrep/context_creator.ipynb`.
