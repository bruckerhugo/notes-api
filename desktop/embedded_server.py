"""Run the notes API inside the desktop app, for the standalone executable.

This is the only desktop module that imports the backend.
"""

import socket
import threading
import time
from pathlib import Path
from types import TracebackType

import uvicorn

STARTUP_TIMEOUT = 10.0


class EmbeddedServer:
    """Serve the API on 127.0.0.1 (free port) in a background thread."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._port: int | None = None

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
        self._thread = threading.Thread(
            target=self._server.run, kwargs={"sockets": [sock]}, daemon=True
        )
        self._thread.start()

        deadline = time.monotonic() + STARTUP_TIMEOUT
        while not self._server.started:
            if not self._thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Embedded server failed to start")
            time.sleep(0.01)

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
