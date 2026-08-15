import tempfile
import unittest
import unittest.mock
from pathlib import Path

from typer.testing import CliRunner

from contain_agent import (
    app,
    build_docker_command,
    get_config_mounts,
    is_sensitive_directory,
)

runner = CliRunner()


class TestContainAgentCLI(unittest.TestCase):
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            "Run AI coding agents in an isolated Docker container", result.output
        )
        self.assertIn("--mount", result.output)
        self.assertIn("--no-mount", result.output)
        self.assertIn("--share-config", result.output)
        self.assertIn("--no-share-config", result.output)

    def test_default_dry_run(self):
        result = runner.invoke(app, ["--dry-run"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("docker run --rm", result.output)
        self.assertIn("contain-agent bash -l -i", result.output)

    def test_mount_dir_and_command_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "my_project"
            project_dir.mkdir()
            result = runner.invoke(
                app, ["--dry-run", str(project_dir), "cat", "bar.txt"]
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn(
                f"-v {project_dir.resolve()}:/workspace/my_project", result.output
            )
            self.assertIn("-w /workspace/my_project", result.output)
            self.assertIn("bash -l -i -c 'cat bar.txt'", result.output)

    def test_mount_dir_with_command_flags(self):
        result = runner.invoke(app, ["--dry-run", ".", "ls", "-la"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("bash -l -i -c 'ls -la'", result.output)

    def test_no_mount_with_command(self):
        result = runner.invoke(app, ["--dry-run", "--no-mount", "ls", "-la"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("-w /workspace", result.output)
        self.assertNotIn("/workspace/contain-agent", result.output)
        self.assertIn("bash -l -i -c 'ls -la'", result.output)

    def test_no_share_config_and_custom_image(self):
        result = runner.invoke(
            app,
            [
                "--dry-run",
                "--no-share-config",
                "--image",
                "my-custom-img",
                ".",
                "yclaude",
                "task",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("my-custom-img", result.output)
        self.assertIn("bash -l -i -c 'yclaude task'", result.output)

    def test_custom_dotfiles_dir_and_env_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("FOO=BAR\n")
            dotfiles_dir = Path(tmpdir) / "dotfiles"
            dotfiles_dir.mkdir()
            (dotfiles_dir / ".claude").mkdir()

            result = runner.invoke(
                app,
                [
                    "--dry-run",
                    "--no-share-config",
                    f"--dotfiles-dir={dotfiles_dir}",
                    f"--env-file={env_file}",
                    "--no-rm",
                    ".",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn(f"--env-file {env_file.resolve()}", result.output)
            self.assertIn(
                f"-v {(dotfiles_dir / '.claude').resolve()}:/home/agent/.claude",
                result.output,
            )
            self.assertNotIn("--rm", result.output)

    def test_is_sensitive_directory(self):
        self.assertTrue(is_sensitive_directory(Path("/")))
        self.assertTrue(is_sensitive_directory(Path("/tmp")))
        self.assertTrue(is_sensitive_directory(Path.home()))
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subproject"
            subdir.mkdir()
            self.assertFalse(is_sensitive_directory(subdir))

    def test_sensitive_directory_refusal(self):
        result = runner.invoke(app, ["/tmp"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Cowardly refusing to mount sensitive directory", result.output)

    def test_sensitive_directory_force(self):
        result = runner.invoke(app, ["--force", "--dry-run", "/tmp"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("docker run", result.output)

    def test_nonexistent_directory_error(self):
        result = runner.invoke(app, ["/path/to/nonexistent/directory/12345"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("does not exist", result.output)

    def test_build_docker_command_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Path(tmpdir) / "myproject"
            ws.mkdir()
            cmd = build_docker_command(
                image="contain-agent",
                workspace_path=ws,
                config_mounts=[("/host/.claude", "/home/agent/.claude")],
                env_file_path=None,
                command=["yclaude", "fix bug"],
                rm=True,
                interactive=True,
            )
            self.assertEqual(cmd[0:3], ["docker", "run", "--rm"])
            self.assertIn("-it", cmd)
            self.assertIn("-v", cmd)
            self.assertIn("/host/.claude:/home/agent/.claude", cmd)
            self.assertIn(f"{ws.resolve()}:/workspace/myproject", cmd)
            self.assertIn("-w", cmd)
            self.assertIn("/workspace/myproject", cmd)
            self.assertIn("contain-agent", cmd)
            self.assertIn("bash", cmd)
            self.assertIn("-l", cmd)
            self.assertIn("-i", cmd)
            self.assertIn("-c", cmd)
            self.assertIn("yclaude 'fix bug'", cmd)

    def test_build_docker_command_no_mount(self):
        cmd = build_docker_command(
            image="contain-agent",
            workspace_path=None,
            config_mounts=None,
            env_file_path=None,
            command=None,
            rm=False,
            interactive=False,
        )
        self.assertEqual(cmd[0:2], ["docker", "run"])
        self.assertNotIn("--rm", cmd)
        self.assertIn("-i", cmd)
        self.assertNotIn("-it", cmd)
        self.assertIn("-w", cmd)
        self.assertIn("/workspace", cmd)
        self.assertIn("contain-agent", cmd)
        self.assertEqual(cmd[-3:], ["bash", "-l", "-i"])

    def test_get_config_mounts_no_share_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dotfiles_dir = Path(tmpdir) / "dotfiles"
            dotfiles_dir.mkdir()
            (dotfiles_dir / ".claude").mkdir()
            (dotfiles_dir / ".gemini").mkdir()

            mounts = get_config_mounts(share_config=False, dotfiles_dir=dotfiles_dir)
            self.assertEqual(len(mounts), 2)
            self.assertEqual(mounts[0][1], "/home/agent/.claude")
            self.assertEqual(mounts[1][1], "/home/agent/.gemini")

    def test_missing_image_error(self):
        with unittest.mock.patch(
            "contain_agent.check_image_exists", return_value=False
        ):
            result = runner.invoke(app, ["--image", "nonexistent-image:latest", "."])
            self.assertEqual(result.exit_code, 1)
            self.assertIn(
                "Docker image 'nonexistent-image:latest' not found locally",
                result.output,
            )

    def test_network_option(self):
        result = runner.invoke(app, ["--dry-run", "--network", "my-bridge-net", "."])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--network my-bridge-net", result.output)


if __name__ == "__main__":
    unittest.main()
