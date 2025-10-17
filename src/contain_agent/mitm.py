import time
import sys
import subprocess
from pathlib import Path
from shutil import which


class NullContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @property
    def env(self) -> dict[str, str]:
        return {}


class ProxyContext(NullContext):
    def __init__(self, proxy_host: str, mitmproxy_dir: Path):
        proxy_host, proxy_port = proxy_host.split(":")
        self.proxy_host = proxy_host
        self.proxy_port = int(proxy_port)
        self.mitmproxy_dir = mitmproxy_dir

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    @property
    def env(self) -> dict[str, str]:
        cert_file = self.mitmproxy_dir / "mitmproxy-ca-cert.pem"
        proxy_url = f"http://{self.proxy_host}:{self.proxy_port}"
        return {
            "SSL_CERT_FILE": str(cert_file),
            "NODE_EXTRA_CA_CERTS": str(cert_file),
            "HTTP_PROXY": proxy_url,
            "all_proxy": proxy_url,
        }


class MitmContext(ProxyContext):
    def __init__(
        self,
        dump_file: str,
        proxy_host: str,
        mitmproxy_dir: Path,
        output=sys.stderr,
    ):
        super().__init__(proxy_host, mitmproxy_dir)
        self.dump_file = dump_file
        self.output = output
        self.process = None

    def print(self, *a, **kw):
        print(*a, **kw, file=self.output)

    @staticmethod
    def find_mitmdump() -> list[str]:
        mitmdump_path = Path("~/.contain-agent/mitmdump").expanduser()
        if mitmdump_path.exists():
            return [mitmdump_path.as_posix()]
        if which("mitmdump"):
            return ["mitmdump"]
        if which("uvx"):
            return ["uvx", "--from", "mitmproxy", "mitmdump"]
        raise RuntimeError("mitmdump not found")

    def __enter__(self):
        cmd = self.find_mitmdump()
        cmd.extend(["-w", self.dump_file])

        self.print(f"Starting mitmproxy: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        time.sleep(1)

        if self.process.poll() is not None:
            raise RuntimeError("mitmdump failed to start")

        self.print(f"mitmdump started with PID {self.process.pid}")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.print("\nStopping mitmproxy...")
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.print("Force killing mitmproxy...")
            self.process.kill()
        self.print(f"Traffic dump saved to {self.dump_file}")
