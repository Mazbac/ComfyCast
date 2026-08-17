from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import quote, urlparse

from .network import get_lan_ip


@dataclass(frozen=True, slots=True)
class MediaEntry:
    path: Path
    content_type: str
    expires_at: float


class MediaRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._entries: dict[str, MediaEntry] = {}

    def register(self, path: str | Path, content_type: str, ttl_seconds: float) -> str:
        resolved = Path(path).resolve(strict=True)
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._cleanup_locked()
            self._entries[token] = MediaEntry(
                resolved,
                content_type,
                time.monotonic() + ttl_seconds,
            )
        return token

    def get(self, token: str) -> MediaEntry | None:
        with self._lock:
            self._cleanup_locked()
            entry = self._entries.get(token)
            if entry is None or not entry.path.is_file():
                return None
            return entry

    def _cleanup_locked(self) -> None:
        now = time.monotonic()
        expired = [
            token
            for token, entry in self._entries.items()
            if entry.expires_at <= now
        ]
        for token in expired:
            self._entries.pop(token, None)


def _parse_range(value: str, size: int) -> tuple[int, int] | None:
    if not value or not value.startswith("bytes="):
        return None
    if size <= 0:
        raise ValueError("Unsatisfiable byte range")
    spec = value[6:].strip()
    if not spec or "," in spec or "-" not in spec:
        raise ValueError("Unsupported byte range")
    start_text, end_text = spec.split("-", 1)
    if not start_text:
        length = int(end_text)
        if length <= 0:
            raise ValueError("Invalid suffix range")
        start = max(size - length, 0)
        return start, size - 1

    start = int(start_text)
    end = int(end_text) if end_text else size - 1
    if start < 0 or start >= size or end < start:
        raise ValueError("Unsatisfiable byte range")
    return start, min(end, size - 1)


class LocalMediaServer:
    def __init__(self):
        self.registry = MediaRegistry()
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._server is not None

    @property
    def current_port(self) -> int | None:
        with self._lock:
            if self._server is None:
                return None
            return int(self._server.server_address[1])

    def ensure_started(self) -> None:
        with self._lock:
            if self._server is not None:
                return
            registry = self.registry

            class Handler(BaseHTTPRequestHandler):
                server_version = "ComfyCast/1.0"
                protocol_version = "HTTP/1.1"

                def do_GET(self):
                    self._serve(send_body=True)

                def do_HEAD(self):
                    self._serve(send_body=False)

                def log_message(self, _format, *_args):
                    return

                def _serve(self, send_body: bool):
                    parts = urlparse(self.path).path.strip("/").split("/")
                    if len(parts) != 3 or parts[0] != "media":
                        self.send_error(404)
                        return
                    entry = registry.get(parts[1])
                    if entry is None:
                        self.send_error(404)
                        return
                    try:
                        size = entry.path.stat().st_size
                    except OSError:
                        self.send_error(404)
                        return

                    try:
                        byte_range = _parse_range(
                            self.headers.get("Range", ""),
                            size,
                        )
                    except (ValueError, TypeError):
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return

                    start, end = byte_range if byte_range else (0, size - 1)
                    length = max(0, end - start + 1)
                    self.send_response(206 if byte_range else 200)
                    self.send_header("Content-Type", entry.content_type)
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "no-store")
                    if byte_range:
                        self.send_header(
                            "Content-Range",
                            f"bytes {start}-{end}/{size}",
                        )
                    self.end_headers()
                    if not send_body or length == 0:
                        return

                    try:
                        with entry.path.open("rb") as source:
                            source.seek(start)
                            remaining = length
                            while remaining > 0:
                                chunk = source.read(min(256 * 1024, remaining))
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                                remaining -= len(chunk)
                    except (
                        BrokenPipeError,
                        ConnectionAbortedError,
                        ConnectionResetError,
                    ):
                        # Receivers may close a range request as soon as they
                        # have buffered enough data. That is not a server error.
                        return

            self._server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
            self._server.daemon_threads = True
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                name="ComfyCastMediaServer",
                daemon=True,
            )
            self._thread.start()

    @property
    def port(self) -> int:
        self.ensure_started()
        port = self.current_port
        assert port is not None
        return port

    def publish(
        self,
        path: str | Path,
        content_type: str,
        ttl_seconds: float = 3600.0,
        *,
        target_host: str | None = None,
    ) -> str:
        self.ensure_started()
        resolved = Path(path).resolve(strict=True)
        token = self.registry.register(resolved, content_type, ttl_seconds)
        filename = quote(resolved.name, safe="")
        host = get_lan_ip(target_host)
        return f"http://{host}:{self.port}/media/{token}/{filename}"

    def stop(self) -> None:
        with self._lock:
            server = self._server
            self._server = None
            self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()


MEDIA_SERVER = LocalMediaServer()
