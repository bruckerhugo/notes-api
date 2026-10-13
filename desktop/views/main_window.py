"""Main window of the desktop app: a thin Qt view driven by NotesPresenter."""

from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from desktop.api_client import Note

NOTE_ID_ROLE = Qt.ItemDataRole.UserRole


class PresenterActions(Protocol):
    """User actions the window forwards to the presenter."""

    def select(self, note_id: int) -> None: ...

    def new_note(self) -> None: ...

    def save(self, title: str, content: str) -> None: ...

    def delete(self) -> None: ...


class MainWindow(QMainWindow):
    """Implements the NotesView protocol; holds no logic of its own."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Notes")
        self.resize(900, 600)
        self._presenter: PresenterActions | None = None

        self.note_list = QListWidget()
        self.new_button = QPushButton("New")
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Title")
        self.content_edit = QPlainTextEdit()
        self.content_edit.setPlaceholderText("Write your note here...")
        self.save_button = QPushButton("Save")
        self.delete_button = QPushButton("Delete")
        self.delete_button.setEnabled(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self.new_button)
        left_layout.addWidget(self.note_list)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.save_button)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self.title_edit)
        right_layout.addWidget(self.content_edit)
        right_layout.addLayout(buttons)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([280, 620])
        self.setCentralWidget(splitter)
        self.statusBar()

    def bind(self, presenter: PresenterActions) -> None:
        self._presenter = presenter
        self.note_list.itemClicked.connect(self._on_item_clicked)
        self.new_button.clicked.connect(presenter.new_note)
        self.save_button.clicked.connect(self._on_save)
        self.delete_button.clicked.connect(presenter.delete)
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self._on_save)

    # --- NotesView ---

    def show_notes(self, notes: list[Note], selected_id: int | None) -> None:
        # Repopulating the list must not be mistaken for a user selection.
        self.note_list.blockSignals(True)
        try:
            self.note_list.clear()
            for note in notes:
                item = QListWidgetItem(note.title)
                item.setData(NOTE_ID_ROLE, note.id)
                self.note_list.addItem(item)
                if note.id == selected_id:
                    self.note_list.setCurrentItem(item)
        finally:
            self.note_list.blockSignals(False)

    def show_note(self, note: Note | None) -> None:
        self.title_edit.setText("" if note is None else note.title)
        self.content_edit.setPlainText("" if note is None else note.content)
        self.delete_button.setEnabled(note is not None)

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Notes", message)

    def show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 5000)

    def confirm_delete(self, note: Note) -> bool:
        answer = QMessageBox.question(
            self,
            "Delete note",
            f"Delete the note “{note.title}”?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    # --- user actions ---

    # Only connected in bind(), so the presenter is always set here.

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        assert self._presenter is not None
        self._presenter.select(item.data(NOTE_ID_ROLE))

    def _on_save(self) -> None:
        assert self._presenter is not None
        self._presenter.save(self.title_edit.text(), self.content_edit.toPlainText())
