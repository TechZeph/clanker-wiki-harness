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
# Run tests
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
```

After installation, replace `PYTHONPATH=src python3 -m clanker_wiki_harness.cli` with:

```bash
clanker-wiki-harness
```
