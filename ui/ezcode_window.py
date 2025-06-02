import sys
import subprocess
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QPlainTextEdit, QFileDialog, QMessageBox, QDockWidget, QSplitter, QToolBar, QAction, QWidget, QInputDialog, QProgressBar, QTableWidget, QPushButton, QTableWidgetItem, QVBoxLayout, QFileSystemModel, QTreeView, QDialog, QLineEdit, QListWidget, QListWidgetItem, QSlider, QLabel, QHBoxLayout, QComboBox, QShortcut
)
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QKeySequence
from PyQt5.QtCore import Qt, QProcess, QSize
import qtawesome as qta
import os

from editor.code_editor import CodeEditor
from editor.output import QtHandler, StreamToLogger
from utils.helpers import validate_input, confirm_action, show_error_message, extract_error_line

class CommandPalette(QDialog):
    def __init__(self, parent, actions):
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setStyleSheet("QDialog { background: #f8fafc; border-radius: 12px; } QLineEdit { font-size: 18px; padding: 8px; border-radius: 8px; } QListWidget { font-size: 16px; border-radius: 8px; }")
        self.setFixedWidth(400)
        self.setFixedHeight(320)
        layout = QVBoxLayout(self)
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
        self.search.setFocus()

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

class EZCode(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_path = ''
        self.log_capture = False
        self.debugging = False
        self.pdb = None
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

    def save_as(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Python File", "", "Python Files (*.py);;All Files (*)", options=options)
        if file_path:
            with open(file_path, 'w') as file:
                code = self.editor.toPlainText()
                file.write(code)
                self.file_path = file_path
            self.status_bar.showMessage(f"Saved as: {file_path}")

    def run_code(self):
        if self.debugging:
            self.stop_debugging()

        code = self.editor.toPlainText()
        process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()

        self.output.clear()
        self.append_output_html(stdout, 'normal')
        if stderr:
            error_line = extract_error_line(stderr)
            if error_line:
                self.editor.highlighter.set_error_line(error_line)
                self.editor.error_tooltip = stderr
            self.append_output_html(stderr, 'error')
        else:
            self.editor.highlighter.clear_error_line()
            self.editor.error_tooltip = ''

        self.status_bar.showMessage("Execution finished")

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
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f8fafc, stop:1 #e0e7ef);
        }
        QMenuBar {
            background: #f8fafc;
            color: #222;
            font-size: 15px;
            border-radius: 8px;
        }
        QMenuBar::item {
            background: transparent;
            color: #222;
            padding: 6px 18px;
            border-radius: 8px;
        }
        QMenuBar::item:selected {
            background: #e0e7ef;
            color: #00c896;
        }
        QMenu {
            background: #f8fafc;
            color: #222;
            font-size: 15px;
            border-radius: 8px;
        }
        QMenu::item {
            padding: 6px 18px;
            border-radius: 8px;
        }
        QMenu::item:selected {
            background: #e0e7ef;
            color: #00c896;
        }
        QToolBar {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f8fafc, stop:1 #e0e7ef);
            border-radius: 12px;
            spacing: 12px;
        }
        QToolButton {
            background: transparent;
            border-radius: 8px;
            padding: 8px;
        }
        QToolButton:hover {
            background: #e0e7ef;
        }
        QStatusBar {
            background: #f8fafc;
            color: #222;
            font-size: 14px;
            border-radius: 8px;
        }
        QDockWidget {
            background: #f8fafc;
            border-radius: 12px;
        }
        QPlainTextEdit {
            background: #f4f7fa;
            color: #222;
            font-family: 'Fira Mono', 'Consolas', 'Courier New', monospace;
            font-size: 16px;
            border-radius: 10px;
            padding: 8px;
        }
        QSplitter::handle {
            background: #e0e7ef;
        }
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00c896, stop:1 #00e6b8);
            color: #fff;
            border-radius: 8px;
            padding: 8px 18px;
            font-size: 15px;
        }
        QPushButton:hover {
            background: #00e6b8;
        }
        QTableWidget {
            background: #f4f7fa;
            border-radius: 8px;
            font-size: 15px;
        }
        QHeaderView::section {
            background: #e0e7ef;
            color: #222;
            border-radius: 8px;
            font-size: 15px;
        }
        QMessageBox {
            background: #f8fafc;
            color: #222;
            border-radius: 12px;
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
        installed_packages = self.execute_command('pip list --format=columns')
        self.package_table.clearContents()
        self.package_table.setRowCount(0)

        # Split the output into lines and parse the package information
        lines = installed_packages.splitlines()[2:]  # Skip the first two header lines
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