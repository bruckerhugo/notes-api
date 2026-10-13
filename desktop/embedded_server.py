"""Run the notes API inside the desktop app, for the standalone executable.

This is the only desktop module that imports the backend.
"""

import logging
import re
import socket
import threading
import time
from pathlib import Path
from types import TracebackType

import uvicorn

STARTUP_TIMEOUT = 10.0


class _ErrorCollector(logging.Handler):
    """Collect the errors uvicorn logs while starting (e.g. a failed lifespan)."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.errors: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        exc = record.exc_info[1] if record.exc_info else None
        self.errors.append(
            str(exc) if exc is not None else _last_exception_line(record.getMessage())
        )


def _last_exception_line(text: str) -> str:
    """Summarize a logged traceback by its last 'SomeError: message' line."""
    matches = re.findall(r"^[\w.]+(?:Error|Exception): .*$", text, flags=re.MULTILINE)
    return matches[-1] if matches else text.strip().splitlines()[0]


class EmbeddedServer:
    """Serve the API on 127.0.0.1 (free port) in a background thread."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._port: int | None = None
        self._error: BaseException | None = None

    @property
    def base_url(self) -> str:
        if self._port is None:
            raise RuntimeError("Embedded server not started")
        return f"http://127.0.0.1:{self._port}"

    def start(self) -> None:
        # Imported here so that importing the desktop package never loads the backend.
        from backend import database
        from backend.main import app

        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        database.configure(f"sqlite:///{self._database_path}")

        # Bind the socket ourselves: port 0 lets the OS pick a free port, with no race.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        self._port = sock.getsockname()[1]

        # Explicit loop/protocol choices avoid optional dependencies (uvloop, httptools,
        # websockets), which matters for the PyInstaller build. log_config=None keeps
        # uvicorn from configuring console logging: its formatter calls
        # sys.stdout.isatty(), and windowed builds have no console (sys.stdout is None).
        config = uvicorn.Config(
            app,
            loop="asyncio",
            http="h11",
            ws="none",
            lifespan="on",
            log_config=None,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)
        uvicorn_errors = logging.getLogger("uvicorn.error")
        collector = _ErrorCollector()
        uvicorn_errors.addHandler(collector)
        try:
            self._error = None
            self._thread = threading.Thread(target=self._serve, args=(sock,), daemon=True)
            self._thread.start()

            deadline = time.monotonic() + STARTUP_TIMEOUT
            while not self._server.started:
                if not self._thread.is_alive() or time.monotonic() > deadline:
                    causes = collector.errors or ([str(self._error)] if self._error else [])
                    cause = f": {causes[0]}" if causes else ""
                    raise RuntimeError(f"Embedded server failed to start{cause}")
                time.sleep(0.01)
        finally:
            uvicorn_errors.removeHandler(collector)

    def _serve(self, sock: socket.socket) -> None:
        # Keep the failure for start(): with log_config=None uvicorn no longer logs it,
        # and an exception escaping a thread would be lost.
        assert self._server is not None
        try:
            self._server.run(sockets=[sock])
        except BaseException as exc:
            self._error = exc

    def stop(self) -> None:
        if self._server is not None and self._thread is not None:
            self._server.should_exit = True
            self._thread.join(timeout=STARTUP_TIMEOUT)

    def __enter__(self) -> "EmbeddedServer":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()
