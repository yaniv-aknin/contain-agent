import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLI_CMD = [sys.executable, "-c", "from contain_agent import app; app()"]


@pytest.fixture(scope="session")
def fake_docker(tmp_path_factory):
    docker_bin = tmp_path_factory.mktemp("bin") / "docker"
    docker_bin.write_text(f"""#!{sys.executable}
import json, os, sys

log_file = os.environ.get("FAKE_DOCKER_LOG")
args = sys.argv[1:]
if log_file:
    with open(log_file, "a") as f:
        f.write(json.dumps(args) + "\\n")

if any("missing" in a for a in args) and "inspect" in args:
    sys.exit(1)

if any("fail_build" in a for a in args) and "build" in args:
    sys.exit(2)

if any("fail_42" in a for a in args):
    sys.exit(42)

sys.exit(0)
""")
    docker_bin.chmod(0o755)
    return docker_bin


@pytest.fixture
def run_cli(fake_docker, tmp_path):
    def _run(*args, home=None, cwd=None, fake_docker=None):
        log_file = tmp_path / "docker_calls.log"
        env = {
            **os.environ,
            "HOME": str(home or tmp_path / "home"),
            "CONTAIN_AGENT_DOCKER_CMD": str(
                fake_docker if fake_docker is not None else fake_docker_fixture
            ),
            "FAKE_DOCKER_LOG": str(log_file),
        }
        Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
        res = subprocess.run(
            [*CLI_CMD, *args],
            env=env,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
        calls = []
        if log_file.exists():
            for line in log_file.read_text().splitlines():
                if line.strip():
                    calls.append(json.loads(line))
        return res, calls

    fake_docker_fixture = fake_docker
    return _run


def test_default_invocation(run_cli, tmp_path):
    ws = tmp_path / "my_project"
    ws.mkdir()
    res, calls = run_cli(cwd=ws)
    assert res.returncode == 0
    assert len(calls) == 2  # image inspect + run
    assert calls[0] == ["image", "inspect", "contain-agent"]
    run_args = calls[1]
    assert run_args[0] == "run"
    assert "--rm" in run_args
    assert f"{ws.resolve()}:/workspace/my_project" in run_args
    assert "/workspace/my_project" in run_args
    assert run_args[-3:] == ["bash", "-l", "-i"]


def test_mount_dir_and_command(run_cli, tmp_path):
    ws = tmp_path / "proj"
    ws.mkdir()
    res, calls = run_cli(str(ws), "cat", "bar.txt")
    assert res.returncode == 0
    run_args = calls[-1]
    assert f"{ws.resolve()}:/workspace/proj" in run_args
    assert run_args[-5:] == ["bash", "-l", "-i", "-c", "cat bar.txt"]


def test_command_flags_passed_intact(run_cli, tmp_path):
    ws = tmp_path / "repo"
    ws.mkdir()
    res, calls = run_cli(".", "ls", "-la", "--color=auto", cwd=ws)
    assert res.returncode == 0
    run_args = calls[-1]
    assert run_args[-5:] == [
        "bash",
        "-l",
        "-i",
        "-c",
        "ls -la --color=auto",
    ]


def test_no_mount(run_cli):
    res, calls = run_cli("--no-mount", "ls", "-la")
    assert res.returncode == 0
    run_args = calls[-1]
    assert "/workspace" in run_args
    assert run_args[-5:] == ["bash", "-l", "-i", "-c", "ls -la"]


def test_share_config(run_cli, tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".gemini").mkdir()
    ws = tmp_path / "ws"
    ws.mkdir()

    res, calls = run_cli(str(ws), home=home)
    assert res.returncode == 0
    run_args = calls[-1]
    assert f"{(home / '.claude').resolve()}:/home/agent/.claude" in run_args
    assert f"{(home / '.gemini').resolve()}:/home/agent/.gemini" in run_args


def test_no_share_config_dotfiles(run_cli, tmp_path):
    home = tmp_path / "home"
    (home / ".gemini").mkdir(parents=True)
    dotfiles = home / ".contain-agent" / "dotfiles"
    dotfiles.mkdir(parents=True)
    (dotfiles / ".claude").mkdir()
    ws = tmp_path / "ws"
    ws.mkdir()

    res, calls = run_cli("--no-share-config", str(ws), home=home)
    assert res.returncode == 0
    run_args = calls[-1]
    assert f"{(dotfiles / '.claude').resolve()}:/home/agent/.claude" in run_args
    assert f"{(home / '.gemini').resolve()}:/home/agent/.gemini" not in run_args


def test_custom_dotfiles_dir(run_cli, tmp_path):
    custom = tmp_path / "custom_dotfiles"
    custom.mkdir()
    (custom / ".custom_auth").touch()
    ws = tmp_path / "ws"
    ws.mkdir()

    res, calls = run_cli("--no-share-config", f"--dotfiles-dir={custom}", str(ws))
    assert res.returncode == 0
    run_args = calls[-1]
    assert f"{(custom / '.custom_auth').resolve()}:/home/agent/.custom_auth" in run_args


def test_env_file_auto_discovery(run_cli, tmp_path):
    home = tmp_path / "home"
    env_dir = home / ".contain-agent"
    env_dir.mkdir(parents=True)
    env_file = env_dir / ".env"
    env_file.write_text("FOO=BAR\n")
    ws = tmp_path / "ws"
    ws.mkdir()

    res, calls = run_cli(str(ws), home=home)
    assert res.returncode == 0
    run_args = calls[-1]
    assert "--env-file" in run_args
    assert str(env_file.resolve()) in run_args


def test_no_env_file_flag(run_cli, tmp_path):
    home = tmp_path / "home"
    env_dir = home / ".contain-agent"
    env_dir.mkdir(parents=True)
    (env_dir / ".env").write_text("FOO=BAR\n")
    ws = tmp_path / "ws"
    ws.mkdir()

    res, calls = run_cli("--no-env-file", str(ws), home=home)
    assert res.returncode == 0
    run_args = calls[-1]
    assert "--env-file" not in run_args


def test_network_flag(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, calls = run_cli("--network", "my_bridge", str(ws))
    assert res.returncode == 0
    run_args = calls[-1]
    assert "--network" in run_args
    assert "my_bridge" in run_args


def test_custom_image_and_no_rm(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, calls = run_cli("--image", "custom:v1", "--no-rm", str(ws))
    assert res.returncode == 0
    run_args = calls[-1]
    assert "custom:v1" in run_args
    assert "--rm" not in run_args


def test_build_image_flag(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, calls = run_cli("--build-image", str(ws))
    assert res.returncode == 0
    assert len(calls) == 3  # inspect + build + run
    build_args = calls[1]
    assert build_args[0] == "build"
    assert "-t" in build_args
    assert "contain-agent" in build_args
    assert "-f" in build_args
    assert "Dockerfile" in build_args[build_args.index("-f") + 1]
    assert "--no-cache" not in build_args
    assert "--build-arg" in build_args
    assert f"UID={os.getuid()}" in build_args


def test_fresh_rebuild_image_flag(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, calls = run_cli("--fresh-rebuild-image", str(ws))
    assert res.returncode == 0
    assert len(calls) == 3  # inspect + build + run
    build_args = calls[1]
    assert "--build-arg" in build_args
    assert f"UID={os.getuid()}" in build_args
    assert any(a.startswith("CACHE_BUST=") for a in build_args)


def test_no_cache_rebuild_image_flag(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, calls = run_cli("--no-cache-rebuild-image", str(ws))
    assert res.returncode == 0
    assert len(calls) == 3  # inspect + build + run
    build_args = calls[1]
    assert "--no-cache" in build_args
    assert f"UID={os.getuid()}" in build_args


def test_auto_build_when_image_missing(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, calls = run_cli("--image", "missing-image", str(ws))
    assert res.returncode == 0
    assert len(calls) == 3  # inspect (failed) + build + run
    assert calls[0] == ["image", "inspect", "missing-image"]
    assert calls[1][0] == "build"
    assert "missing-image" in calls[1]
    assert calls[2][0] == "run"
    assert "missing-image" in calls[2]
    assert (
        "Docker image 'missing-image' not found locally. Building it..." in res.stderr
    )


def test_auto_build_failure_propagation(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, calls = run_cli("--image", "missing-image-fail_build", str(ws))
    assert res.returncode == 2
    assert len(calls) == 2  # inspect + build (failed)


def test_sensitive_directory_refusal_and_force(run_cli):
    res, calls = run_cli("/tmp")
    assert res.returncode == 1
    assert len(calls) == 0
    assert "Cowardly refusing to mount sensitive directory" in res.stderr

    res_force, calls_force = run_cli("--force", "/tmp")
    assert res_force.returncode == 0
    run_args = calls_force[-1]
    assert "/workspace/tmp" in run_args


def test_nonexistent_workspace_directory(run_cli):
    res, calls = run_cli("/nonexistent/folder/12345")
    assert res.returncode == 1
    assert len(calls) == 0
    assert "does not exist" in res.stderr


def test_exit_code_propagation(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, calls = run_cli(str(ws), "fail_42")
    assert res.returncode == 42
    assert len(calls) == 2


def test_docker_missing_error(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    nonexistent_docker = tmp_path / "missing_docker_executable"
    res, calls = run_cli(str(ws), fake_docker=nonexistent_docker)
    assert res.returncode == 1
    assert len(calls) == 0
    assert "Error: 'docker' command not found." in res.stderr
    assert "Please ensure Docker is installed and in your PATH." in res.stderr


def test_build_image_command_uid():
    from contain_agent import build_image_command

    cmd_default = build_image_command("test-image")
    assert "--build-arg" in cmd_default
    idx = cmd_default.index("--build-arg")
    assert cmd_default[idx + 1] == f"UID={os.getuid()}"

    cmd_custom = build_image_command("test-image", uid=1234)
    assert "--build-arg" in cmd_custom
    idx = cmd_custom.index("--build-arg")
    assert cmd_custom[idx + 1] == "UID=1234"


def test_load_valid_settings(tmp_path):
    from contain_agent import load_settings

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "default_command": "claude",
                "default_args": ["--verbose", "--model", "opus"],
            }
        )
    )
    s = load_settings(settings_file)
    assert s.default_command == "claude"
    assert s.default_args == ["--verbose", "--model", "opus"]


def test_load_invalid_settings(tmp_path):
    from contain_agent import Settings, load_settings

    # Corrupt JSON syntax
    p1 = tmp_path / "corrupt.json"
    p1.write_text("{not valid json")
    assert load_settings(p1) == Settings()

    # Schema mismatch
    p2 = tmp_path / "schema_mismatch.json"
    p2.write_text(json.dumps({"default_args": "not-a-list"}))
    assert load_settings(p2) == Settings()


def test_default_command_changes_command_line(run_cli, tmp_path):
    home = tmp_path / "home"
    agent_dir = home / ".contain-agent"
    agent_dir.mkdir(parents=True)
    settings_file = agent_dir / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "default_command": "claude",
                "default_args": ["--verbose"],
            }
        )
    )
    ws = tmp_path / "ws"
    ws.mkdir()

    res, calls = run_cli(str(ws), home=home)
    assert res.returncode == 0
    run_args = calls[-1]
    assert run_args[-5:] == ["bash", "-l", "-i", "-c", "claude --verbose"]
