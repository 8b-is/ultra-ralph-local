from __future__ import annotations

import json
from pathlib import Path

import ultra_ralph_local.cli as cli


class Args:
    def __init__(self, **kwargs):
        self.workspace = kwargs.get("workspace")
        self.depth = kwargs.get("depth", cli.DEFAULT_DEPTH)
        self.members = kwargs.get("members", cli.DEFAULT_MEMBERS)
        self.prompt = kwargs.get("prompt")
        self.openrouter_api_key = kwargs.get("openrouter_api_key")
        self.hf_token = kwargs.get("hf_token")
        self.hf_repo = kwargs.get("hf_repo")
        self.hf_path = kwargs.get("hf_path")
        self.upload = kwargs.get("upload")


def test_append_log_hash_chain(tmp_path: Path) -> None:
    workspace = tmp_path
    first = cli.append_log(workspace, "Decision: first")
    second = cli.append_log(workspace, "Decision: second")

    lines = (workspace / cli.LOG_NAME).read_text(encoding="utf-8").splitlines()

    assert first.startswith("appended: ")
    assert second.startswith("appended: ")
    assert len(lines) == 2
    assert len(lines[0].split("|", 2)[0]) == 64
    assert len(lines[1].split("|", 2)[0]) == 64
    assert lines[0] != lines[1]


def test_duplicate_detection_uses_token_similarity(tmp_path: Path) -> None:
    workspace = tmp_path
    cli.append_log(workspace, "Decision: add the final note to workspace.txt")

    assert cli.is_duplicate(workspace, "Decision: add final note to workspace.txt") is True
    assert cli.is_duplicate(workspace, "Decision: rotate the OpenRouter key") is False


def test_resolve_config_prefers_cli_over_env_over_saved_config(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_path = config_dir / "config.json"
    config_dir.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "openrouter_api_key": "saved-openrouter",
                "hf_token": "saved-hf",
                "hf_repo": "saved/repo",
                "hf_path": "saved/path.log",
                "upload_enabled": True,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cli, "CONFIG_PATH", config_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-openrouter")
    monkeypatch.setenv("HF_TOKEN", "env-hf")
    monkeypatch.setenv("RALPH_HF_REPO", "env/repo")
    monkeypatch.setenv("RALPH_HF_PATH", "env/path.log")
    monkeypatch.setenv("RALPH_UPLOAD", "false")

    resolved = cli.resolve_config(
        Args(
            workspace=str(tmp_path / "workspace"),
            openrouter_api_key="cli-openrouter",
            hf_token="cli-hf",
            hf_repo="cli/repo",
            hf_path="cli/path.log",
            upload=True,
        )
    )

    assert resolved.openrouter_api_key == "cli-openrouter"
    assert resolved.hf_token == "cli-hf"
    assert resolved.hf_repo == "cli/repo"
    assert resolved.hf_path == "cli/path.log"
    assert resolved.upload_enabled is True


def test_resolve_config_uses_default_hf_target(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_path = config_dir / "config.json"
    monkeypatch.setattr(cli, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cli, "CONFIG_PATH", config_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-openrouter")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("RALPH_HF_REPO", raising=False)
    monkeypatch.delenv("RALPH_HF_PATH", raising=False)
    monkeypatch.delenv("RALPH_UPLOAD", raising=False)

    resolved = cli.resolve_config(Args(workspace=str(tmp_path / "workspace")))

    assert resolved.hf_repo == cli.DEFAULT_HF_REPO
    assert resolved.hf_path == cli.DEFAULT_HF_PATH
    assert resolved.upload_enabled is True


def test_first_run_setup_uses_custom_hf_destination(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_path = config_dir / "config.json"
    monkeypatch.setattr(cli, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cli, "CONFIG_PATH", config_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("RALPH_HF_REPO", raising=False)
    monkeypatch.delenv("RALPH_HF_PATH", raising=False)
    monkeypatch.delenv("RALPH_UPLOAD", raising=False)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)

    monkeypatch.setattr(
        cli,
        "run_setup",
        lambda existing: cli.Config(
            openrouter_api_key="setup-openrouter",
            hf_token="setup-hf",
            hf_repo="custom/repo",
            hf_path="custom/path.log",
            upload_enabled=False,
        ),
    )

    resolved = cli.resolve_config(Args(workspace=str(tmp_path / "workspace")))

    assert resolved.openrouter_api_key == "setup-openrouter"
    assert resolved.hf_token == "setup-hf"
    assert resolved.hf_repo == "custom/repo"
    assert resolved.hf_path == "custom/path.log"
    assert resolved.upload_enabled is False


def test_prompt_secret_value_does_not_echo_saved_secret(monkeypatch) -> None:
    prompts = []

    def fake_getpass(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr(cli.getpass, "getpass", fake_getpass)

    value = cli.prompt_secret_value("OpenRouter API key", "sk-secret", required=True)

    assert value == "sk-secret"
    assert prompts == ["OpenRouter API key [saved]: "]
    assert "sk-secret" not in prompts[0]


def test_upload_log_uses_dataset_defaults(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path
    cli.append_log(workspace, "Decision: ship the public repo")
    calls = {}

    class FakeApi:
        def __init__(self, token: str | None = None):
            calls["token"] = token

        def upload_file(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr(cli, "HfApi", FakeApi)

    run_config = cli.RunConfig(
        workspace=workspace,
        openrouter_api_key="sk-test",
        hf_token="hf-test",
        hf_repo=cli.DEFAULT_HF_REPO,
        hf_path=cli.DEFAULT_HF_PATH,
        upload_enabled=True,
        depth=cli.DEFAULT_DEPTH,
        members=cli.DEFAULT_MEMBERS,
        prompt=None,
    )
    cli.upload_log(run_config, lambda _message: None)

    assert calls["token"] == "hf-test"
    assert calls["repo_id"] == cli.DEFAULT_HF_REPO
    assert calls["path_in_repo"] == cli.DEFAULT_HF_PATH
    assert calls["repo_type"] == "dataset"
