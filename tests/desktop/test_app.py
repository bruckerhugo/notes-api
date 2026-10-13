from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from pytestqt.qtbot import QtBot

import desktop.app
from desktop.api_client import ApiUnavailable
from desktop.app import api_base_url, create_window, default_database_path
from desktop.views.main_window import MainWindow
from tests.desktop.fakes import FakeNotesClient


def test_create_window_shows_the_notes_from_the_api(qtbot: QtBot) -> None:
    window = create_window(FakeNotesClient("first", "second"))
    qtbot.addWidget(window)

    titles = [window.note_list.item(i).text() for i in range(window.note_list.count())]
    assert titles == ["first", "second"]


def test_create_window_wires_the_presenter(qtbot: QtBot) -> None:
    api = FakeNotesClient()
    window = create_window(api)
    qtbot.addWidget(window)

    window.title_edit.setText("From the window")
    window.save_button.click()

    assert [note.title for note in api.notes.values()] == ["From the window"]
    assert window.note_list.count() == 1


def test_api_base_url_is_none_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)

    assert api_base_url() is None


def test_api_base_url_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTES_API_URL", "http://notes.example:9000")

    assert api_base_url() == "http://notes.example:9000"


def test_default_database_path_is_in_the_user_data_directory(qtbot: QtBot) -> None:
    path = default_database_path()

    assert path.name == "notes.db"
    assert path.is_absolute()
    assert "notes-api" in path.parts[-2]


# --- main() ---


@dataclass
class FakeServer:
    """Stands in for EmbeddedServer: records its lifecycle, starts nothing."""

    database_path: Path
    events: list[str] = field(default_factory=list)
    base_url: str = "http://127.0.0.1:5555"
    fail: bool = False

    def start(self) -> None:
        self.events.append("start")
        if self.fail:
            raise RuntimeError("Embedded server failed to start")

    def stop(self) -> None:
        self.events.append("stop")


@dataclass
class MainHarness:
    servers: list[FakeServer] = field(default_factory=list)
    server_fails: bool = False
    api_error: Exception | None = None
    dialogs: list[str] = field(default_factory=list)
    base_urls: list[str] = field(default_factory=list)
    shown: list[str] = field(default_factory=list)
    exec_calls: int = 0


@pytest.fixture
def harness(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> MainHarness:
    """Run desktop.app.main() without a real server, network or event loop."""
    harness = MainHarness()

    def fake_server(database_path: Path) -> FakeServer:
        server = FakeServer(database_path, fail=harness.server_fails)
        harness.servers.append(server)
        return server

    class FakeClient(FakeNotesClient):
        def __init__(self, http: object) -> None:
            super().__init__("from the API")
            self.fail_with = harness.api_error  # type: ignore[assignment]
            harness.base_urls.append(str(http.base_url).rstrip("/"))  # type: ignore[attr-defined]

    def fake_exec() -> int:
        harness.exec_calls += 1
        harness.shown.extend(
            w.windowTitle() for w in QApplication.topLevelWidgets() if w.isVisible()
        )
        return 7

    real_create_window = desktop.app.create_window

    def tracked_create_window(api: object) -> MainWindow:
        # Hand the window to qtbot so it is closed and destroyed after the test;
        # a leaked live window broke the following Qt tests under coverage.
        window = real_create_window(api)  # type: ignore[arg-type]
        qtbot.addWidget(window)
        return window

    monkeypatch.setattr(desktop.app, "EmbeddedServer", fake_server)
    monkeypatch.setattr(desktop.app, "NotesClient", FakeClient)
    monkeypatch.setattr(desktop.app, "create_window", tracked_create_window)
    monkeypatch.setattr(desktop.app, "default_database_path", lambda: tmp_path / "notes.db")
    monkeypatch.setattr(QApplication, "exec", staticmethod(fake_exec))
    # A modal dialog would block a headless smoke test forever: record them instead.
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: harness.dialogs.append(args[2]))
    return harness


def test_main_starts_the_embedded_server_by_default(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)

    assert desktop.app.main([]) == 7

    [server] = harness.servers
    assert server.database_path == tmp_path / "notes.db"
    assert server.events == ["start", "stop"]
    assert harness.base_urls == ["http://127.0.0.1:5555"]
    assert "Notes" in harness.shown


def test_main_uses_notes_api_url_without_embedded_server(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NOTES_API_URL", "http://notes.example:9000")

    assert desktop.app.main([]) == 7

    assert harness.servers == []
    assert harness.base_urls == ["http://notes.example:9000"]


def test_main_stops_the_embedded_server_even_if_the_app_crashes(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)

    def crash() -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr(QApplication, "exec", staticmethod(crash))

    with pytest.raises(RuntimeError, match="boom"):
        desktop.app.main([])

    assert harness.servers[0].events == ["start", "stop"]


def test_smoke_test_checks_the_api_and_exits_without_event_loop(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)

    assert desktop.app.main(["--smoke-test"]) == 0

    assert harness.exec_calls == 0
    assert harness.servers[0].events == ["start", "stop"]
    assert "Smoke test OK" in capsys.readouterr().out


def test_smoke_test_works_without_stdout(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Windowed PyInstaller builds on Windows have no console: sys.stdout is None.
    monkeypatch.delenv("NOTES_API_URL", raising=False)
    monkeypatch.setattr("sys.stdout", None)

    assert desktop.app.main(["--smoke-test"]) == 0


def test_smoke_test_writes_its_result_to_the_log_file(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)
    log = tmp_path / "smoke.log"

    assert desktop.app.main(["--smoke-test", "--smoke-log", str(log)]) == 0

    assert "Smoke test OK" in log.read_text()


def test_smoke_test_fails_without_dialog_when_the_api_does_not_answer(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)
    harness.api_error = ApiUnavailable("Notes API unavailable: connection refused")
    log = tmp_path / "smoke.log"

    assert desktop.app.main(["--smoke-test", "--smoke-log", str(log)]) == 1

    assert harness.dialogs == []
    assert harness.exec_calls == 0
    assert "Smoke test FAILED: Notes API unavailable" in log.read_text()
    assert harness.servers[0].events == ["start", "stop"]


def test_smoke_test_fails_cleanly_when_the_embedded_server_does_not_start(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)
    harness.server_fails = True
    log = tmp_path / "smoke.log"

    assert desktop.app.main(["--smoke-test", "--smoke-log", str(log)]) == 1

    assert "Smoke test FAILED: Embedded server failed to start" in log.read_text()


def test_embedded_server_failure_is_raised_outside_smoke_test(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)
    harness.server_fails = True

    with pytest.raises(RuntimeError, match="failed to start"):
        desktop.app.main([])


def test_smoke_test_arms_a_watchdog_that_dumps_stacks_and_exits(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        "faulthandler.dump_traceback_later",
        lambda timeout, exit, file: calls.append(("arm", (timeout, exit, file.name))),
    )
    monkeypatch.setattr(
        "faulthandler.cancel_dump_traceback_later", lambda: calls.append(("cancel", None))
    )
    log = tmp_path / "smoke.log"

    assert desktop.app.main(["--smoke-test", "--smoke-log", str(log)]) == 0

    assert calls == [("arm", (desktop.app.SMOKE_TIMEOUT, True, str(log))), ("cancel", None)]
    assert log.read_text().startswith("Smoke test started")


def test_no_watchdog_outside_smoke_test(
    harness: MainHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NOTES_API_URL", raising=False)
    armed: list[float] = []
    monkeypatch.setattr("faulthandler.dump_traceback_later", lambda *a, **k: armed.append(1))

    desktop.app.main([])

    assert armed == []
