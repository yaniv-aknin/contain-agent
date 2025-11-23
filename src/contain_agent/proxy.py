import time
import sys
import subprocess
import socket
from pathlib import Path
from shutil import which


def find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def get_proxy_env(proxy_host: str, proxy_port: int, cert_file: Path) -> dict[str, str]:
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    return {
        "SSL_CERT_FILE": str(cert_file),
        "NODE_EXTRA_CA_CERTS": str(cert_file),
        "HTTP_PROXY": proxy_url,
        "all_proxy": proxy_url,
    }


def get_transparent_proxy_env(proxy_host: str, proxy_port: int, cert_file: Path) -> dict[str, str]:
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    return {
        "SSL_CERT_FILE": str(cert_file),
        "NODE_EXTRA_CA_CERTS": str(cert_file),
        "TRANSPARENT_PROXY": "1",
        "HTTP_PROXY": proxy_url,
    }


def find_dump_executable(executable_name: str) -> list[str]:
    local_path = Path(f"~/.contain-agent/{executable_name}").expanduser()
    if local_path.exists():
        return [local_path.as_posix()]
    if which(executable_name):
        return [executable_name]

    if executable_name == "mitmdump" and which("uvx"):
        return ["uvx", "--from", "mitmproxy", "mitmdump"]

    raise RuntimeError(f"{executable_name} not found")


def find_mitmdump() -> list[str]:
    return find_dump_executable("mitmdump")


def start_mitmdump(dump_file: str, port: int = None, executable: str = "mitmdump", output=sys.stderr):
    if port is None:
        port = find_free_port()

    cmd = find_dump_executable(executable)
    cmd.extend(["-p", str(port), "-w", dump_file])

    print(f"Starting {executable} on port {port}: {' '.join(cmd)}", file=output)
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    time.sleep(1)

    if process.poll() is not None:
        raise RuntimeError(f"{executable} failed to start")

    print(f"{executable} started with PID {process.pid}", file=output)
    return process, port


def stop_mitmdump(process, dump_file: str, output=sys.stderr):
    print("\nStopping mitmproxy...", file=output)
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        print("Force killing mitmproxy...", file=output)
        process.kill()
    print(f"Traffic dump saved to {dump_file}", file=output)
