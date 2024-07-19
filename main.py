import sys
import re
import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QFileDialog, QMessageBox,
    QDockWidget, QSplitter, QToolBar, QAction, QWidget, QSplashScreen, QLabel,
    QMenu, QVBoxLayout, QTextEdit, QDialog, QInputDialog, QProgressBar, QTableWidget, QPushButton, QTableWidgetItem
)
from PyQt5.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QPainter, QIcon, QTextCursor, QPixmap
from PyQt5.QtCore import Qt, QSize, QTimer, QRect, QObject, pyqtSignal, pyqtSlot, QProcess

import qtawesome as qta
import logging
from PyQt5.QtCore import Qt, QRect, QUrl, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout

import sys
import os
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel


class QtHandler(logging.Handler):
    def __init__(self, output_widget):
        super().__init__()
        self.output_widget = output_widget

    def emit(self, record):
        msg = self.format(record)
        self.output_widget.appendPlainText(msg)
        
        
        
class CustomStdout(QObject):
    text_written = pyqtSignal(str)

    def write(self, text):
        self.text_written.emit(str(text))

    def flush(self):
        pass

class CustomStderr(QObject):
    text_written = pyqtSignal(str)

    def write(self, text):
        self.text_written.emit(str(text))

    def flush(self):
        pass

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)

    def mousePressEvent(self, event):
        self.editor.line_number_area_mouse_event(event)

class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.error_line = -1
        self.error_format = QTextCharFormat()
        self.error_format.setBackground(QColor("red"))

        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("blue"))
        self.keywords = ["def", "class", "import", "from", "return", "if", "elif", "else", "while", "for", "try", "except"]

    def highlightBlock(self, text):
        if self.currentBlock().blockNumber() == self.error_line:
            self.setFormat(0, len(text), self.error_format)
        for keyword in self.keywords:
            expression = re.compile(fr'\b{keyword}\b')
            for match in expression.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), self.keyword_format)

    def set_error_line(self, line):
        self.error_line = line - 1  # Convert to 0-based index
        self.rehighlight()

    def clear_error_line(self):
        self.error_line = -1
        self.rehighlight()

class CodeEditor(QPlainTextEdit):
    def __init__(self, *args):
        super().__init__(*args)
        self.setFont(QFont("Courier", 12))
        self.highlighter = SyntaxHighlighter(self.document())
        self.line_number_area = LineNumberArea(self)
        self.breakpoints = set()
        self.debugging_mode = False
        self.current_line = -1

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)

        self.update_line_number_area_width(0)

    def line_number_area_width(self):
        digits = len(str(self.blockCount()))
        space = 3 + self.fontMetrics().width('9') * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(cr.left(), cr.top(), self.line_number_area_width(), cr.height())

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), Qt.lightGray)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(Qt.black)
                painter.drawText(0, int(top), self.line_number_area.width(), self.fontMetrics().height(), Qt.AlignRight, number)
                if block_number + 1 in self.breakpoints:
                    painter.setPen(Qt.red)
                    painter.drawEllipse(0, int(top), 10, 10)
                if block_number == self.current_line:
                    painter.setPen(Qt.green)
                    painter.drawText(10, int(top) + self.fontMetrics().ascent(), "→")

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def line_number_area_mouse_event(self, event):
        if event.button() == Qt.LeftButton and self.debugging_mode:
            line_number = self.cursorForPosition(event.pos()).blockNumber() + 1
            if line_number in self.breakpoints:
                self.breakpoints.remove(line_number)
            else:
                self.breakpoints.add(line_number)
            self.update_line_number_area(self.contentsRect(), 0)

    def toggle_debugging_mode(self):
        self.debugging_mode = not self.debugging_mode

    def set_current_line(self, line):
        self.current_line = line
        self.viewport().update()
        
        
class CommandRunner(QObject):
    finished = pyqtSignal(str, str)  # Signal to send stdout and stderr on completion

    def run_command(self, command):
        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.on_ready_read)
        self.process.finished.connect(self.on_finished)
        self.process.start(command)

    def on_ready_read(self):
        output = self.process.readAllStandardOutput().data().decode()
        self.stdout += output

    def on_finished(self):
        self.finished.emit(self.stdout, '')

    def kill_process(self):
        self.process.kill()

    def run_command_sync(self, command):
        self.stdout = ''
        self.run_command(command)
        self.process.waitForFinished()
        return self.stdout
    

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

    def init_ui(self):
        self.setWindowTitle('EZap Editor')
        self.setGeometry(100, 100, 1000, 800)

        self.editor = CodeEditor()
        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)

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
        self.apply_stylesheet()
        self.set_light_mode()
        self.show()

    def create_toolbar(self, mode='light'):
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)
        color = 'black' if mode == "light" else 'white'
        color_active = 'green' if mode == 'light' else '#80c0ff'  # Set the color based on the mode

        open_action = QAction(qta.icon('fa.folder-open', color = color, color_active=color_active), "Open", self)
        open_action.triggered.connect(self.open_file)
        save_action = QAction(qta.icon('fa.save', color = color, color_active=color_active), "Save", self)
        save_action.triggered.connect(self.save_file)
        run_action = QAction(qta.icon('fa.play', color = color, color_active=color_active), "Run", self)
        run_action.triggered.connect(self.run_code)
        debug_action = QAction(qta.icon('fa.bug', color = color, color_active=color_active), "Debug", self)
        debug_action.triggered.connect(self.toggle_debugging_mode)

        self.toolbar.addAction(open_action)
        self.toolbar.addAction(save_action)
        self.toolbar.addAction(run_action)
        self.toolbar.addAction(debug_action)
    def create_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu('File')
        open_action = QAction('Open', self)
        open_action.triggered.connect(self.open_file)
        save_action = QAction('Save', self)
        save_action.triggered.connect(self.save_file)
        save_as_action = QAction('Save As', self)
        save_as_action.triggered.connect(self.save_as)
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)

        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addAction(exit_action)

        run_menu = menubar.addMenu('Run')
        run_action = QAction('Run', self)
        run_action.triggered.connect(self.run_code)
        run_menu.addAction(run_action)

        debug_menu = menubar.addMenu('Debug')
        debug_action = QAction('Debug', self)
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
        # console_log_action = QAction('Console Log', self, checkable=True)
        # console_log_action.setChecked(self.log_capture)
        # console_log_action.triggered.connect(self.toggle_console_log)
        # settings_menu.addAction(console_log_action)

    def create_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

    def open_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Python File", "", "Python Files (*.py);;All Files (*)", options=options)
        if file_path:
            with open(file_path, 'r') as file:
                self.editor.setPlainText(file.read())
                self.file_path = file_path
            self.status_bar.showMessage(f"Opened: {file_path}")

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
        self.output.appendPlainText(stdout)
        if stderr:
            error_line = self.extract_error_line(stderr)
            if error_line:
                self.editor.highlighter.set_error_line(error_line)
            self.write_text_to_output(stderr)
        else:
            self.editor.highlighter.clear_error_line()

        self.status_bar.showMessage("Execution finished")

    def extract_error_line(self, error_message):
        match = re.search(r'File.*line (\d+)', error_message)
        if match:
            return int(match.group(1))
        return None

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

    def apply_stylesheet(self):
        self.setStyleSheet("""
        QMainWindow {
            background-color: #353535;
        }
        QMenuBar {
            background-color: #2b2b2b;
            color: #f8f8f2;
        }
        QMenuBar::item {
            background-color: #2b2b2b;
            color: #f8f8f2;
        }
        QMenuBar::item::selected {
            background-color: #444444;
        }
        QMenu {
            background-color: #2b2b2b;
            color: #f8f8f2;
        }
        QMenu::item::selected {
            background-color: #444444;
        }
        QToolBar {
            background-color: #2b2b2b;
        }
        QStatusBar {
            background-color: #2b2b2b;
            color: #f8f8f2;
        }
        QMessageBox {
            background-color: #2b2b2b;
            color: #f8f8f2;
        }
        QPushButton {
            background-color: #444444;
            color: #f8f8f2;
        }
        QPushButton::hover {
            background-color: #555555;
        }
        QPlainTextEdit {
            background-color: #2b2b2b;
            color: #f8f8f2;
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
            if self.validate_input(package_name):
                if self.confirm_action(f'install {package_name}'):
                    self.execute_command_async(f'pip install {package_name}')

    def uninstall_package(self):
        self.output.clear()
        package_name, ok = QInputDialog.getText(self, 'Uninstall Package', 'Enter package name:')
        if ok:
            if self.validate_input(package_name):
                if self.confirm_action(f'uninstall {package_name}'):
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

    def validate_input(self, text):
        if not text.strip():
            self.show_error_message("Input cannot be empty")
            return False
        return True

    def confirm_action(self, action_name):
        reply = QMessageBox.question(self, 'Confirmation', f'Are you sure you want to {action_name}?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reply == QMessageBox.Yes

    def show_error_message(self, message):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText("Error")
        msg.setInformativeText(message)
        msg.setWindowTitle("Error")
        msg.exec_()

    def execute_command(self, command):
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        return stdout

    # def handle_command_finished(self, stdout, stderr):
    #     # Handle command completion, update GUI as needed
    #     if stderr:
    #         self.write_text_to_output(stderr)
    #     self.show_installed_packages()  # Example of updating GUI after command completion
    def write_text_to_output(self, text):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)

        if not self.output.toPlainText().endswith('\n'):
            cursor.insertText('\n')

        cursor.insertText(text + '\n')
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

class StreamToLogger:
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass

sys.stdout = StreamToLogger(logging.getLogger(), logging.INFO)
sys.stderr = StreamToLogger(logging.getLogger(), logging.ERROR)


class SplashScreen(QSplashScreen):
    def __init__(self, image_path):
        # Load the splash background image
        splash_pix = QPixmap(image_path)
        
        # Resize the pixmap to desired dimensions (e.g., 300x200)
        splash_pix = splash_pix.scaled(800, 800, Qt.KeepAspectRatio)

        super().__init__(splash_pix, Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setMask(splash_pix.mask())

        # Set up progress label
        self.progress = QLabel(self)
        self.progress.setGeometry(QRect(0, splash_pix.height() - 30, splash_pix.width(), 20))
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("QLabel { color: black; }")

    def show_progress(self, message):
        self.progress.setText(message)
        QApplication.processEvents()

def main():
    print("Starting application...")
    app = QApplication(sys.argv)

    # Get the path to the image file
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    image_path = os.path.join(base_path, 'images', 'splash.jpg')
    icon_path = os.path.join(base_path, 'images', 'icon.png')
    
    # Set the application icon
    app.setWindowIcon(QIcon(icon_path))
    
    print(f"Loading splash screen with image: {image_path}")
    splash = SplashScreen(image_path)
    splash.show()
    splash.show_progress("Loading...")

    # Simulate loading time
    QTimer.singleShot(3000, splash.close)

    print("Initializing main editor window...")
    editor = EZCode()
    editor.show()
    splash.finish(editor)
    # print("Splash screen finished, main editor should be visible.")

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()