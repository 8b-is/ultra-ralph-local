from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import signal
import sys
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence

from huggingface_hub import HfApi
from platformdirs import user_config_path

DEFAULT_HF_REPO = "PeetPedro/ultrawhale-dogfood"
DEFAULT_HF_PATH = "ralph/decisions.log"
DEFAULT_DEPTH = 4
DEFAULT_MEMBERS = 4
DEFAULT_INTERVAL = 1_980
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LOG_NAME = "decisions.log"
LOOP_LOG_NAME = "ralph-loop.log"
CONFIG_DIR = user_config_path("ultra-ralph-local", "8b-is")
CONFIG_PATH = CONFIG_DIR / "config.json"
SYSTEM_PROMPT = textwrap.dedent(
    """\
    You are ralph, a minimal decision-loop agent.
    Reply with exactly one line, choosing one of these four exact forms:
        Action: list
        Action: read|workspace.txt
        Action: append|Decision: <your one-sentence decision>
        Action: finish|Done
    Do not invent filenames. Use read|workspace.txt to see the state. Then append
    one decision, then finish.
    """
)


@dataclass
class Config:
    openrouter_api_key: str | None = None
    hf_token: str | None = None
    hf_repo: str = DEFAULT_HF_REPO
    hf_path: str = DEFAULT_HF_PATH
    upload_enabled: bool = True


@dataclass
class RunConfig:
    workspace: Path
    openrouter_api_key: str
    hf_token: str | None
    hf_repo: str
    hf_path: str
    upload_enabled: bool
    depth: int
    members: int
    prompt: str | None


class GracefulStop:
    def __init__(self) -> None:
        self.stop_requested = False

    def handler(self, signum: int, _frame: object) -> None:
        self.stop_requested = True
        signal_name = signal.Signals(signum).name
        print(f"\n[{utc_now()}] stop requested via {signal_name}; finishing current run then exiting cleanly.")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def next_run_at(interval_seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_logger(log_path: Path | None) -> Callable[[str], None]:
    def log(message: str) -> None:
        line = f"[{utc_now()}] {message}"
        print(line)
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    return log


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        return Config()
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return Config(
        openrouter_api_key=data.get("openrouter_api_key") or None,
        hf_token=data.get("hf_token") or None,
        hf_repo=data.get("hf_repo") or DEFAULT_HF_REPO,
        hf_path=data.get("hf_path") or DEFAULT_HF_PATH,
        upload_enabled=bool(data.get("upload_enabled", True)),
    )


def save_config(config: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(
            {
                "openrouter_api_key": config.openrouter_api_key,
                "hf_token": config.hf_token,
                "hf_repo": config.hf_repo,
                "hf_path": config.hf_path,
                "upload_enabled": config.upload_enabled,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(CONFIG_PATH, 0o600)


def prompt_value(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    return default or ""


def prompt_secret_value(label: str, default: str | None = None, *, required: bool) -> str:
    suffix = " [saved]" if default else ""
    while True:
        value = getpass.getpass(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        if not required:
            return ""
        print("This value is required.")


def run_setup(existing: Config | None = None) -> Config:
    config = existing or load_config()
    print(f"Writing config to {CONFIG_PATH}")
    openrouter_api_key = prompt_secret_value(
        "OpenRouter API key",
        config.openrouter_api_key,
        required=True,
    )
    hf_token = prompt_secret_value(
        "Hugging Face token (leave blank to skip uploads unless HF_TOKEN is set)",
        config.hf_token,
        required=False,
    )
    hf_repo = prompt_value("Hugging Face dataset repo", config.hf_repo or DEFAULT_HF_REPO)
    hf_path = prompt_value("Dataset path", config.hf_path or DEFAULT_HF_PATH)
    upload_default = "yes" if config.upload_enabled else "no"
    upload_enabled = prompt_value("Enable uploads by default? (yes/no)", upload_default).lower() not in {"n", "no", "0", "false"}
    updated = Config(
        openrouter_api_key=openrouter_api_key,
        hf_token=hf_token or None,
        hf_repo=hf_repo,
        hf_path=hf_path,
        upload_enabled=upload_enabled,
    )
    save_config(updated)
    print("Saved config.")
    return updated


def resolve_config(args: argparse.Namespace) -> RunConfig:
    saved = load_config()
    workspace = Path(
        args.workspace
        or os.getenv("RALPH_DIR")
        or os.getenv("ULTRA_RALPH_WORKSPACE")
        or os.getcwd()
    ).expanduser().resolve()

    openrouter_api_key = (
        args.openrouter_api_key
        or os.getenv("OPENROUTER_API_KEY")
        or saved.openrouter_api_key
    )

    cli_hf_token = args.hf_token
    env_hf_token = os.getenv("HF_TOKEN")
    cli_hf_repo = args.hf_repo
    env_hf_repo = os.getenv("RALPH_HF_REPO")
    cli_hf_path = args.hf_path
    env_hf_path = os.getenv("RALPH_HF_PATH")

    hf_token = cli_hf_token or env_hf_token or saved.hf_token
    hf_repo = cli_hf_repo or env_hf_repo or saved.hf_repo or DEFAULT_HF_REPO
    hf_path = cli_hf_path or env_hf_path or saved.hf_path or DEFAULT_HF_PATH

    upload_enabled = saved.upload_enabled
    env_upload = os.getenv("RALPH_UPLOAD")
    if env_upload is not None:
        upload_enabled = env_upload.lower() not in {"0", "false", "no"}
    if getattr(args, "upload", None) is True:
        upload_enabled = True
    if getattr(args, "upload", None) is False:
        upload_enabled = False

    if not openrouter_api_key:
        if sys.stdin.isatty() and sys.stdout.isatty():
            print("No OpenRouter key found. Starting first-run setup.")
            saved = run_setup(saved)
            openrouter_api_key = saved.openrouter_api_key
            if cli_hf_token is None and env_hf_token is None:
                hf_token = saved.hf_token
            if cli_hf_repo is None and env_hf_repo is None:
                hf_repo = saved.hf_repo or DEFAULT_HF_REPO
            if cli_hf_path is None and env_hf_path is None:
                hf_path = saved.hf_path or DEFAULT_HF_PATH
            if env_upload is None and getattr(args, "upload", None) is None:
                upload_enabled = saved.upload_enabled
        else:
            raise SystemExit("Missing OpenRouter key. Run `ultra-ralph-local setup` or set OPENROUTER_API_KEY.")

    return RunConfig(
        workspace=workspace,
        openrouter_api_key=openrouter_api_key,
        hf_token=hf_token,
        hf_repo=hf_repo,
        hf_path=hf_path,
        upload_enabled=upload_enabled,
        depth=args.depth,
        members=args.members,
        prompt=args.prompt,
    )


def list_files(dir_path: Path) -> str:
    try:
        entries = sorted(dir_path.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.lower()))
    except OSError as exc:
        return f"error: {exc}"
    lines = [f"{entry.name}/" if entry.is_dir() else entry.name for entry in entries]
    return "\n".join(lines)


def read_file(dir_path: Path, relative_path: str) -> str:
    candidate = (dir_path / relative_path).resolve()
    try:
        candidate.relative_to(dir_path.resolve())
    except ValueError:
        return "error: path escapes workspace"
    try:
        data = candidate.read_text(encoding="utf-8")
    except OSError as exc:
        return f"error: {exc}"
    if len(data) > 8_000:
        data = data[:8_000]
    return data


def append_log(dir_path: Path, text: str) -> str:
    log_path = dir_path / LOG_NAME
    prev_hash = ""
    if log_path.exists():
        lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if lines:
            prev_hash = lines[-1].split("|", 1)[0]
    now = datetime.now(timezone.utc)
    payload = f"{prev_hash}\n{text}\n{now.isoformat()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    line = f"{digest}|{now.strftime('%Y-%m-%dT%H:%M:%SZ')}|{text.strip()}"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return f"appended: {line}"


def tokenize(text: str) -> dict[str, int]:
    tokens: dict[str, int] = {}
    current: list[str] = []
    for char in text.lower():
        if char.isalnum() or char == "_":
            current.append(char)
            continue
        if len(current) > 1:
            token = "".join(current)
            tokens[token] = tokens.get(token, 0) + 1
        current = []
    if len(current) > 1:
        token = "".join(current)
        tokens[token] = tokens.get(token, 0) + 1
    return tokens


def jaccard(left: dict[str, int], right: dict[str, int]) -> float:
    if not left and not right:
        return 1.0
    keys = set(left) | set(right)
    intersection = sum(min(left.get(key, 0), right.get(key, 0)) for key in keys)
    union = sum(max(left.get(key, 0), right.get(key, 0)) for key in keys)
    return 0.0 if union == 0 else intersection / union


def is_duplicate(dir_path: Path, text: str) -> bool:
    log_path = dir_path / LOG_NAME
    if not log_path.exists():
        return False
    probe = tokenize(text.removeprefix("Decision:"))
    if not probe:
        return False
    for line in log_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        if jaccard(probe, tokenize(parts[2])) >= 0.6:
            return True
    return False


def dyad_context(repo_dir: Path) -> str:
    pieces: list[str] = []
    for name in ("README.md", "essences.md"):
        path = repo_dir / name
        if path.exists():
            pieces.append(path.read_text(encoding="utf-8"))
    summaries = sorted(repo_dir.glob("session-*-summary.md"))
    if summaries:
        latest = summaries[-1]
        pieces.append(f"latest session ({latest.name}):\n{latest.read_text(encoding='utf-8')}")
    joined = "\n---\n".join(piece for piece in pieces if piece.strip())
    if not joined:
        raise FileNotFoundError(repo_dir)
    if len(joined) > 2_500:
        joined = joined[:2_500] + "…"
    return joined


def default_prompt(workspace: Path) -> str:
    snapshot = [f"Workspace state:\n{list_files(workspace)}"]

    workspace_txt = workspace / "workspace.txt"
    if workspace_txt.exists():
        snapshot.append(f"workspace.txt:\n{workspace_txt.read_text(encoding='utf-8')}")

    dyad_dir = workspace / "dyad-mapping"
    if dyad_dir.exists():
        try:
            snapshot.append(f"dyad-mapping context (our working sessions):\n{dyad_context(dyad_dir)}")
        except OSError:
            pass

    log_path = workspace / LOG_NAME
    if log_path.exists():
        lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        tail = lines[-3:]
        snapshot.append(f"decisions.log (last {len(tail)}):\n" + "\n".join(tail))
    else:
        snapshot.append("decisions.log: (empty)")

    return (
        "Here is the current workspace state and our dyad-mapping session context. "
        "Decide the single most important next step for the quantal/guardrail work, "
        "grounded in this context, append it as a decision, then finish.\n\n"
        + "\n\n".join(snapshot)
    )


def clean_out(text: str) -> str:
    marker = "<end_of_turn>"
    if marker in text:
        text = text.split(marker, 1)[0]
    return text.strip()


def extract_decision(reply: str) -> str:
    for line in reply.splitlines():
        trimmed = line.strip()
        if not trimmed.startswith("Action:"):
            continue
        rest = trimmed.removeprefix("Action:").strip()
        if rest.startswith("append|"):
            return rest.removeprefix("append|").strip()
    return reply.strip()


def majority_decision(replies: Sequence[str]) -> str:
    counts: dict[str, int] = {}
    ordered: list[str] = []
    original: dict[str, str] = {}
    for reply in replies:
        decision = extract_decision(reply)
        normalized = decision.strip().lower()
        if not normalized or normalized.startswith("error"):
            continue
        if normalized not in counts:
            counts[normalized] = 0
            ordered.append(normalized)
            original[normalized] = decision.strip()
        counts[normalized] += 1
    best = ""
    best_count = 0
    for normalized in ordered:
        if counts[normalized] > best_count:
            best = normalized
            best_count = counts[normalized]
    if best:
        return original[best]
    for reply in replies:
        decision = extract_decision(reply)
        if not decision.lower().startswith("error"):
            return decision
    return "no decision (model returned errors)"


def chat(messages: list[dict[str, str]], api_key: str, temperature: float) -> str:
    payload = json.dumps(
        {
            "model": DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2_000,
        }
    ).encode("utf-8")
    request = urllib.request.Request(OPENROUTER_URL, data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2_000]
        raise RuntimeError(f"llm http {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"llm request failed: {exc.reason}") from exc

    decoded = json.loads(body)
    choices = decoded.get("choices") or []
    if not choices:
        raise RuntimeError("llm: empty choices")
    content = choices[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("llm: empty message content")
    return str(content)


def ralph_council(run_config: RunConfig, prompt: str, depth: int, logger: Callable[[str], None]) -> str:
    temperatures = [0.2 + 0.3 * index for index in range(run_config.members)]
    replies: list[str] = []
    for temperature in temperatures:
        try:
            raw = chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                run_config.openrouter_api_key,
                temperature,
            )
            replies.append(clean_out(raw))
        except RuntimeError as exc:
            replies.append(f"ERROR: {exc}")
    winner = majority_decision(replies)
    logger(f"depth {depth + 1}/{run_config.depth} · {run_config.members} ralphs → winner: {truncate(winner, 160)}")
    if depth + 1 < run_config.depth:
        next_prompt = (
            f"A previous ralph decided: {winner}\n\n"
            "Refine or confirm this decision. Reply with exactly one line: "
            "Action: append|Decision: <final one-sentence decision>"
        )
        return ralph_council(run_config, next_prompt, depth + 1, logger)
    return winner


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def upload_log(run_config: RunConfig, logger: Callable[[str], None]) -> None:
    if not run_config.upload_enabled:
        logger("upload skipped: disabled")
        return
    if not run_config.hf_token:
        logger("upload skipped: no Hugging Face token configured")
        return
    log_path = run_config.workspace / LOG_NAME
    if not log_path.exists():
        logger(f"upload skipped: missing {log_path}")
        return
    try:
        api = HfApi(token=run_config.hf_token)
        api.upload_file(
            path_or_fileobj=str(log_path),
            path_in_repo=run_config.hf_path,
            repo_id=run_config.hf_repo,
            repo_type="dataset",
        )
        logger(f"uploaded {LOG_NAME} → {run_config.hf_repo}/{run_config.hf_path}")
    except Exception as exc:  # pragma: no cover - network/auth edge cases
        logger(f"upload failed: {exc}")


def run_once(run_config: RunConfig, logger: Callable[[str], None]) -> int:
    run_config.workspace.mkdir(parents=True, exist_ok=True)
    prompt = run_config.prompt or default_prompt(run_config.workspace)
    logger(
        f"ultra-ralph-local | model {DEFAULT_MODEL} | depth {run_config.depth} × {run_config.members} ralphs | dir {run_config.workspace}"
    )
    winner = ralph_council(run_config, prompt, 0, logger)
    if not is_duplicate(run_config.workspace, winner):
        result = append_log(run_config.workspace, winner)
        logger(truncate(result, 220))
    else:
        logger("decision already in log; keeping existing entries")
    upload_log(run_config, logger)
    logger("done")
    return 0


def run_loop(run_config: RunConfig, interval_seconds: int) -> int:
    stop = GracefulStop()
    previous_handlers = {
        sig: signal.getsignal(sig)
        for sig in (signal.SIGINT, signal.SIGTERM)
    }
    for sig in previous_handlers:
        signal.signal(sig, stop.handler)

    logger = make_logger(run_config.workspace / LOOP_LOG_NAME)
    logger(
        f"loop started | model: {DEFAULT_MODEL} | depth {run_config.depth} × {run_config.members} ralphs | interval: {interval_seconds}s"
    )
    logger(f"uploads default to {run_config.hf_repo}/{run_config.hf_path}")
    run_number = 0
    try:
        while not stop.stop_requested:
            run_number += 1
            started = time.time()
            logger(f"run #{run_number} starting")
            exit_code = run_once(run_config, logger)
            duration = int(time.time() - started)
            if exit_code == 0:
                logger(f"run #{run_number} finished in {duration}s")
            else:
                logger(f"run #{run_number} exited with code {exit_code} after {duration}s")
            if stop.stop_requested:
                break
            logger(f"sleeping {interval_seconds}s; next run at {next_run_at(interval_seconds)}; CTRL-C to stop")
            end_sleep = time.time() + interval_seconds
            while time.time() < end_sleep and not stop.stop_requested:
                time.sleep(min(1, end_sleep - time.time()))
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
    logger(f"loop stopped cleanly after {run_number} run(s)")
    return 0


def add_shared_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", help="Workspace directory. Defaults to the current directory.")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help=f"Recursive council depth. Default: {DEFAULT_DEPTH}.")
    parser.add_argument("--members", type=int, default=DEFAULT_MEMBERS, help=f"Ralphs per depth. Default: {DEFAULT_MEMBERS}.")
    parser.add_argument("--prompt", help="Override the default prompt.")
    parser.add_argument("--openrouter-api-key", help="Override OPENROUTER_API_KEY.")
    parser.add_argument("--hf-token", help="Override HF_TOKEN.")
    parser.add_argument("--hf-repo", help=f"Override the default dataset repo ({DEFAULT_HF_REPO}).")
    parser.add_argument("--hf-path", help=f"Override the default dataset path ({DEFAULT_HF_PATH}).")
    upload_group = parser.add_mutually_exclusive_group()
    upload_group.add_argument("--upload", dest="upload", action="store_true", default=None, help="Force uploads on for this run.")
    upload_group.add_argument("--no-upload", dest="upload", action="store_false", default=None, help="Disable uploads for this run.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ultra-ralph-local")
    subparsers = parser.add_subparsers(dest="command")

    setup_parser = subparsers.add_parser("setup", help="Interactively store your OpenRouter and optional Hugging Face settings.")
    setup_parser.set_defaults(handler=handle_setup)

    run_parser = subparsers.add_parser("run", help="Run one Ralph council iteration.")
    add_shared_run_args(run_parser)
    run_parser.set_defaults(handler=handle_run)

    loop_parser = subparsers.add_parser("loop", help="Run the Ralph council on an interval until stopped.")
    add_shared_run_args(loop_parser)
    loop_parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help=f"Seconds between runs. Default: {DEFAULT_INTERVAL}.")
    loop_parser.set_defaults(handler=handle_loop)

    return parser


def handle_setup(args: argparse.Namespace) -> int:
    run_setup(load_config())
    return 0


def validate_args(args: argparse.Namespace) -> None:
    if getattr(args, "depth", DEFAULT_DEPTH) < 1:
        raise SystemExit("--depth must be >= 1")
    if getattr(args, "members", DEFAULT_MEMBERS) < 1:
        raise SystemExit("--members must be >= 1")
    if getattr(args, "interval", DEFAULT_INTERVAL) < 1:
        raise SystemExit("--interval must be >= 1")


def handle_run(args: argparse.Namespace) -> int:
    validate_args(args)
    return run_once(resolve_config(args), make_logger(None))


def handle_loop(args: argparse.Namespace) -> int:
    validate_args(args)
    return run_loop(resolve_config(args), args.interval)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    argv = list(argv or sys.argv[1:])
    if not argv:
        argv = ["run"]
    elif argv[0] not in {"setup", "run", "loop", "-h", "--help"}:
        argv.insert(0, "run")
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
