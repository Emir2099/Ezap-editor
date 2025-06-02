import sys
import subprocess
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QPlainTextEdit, QFileDialog, QMessageBox, QDockWidget, QSplitter, QToolBar, QAction, QWidget, QInputDialog, QProgressBar, QTableWidget, QPushButton, QTableWidgetItem, QVBoxLayout, QFileSystemModel, QTreeView, QDialog, QLineEdit, QListWidget, QListWidgetItem, QSlider, QLabel, QHBoxLayout, QComboBox, QShortcut, QProgressDialog, QGraphicsOpacityEffect, QListView, QAbstractItemView
)
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QKeySequence
from PyQt5.QtCore import Qt, QProcess, QSize, QThread, pyqtSignal, QPropertyAnimation, QTimer
import qtawesome as qta
import os
import time
import glob

from editor.code_editor import CodeEditor
from editor.output import QtHandler, StreamToLogger
from utils.helpers import validate_input, confirm_action, show_error_message, extract_error_line

class CommandPalette(QDialog):
    def __init__(self, parent, actions):
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setStyleSheet("QDialog { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #181c2a, stop:1 #00c896); border: 2px solid #00c896; border-radius: 18px; } QLineEdit { font-size: 18px; padding: 8px; border-radius: 8px; background: #23263a; color: #fff; border: 1px solid #00c896; } QListWidget { font-size: 16px; border-radius: 8px; background: #23263a; color: #fff; }")
        self.setFixedWidth(400)
        self.setFixedHeight(320)
        layout = QVBoxLayout(self)
        # Close button row
        close_btn_layout = QHBoxLayout()
        close_btn_layout.addStretch()
        close_btn = QPushButton("✕", self)
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("QPushButton { background: transparent; color: #fff; font-size: 18px; border: none; } QPushButton:hover { color: #00c896; }")
        close_btn.clicked.connect(self.reject)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Close (Esc)")
        close_btn_layout.addWidget(close_btn)
        layout.addLayout(close_btn_layout)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Type a command...")
        self.list = QListWidget(self)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        self.actions = actions
        self.filtered = list(actions.keys())
        self.update_list()
        self.search.textChanged.connect(self.filter_list)
        self.search.returnPressed.connect(self.trigger_selected)
        self.list.itemActivated.connect(self.trigger_selected)
        self.list.itemClicked.connect(self.trigger_selected)
        # Sci-fi glow effect
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(350)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.start()

    def filter_list(self, text):
        self.filtered = [k for k in self.actions if text.lower() in k.lower()]
        self.update_list()

    def update_list(self):
        self.list.clear()
        for k in self.filtered:
            item = QListWidgetItem(k)
            self.list.addItem(item)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def trigger_selected(self):
        if self.list.currentRow() >= 0:
            action = self.filtered[self.list.currentRow()]
            self.actions[action]()
            self.accept()

    def accept(self):
        # Fade out on close
        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(250)
        self.anim.setStartValue(1)
        self.anim.setEndValue(0)
        self.anim.finished.connect(super().accept)
        self.anim.start()

    def reject(self):
        print('Command palette closed')  # Debug print
        super().reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

class SettingsDialog(QDialog):
    def __init__(self, parent, current_font_size, current_theme):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setFixedWidth(350)
        self.setFixedHeight(200)
        self.setStyleSheet("QDialog { background: #f8fafc; border-radius: 12px; } QLabel { font-size: 16px; } QSlider { min-width: 150px; } QComboBox { font-size: 15px; border-radius: 8px; padding: 4px; }")
        layout = QVBoxLayout(self)
        # Theme
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText(current_theme)
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        # Font size
        font_layout = QHBoxLayout()
        font_label = QLabel("Font Size:")
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setMinimum(10)
        self.font_slider.setMaximum(28)
        self.font_slider.setValue(current_font_size)
        self.font_value = QLabel(str(current_font_size))
        self.font_slider.valueChanged.connect(lambda v: self.font_value.setText(str(v)))
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.font_slider)
        font_layout.addWidget(self.font_value)
        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        # Add to main layout
        layout.addLayout(theme_layout)
        layout.addLayout(font_layout)
        layout.addStretch()
        layout.addLayout(btn_layout)

    def get_settings(self):
        return self.theme_combo.currentText(), self.font_slider.value()

class PackageListWorker(QThread):
    result = pyqtSignal(str)
    def run(self):
        import subprocess
        process = subprocess.Popen('pip list --format=columns', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        self.result.emit(stdout)

class QuickFileSwitcher(QDialog):
    def __init__(self, parent, root_path):
        super().__init__(parent)
        self.setWindowTitle("Quick File Switcher")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setStyleSheet("QDialog { background: #23263a; border: 2px solid #00c896; border-radius: 16px; } QListWidget { background: #23263a; color: #fff; font-size: 16px; border-radius: 8px; }")
        self.setFixedWidth(400)
        self.setFixedHeight(320)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)
        # Recursively find all .py files
        py_files = [os.path.relpath(f, root_path) for f in glob.glob(os.path.join(root_path, '**', '*.py'), recursive=True)]
        self.list_widget.addItems(py_files)
        self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(self.accept)
        self.list_widget.installEventFilter(self)
        # Touchpad scroll is supported by default

    def eventFilter(self, obj, event):
        if obj is self.list_widget and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self.accept()
                return True
        return super().eventFilter(obj, event)

    def selected_file(self):
        item = self.list_widget.currentItem()
        if item:
            return os.path.abspath(item.text())
        return None

class EZCode(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_path = ''
        self.log_capture = False
        self.debugging = False
        self.pdb = None
        self.notification_label = None
        self.run_process = None
        self.stop_action = None
        self.init_ui()

        # Add a logging handler
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.qt_handler = QtHandler(self.output)
        self.qt_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.qt_handler.setFormatter(formatter)
        self.logger.addHandler(self.qt_handler)

        self.create_package_actions()
        # Initialize other variables and widgets
        # self.setup_package_management()
        self.setup_command_palette()
        self.setup_file_explorer_shortcut()
        self.setup_quick_file_switcher()

    def init_ui(self):
        self.setWindowTitle('EZap Editor')
        self.setGeometry(100, 100, 1100, 850)

        self.editor = CodeEditor()
        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)

        # File Explorer Panel
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(os.getcwd())
        self.file_model.setNameFilters(["*.py"])
        self.file_model.setNameFilterDisables(False)
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(os.getcwd()))
        self.file_tree.setColumnHidden(1, True)
        self.file_tree.setColumnHidden(2, True)
        self.file_tree.setColumnHidden(3, True)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setStyleSheet("QTreeView { background: #f4f7fa; border-radius: 10px; font-size: 15px; } QTreeView::item:selected { background: #e0e7ef; color: #00c896; }")
        self.file_tree.clicked.connect(self.open_file_from_explorer)
        self.file_tree.setMinimumWidth(220)

        self.dock_file_explorer = QDockWidget("File Explorer", self)
        self.dock_file_explorer.setWidget(self.file_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_file_explorer)

        self.dock_output = QDockWidget("Output Console", self)
        self.dock_output.setWidget(self.output)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_output)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.editor)
        self.editor.setMinimumHeight(400)
        self.output.setMinimumHeight(200)
        self.splitter.addWidget(self.dock_output)
        self.splitter.setSizes([600, 200])
        self.setCentralWidget(self.splitter)

        self.create_toolbar()
        self.create_menu()
        self.create_status_bar()
        self.apply_modern_stylesheet()
        self.set_light_mode()
        self.show_welcome_if_no_file()
        self.show()

    def create_toolbar(self, mode='light'):
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setIconSize(QSize(32, 32))
        self.toolbar.setStyleSheet("QToolBar { spacing: 12px; border-radius: 12px; padding: 8px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f8fafc, stop:1 #e0e7ef); }")
        self.addToolBar(self.toolbar)
        color = '#222' if mode == "light" else '#f8f8f2'
        color_active = '#00c896' if mode == 'light' else '#80c0ff'

        open_action = QAction(qta.icon('fa.folder-open', color=color, color_active=color_active), "Open", self)
        open_action.setShortcut('Ctrl+O')
        open_action.setToolTip("Open File (Ctrl+O)")
        open_action.triggered.connect(self.open_file)
        save_action = QAction(qta.icon('fa.save', color=color, color_active=color_active), "Save", self)
        save_action.setShortcut('Ctrl+S')
        save_action.setToolTip("Save File (Ctrl+S)")
        save_action.triggered.connect(self.save_file)
        run_action = QAction(qta.icon('fa.play-circle', color='#00c896', color_active='#00e6b8'), "Run", self)
        run_action.setShortcut('F5')
        run_action.setToolTip("Run Code (F5)")
        run_action.triggered.connect(self.run_code)
        debug_action = QAction(qta.icon('fa.bug', color='#e67e22', color_active='#f39c12'), "Debug", self)
        debug_action.setShortcut('F9')
        debug_action.setToolTip("Toggle Debug Mode (F9)")
        debug_action.triggered.connect(self.toggle_debugging_mode)

        self.toolbar.addAction(open_action)
        self.toolbar.addAction(save_action)
        self.toolbar.addAction(run_action)
        self.toolbar.addAction(debug_action)

    def create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu('File')
        open_action = QAction('Open', self)
        open_action.setShortcut('Ctrl+O')
        open_action.setToolTip('Open File (Ctrl+O)')
        open_action.triggered.connect(self.open_file)
        save_action = QAction('Save', self)
        save_action.setShortcut('Ctrl+S')
        save_action.setToolTip('Save File (Ctrl+S)')
        save_action.triggered.connect(self.save_file)
        save_as_action = QAction('Save As', self)
        save_as_action.setToolTip('Save As')
        save_as_action.triggered.connect(self.save_as)
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setToolTip('Exit (Ctrl+Q)')
        exit_action.triggered.connect(self.close)

        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addAction(exit_action)

        run_menu = menubar.addMenu('Run')
        run_action = QAction('Run', self)
        run_action.setShortcut('F5')
        run_action.setToolTip('Run Code (F5)')
        run_action.triggered.connect(self.run_code)
        run_menu.addAction(run_action)

        debug_menu = menubar.addMenu('Debug')
        debug_action = QAction('Debug', self)
        debug_action.setShortcut('F9')
        debug_action.setToolTip('Toggle Debug Mode (F9)')
        debug_action.triggered.connect(self.toggle_debugging_mode)

        debug_menu.addAction(debug_action)

        view_menu = menubar.addMenu('View')
        toggle_output_action = QAction('Toggle Output Console', self)
        toggle_output_action.triggered.connect(self.toggle_output_console)
        view_menu.addAction(toggle_output_action)
        reset_layout_action = QAction('Reset Layout', self)
        reset_layout_action.triggered.connect(self.reset_layout)
        view_menu.addAction(reset_layout_action)
        clear_output_action = QAction('Clear Output Console', self)
        clear_output_action.triggered.connect(self.clear_output_console)
        view_menu.addAction(clear_output_action)

        settings_menu = menubar.addMenu('Settings')
        light_mode_action = QAction('Light Mode', self)
        light_mode_action.triggered.connect(self.set_light_mode)
        dark_mode_action = QAction('Dark Mode', self)
        dark_mode_action.triggered.connect(self.set_dark_mode)
        settings_menu.addAction(light_mode_action)
        settings_menu.addAction(dark_mode_action)
        settings_action = QAction('Settings...', self)
        settings_action.triggered.connect(self.show_settings_dialog)
        settings_menu.addAction(settings_action)
        # console_log_action = QAction('Console Log', self, checkable=True)
        # console_log_action.setChecked(self.log_capture)
        # console_log_action.triggered.connect(self.toggle_console_log)
        # settings_menu.addAction(console_log_action)

    def create_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        # Font size slider
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setMinimum(10)
        self.font_slider.setMaximum(28)
        self.font_slider.setValue(self.editor.font().pointSize())
        self.font_slider.setFixedWidth(100)
        self.font_slider.setToolTip("Font Size")
        self.font_slider.valueChanged.connect(self.set_editor_font_size)
        self.status_bar.addPermanentWidget(QLabel("Font Size:"))
        self.status_bar.addPermanentWidget(self.font_slider)

    def set_editor_font_size(self, value):
        self.editor.setFont(QFont("Courier", value))

    def open_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Python File", "", "Python Files (*.py);;All Files (*)", options=options)
        if file_path:
            with open(file_path, 'r') as file:
                self.editor.setPlainText(file.read())
                self.file_path = file_path
            self.status_bar.showMessage(f"Opened: {file_path}")
        else:
            self.show_welcome_if_no_file()

    def save_file(self):
        if not self.file_path:
            self.save_as()
        else:
            with open(self.file_path, 'w') as file:
                code = self.editor.toPlainText()
                file.write(code)
            self.status_bar.showMessage(f"Saved: {self.file_path}")
            self.show_notification("File saved!")

    def save_as(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Python File", "", "Python Files (*.py);;All Files (*)", options=options)
        if file_path:
            with open(file_path, 'w') as file:
                code = self.editor.toPlainText()
                file.write(code)
                self.file_path = file_path
            self.status_bar.showMessage(f"Saved as: {file_path}")
            self.show_notification("File saved!")

    def run_code(self):
        if self.run_process is not None:
            self.show_notification("A script is already running!")
            return
        if self.debugging:
            self.stop_debugging()
        code = self.editor.toPlainText()
        self.output.clear()
        # Write code to a temp file
        import tempfile
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.py', mode='w', encoding='utf-8')
        self.temp_file.write(code)
        self.temp_file.close()
        # Start QProcess
        self.run_process = QProcess(self)
        self.run_process.setProcessChannelMode(QProcess.MergedChannels)
        self.run_process.readyReadStandardOutput.connect(self.handle_run_stdout)
        self.run_process.readyReadStandardError.connect(self.handle_run_stderr)
        self.run_process.finished.connect(self.handle_run_finished)
        self.run_process.start(sys.executable, [self.temp_file.name])
        # Add Stop button
        if not self.stop_action:
            self.stop_action = QAction(qta.icon('fa.stop', color='#e74c3c'), "Stop", self)
            self.stop_action.setToolTip("Stop Running Script")
            self.stop_action.triggered.connect(self.stop_run_code)
            self.toolbar.addAction(self.stop_action)
        self.status_bar.showMessage("Running script...")

    def handle_run_stdout(self):
        output = self.run_process.readAllStandardOutput().data().decode(errors='replace')
        self.output.moveCursor(QTextCursor.End)
        self.output.insertPlainText(output)
        self.output.moveCursor(QTextCursor.End)

    def handle_run_stderr(self):
        error = self.run_process.readAllStandardError().data().decode(errors='replace')
        self.output.moveCursor(QTextCursor.End)
        self.output.insertPlainText(error)
        self.output.moveCursor(QTextCursor.End)

    def handle_run_finished(self):
        self.status_bar.showMessage("Execution finished")
        if self.stop_action:
            self.toolbar.removeAction(self.stop_action)
            self.stop_action = None
        self.run_process = None
        import os
        if hasattr(self, 'temp_file'):
            try:
                os.unlink(self.temp_file.name)
            except Exception:
                pass

    def stop_run_code(self):
        if self.run_process:
            self.run_process.kill()
            self.status_bar.showMessage("Script stopped.")
            self.show_notification("Script stopped!")

    def toggle_debugging_mode(self):
        self.editor.toggle_debugging_mode()
        self.status_bar.showMessage("Debugging mode " + ("enabled" if self.editor.debugging_mode else "disabled"))

    def set_light_mode(self):
        self.editor.setStyleSheet("QPlainTextEdit { background-color: white; color: black; }")
        self.output.setStyleSheet("QPlainTextEdit { background-color: white; color: black; }")
        self.setStyleSheet("QWidget { background-color: white; color: black; }")
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #cccccc; }")
        self.removeToolBar(self.toolbar)
        self.create_toolbar(mode='light')

    def set_dark_mode(self):
        self.editor.setStyleSheet("QPlainTextEdit { background-color: #2b2b2b; color: #f8f8f2; }")
        self.output.setStyleSheet("QPlainTextEdit { background-color: #2b2b2b; color: #f8f8f2; }")
        self.setStyleSheet("QWidget { background-color: #2b2b2b; color: #f8f8f2; }")
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #3f3f3f; }")
        self.removeToolBar(self.toolbar)
        self.create_toolbar(mode='dark')

    def toggle_output_console(self):
        if self.dock_output.isVisible():
            self.dock_output.hide()
        else:
            self.dock_output.show()

    def reset_layout(self):
        self.removeToolBar(self.toolbar)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        self.toolbar.show()

        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_output)
        self.dock_output.show()

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Close', 'Are you sure you want to quit?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def apply_modern_stylesheet(self):
        self.setStyleSheet("""
        QMainWindow {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #181c2a, stop:1 #23263a);
        }
        QMenuBar {
            background: rgba(24,28,42,0.95);
            color: #00c896;
            font-size: 15px;
            border-radius: 8px;
        }
        QMenuBar::item {
            background: transparent;
            color: #00c896;
            padding: 6px 18px;
            border-radius: 8px;
        }
        QMenuBar::item:selected {
            background: #23263a;
            color: #fff;
        }
        QMenu {
            background: rgba(24,28,42,0.98);
            color: #00c896;
            font-size: 15px;
            border-radius: 8px;
        }
        QMenu::item {
            padding: 6px 18px;
            border-radius: 8px;
        }
        QMenu::item:selected {
            background: #23263a;
            color: #fff;
        }
        QToolBar {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #23263a, stop:1 #00c896);
            border-radius: 16px;
            spacing: 12px;
            border: 2px solid #00c896;
        }
        QToolButton {
            background: rgba(24,28,42,0.8);
            border-radius: 12px;
            padding: 8px;
            color: #00c896;
            border: 1.5px solid #00c896;
        }
        QToolButton:hover {
            background: #00c896;
            color: #fff;
        }
        QStatusBar {
            background: #181c2a;
            color: #00c896;
            font-size: 14px;
            border-radius: 8px;
        }
        QDockWidget {
            background: rgba(24,28,42,0.95);
            border-radius: 16px;
            border: 2px solid #00c896;
        }
        QPlainTextEdit {
            background: #23263a;
            color: #fff;
            font-family: 'Fira Mono', 'Consolas', 'Courier New', monospace;
            font-size: 16px;
            border-radius: 12px;
            padding: 8px;
            border: 1.5px solid #00c896;
        }
        QSplitter::handle {
            background: #00c896;
        }
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00c896, stop:1 #23263a);
            color: #fff;
            border-radius: 12px;
            padding: 8px 18px;
            font-size: 15px;
            border: 2px solid #00c896;
        }
        QPushButton:hover {
            background: #00c896;
            color: #23263a;
        }
        QTableWidget {
            background: #23263a;
            border-radius: 12px;
            font-size: 15px;
            color: #fff;
            border: 1.5px solid #00c896;
        }
        QHeaderView::section {
            background: #00c896;
            color: #23263a;
            border-radius: 8px;
            font-size: 15px;
        }
        QMessageBox {
            background: #23263a;
            color: #00c896;
            border-radius: 16px;
        }
        """)

    def toggle_console_log(self, checked):
        self.log_capture = checked
        if checked:
            logging.getLogger().addHandler(self.qt_handler)
        else:
            logging.getLogger().removeHandler(self.qt_handler)

    def setup_package_management(self):
        self.package_dock = QDockWidget("Package Viewer", self)
        self.package_widget = QWidget()
        self.package_layout = QVBoxLayout(self.package_widget)

        # self.show_packages_button = QPushButton('Show Installed Packages')
        # self.show_packages_button.clicked.connect(self.show_installed_packages)
        # self.package_layout.addWidget(self.show_packages_button)

        self.package_table = QTableWidget()
        self.package_table.setColumnCount(2)
        self.package_table.setHorizontalHeaderLabels(['Package', 'Version'])
        self.package_layout.addWidget(self.package_table)

        self.package_dock.setWidget(self.package_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.package_dock)
        
        # self.create_package_actions()
        

    def create_package_actions(self):
        # Create actions for package management
        install_action = QAction('Install Package', self)
        install_action.triggered.connect(self.install_package)

        uninstall_action = QAction('Uninstall Package', self)
        uninstall_action.triggered.connect(self.uninstall_package)

        show_installed_action = QAction('Show Installed Packages', self)
        show_installed_action.triggered.connect(self.show_installed_packages)

        # Add these actions to a menu or toolbar as needed
        package_menu = self.menuBar().addMenu('Package')
        package_menu.addAction(install_action)
        package_menu.addAction(uninstall_action)
        package_menu.addAction(show_installed_action)

    def install_package(self):
        self.output.clear()
        package_name, ok = QInputDialog.getText(self, 'Install Package', 'Enter package name:')
        if ok:
            if validate_input(package_name, self):
                if confirm_action(f'install {package_name}', self):
                    self.execute_command_async(f'pip install {package_name}')

    def uninstall_package(self):
        self.output.clear()
        package_name, ok = QInputDialog.getText(self, 'Uninstall Package', 'Enter package name:')
        if ok:
            if validate_input(package_name, self):
                if confirm_action(f'uninstall {package_name}', self):
                    self.execute_command_async(f'pip uninstall {package_name}')
        else:
            self.write_text_to_output("Uninstallation cancelled")

    def execute_command_async(self, command):
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_command_finished)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)  # Set indeterminate mode
        self.statusBar().addWidget(self.progress_bar)
        self.progress_bar.show()

        self.process.start(command)
        
        
    def clear_output_console(self):
        self.output.clear()
    
    def handle_stdout(self):
        output = self.process.readAllStandardOutput().data().decode().strip()
        self.write_text_to_output(output)

        # Check if the output contains a prompt that requires user input
        if "Proceed (Y/n)?" in output:
            self.get_user_input()
            
    def get_user_input(self):
        # Allow user to input response directly into the output console
        response, ok = QInputDialog.getText(self, 'User Input Required', 'Input required (Y/N):')
        # Check if the response is not one of the valid options
        if response not in ["Y", "N", "y", "n"]:
            self.write_text_to_output("Command terminated.\nResponse is " + response)
            self.process.kill()
            return  # Exit the function to avoid further processing

        if ok:
            # Send user response as input to the ongoing process if response is "Y" or "y"
            if response in ["Y", "y"]:
                self.process.write((response + '\n').encode())
            else:
                self.write_text_to_output("Uninstallation canceled!")
                self.process.kill()
        else:
            self.write_text_to_output("Uninstallation canceled!")
            self.process.kill()

    def handle_stderr(self):
        error = self.process.readAllStandardError().data().decode().strip()
        self.write_text_to_output(error)

    def handle_command_finished(self):
        self.progress_bar.deleteLater()
        self.process.deleteLater()
        self.statusBar().clearMessage()  # Clear status bar message if any
        # self.show_installed_packages()  # Update GUI as needed after command completion

    def show_installed_packages(self):
        self.setup_package_management()
        self.package_table.clearContents()
        self.package_table.setRowCount(0)
        # Show loading spinner overlay
        self.loading_dialog = QProgressDialog("Loading installed packages...", None, 0, 0, self)
        self.loading_dialog.setWindowModality(Qt.ApplicationModal)
        self.loading_dialog.setCancelButton(None)
        self.loading_dialog.setMinimumDuration(0)
        self.loading_dialog.setStyleSheet("QProgressDialog { background: #222; color: #fff; border-radius: 12px; font-size: 16px; }")
        self.loading_dialog.show()
        # Start worker thread
        self.pkg_worker = PackageListWorker()
        self.pkg_worker.result.connect(self.on_packages_loaded)
        self.pkg_worker.start()

    def on_packages_loaded(self, installed_packages):
        self.loading_dialog.close()
        self.package_table.clearContents()
        self.package_table.setRowCount(0)
        lines = installed_packages.splitlines()[2:]
        for line in lines:
            package_info = line.split()
            if len(package_info) >= 2:
                package_name = package_info[0]
                package_version = package_info[1]
                row_position = self.package_table.rowCount()
                self.package_table.insertRow(row_position)
                self.package_table.setItem(row_position, 0, QTableWidgetItem(package_name))
                self.package_table.setItem(row_position, 1, QTableWidgetItem(package_version))

    def execute_command(self, command):
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        return stdout

    def write_text_to_output(self, text):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)

        if not self.output.toPlainText().endswith('\n'):
            cursor.insertText('\n')

        cursor.insertText(text + '\n')
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def open_file_from_explorer(self, index):
        file_path = self.file_model.filePath(index)
        if os.path.isfile(file_path):
            with open(file_path, 'r') as file:
                self.editor.setPlainText(file.read())
                self.file_path = file_path
            self.status_bar.showMessage(f"Opened: {file_path}") 

    def setup_command_palette(self):
        self.palette_actions = {
            "Open File": self.open_file,
            "Save File": self.save_file,
            "Save As": self.save_as,
            "Run Code": self.run_code,
            "Toggle Debug Mode": self.toggle_debugging_mode,
            "Light Mode": self.set_light_mode,
            "Dark Mode": self.set_dark_mode,
            "Show Installed Packages": self.show_installed_packages,
            "Install Package": self.install_package,
            "Uninstall Package": self.uninstall_package,
            "Clear Output Console": self.clear_output_console,
            "Reset Layout": self.reset_layout,
            "Toggle Output Console": self.toggle_output_console,
            "Exit": self.close,
            "Settings...": self.show_settings_dialog,
        }
        self.palette_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        self.palette_shortcut.activated.connect(self.show_command_palette)

    def show_command_palette(self):
        dlg = CommandPalette(self, self.palette_actions)
        dlg.move(self.geometry().center() - dlg.rect().center())
        dlg.exec_() 

    def show_settings_dialog(self):
        current_theme = "Light" if self.editor.palette().color(self.editor.backgroundRole()).lightness() > 128 else "Dark"
        dlg = SettingsDialog(self, self.editor.font().pointSize(), current_theme)
        if dlg.exec_() == QDialog.Accepted:
            theme, font_size = dlg.get_settings()
            if theme == "Light":
                self.set_light_mode()
            else:
                self.set_dark_mode()
            self.editor.setFont(QFont("Courier", font_size)) 

    def show_welcome_if_no_file(self):
        if not self.file_path:
            welcome = (
                "Welcome to EZap Editor!\n"
                "\n"
                "- Open or create a Python file to get started.\n"
                "- Ctrl+O: Open File\n"
                "- Ctrl+S: Save File\n"
                "- F5: Run Code\n"
                "- Ctrl+Shift+P: Command Palette\n"
                "- Use the left panel to browse your files.\n"
                "- Switch themes and font size in Settings.\n"
                "\nHappy coding! 🚀"
            )
            self.editor.setPlainText(welcome) 

    def setup_file_explorer_shortcut(self):
        self.explorer_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.explorer_shortcut.activated.connect(self.toggle_file_explorer_animated)

    def toggle_file_explorer_animated(self):
        dock = self.dock_file_explorer
        if dock.isVisible():
            anim = QPropertyAnimation(dock, b"maximumWidth")
            anim.setDuration(350)
            anim.setStartValue(dock.width())
            anim.setEndValue(0)
            anim.finished.connect(dock.hide)
            anim.start()
            self._explorer_anim = anim  # Keep reference
        else:
            dock.show()
            anim = QPropertyAnimation(dock, b"maximumWidth")
            anim.setDuration(350)
            anim.setStartValue(0)
            anim.setEndValue(220)
            anim.start()
            self._explorer_anim = anim 

    def show_notification(self, message):
        if self.notification_label:
            self.notification_label.deleteLater()
        self.notification_label = QLabel(message, self)
        self.notification_label.setStyleSheet("QLabel { background: rgba(0,200,150,0.92); color: #fff; font-size: 18px; border-radius: 12px; padding: 12px 32px; border: 2px solid #00c896; box-shadow: 0 0 24px #00c896; }")
        self.notification_label.setAlignment(Qt.AlignCenter)
        self.notification_label.setFixedWidth(260)
        self.notification_label.move(self.width()//2 - 130, 60)
        self.notification_label.setGraphicsEffect(QGraphicsOpacityEffect(self.notification_label))
        self.notification_label.show()
        effect = self.notification_label.graphicsEffect()
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(350)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.start()
        self._notif_anim = anim
        # Fade out after 1.5s
        def fade_out():
            anim2 = QPropertyAnimation(effect, b"opacity")
            anim2.setDuration(600)
            anim2.setStartValue(1)
            anim2.setEndValue(0)
            anim2.finished.connect(self.notification_label.deleteLater)
            anim2.start()
            self._notif_anim = anim2
        QTimer.singleShot(1500, fade_out) 

    def setup_quick_file_switcher(self):
        self.quick_switch_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.quick_switch_shortcut.activated.connect(self.show_quick_file_switcher)

    def show_quick_file_switcher(self):
        dlg = QuickFileSwitcher(self, os.getcwd())
        if dlg.exec_() == QDialog.Accepted:
            file_path = dlg.selected_file()
            if file_path:
                self.open_file_with_animation(file_path)

    def open_file_with_animation(self, file_path):
        # Fade out editor, open file, fade in
        effect = QGraphicsOpacityEffect(self.editor)
        self.editor.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(200)
        anim.setStartValue(1)
        anim.setEndValue(0)
        def after_fade_out():
            with open(file_path, 'r') as file:
                self.editor.setPlainText(file.read())
                self.file_path = file_path
            self.status_bar.showMessage(f"Opened: {file_path}")
            anim2 = QPropertyAnimation(effect, b"opacity")
            anim2.setDuration(200)
            anim2.setStartValue(0)
            anim2.setEndValue(1)
            anim2.start()
            self._editor_anim = anim2
        anim.finished.connect(after_fade_out)
        anim.start()
        self._editor_anim = anim 