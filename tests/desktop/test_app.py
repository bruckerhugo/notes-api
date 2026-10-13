from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

import desktop.app
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

    def start(self) -> None:
        self.events.append("start")

    def stop(self) -> None:
        self.events.append("stop")


@dataclass
class MainHarness:
    servers: list[FakeServer] = field(default_factory=list)
    base_urls: list[str] = field(default_factory=list)
    shown: list[str] = field(default_factory=list)
    exec_calls: int = 0


@pytest.fixture
def harness(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> MainHarness:
    """Run desktop.app.main() without a real server, network or event loop."""
    harness = MainHarness()

    def fake_server(database_path: Path) -> FakeServer:
        server = FakeServer(database_path)
        harness.servers.append(server)
        return server

    class FakeClient(FakeNotesClient):
        def __init__(self, http: object) -> None:
            super().__init__("from the API")
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
