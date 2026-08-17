# Contributing

## Development setup

1. Install `uv`.
2. Clone the repo.
3. Run:

```bash
uv run ultra-ralph-local setup
```

## Before opening a PR

Run the tests:

```bash
uv run --with pytest pytest
```

If you change CLI behavior, update `README.md` too.

## Scope

Keep changes small and direct.

Preferred contributions:

- bug fixes
- packaging improvements
- clearer docs
- reliability improvements around config and upload behavior

Please avoid unrelated refactors in the same PR.
