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
import json, sys

args = sys.argv[1:]
if not args:
    sys.exit(0)

if args[0] == "image" and len(args) >= 2 and args[1] == "inspect":
    sys.exit(1 if "nonexistent" in args[2] else 0)

if args[0] == "run":
    print("DOCKER_ARGS:" + json.dumps(args[1:]))
    sys.exit(42 if "fail_42" in args else 0)

sys.exit(0)
""")
    docker_bin.chmod(0o755)
    return docker_bin


@pytest.fixture
def run_cli(fake_docker, tmp_path):
    def _run(*args, home=None, cwd=None, fake_docker=None):
        env = {
            **os.environ,
            "HOME": str(home or tmp_path / "home"),
            "CONTAIN_AGENT_DOCKER_CMD": str(
                fake_docker if fake_docker is not None else fake_docker_fixture
            ),
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
        docker_args = []
        for line in res.stdout.splitlines():
            if line.startswith("DOCKER_ARGS:"):
                docker_args = json.loads(line[len("DOCKER_ARGS:") :])
                break
        return res, docker_args

    fake_docker_fixture = fake_docker
    return _run


def test_default_invocation(run_cli, tmp_path):
    ws = tmp_path / "my_project"
    ws.mkdir()
    res, args = run_cli(cwd=ws)
    assert res.returncode == 0
    assert "--rm" in args
    assert f"{ws.resolve()}:/workspace/my_project" in args
    assert "/workspace/my_project" in args
    assert args[-3:] == ["bash", "-l", "-i"]


def test_mount_dir_and_command(run_cli, tmp_path):
    ws = tmp_path / "proj"
    ws.mkdir()
    res, args = run_cli(str(ws), "cat", "bar.txt")
    assert res.returncode == 0
    assert f"{ws.resolve()}:/workspace/proj" in args
    assert args[-5:] == ["bash", "-l", "-i", "-c", "cat bar.txt"]


def test_command_flags_passed_intact(run_cli, tmp_path):
    ws = tmp_path / "repo"
    ws.mkdir()
    res, args = run_cli(".", "ls", "-la", "--color=auto", cwd=ws)
    assert res.returncode == 0
    assert args[-5:] == [
        "bash",
        "-l",
        "-i",
        "-c",
        "ls -la --color=auto",
    ]


def test_no_mount(run_cli):
    res, args = run_cli("--no-mount", "ls", "-la")
    assert res.returncode == 0
    assert "/workspace" in args
    assert args[-5:] == ["bash", "-l", "-i", "-c", "ls -la"]


def test_share_config(run_cli, tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".gemini").mkdir()
    ws = tmp_path / "ws"
    ws.mkdir()

    res, args = run_cli(str(ws), home=home)
    assert res.returncode == 0
    assert f"{(home / '.claude').resolve()}:/home/agent/.claude" in args
    assert f"{(home / '.gemini').resolve()}:/home/agent/.gemini" in args


def test_no_share_config_dotfiles(run_cli, tmp_path):
    home = tmp_path / "home"
    (home / ".gemini").mkdir(parents=True)
    dotfiles = home / ".contain-agent" / "dotfiles"
    dotfiles.mkdir(parents=True)
    (dotfiles / ".claude").mkdir()
    ws = tmp_path / "ws"
    ws.mkdir()

    res, args = run_cli("--no-share-config", str(ws), home=home)
    assert res.returncode == 0
    assert f"{(dotfiles / '.claude').resolve()}:/home/agent/.claude" in args
    assert f"{(home / '.gemini').resolve()}:/home/agent/.gemini" not in args


def test_custom_dotfiles_dir(run_cli, tmp_path):
    custom = tmp_path / "custom_dotfiles"
    custom.mkdir()
    (custom / ".custom_auth").touch()
    ws = tmp_path / "ws"
    ws.mkdir()

    res, args = run_cli("--no-share-config", f"--dotfiles-dir={custom}", str(ws))
    assert res.returncode == 0
    assert f"{(custom / '.custom_auth').resolve()}:/home/agent/.custom_auth" in args


def test_env_file_auto_discovery(run_cli, tmp_path):
    home = tmp_path / "home"
    env_dir = home / ".contain-agent"
    env_dir.mkdir(parents=True)
    env_file = env_dir / ".env"
    env_file.write_text("FOO=BAR\n")
    ws = tmp_path / "ws"
    ws.mkdir()

    res, args = run_cli(str(ws), home=home)
    assert res.returncode == 0
    assert "--env-file" in args
    assert str(env_file.resolve()) in args


def test_no_env_file_flag(run_cli, tmp_path):
    home = tmp_path / "home"
    env_dir = home / ".contain-agent"
    env_dir.mkdir(parents=True)
    (env_dir / ".env").write_text("FOO=BAR\n")
    ws = tmp_path / "ws"
    ws.mkdir()

    res, args = run_cli("--no-env-file", str(ws), home=home)
    assert res.returncode == 0
    assert "--env-file" not in args


def test_network_flag(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, args = run_cli("--network", "my_bridge", str(ws))
    assert res.returncode == 0
    assert "--network" in args
    assert "my_bridge" in args


def test_custom_image_and_no_rm(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, args = run_cli("--image", "custom:v1", "--no-rm", str(ws))
    assert res.returncode == 0
    assert "custom:v1" in args
    assert "--rm" not in args


def test_missing_image_error(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, _ = run_cli("--image", "nonexistent-image", str(ws))
    assert res.returncode == 1
    assert "Error: Docker image 'nonexistent-image' not found locally." in res.stderr
    assert "docker build -t nonexistent-image ." in res.stderr


def test_sensitive_directory_refusal_and_force(run_cli):
    res, _ = run_cli("/tmp")
    assert res.returncode == 1
    assert "Cowardly refusing to mount sensitive directory" in res.stderr

    res_force, args = run_cli("--force", "/tmp")
    assert res_force.returncode == 0
    assert "/workspace/tmp" in args


def test_nonexistent_workspace_directory(run_cli):
    res, _ = run_cli("/nonexistent/folder/12345")
    assert res.returncode == 1
    assert "does not exist" in res.stderr


def test_exit_code_propagation(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    res, _ = run_cli(str(ws), "fail_42")
    assert res.returncode == 42


def test_docker_missing_error(run_cli, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    nonexistent_docker = tmp_path / "missing_docker_executable"
    res, _ = run_cli(str(ws), fake_docker=nonexistent_docker)
    assert res.returncode == 1
    assert "Error: 'docker' command not found." in res.stderr
    assert "Please ensure Docker is installed and in your PATH." in res.stderr
