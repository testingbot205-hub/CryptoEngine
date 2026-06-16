"""
main_window.py — Головне вікно SecureMsg (PyQt6)
=================================================
Сучасний темний інтерфейс з трьома вкладками:
  1. Шифрування  — текст і файли
  2. Дешифрування — текст і файли
  3. Ключі        — управління своїми ключами та контактами
"""

import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QTextEdit, QPushButton, QComboBox,
    QFileDialog, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QDialog, QDialogButtonBox, QFormLayout,
    QSplitter, QFrame, QInputDialog, QCheckBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor, QTextCursor
from PyQt6.QtCore import QTimer

import key_manager as km
import crypto_engine as ce


# --------------------------------------------------------------------------- #
#  Темна палітра                                                               #
# --------------------------------------------------------------------------- #

DARK_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #1a1a2e;
}
QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #2d2d4e;
    border-radius: 8px;
    background-color: #16213e;
}
QTabBar::tab {
    background: #0f3460;
    color: #a0a0b0;
    padding: 10px 24px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    font-weight: 500;
}
QTabBar::tab:selected {
    background: #e94560;
    color: #ffffff;
    font-weight: 600;
}
QTabBar::tab:hover:!selected {
    background: #1a4a7a;
    color: #e0e0e0;
}
QTextEdit, QLineEdit {
    background-color: #0d1b2a;
    border: 1px solid #2d2d4e;
    border-radius: 6px;
    padding: 8px;
    color: #e0e0e0;
    selection-background-color: #e94560;
}
QTextEdit:focus, QLineEdit:focus {
    border: 1px solid #e94560;
}
QPushButton {
    background-color: #0f3460;
    color: #e0e0e0;
    border: none;
    border-radius: 6px;
    padding: 9px 20px;
    font-weight: 500;
    min-width: 120px;
}
QPushButton:hover {
    background-color: #1a4a7a;
}
QPushButton:pressed {
    background-color: #e94560;
}
QPushButton#primary {
    background-color: #e94560;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#primary:hover {
    background-color: #ff6b81;
}
QPushButton#danger {
    background-color: #4a1a2a;
    color: #ff6b81;
}
QPushButton#danger:hover {
    background-color: #6a2a3a;
}
QPushButton#success {
    background-color: #1a4a3a;
    color: #4ecca3;
}
QPushButton#success:hover {
    background-color: #2a6a5a;
}
QComboBox {
    background-color: #0d1b2a;
    border: 1px solid #2d2d4e;
    border-radius: 6px;
    padding: 7px 12px;
    color: #e0e0e0;
    min-width: 160px;
}
QComboBox:focus { border: 1px solid #e94560; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #0d1b2a;
    border: 1px solid #2d2d4e;
    selection-background-color: #e94560;
}
QListWidget {
    background-color: #0d1b2a;
    border: 1px solid #2d2d4e;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item {
    padding: 8px 12px;
    border-radius: 4px;
    margin: 1px 0;
}
QListWidget::item:selected {
    background-color: #e94560;
    color: #ffffff;
}
QListWidget::item:hover:!selected {
    background-color: #1a3a5a;
}
QLabel#title {
    font-size: 16px;
    font-weight: 700;
    color: #e94560;
    margin-bottom: 4px;
}
QLabel#subtitle {
    font-size: 11px;
    color: #707090;
    margin-bottom: 8px;
}
QLabel#section {
    font-size: 12px;
    font-weight: 600;
    color: #a0a0c0;
    margin-top: 8px;
}
QFrame#separator {
    background-color: #2d2d4e;
    max-height: 1px;
    margin: 8px 0;
}
QCheckBox {
    color: #a0a0c0;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 3px;
    border: 1px solid #2d2d4e;
    background: #0d1b2a;
}
QCheckBox::indicator:checked {
    background: #e94560;
    border-color: #e94560;
}
QScrollBar:vertical {
    background: #0d1b2a;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2d2d4e;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #4d4d6e; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip {
    background-color: #0d1b2a;
    color: #e0e0e0;
    border: 1px solid #2d2d4e;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
"""


# --------------------------------------------------------------------------- #
#  Допоміжні функції                                                           #
# --------------------------------------------------------------------------- #

def label(text: str, style: str = "") -> QLabel:
    lbl = QLabel(text)
    if style:
        lbl.setObjectName(style)
    return lbl


def separator() -> QFrame:
    f = QFrame()
    f.setObjectName("separator")
    f.setFrameShape(QFrame.Shape.HLine)
    return f


def make_button(text: str, style_id: str = "", min_w: int = 120) -> QPushButton:
    btn = QPushButton(text)
    if style_id:
        btn.setObjectName(style_id)
    btn.setMinimumWidth(min_w)
    return btn


# --------------------------------------------------------------------------- #
#  Діалог першого запуску                                                      #
# --------------------------------------------------------------------------- #

class FirstRunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SecureMsg — перше налаштування")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        layout.addWidget(label("Вітаємо у SecureMsg", "title"))
        layout.addWidget(label(
            "Ключів не знайдено. Згенеруємо нову пару RSA-2048.\n"
            "Приватний ключ залишається тільки у вас.", "subtitle"
        ))
        layout.addWidget(separator())

        form = QFormLayout()
        form.setSpacing(10)

        self.pwd_check = QCheckBox("Захистити приватний ключ паролем")
        layout.addWidget(self.pwd_check)

        self.pwd_edit = QLineEdit()
        self.pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_edit.setPlaceholderText("Пароль для приватного ключа")
        self.pwd_edit.setEnabled(False)

        self.pwd_confirm = QLineEdit()
        self.pwd_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_confirm.setPlaceholderText("Підтвердження паролю")
        self.pwd_confirm.setEnabled(False)

        self.pwd_check.toggled.connect(self.pwd_edit.setEnabled)
        self.pwd_check.toggled.connect(self.pwd_confirm.setEnabled)

        form.addRow("Пароль:", self.pwd_edit)
        form.addRow("Підтвердити:", self.pwd_confirm)
        layout.addLayout(form)

        hint = label(
            "Якщо не встановити пароль — ключ зберігається у відкритому вигляді.\n"
            "Для корпоративного використання пароль рекомендовано.", "subtitle"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def validate_and_accept(self):
        if self.pwd_check.isChecked():
            if not self.pwd_edit.text():
                QMessageBox.warning(self, "Помилка", "Введіть пароль або зніміть прапорець.")
                return
            if self.pwd_edit.text() != self.pwd_confirm.text():
                QMessageBox.warning(self, "Помилка", "Паролі не збігаються.")
                return
        self.accept()

    def get_password(self) -> str | None:
        if self.pwd_check.isChecked():
            return self.pwd_edit.text()
        return None


# --------------------------------------------------------------------------- #
#  Діалог додавання контакту                                                   #
# --------------------------------------------------------------------------- #

class AddContactDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Додати контакт")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(label("Додати публічний ключ контакту", "title"))
        layout.addWidget(label(
            "Вставте PEM-ключ колеги або клієнта, або оберіть файл .pem", "subtitle"
        ))

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Наприклад: Ivan_Petrenko або Client_ABC")
        form.addRow("Ім'я контакту:", self.name_edit)
        layout.addLayout(form)

        self.key_edit = QTextEdit()
        self.key_edit.setPlaceholderText(
            "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
        )
        self.key_edit.setMaximumHeight(160)
        layout.addWidget(self.key_edit)

        row = QHBoxLayout()
        load_btn = make_button("📂 Завантажити .pem файл")
        load_btn.clicked.connect(self.load_from_file)
        row.addWidget(load_btn)
        row.addStretch()
        layout.addLayout(row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def load_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Оберіть публічний ключ", "", "PEM файли (*.pem);;Всі файли (*)"
        )
        if path:
            self.key_edit.setPlainText(Path(path).read_text())
            if not self.name_edit.text():
                self.name_edit.setText(Path(path).stem)

    def validate_and_accept(self):
        name = self.name_edit.text().strip()
        pem = self.key_edit.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "Помилка", "Введіть ім'я контакту.")
            return
        if not pem:
            QMessageBox.warning(self, "Помилка", "Вставте або завантажте публічний ключ.")
            return
        try:
            ce.load_public_key(pem.encode())
        except Exception:
            QMessageBox.critical(self, "Помилка", "Це не валідний RSA публічний ключ.")
            return
        self.accept()

    def get_data(self) -> tuple[str, str]:
        return self.name_edit.text().strip(), self.key_edit.toPlainText().strip()


# --------------------------------------------------------------------------- #
#  Вкладка «Шифрування»                                                        #
# --------------------------------------------------------------------------- #

class EncryptTab(QWidget):
    status_message = pyqtSignal(str, str)   # (text, level: info/ok/error)

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Отримувач ---
        layout.addWidget(label("Шифрування", "title"))
        layout.addWidget(label(
            "Зашифруйте текст або файл публічним ключем отримувача. "
            "Розшифрувати зможе тільки власник відповідного приватного ключа.", "subtitle"
        ))

        row = QHBoxLayout()
        row.addWidget(label("Отримувач:", "section"))
        self.contact_combo = QComboBox()
        self.contact_combo.setPlaceholderText("Оберіть контакт...")
        row.addWidget(self.contact_combo)
        self.no_contacts_lbl = QLabel("⚠ Немає контактів — додайте на вкладці 'Ключі та контакти'")
        self.no_contacts_lbl.setStyleSheet("font-size: 11px; color: #e9a800; margin-left: 10px;")
        self.no_contacts_lbl.setVisible(False)
        row.addWidget(self.no_contacts_lbl)
        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(separator())

        # --- Текст ---
        layout.addWidget(label("Текст для шифрування:", "section"))
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Введіть конфіденційне повідомлення...")
        self.text_input.setMinimumHeight(120)
        layout.addWidget(self.text_input)

        row2 = QHBoxLayout()
        self.encrypt_text_btn = make_button("🔒 Зашифрувати текст", "primary")
        self.encrypt_text_btn.clicked.connect(self.encrypt_text)
        self.encrypt_text_btn.setToolTip("Зашифрувати введений текст публічним ключем отримувача")
        self.copy_btn = make_button("📋 Копіювати результат")
        self.copy_btn.clicked.connect(self.copy_result)
        self.copy_btn.setToolTip("Скопіювати Base64-рядок у буфер обміну для відправки")
        self.save_text_btn = make_button("💾 Зберегти як .smsg")
        self.save_text_btn.clicked.connect(self.save_text_result)
        self.save_text_btn.setToolTip("Зберегти зашифроване повідомлення як файл .smsg")
        row2.addWidget(self.encrypt_text_btn)
        row2.addWidget(self.copy_btn)
        row2.addWidget(self.save_text_btn)
        row2.addStretch()
        layout.addLayout(row2)

        layout.addWidget(separator())

        # --- Файл ---
        layout.addWidget(label("Або зашифрувати файл:", "section"))
        row3 = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Шлях до файлу...")
        self.file_path_edit.setReadOnly(True)
        browse_btn = make_button("📂 Обрати файл")
        browse_btn.clicked.connect(self.browse_file)
        row3.addWidget(self.file_path_edit)
        row3.addWidget(browse_btn)
        layout.addLayout(row3)

        self.encrypt_file_btn = make_button("🔒 Зашифрувати файл", "primary")
        self.encrypt_file_btn.clicked.connect(self.encrypt_file)
        self.encrypt_file_btn.setToolTip("Зашифрувати файл і зберегти як .smsg")
        layout.addWidget(self.encrypt_file_btn)

        layout.addWidget(separator())

        # --- Результат ---
        layout.addWidget(label("Результат (Base64):", "section"))
        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setPlaceholderText("Зашифрований вміст з'явиться тут...")
        self.result_edit.setMinimumHeight(80)
        layout.addWidget(self.result_edit)

    def refresh_contacts(self):
        self.contact_combo.clear()
        contacts = km.list_contacts()
        for c in contacts:
            self.contact_combo.addItem(c)
        self.no_contacts_lbl.setVisible(len(contacts) == 0)

    def _get_recipient_key(self):
        name = self.contact_combo.currentText()
        if not name:
            QMessageBox.warning(self, "Помилка", "Оберіть отримувача зі списку контактів.")
            return None
        try:
            return km.load_contact_key(name)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", str(e))
            return None

    def encrypt_text(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Помилка", "Введіть текст для шифрування.")
            return
        pub_key = self._get_recipient_key()
        if not pub_key:
            return
        try:
            pkg = ce.encrypt_text(text, pub_key)
            import base64
            self.result_edit.setPlainText(base64.b64encode(pkg).decode())
            self.status_message.emit("✅ Текст зашифровано успішно", "ok")
        except Exception as e:
            QMessageBox.critical(self, "Помилка шифрування", str(e))

    def copy_result(self):
        text = self.result_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status_message.emit("📋 Скопійовано до буфера обміну", "info")

    def save_text_result(self):
        data = self.result_edit.toPlainText()
        if not data:
            QMessageBox.warning(self, "Немає даних", "Спочатку зашифруйте текст.")
            return
        import base64
        raw = base64.b64decode(data)
        if not raw:
            QMessageBox.warning(self, "Помилка", "Зашифровані дані порожні.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Зберегти зашифроване повідомлення", "message.smsg",
            "SecureMsg файли (*.smsg);;Всі файли (*)"
        )
        if path:
            Path(path).write_bytes(raw)
            self.status_message.emit(f"💾 Збережено: {Path(path).name}", "ok")

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Оберіть файл", "", "Всі файли (*)")
        if path:
            self.file_path_edit.setText(path)

    def encrypt_file(self):
        file_path = self.file_path_edit.text()
        if not file_path:
            QMessageBox.warning(self, "Помилка", "Оберіть файл.")
            return
        pub_key = self._get_recipient_key()
        if not pub_key:
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Зберегти зашифрований файл",
            Path(file_path).stem + ".smsg",
            "SecureMsg файли (*.smsg);;Всі файли (*)"
        )
        if not save_path:
            return
        try:
            pkg = ce.encrypt_file(file_path, pub_key)
            Path(save_path).write_bytes(pkg)
            self.status_message.emit(
                f"✅ Файл зашифровано → {Path(save_path).name}", "ok"
            )
        except Exception as e:
            QMessageBox.critical(self, "Помилка шифрування", str(e))


# --------------------------------------------------------------------------- #
#  Вкладка «Дешифрування»                                                      #
# --------------------------------------------------------------------------- #

class DecryptTab(QWidget):
    status_message = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._key_password: str | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(label("Дешифрування", "title"))
        layout.addWidget(label(
            "Розшифруйте повідомлення або файл своїм приватним ключем.", "subtitle"
        ))

        layout.addWidget(separator())

        # --- Текст/Base64 ---
        layout.addWidget(label("Base64-рядок або вміст .smsg файлу:", "section"))
        self.cipher_input = QTextEdit()
        self.cipher_input.setPlaceholderText("Вставте зашифрований Base64-рядок сюди...")
        self.cipher_input.setMinimumHeight(100)
        layout.addWidget(self.cipher_input)

        row = QHBoxLayout()
        self.decrypt_text_btn = make_button("🔓 Розшифрувати текст", "primary")
        self.decrypt_text_btn.clicked.connect(self.decrypt_text)
        self.decrypt_text_btn.setToolTip("Розшифрувати Base64-рядок своїм приватним ключем")
        self.clear_btn = make_button("🗑 Очистити")
        self.clear_btn.clicked.connect(self.cipher_input.clear)
        self.clear_btn.setToolTip("Очистити поле введення")
        row.addWidget(self.decrypt_text_btn)
        row.addWidget(self.clear_btn)
        row.addStretch()
        layout.addLayout(row)

        layout.addWidget(separator())

        # --- Файл .smsg ---
        layout.addWidget(label("Або розшифрувати .smsg файл:", "section"))
        row2 = QHBoxLayout()
        self.smsg_path_edit = QLineEdit()
        self.smsg_path_edit.setPlaceholderText("Шлях до .smsg файлу...")
        self.smsg_path_edit.setReadOnly(True)
        browse_btn = make_button("📂 Обрати .smsg")
        browse_btn.clicked.connect(self.browse_smsg)
        row2.addWidget(self.smsg_path_edit)
        row2.addWidget(browse_btn)
        layout.addLayout(row2)

        self.decrypt_file_btn = make_button("🔓 Розшифрувати файл", "primary")
        self.decrypt_file_btn.clicked.connect(self.decrypt_file)
        layout.addWidget(self.decrypt_file_btn)

        layout.addWidget(separator())

        # --- Результат ---
        layout.addWidget(label("Розшифрований текст:", "section"))
        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setPlaceholderText("Розшифрований вміст з'явиться тут...")
        layout.addWidget(self.result_edit)

        row3 = QHBoxLayout()
        copy_btn = make_button("📋 Копіювати")
        copy_btn.clicked.connect(self.copy_result)
        save_txt_btn = make_button("💾 Зберегти як .txt")
        save_txt_btn.clicked.connect(self.save_text_result)
        row3.addWidget(copy_btn)
        row3.addWidget(save_txt_btn)
        row3.addStretch()
        layout.addLayout(row3)

    def _get_private_key(self):
        try:
            return km.load_own_private_key(self._key_password)
        except ValueError:
            # Пароль не підійшов — запитати
            pwd, ok = QInputDialog.getText(
                self, "Пароль ключа", "Введіть пароль приватного ключа:",
                QLineEdit.EchoMode.Password
            )
            if not ok:
                return None
            try:
                key = km.load_own_private_key(pwd)
                self._key_password = pwd   # кешуємо тільки після успіху
                return key
            except ValueError as e:
                self._key_password = None  # WARN1: скинути при помилці
                QMessageBox.critical(self, "Помилка", str(e))
                return None

    def copy_result(self):
        text = self.result_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status_message.emit("📋 Скопійовано", "info")

    def save_text_result(self):
        text = self.result_edit.toPlainText()
        if not text:
            QMessageBox.warning(self, "Немає даних", "Спочатку розшифруйте повідомлення.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Зберегти розшифрований текст", "message.txt",
            "Текстові файли (*.txt);;Всі файли (*)"
        )
        if path:
            Path(path).write_text(text, encoding="utf-8")
            self.status_message.emit(f"💾 Збережено: {Path(path).name}", "ok")

    def decrypt_text(self):
        b64 = self.cipher_input.toPlainText().strip()
        if not b64:
            QMessageBox.warning(self, "Помилка", "Вставте зашифрований рядок.")
            return
        priv = self._get_private_key()
        if not priv:
            return
        try:
            import base64
            pkg = base64.b64decode(b64)
            text = ce.decrypt_text(pkg, priv)
            self.result_edit.setPlainText(text)
            self.status_message.emit("✅ Розшифровано успішно", "ok")
        except Exception as e:
            QMessageBox.critical(self, "Помилка дешифрування", str(e))

    def browse_smsg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Оберіть .smsg файл", "", "SecureMsg файли (*.smsg);;Всі файли (*)"
        )
        if path:
            self.smsg_path_edit.setText(path)

    def decrypt_file(self):
        smsg_path = self.smsg_path_edit.text()
        if not smsg_path:
            QMessageBox.warning(self, "Помилка", "Оберіть .smsg файл.")
            return
        priv = self._get_private_key()
        if not priv:
            return
        try:
            pkg = Path(smsg_path).read_bytes()
            filename, content = ce.decrypt_file(pkg, priv)
        except Exception as e:
            QMessageBox.critical(self, "Помилка дешифрування", str(e))
            return

        # БАГ 2: Показати вміст у полі результату якщо це текст
        try:
            decoded_text = content.decode("utf-8")
            self.result_edit.setPlainText(decoded_text)
            self.status_message.emit(f"✅ Файл розшифровано: {filename}", "ok")
        except UnicodeDecodeError:
            self.result_edit.setPlainText(f"[Бінарний файл: {filename}, {len(content)} байт]")

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Зберегти розшифрований файл", filename, "Всі файли (*)"
        )
        if save_path:
            Path(save_path).write_bytes(content)
            self.status_message.emit(f"✅ Файл збережено: {Path(save_path).name}", "ok")


# --------------------------------------------------------------------------- #
#  Вкладка «Ключі та контакти»                                                 #
# --------------------------------------------------------------------------- #

class KeysTab(QWidget):
    status_message = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Ліва колонка: мій ключ ---
        left = QVBoxLayout()
        left.addWidget(label("Мій публічний ключ", "title"))
        left.addWidget(label(
            "Надішліть цей ключ колезі або клієнту — він зашифрує ним повідомлення для вас.", "subtitle"
        ))

        self.my_key_edit = QTextEdit()
        self.my_key_edit.setReadOnly(True)
        self.my_key_edit.setPlaceholderText("Тут буде ваш публічний ключ...")
        self.my_key_edit.setMinimumHeight(160)
        left.addWidget(self.my_key_edit)

        row_keys1 = QHBoxLayout()
        row_keys1.setSpacing(8)
        copy_key_btn = make_button("📋 Копіювати ключ", min_w=0)
        copy_key_btn.clicked.connect(self.copy_my_key)
        copy_key_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        save_key_btn = make_button("💾 Зберегти .pem", "success", min_w=0)
        save_key_btn.clicked.connect(self.save_my_key)
        save_key_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_keys1.addWidget(copy_key_btn)
        row_keys1.addWidget(save_key_btn)
        left.addLayout(row_keys1)

        row_keys2 = QHBoxLayout()
        regen_btn = make_button("🔄 Згенерувати нові ключі", "danger", min_w=0)
        regen_btn.clicked.connect(self.regenerate_keys)
        regen_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_keys2.addWidget(regen_btn)
        left.addLayout(row_keys2)

        # --- Права колонка: контакти ---
        right = QVBoxLayout()
        right.addWidget(label("Контакти", "title"))
        right.addWidget(label(
            "Публічні ключі колег та клієнтів — для шифрування повідомлень їм.", "subtitle"
        ))

        self.contacts_list = QListWidget()
        self.contacts_list.setMinimumWidth(200)
        self.contacts_list.setToolTip("Оберіть контакт для перегляду його публічного ключа")
        self.contacts_list.currentItemChanged.connect(self._on_contact_selected)
        right.addWidget(self.contacts_list)

        # Ряд 1: Додати + Видалити
        row2a = QHBoxLayout()
        row2a.setSpacing(8)
        add_btn = make_button("➕ Додати контакт", "primary", min_w=0)
        add_btn.clicked.connect(self.add_contact)
        add_btn.setToolTip("Вставити або завантажити публічний ключ (.pem) нового контакту")
        add_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        del_btn = make_button("🗑 Видалити", "danger", min_w=0)
        del_btn.clicked.connect(self.delete_contact)
        del_btn.setToolTip("Видалити обраний контакт зі списку")
        del_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row2a.addWidget(add_btn)
        row2a.addWidget(del_btn)
        right.addLayout(row2a)

        # Ряд 2: Переглянути + Зберегти .pem (активні тільки при виборі)
        row2b = QHBoxLayout()
        row2b.setSpacing(8)
        self.view_key_btn = make_button("🔍 Переглянути ключ", min_w=0)
        self.view_key_btn.clicked.connect(self.view_contact_key)
        self.view_key_btn.setToolTip("Показати публічний ключ обраного контакту у окремому вікні")
        self.view_key_btn.setEnabled(False)
        self.view_key_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.export_contact_btn = make_button("💾 Зберегти .pem", "success", min_w=0)
        self.export_contact_btn.clicked.connect(self.export_contact_key)
        self.export_contact_btn.setToolTip("Зберегти публічний ключ контакту у файл .pem")
        self.export_contact_btn.setEnabled(False)
        self.export_contact_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row2b.addWidget(self.view_key_btn)
        row2b.addWidget(self.export_contact_btn)
        right.addLayout(row2b)

        # Панель перегляду ключа контакту
        right.addWidget(label("Публічний ключ контакту:", "section"))
        self.contact_key_edit = QTextEdit()
        self.contact_key_edit.setReadOnly(True)
        self.contact_key_edit.setPlaceholderText("Оберіть контакт зі списку щоб побачити його ключ...")
        self.contact_key_edit.setMinimumHeight(120)
        right.addWidget(self.contact_key_edit)

        copy_contact_key_btn = make_button("📋 Копіювати ключ контакту", min_w=0)
        copy_contact_key_btn.clicked.connect(self.copy_contact_key)
        copy_contact_key_btn.setToolTip("Скопіювати публічний ключ обраного контакту")
        copy_contact_key_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        right.addWidget(copy_contact_key_btn)

        hint_lbl = QLabel('Щоб отримати ключ від колеги: попросіть натиснути "Зберегти .pem" і передати файл.')
        hint_lbl.setObjectName("subtitle")
        hint_lbl.setWordWrap(True)
        right.addWidget(hint_lbl)

        layout.addLayout(left, 55)
        layout.addLayout(right, 45)

    def refresh(self):
        try:
            pem = km.get_own_public_key_pem()
            self.my_key_edit.setPlainText(pem)
        except Exception:
            self.my_key_edit.setPlainText("")
        self.refresh_contacts()

    def refresh_contacts(self):
        self.contacts_list.clear()
        for name in km.list_contacts():
            self.contacts_list.addItem(name)

    def copy_my_key(self):
        key = self.my_key_edit.toPlainText()
        if key:
            QApplication.clipboard().setText(key)
            self.status_message.emit("📋 Публічний ключ скопійовано", "info")

    def save_my_key(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Зберегти публічний ключ", "my_public_key.pem",
            "PEM файли (*.pem);;Всі файли (*)"
        )
        if path:
            Path(path).write_text(self.my_key_edit.toPlainText())
            self.status_message.emit(f"💾 Ключ збережено: {Path(path).name}", "ok")

    def regenerate_keys(self):
        reply = QMessageBox.warning(
            self, "Увага!",
            "Генерація нових ключів зробить недійсними всі раніше зашифровані дані.\n"
            "Продовжити?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            dlg = FirstRunDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                km.create_own_keys(dlg.get_password())
                self.refresh()
                self.status_message.emit("🔑 Нові ключі згенеровано", "ok")

    def add_contact(self):
        dlg = AddContactDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, pem = dlg.get_data()
            km.save_contact(name, pem)
            self.refresh_contacts()
            self.status_message.emit(f"✅ Контакт «{name}» додано", "ok")

    def _on_contact_selected(self, current, previous):
        has = current is not None
        self.view_key_btn.setEnabled(has)
        self.export_contact_btn.setEnabled(has)
        if has:
            try:
                pem = km.get_contact_pem(current.text())
                self.contact_key_edit.setPlainText(pem)
            except Exception as e:
                self.contact_key_edit.setPlainText(f"Помилка завантаження: {e}")
        else:
            self.contact_key_edit.setPlainText("")

    def view_contact_key(self):
        item = self.contacts_list.currentItem()
        if not item:
            return
        name = item.text()
        try:
            pem = km.get_contact_pem(name)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", str(e))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Публічний ключ: {name}")
        dlg.setMinimumWidth(520)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)
        lay.addWidget(label(f"Публічний ключ контакту «{name}»", "title"))
        lay.addWidget(label("RSA-2048 Public Key (PEM)", "subtitle"))
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(pem)
        txt.setMinimumHeight(220)
        txt.setStyleSheet("font-family: monospace; font-size: 11px;")
        lay.addWidget(txt)
        row = QHBoxLayout()
        copy_btn = make_button("📋 Копіювати")
        copy_btn.clicked.connect(lambda: (
            QApplication.clipboard().setText(pem),
            self.status_message.emit(f"📋 Ключ {name} скопійовано", "info")
        ))
        save_btn = make_button("💾 Зберегти .pem", "success")
        save_btn.clicked.connect(lambda: self._save_contact_pem(name, pem))
        close_btn = make_button("Закрити")
        close_btn.clicked.connect(dlg.accept)
        row.addWidget(copy_btn)
        row.addWidget(save_btn)
        row.addStretch()
        row.addWidget(close_btn)
        lay.addLayout(row)
        dlg.setStyleSheet(self.window().styleSheet())
        dlg.exec()

    def _save_contact_pem(self, name, pem):
        path, _ = QFileDialog.getSaveFileName(
            self, "Зберегти публічний ключ", f"{name}.pem",
            "PEM файли (*.pem);;Всі файли (*)"
        )
        if path:
            Path(path).write_text(pem)
            self.status_message.emit(f"💾 Ключ {name} збережено", "ok")

    def export_contact_key(self):
        item = self.contacts_list.currentItem()
        if not item:
            return
        name = item.text()
        try:
            pem = km.get_contact_pem(name)
            self._save_contact_pem(name, pem)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", str(e))

    def copy_contact_key(self):
        pem = self.contact_key_edit.toPlainText()
        if pem:
            QApplication.clipboard().setText(pem)
            item = self.contacts_list.currentItem()
            name = item.text() if item else "контакту"
            self.status_message.emit(f"📋 Ключ {name} скопійовано", "info")

    def delete_contact(self):
        item = self.contacts_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Помилка", "Оберіть контакт зі списку.")
            return
        name = item.text()
        reply = QMessageBox.question(
            self, "Підтвердження",
            f"Видалити контакт «{name}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            km.delete_contact(name)
            self.contact_key_edit.setPlainText("")
            self.refresh_contacts()
            self.status_message.emit(f"🗑 Контакт «{name}» видалено", "info")



# --------------------------------------------------------------------------- #
#  Вкладка «Про програму»                                                      #
# --------------------------------------------------------------------------- #

class AboutTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()

        inner = QVBoxLayout()
        inner.setSpacing(6)
        inner.setContentsMargins(40, 24, 40, 24)

        # Логотип / заголовок
        logo_lbl = QLabel("🔐")
        logo_lbl.setStyleSheet("font-size: 52px;")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(logo_lbl)

        app_name = QLabel("SecureMsg")
        app_name.setStyleSheet("font-size: 28px; font-weight: 700; color: #e94560;")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(app_name)

        app_sub = QLabel("Захищений обмін повідомленнями")
        app_sub.setStyleSheet("font-size: 13px; color: #707090;")
        app_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(app_sub)

        inner.addSpacing(16)

        # Роздільник
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("background: #2d2d4e; max-height: 1px; margin: 0 80px;")
        inner.addWidget(sep1)

        inner.addSpacing(16)

        # Автор
        author_title = QLabel("Розробник")
        author_title.setStyleSheet("font-size: 11px; color: #707090; font-weight: 600; letter-spacing: 1px;")
        author_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(author_title)

        author_name = QLabel("Суденко Богдан Олександрович")
        author_name.setStyleSheet("font-size: 18px; font-weight: 700; color: #e0e0e0;")
        author_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(author_name)

        group_lbl = QLabel("Студент групи 401-ТН")
        group_lbl.setStyleSheet("font-size: 13px; color: #a0a0c0;")
        group_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(group_lbl)

        inner.addSpacing(6)

        place_lbl = QLabel("Полтава, 2026")
        place_lbl.setStyleSheet("font-size: 13px; color: #707090;")
        place_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(place_lbl)

        inner.addSpacing(24)

        # Роздільник
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background: #2d2d4e; max-height: 1px; margin: 0 80px;")
        inner.addWidget(sep2)

        inner.addSpacing(16)

        # Технічна інформація
        tech_title = QLabel("Технології шифрування")
        tech_title.setStyleSheet("font-size: 11px; color: #707090; font-weight: 600; letter-spacing: 1px;")
        tech_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(tech_title)

        tech_info = QLabel("RSA-2048 (OAEP/SHA-256) + AES-256-GCM")
        tech_info.setStyleSheet("font-size: 14px; color: #4ecca3; font-family: monospace;")
        tech_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(tech_info)

        tech_desc = QLabel(
            "Гібридна схема: RSA шифрує одноразовий сесійний ключ,\n"
            "AES-GCM шифрує дані з автентифікацією цілісності."
        )
        tech_desc.setStyleSheet("font-size: 11px; color: #707090; line-height: 160%;")
        tech_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(tech_desc)

        inner.addSpacing(16)

        # Бібліотеки
        libs_lbl = QLabel("PyQt6 • cryptography • Python 3.11+")
        libs_lbl.setStyleSheet("font-size: 11px; color: #505070;")
        libs_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(libs_lbl)

        outer.addLayout(inner)
        outer.addStretch()

# --------------------------------------------------------------------------- #
#  Головне вікно                                                               #
# --------------------------------------------------------------------------- #

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SecureMsg — Захищений обмін повідомленнями")
        self.setMinimumSize(860, 640)
        self.resize(980, 720)
        self.setStyleSheet(DARK_STYLESHEET)

        self._setup_ui()
        self._first_run_check()
        self._refresh_all()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Заголовок
        header = QWidget()
        header.setStyleSheet("background-color: #0f3460; padding: 12px 20px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)
        title_lbl = QLabel("🔐 SecureMsg")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #e94560;")
        subtitle_lbl = QLabel("RSA-2048 + AES-256-GCM | Weatherford Ukraine")
        subtitle_lbl.setStyleSheet("font-size: 11px; color: #707090;")
        header_layout.addWidget(title_lbl)
        header_layout.addWidget(subtitle_lbl)
        header_layout.addStretch()
        main_layout.addWidget(header)

        # Вкладки
        self.tabs = QTabWidget()
        self.encrypt_tab = EncryptTab()
        self.decrypt_tab = DecryptTab()
        self.keys_tab = KeysTab()
        self.about_tab = AboutTab()

        self.tabs.addTab(self.encrypt_tab, "🔒  Шифрування")
        self.tabs.addTab(self.decrypt_tab, "🔓  Дешифрування")
        self.tabs.addTab(self.keys_tab, "🔑  Ключі та контакти")
        self.tabs.addTab(self.about_tab, "ℹ  Про програму")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 0)
        content_layout.addWidget(self.tabs)
        main_layout.addWidget(content)

        # Статусний рядок
        self.status_bar_label = QLabel("Готово")
        self.status_bar_label.setStyleSheet(
            "padding: 6px 20px; background: #0d1b2a; color: #707090; font-size: 11px;"
        )
        main_layout.addWidget(self.status_bar_label)

        # Підключення сигналів статусу
        for tab in (self.encrypt_tab, self.decrypt_tab, self.keys_tab):
            tab.status_message.connect(self._show_status)

    def _on_tab_changed(self, index):
        if index == 0:
            self.encrypt_tab.refresh_contacts()
        elif index == 2:
            self.keys_tab.refresh()

    def _first_run_check(self):
        if not km.has_own_keys():
            dlg = FirstRunDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                km.create_own_keys(dlg.get_password())
            else:
                QMessageBox.critical(
                    self, "Помилка",
                    "Без ключів SecureMsg не може працювати. Перезапустіть програму."
                )
                # БАГ 4: закрити програму після відмови
                QTimer.singleShot(0, self.close)

    def _refresh_all(self):
        self.encrypt_tab.refresh_contacts()
        self.keys_tab.refresh()

    def _show_status(self, message: str, level: str):
        colors = {"ok": "#4ecca3", "error": "#ff6b81", "info": "#a0a0d0"}
        color = colors.get(level, "#a0a0d0")
        self.status_bar_label.setStyleSheet(
            f"padding: 6px 20px; background: #0d1b2a; color: {color}; font-size: 11px;"
        )
        self.status_bar_label.setText(message)


# --------------------------------------------------------------------------- #
#  Точка входу                                                                 #
# --------------------------------------------------------------------------- #

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SecureMsg")
    app.setOrganizationName("Weatherford Ukraine")

    # БАГ 1: встановити іконку програми (файл icon.png або icon.ico поруч з main.py)
    _icon_candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"),
    ]
    for _icon_path in _icon_candidates:
        if os.path.exists(_icon_path):
            app.setWindowIcon(QIcon(_icon_path))
            break

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
