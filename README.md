# ultra-ralph-local

Public `uvx` CLI for running a small recursive Ralph council against OpenRouter, appending the winning decision to a hash-chained `decisions.log`, and optionally uploading that log to Hugging Face.

By default, uploads target:

- dataset repo: `PeetPedro/ultrawhale-dogfood`
- dataset path: `ralph/decisions.log`

You can keep those defaults or override them during first-run setup.

## What it does

Each run:

1. snapshots the workspace
2. optionally reads `workspace.txt`
3. optionally reads `dyad-mapping/`
4. asks a small council of Ralphs for the next decision
5. appends the winning decision to `decisions.log`
6. optionally uploads `decisions.log` to Hugging Face

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for `uvx`
- an OpenRouter API key
- optional: a Hugging Face token if you want uploads

## Quick start

Run the setup flow:

```bash
uvx --from git+https://github.com/8b-is/ultra-ralph-local ultra-ralph-local setup
```

The setup prints the exact config path it writes to.

Typical locations:

- macOS: `~/Library/Application Support/ultra-ralph-local/config.json`
- Linux: `~/.config/ultra-ralph-local/config.json`
- Windows: platformdirs user config directory for `ultra-ralph-local`

It asks for:

- `OPENROUTER_API_KEY` (required)
- `HF_TOKEN` (optional)
- Hugging Face dataset repo, default `PeetPedro/ultrawhale-dogfood`
- dataset path, default `ralph/decisions.log`
- whether uploads should be enabled by default

Then run one iteration in the current directory:

```bash
uvx --from git+https://github.com/8b-is/ultra-ralph-local ultra-ralph-local
```

Or point it at another workspace:

```bash
uvx --from git+https://github.com/8b-is/ultra-ralph-local ultra-ralph-local \
  --workspace /path/to/workspace
```

## Loop mode

Run continuously every 33 minutes:

```bash
uvx --from git+https://github.com/8b-is/ultra-ralph-local ultra-ralph-local loop
```

Custom interval:

```bash
uvx --from git+https://github.com/8b-is/ultra-ralph-local ultra-ralph-local loop --interval 900
```

`CTRL-C` requests a graceful stop: the current run finishes, then the loop exits.

Loop output is also appended to `ralph-loop.log` inside the workspace.

## Configuration precedence

Highest to lowest:

1. CLI flags
2. environment variables
3. saved config file
4. built-in defaults

Supported environment variables:

- `OPENROUTER_API_KEY`
- `HF_TOKEN`
- `RALPH_DIR` or `ULTRA_RALPH_WORKSPACE`
- `RALPH_HF_REPO`
- `RALPH_HF_PATH`
- `RALPH_UPLOAD`

## Upload behavior

Uploads are non-fatal.

If Hugging Face auth is missing or upload fails:

- the local run still succeeds
- `decisions.log` is still updated
- the CLI prints a warning

Disable uploads for one run:

```bash
uvx --from git+https://github.com/8b-is/ultra-ralph-local ultra-ralph-local --no-upload
```

Override the default destination:

```bash
uvx --from git+https://github.com/8b-is/ultra-ralph-local ultra-ralph-local \
  --hf-repo your-name/your-dataset \
  --hf-path ralph/decisions.log
```

## Workspace inputs

The current workspace is the prompt context.

Optional files/directories:

- `workspace.txt`: extra plain-text context
- `dyad-mapping/`: additional context from `README.md`, `essences.md`, and the latest `session-*-summary.md`

If those files are absent, the tool still runs.

## Local development

Clone the repo, then run:

```bash
uv run ultra-ralph-local setup
uv run ultra-ralph-local
uv run ultra-ralph-local loop
```

Run tests:

```bash
uv run --with pytest pytest
```

## Repo files

- `src/ultra_ralph_local/cli.py`: main CLI
- `start_ralph_loop.sh`: thin local wrapper around `uv run`
- `dyad-mapping/`: optional context files shipped in this repo

## Security notes

- no API keys are committed
- config is written to a user config file, not the repo
- uploads use the Hugging Face API, not an external `hf` CLI dependency
- `decisions.log` and `ralph-loop.log` are local runtime artifacts and are ignored

## License

MIT. See [`LICENSE`](./LICENSE).
