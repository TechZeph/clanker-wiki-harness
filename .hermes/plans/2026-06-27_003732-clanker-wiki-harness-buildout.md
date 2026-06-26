# Clanker Wiki Harness Buildout Implementation Plan

> **For Hermes:** Use subagent-driven-development or a fresh focused implementation context to implement this plan task-by-task. After each task, run the task-specific tests, then the full harness verification command. Keep project state updated in `~/workspace/vaults/clanker-vault/wiki/projects/clanker-wiki-harness/`.

**Goal:** Turn `clanker-wiki-harness` from a safe staging/validation/diff foundation into an installable, portable, local-first pipeline for staged source ingest, model-assisted extraction planning, deterministic wiki writes, reviewable diffs, and approved live apply.

**Architecture:** Keep the trust boundary strict: source extraction and model calls produce artifacts/plans outside the live vault; deterministic Python code writes only to a staging vault; validators and diff reports gate every transition; live apply requires explicit approval. Keep paths portable via `Path.home()`, `~`, `$CLANKER_WORKSPACE`, and `$CLANKER_WIKI_RUNS_DIR`; never hardcode account-specific absolute paths.

**Tech Stack:** Python 3.11+, stdlib-first CLI (`argparse`, `pathlib`, `json`, `filecmp`, `shutil`, `subprocess` where necessary), pytest, optional local external tools for later PDF/OCR/model steps.

---

## Current State Snapshot

Repository:

```text
~/workspace/repos/clanker-wiki-harness
```

Durable project state:

```text
~/workspace/vaults/clanker-vault/wiki/projects/clanker-wiki-harness/
```

Current repo status as of 2026-06-27:

```text
?? .gitignore
?? README.md
?? pyproject.toml
?? src/
?? tests/
```

Current working capabilities:

- Portable default vault resolution via `src/clanker_wiki_harness/paths.py`:
  - `$CLANKER_WORKSPACE/vaults/clanker-vault` when `CLANKER_WORKSPACE` is set.
  - `~/workspace/vaults/clanker-vault` otherwise.
- `stage`: copies a vault into an isolated staging run and excludes UI/cache state.
- `validate`: validates required vault files, source-root immutability, basic page metadata, wikilinks, and source links.
- `diff`: generates a markdown added/removed/modified file report.
- `extract_contract.py`: validates structured model extraction-plan JSON before any writer exists.
- Security hardening already present:
  - staging run IDs reject traversal-like values such as `../escape`.
  - extraction-plan paths reject absolute paths and `..` traversal.
- Installable script entry in `pyproject.toml`:
  - `clanker-wiki-harness = clanker_wiki_harness.cli:main`
- Latest ad-hoc verification evidence:
  - pytest: 14 passed.
  - live-vault validate passed.
  - staging + baseline validate passed.
  - `CLANKER_WORKSPACE` fake workspace default resolution passed.
  - traversal guards passed.
  - security/path scan found no account-specific paths or obvious dangerous primitives.

Current known limitations:

- No PDF/text extraction command yet.
- No local model/Ollama planning command yet.
- No deterministic markdown writer yet.
- No automatic index/log updates yet.
- No apply-to-live command yet.
- No warning/error severity split in validation reports.
- No duplicate canonical-page detection beyond simple link existence.
- No model-evaluation fixtures.

---

## Non-Negotiable Conventions

1. **Portable paths only**
   - Use `~/workspace/...` in docs and shell examples.
   - Use `Path.home()`, `.expanduser()`, `$CLANKER_WORKSPACE`, and `$CLANKER_WIKI_RUNS_DIR` in code.
   - Never write account-specific absolute paths into repo code/docs/tests except in intentionally ignored local scratch output.

2. **Source roots are immutable**
   - `raw/` and `Clippings/` are evidence roots.
   - Extraction artifacts must be written outside the vault or under staging/report dirs, never into source roots.

3. **Model output never writes markdown directly**
   - Models emit JSON plans.
   - Contract validation checks safety.
   - Deterministic code writes markdown in staging.
   - Vault validators check the result.

4. **Review before live apply**
   - Every ingest should produce validation output and a diff report before live changes.
   - Live apply should refuse unsafe states and require explicit confirmation unless a future trusted automation mode is deliberately designed.

5. **Update durable state after meaningful changes**
   - Update these project pages after capability changes:
     - `wiki/projects/clanker-wiki-harness/current-state.md`
     - `wiki/projects/clanker-wiki-harness/validation.md`
     - `wiki/projects/clanker-wiki-harness/roadmap.md` when roadmap changes
     - `wiki/projects/clanker-wiki-harness/decisions.md` for architecture/trust-boundary decisions
   - Append `wiki/log.md` for vault project-state edits.

---

## Phase 0: Land the Current Foundation Cleanly

### Task 0.1: Review and commit current initialized repo

**Objective:** Turn the currently untracked initialized repo into a clean baseline commit.

**Files:**
- Review: all untracked repo files under `~/workspace/repos/clanker-wiki-harness`

**Steps:**

1. Inspect status:

```bash
cd ~/workspace/repos/clanker-wiki-harness
git status --short
```

Expected: untracked `.gitignore`, `README.md`, `pyproject.toml`, `src/`, and `tests/`.

2. Run verification:

```bash
python3 -m pytest -q
PYTHONPATH=src python3 -m clanker_wiki_harness.cli validate
```

Expected:

```text
14 passed
OK: vault validation passed
```

3. Run a focused portability/security scan before committing.

Use a temporary verifier under `/tmp` or the future `scripts/verify.py` command to check for account-specific absolute paths, obvious secret assignments, dangerous shell invocation, dynamic code execution, and unsafe deserialization. The scan should ignore `.git`, Python caches, and pytest caches, and it should fail closed if any match is found.

4. Commit:

```bash
git add .
git commit -m "feat: initialize portable wiki harness foundation"
```

**Verification:** `git status --short` should be empty after commit.

---

## Phase 1: Stronger Validators

### Task 1.1: Add validation severity structure

**Objective:** Split hard errors from advisory warnings so duplicate-page candidates and style issues can warn without blocking everything.

**Files:**
- Modify: `src/clanker_wiki_harness/validators.py`
- Modify: `src/clanker_wiki_harness/cli.py`
- Test: `tests/test_validators.py`
- Test: `tests/test_cli.py`

**Design:**

Change `ValidationReport` from only `messages` to:

```python
@dataclass
class ValidationReport:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def messages(self) -> list[str]:
        return self.errors + self.warnings
```

**Steps:**

1. Add failing tests for warning-only report where `ok` remains true.
2. Update `validate_vault()` call sites to populate `errors=[]`, `warnings=[]`.
3. Update CLI output to print warnings separately.
4. Run:

```bash
python3 -m pytest tests/test_validators.py tests/test_cli.py -q
python3 -m pytest -q
```

---

### Task 1.2: Validate index coverage for new/changed pages

**Objective:** Ensure staged additions are findable from themed indexes.

**Files:**
- Modify: `src/clanker_wiki_harness/validators.py`
- Test: `tests/test_validators.py`

**Rules:**

When `--baseline` is provided:

- If a new `wiki/*-source.md` or source-summary page exists, require a wikilink from `wiki/index-sources.md`.
- If a new durable page exists, require a wikilink from one matching themed index where possible:
  - concept -> `index-concepts.md`
  - tool -> `index-tools.md`
  - method -> `index-methods.md`
  - benchmark -> `index-benchmarks.md`
  - person -> `index-people.md`
  - claim -> `index-claims.md`
  - workflow -> `index-workflows.md`
  - question -> `index-questions.md`

**Implementation approach:**

- Start conservative: infer source-summary by filename suffix `-source.md` or page type marker if later introduced.
- For durable-page type inference, use either path/name conventions or an optional `**Type**:` field later; do not overfit now.
- If type cannot be inferred, warn instead of error.

**Verification:** Add tests with a staged new source page absent from `index-sources.md`; expect hard error.

---

### Task 1.3: Validate log updates for staged wiki changes

**Objective:** If staged `wiki/` files changed relative to baseline, require `wiki/log.md` to be modified too.

**Files:**
- Modify: `src/clanker_wiki_harness/validators.py`
- Test: `tests/test_validators.py`

**Rules:**

- If any file under `wiki/` except `wiki/log.md` is added/removed/modified relative to baseline, then `wiki/log.md` must also differ from baseline.
- If only `wiki/log.md` changed, do not require extra log updates.

**Verification:**

- Test changed page with unchanged log -> error.
- Test changed page with changed log -> ok.

---

### Task 1.4: Validate project indexes remain navigational

**Objective:** Prevent `wiki/projects/<project>/index.md` from becoming a long project brief.

**Files:**
- Modify: `src/clanker_wiki_harness/validators.py`
- Test: `tests/test_validators.py`

**Initial heuristic:**

- For any `wiki/projects/*/index.md`:
  - warn if over 120 lines.
  - warn if it has more than 2 non-navigation headings besides title/route-map/related pages.
  - error only if it lacks links to sibling pages and is clearly content-heavy.

**Verification:** Add fixture project index with a long essay; expect warning or error depending final heuristic.

---

### Task 1.5: Validate approved source citation style

**Objective:** Catch source links that do not resolve or do not use the expected relative style.

**Files:**
- Modify: `src/clanker_wiki_harness/validators.py`
- Test: `tests/test_validators.py`

**Rules:**

- Source links should point into `../raw/` or `../Clippings/` relative to the wiki page.
- Link targets must not escape the vault after resolution.
- Existing missing-source-link behavior stays hard error.
- Non-standard but resolving source links can start as warnings.

---

## Phase 2: Extraction Command

### Task 2.1: Create extraction module and artifact layout

**Objective:** Add a non-mutating extraction artifact writer outside the vault.

**Files:**
- Create: `src/clanker_wiki_harness/extract.py`
- Modify: `src/clanker_wiki_harness/cli.py`
- Test: `tests/test_extract.py`

**Command shape:**

```bash
clanker-wiki-harness extract SOURCE --output-dir /tmp/clanker-wiki-harness/<run-id>/extract
```

**Artifact layout:**

```text
extract/
  source.txt
  metadata.json
```

**Rules:**

- `SOURCE` must resolve under `raw/` or `Clippings/` of the selected vault.
- Do not write under the live vault.
- Markdown/text files can be copied/extracted with stdlib first.
- PDF support can be a separate task.

---

### Task 2.2: Add markdown/text extraction

**Objective:** Support `.md`, `.txt`, `.json`, `.yaml`, `.yml`, and `.csv` sources with safe text extraction.

**Files:**
- Modify: `src/clanker_wiki_harness/extract.py`
- Test: `tests/test_extract.py`

**Verification:**

- Test extracting `Clippings/ideas/example.md` into tempfile output.
- Ensure source file is unchanged.
- Ensure output path is outside the vault.

---

### Task 2.3: Add PDF extraction adapter

**Objective:** Add PDF text extraction without making PDF dependencies mandatory unless needed.

**Files:**
- Modify: `src/clanker_wiki_harness/extract.py`
- Modify: `pyproject.toml` if optional dependency is chosen.
- Test: `tests/test_extract.py`

**Approach options:**

- Prefer optional dependency group for PyMuPDF or pypdf.
- If dependency unavailable, fail with actionable message:

```text
PDF extraction requires installing the pdf extra: pip install -e '.[pdf]'
```

**Verification:** Unit test dependency-missing path without requiring real PDF library.

---

## Phase 3: Model Planning Command

### Task 3.1: Define model provider interface

**Objective:** Keep Ollama/model invocation isolated and testable.

**Files:**
- Create: `src/clanker_wiki_harness/model_client.py`
- Test: `tests/test_model_client.py`

**Interface:**

```python
@dataclass
class ModelRequest:
    model: str
    prompt: str
    endpoint: str = 'http://127.0.0.1:11434/api/generate'

class ModelClient:
    def generate_json(self, request: ModelRequest) -> dict[str, Any]: ...
```

**Security:**

- No shell invocation for model calls.
- Use Python HTTP stdlib or optional requests/httpx.
- Timeouts required.

---

### Task 3.2: Add `plan` command for extraction-plan JSON

**Objective:** Use extracted source text and current wiki context to ask a model for structured JSON, then validate it.

**Files:**
- Modify: `src/clanker_wiki_harness/cli.py`
- Create: `src/clanker_wiki_harness/planning.py`
- Test: `tests/test_planning.py`

**Command shape:**

```bash
clanker-wiki-harness plan \
  --vault ~/workspace/vaults/clanker-vault \
  --extracted /tmp/clanker-wiki-harness/run/extract/source.txt \
  --model qwen3.5:9b \
  --output /tmp/clanker-wiki-harness/run/plan.json
```

**Rules:**

- Model output must be parsed and passed through `validate_extraction_plan()`.
- Invalid model output should write a failure report, not modify staging.

---

## Phase 4: Deterministic Markdown Writer

### Task 4.1: Define page rendering primitives

**Objective:** Centralize wiki page formatting so models never write final markdown.

**Files:**
- Create: `src/clanker_wiki_harness/render.py`
- Test: `tests/test_render.py`

**Functions:**

```python
def render_page(title: str, summary: str, sources: list[str], body: str, related_pages: list[str]) -> str: ...
def render_log_entry(...): ...
def render_index_line(slug: str, description: str) -> str: ...
```

**Verification:** Snapshot-like string tests for required fields.

---

### Task 4.2: Add `write` command that applies a validated plan to staging

**Objective:** Convert plan JSON into staged wiki files, indexes, and log entries.

**Files:**
- Create: `src/clanker_wiki_harness/writer.py`
- Modify: `src/clanker_wiki_harness/cli.py`
- Test: `tests/test_writer.py`

**Command shape:**

```bash
clanker-wiki-harness write \
  --staged /tmp/clanker-wiki-harness/run/vault \
  --plan /tmp/clanker-wiki-harness/run/plan.json
```

**Rules:**

- Refuse invalid plan.
- Write only under `staged/wiki/`.
- Never write under staged `raw/` or `Clippings/`.
- Append staged `wiki/log.md`.
- Update relevant indexes.

---

### Task 4.3: Add conservative existing-page behavior

**Objective:** Avoid destructive overwrites of existing durable pages.

**Files:**
- Modify: `src/clanker_wiki_harness/writer.py`
- Test: `tests/test_writer.py`

**Rules:**

- New pages can be created.
- Existing source-summary pages can be updated only if the plan explicitly says update.
- Existing durable pages should get clearly marked proposed sections or patch artifacts until the patching strategy is designed.

---

## Phase 5: Apply Command

### Task 5.1: Implement pre-apply validation and changed-file summary

**Objective:** Create a safe live-apply entry point that first proves staging is valid.

**Files:**
- Create: `src/clanker_wiki_harness/apply.py`
- Modify: `src/clanker_wiki_harness/cli.py`
- Test: `tests/test_apply.py`

**Command shape:**

```bash
clanker-wiki-harness apply \
  --baseline ~/workspace/vaults/clanker-vault \
  --staged /tmp/clanker-wiki-harness/run/vault
```

**Rules:**

- Run `validate_vault(staged, baseline)` first.
- Refuse if validation has errors.
- Print changed files before applying.
- Default should require confirmation.

---

### Task 5.2: Add backup/patch generation before apply

**Objective:** Ensure live apply is reversible.

**Files:**
- Modify: `src/clanker_wiki_harness/apply.py`
- Test: `tests/test_apply.py`

**Options:**

- Create timestamped tar/zip backup of changed live files.
- Or generate a patch file under runs dir before copy.

**Verification:** Test that backup/patch exists before files are copied.

---

## Phase 6: Model Evaluation Fixtures

### Task 6.1: Add fixture corpus

**Objective:** Create known input/output cases to compare local models before trusting them.

**Files:**
- Create: `tests/fixtures/sources/`
- Create: `tests/fixtures/expected_plans/`
- Create: `src/clanker_wiki_harness/eval.py`
- Test: `tests/test_eval.py`

**Fixture types:**

- short paper-like markdown
- tool README snippet
- Zeph idea clipping
- ambiguous claim/question source

---

### Task 6.2: Add scoring report

**Objective:** Score plans on JSON validity, path safety, source coverage, page categorization, citation fidelity hints, and useful next actions.

**Files:**
- Modify: `src/clanker_wiki_harness/eval.py`
- Modify: `src/clanker_wiki_harness/cli.py`
- Test: `tests/test_eval.py`

**Command shape:**

```bash
clanker-wiki-harness eval-model --model qwen3.5:9b --fixtures tests/fixtures
```

---

## Phase 7: Packaging and Developer Experience

### Task 7.1: Add installation docs and smoke install test

**Objective:** Ensure this runs on a fresh machine with the Clanker folder structure initialized.

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`
- Test: possible install smoke under `/tmp` via ad-hoc verifier

**Docs:**

```bash
cd ~/workspace/repos/clanker-wiki-harness
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
clanker-wiki-harness --help
```

---

### Task 7.2: Add canonical verification script

**Objective:** Avoid repeated “ad-hoc only” ambiguity by defining one explicit project verification command.

**Files:**
- Create: `scripts/verify.py` or `scripts/verify.sh`
- Modify: `README.md`

**Command:**

```bash
python3 scripts/verify.py
```

**Checks:**

- pytest
- portable live-vault validate when vault exists
- staging smoke test when vault exists
- security/path scan
- optional installed CLI check

---

## Always-Run Verification Before Claiming Done

From repo root:

```bash
python3 -m pytest -q
PYTHONPATH=src python3 -m clanker_wiki_harness.cli validate
```

For changed portability/security behavior, also run a temp verifier under `/tmp` with filename prefix `hermes-verify-` that checks:

- `CLANKER_WORKSPACE` override.
- staging to tempfile runs dir.
- unsafe run ID rejection.
- extraction-plan traversal rejection.
- no account-specific absolute paths in repo files.

If/when `scripts/verify.py` exists, that should become the canonical single command.

---

## Risks and Tradeoffs

- Validator strictness can block useful staged drafts if introduced too aggressively. Start warnings-first for subjective checks, errors for safety/source integrity.
- PDF extraction dependencies can complicate install. Keep PDF extras optional.
- Model planning may produce valid JSON that is semantically poor. Model eval fixtures are needed before trusting automation at scale.
- Apply-to-live is high consequence. Keep confirmation and backup mandatory until repeated real-world use proves safe.
- Existing-page patching is harder than new-page rendering. Prefer conservative proposal sections or patch artifacts before automatic merge logic.

---

## Open Questions to Resolve With Zeph

1. Should the next implementation focus be stronger validators or extraction command first?
2. Should validation warnings ever block apply, or only hard errors?
3. What should be the first real source fixture: a paper, a README, or a Zeph idea clipping?
4. Should the deterministic writer update existing durable pages directly, or create proposed patch files for review?
5. Should the harness eventually become a Hermes skill-backed workflow, a standalone CLI, or both?

---

## Recommended Next Move

Do Phase 0 first: commit the current clean foundation.

Then do Phase 1 before any local model integration. Strong validators are the safety net that will make the later LLM pieces useful instead of risky.
