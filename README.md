# clanker-wiki-harness

Staging and validation harness for the Clanker vault at `~/workspace/vaults/clanker-vault`.

Purpose:

1. Copy the live vault to an isolated staging directory.
2. Let agents/local LLMs propose or apply wiki changes in staging.
3. Validate links, citations, page format, index/log hygiene, and source-root immutability.
4. Produce a diff report before live apply.

This repo is intentionally separate from the vault so test code and experiments do not clutter the second brain.

## Portable paths

The Clanker folder layout is stable, but the operating-system username is not. Do not hardcode account-specific absolute paths in scripts or docs.

Default layout:

```text
~/workspace/
  vaults/clanker-vault/
  repos/clanker-wiki-harness/
```

The CLI resolves its default vault path from:

1. `$CLANKER_WORKSPACE/vaults/clanker-vault`, when `CLANKER_WORKSPACE` is set.
2. `~/workspace/vaults/clanker-vault`, otherwise.

Staging runs should stay outside the live vault. The default staging location is `/tmp/clanker-wiki-harness` unless `$CLANKER_WIKI_RUNS_DIR` is set.

## Usage

From this repo:

```bash
# Run full project verification
python3 scripts/verify.py

# Or run only the test suite
python3 -m pytest -q

# Copy live vault into staging
PYTHONPATH=src python3 -m clanker_wiki_harness.cli stage \
  ~/workspace/vaults/clanker-vault \
  /tmp/clanker-wiki-harness \
  smoke-run

# Validate the default live vault
PYTHONPATH=src python3 -m clanker_wiki_harness.cli validate

# Validate a staged vault against the live baseline
PYTHONPATH=src python3 -m clanker_wiki_harness.cli validate \
  /tmp/clanker-wiki-harness/smoke-run/vault \
  --baseline ~/workspace/vaults/clanker-vault

# Produce a markdown diff report
PYTHONPATH=src python3 -m clanker_wiki_harness.cli diff \
  ~/workspace/vaults/clanker-vault \
  /tmp/clanker-wiki-harness/smoke-run/vault \
  --output /tmp/clanker-wiki-harness/smoke-run/diff.md

# Ask Ollama for a validated JSON extraction plan
PYTHONPATH=src python3 -m clanker_wiki_harness.cli plan \
  'Clippings/ideas/example.md' \
  --vault ~/workspace/vaults/clanker-vault \
  --model gemma3:12b \
  --attempts 3 \
  --output /tmp/clanker-wiki-harness/example-plan.json

# Let a local model write markdown into staging, validate, repair, and report a diff
PYTHONPATH=src python3 -m clanker_wiki_harness.cli ingest-local \
  'Clippings/ideas/example.md' \
  --vault ~/workspace/vaults/clanker-vault \
  --runs-dir /tmp/clanker-wiki-harness \
  --run-id example-ingest \
  --model gemma3:12b \
  --attempts 3

# After reviewing the diff, apply validated staged wiki changes to the live vault
PYTHONPATH=src python3 -m clanker_wiki_harness.cli apply \
  /tmp/clanker-wiki-harness/example-ingest/vault \
  --vault ~/workspace/vaults/clanker-vault
```

The `plan` command uses Ollama's HTTP API in JSON mode, extracts a JSON object from wrapped model output when needed, applies limited deterministic repairs for common page-type aliases, retries invalid JSON or contract-invalid plans, then validates the result with the extraction-plan contract.

The `ingest-local` command uses plain markdown sections instead of JSON. The model writes a complete source-summary page plus small `APPEND` snippets for `wiki/index-sources.md` and `wiki/log.md`. The harness applies those edits only to a staging copy, validates the staged vault, feeds validation errors back to the model for repair, and writes a diff report. It does not apply changes to the live vault.

The `apply` command validates the staged vault against the live baseline, refuses removed files or source-root changes, and copies only added/modified `wiki/*.md` files into the live vault.

After installation, replace `PYTHONPATH=src python3 -m clanker_wiki_harness.cli` with:

```bash
clanker-wiki-harness
```
