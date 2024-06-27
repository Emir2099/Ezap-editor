import sys
import re
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPlainTextEdit, QFileDialog, QMessageBox, QDockWidget, QSplitter, QToolBar, QAction, QStatusBar, QWidget, QTextEdit, QSplashScreen, QLabel, QMenu, QCheckBox, QVBoxLayout, QDialog)
from PyQt5.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QPainter, QIcon, QTextFormat, QPixmap
from PyQt5.QtCore import Qt, QSize, QTimer, QRect
import qtawesome as qta
import pdb

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

class EzapEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_path = ''
        self.log_capture = True
        self.debugging = False
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Ezap Editor')
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
        self.show()

    def create_toolbar(self):
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)

        open_action = QAction(qta.icon('fa.folder-open', color='black'), "Open", self)
        open_action.triggered.connect(self.open_file)
        save_action = QAction(qta.icon('fa.save', color='black'), "Save", self)
        save_action.triggered.connect(self.save_file)
        run_action = QAction(qta.icon('fa.play', color='black'), "Run", self)
        run_action.triggered.connect(self.run_code)
        debug_action = QAction(qta.icon('fa.bug', color='black'), "Debug", self)
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
        step_action = QAction('Step', self)
        step_action.triggered.connect(self.step_code)
        continue_action = QAction('Continue', self)
        continue_action.triggered.connect(self.continue_code)
        debug_menu.addAction(debug_action)
        debug_menu.addAction(step_action)
        debug_menu.addAction(continue_action)

        view_menu = menubar.addMenu('View')
        toggle_output_action = QAction('Toggle Output Console', self)
        toggle_output_action.triggered.connect(self.toggle_output_console)
        view_menu.addAction(toggle_output_action)
        reset_layout_action = QAction('Reset Layout', self)
        reset_layout_action.triggered.connect(self.reset_layout)
        view_menu.addAction(reset_layout_action)

        settings_menu = menubar.addMenu('Settings')
        light_mode_action = QAction('Light Mode', self)
        light_mode_action.triggered.connect(self.set_light_mode)
        dark_mode_action = QAction('Dark Mode', self)
        dark_mode_action.triggered.connect(self.set_dark_mode)
        settings_menu.addAction(light_mode_action)
        settings_menu.addAction(dark_mode_action)
        console_log_action = QAction('Console Log', self, checkable=True)
        console_log_action.setChecked(self.log_capture)
        console_log_action.triggered.connect(self.toggle_console_log)
        settings_menu.addAction(console_log_action)

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
            self.run_debugging_code()
        else:
            code = self.editor.toPlainText()
            with open('temp_script.py', 'w') as file:
                file.write(code)
            process = subprocess.Popen(['python', 'temp_script.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, error = process.communicate()

            if self.log_capture:
                self.output.appendPlainText("\n" + "-" * 40 + " New Run " + "-" * 40 + "\n")

            if output:
                self.output.appendPlainText(output.decode())
            if error:
                self.output.appendPlainText(error.decode())

            if error:
                error_lines = re.findall(r'File ".*", line (\d+)', error.decode())
                if error_lines:
                    self.editor.highlighter.set_error_line(int(error_lines[-1]))
                self.status_bar.showMessage("Error occurred during execution.")
            else:
                self.editor.highlighter.clear_error_line()
                self.status_bar.showMessage("Code executed successfully.")

    def toggle_debugging_mode(self):
        self.debugging = not self.debugging
        self.editor.toggle_debugging_mode()
        if self.debugging:
            self.status_bar.showMessage("Debugging mode enabled.")
        else:
            self.status_bar.showMessage("Debugging mode disabled.")

    def run_debugging_code(self):
        self.editor.set_current_line(-1)
        self.editor.breakpoints.add(1)  # Breakpoint at the first line by default
        line_number = 1
        code = self.editor.toPlainText()
        self.pdb = pdb.Pdb()
        while line_number in self.editor.breakpoints:
            self.editor.set_current_line(line_number)
            self.editor.viewport().update()
            self.editor.breakpoints.remove(line_number)
            self.pdb.set_trace()
            self.pdb.run(code)
            line_number += 1

    def step_code(self):
        if self.debugging and self.pdb:
            self.pdb.set_continue()
            self.pdb.run(self.editor.toPlainText())

    def continue_code(self):
        if self.debugging and self.pdb:
            self.pdb.set_continue()

    def set_light_mode(self):
        self.editor.setStyleSheet("QPlainTextEdit { background-color: white; color: black; }")
        self.output.setStyleSheet("QPlainTextEdit { background-color: white; color: black; }")
        self.setStyleSheet("QWidget { background-color: white; color: black; }")
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #cccccc; }")

    def set_dark_mode(self):
        self.editor.setStyleSheet("QPlainTextEdit { background-color: #2b2b2b; color: #f8f8f2; }")
        self.output.setStyleSheet("QPlainTextEdit { background-color: #2b2b2b; color: #f8f8f2; }")
        self.setStyleSheet("QWidget { background-color: #2b2b2b; color: #f8f8f2; }")
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #3f3f3f; }")

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

class SplashScreen(QSplashScreen):
    def __init__(self):
        splash_pix = QPixmap(400, 300)
        splash_pix.fill(Qt.white)
        super().__init__(splash_pix, Qt.WindowStaysOnTopHint)

        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setMask(splash_pix.mask())

        self.progress = QLabel(self)
        self.progress.setGeometry(QRect(0, splash_pix.height() - 50, splash_pix.width(), 20))
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("QLabel { color: black; }")

    def show_progress(self, message):
        self.progress.setText(message)
        QApplication.processEvents()

def main():
    app = QApplication(sys.argv)

    splash = SplashScreen()
    splash.show()
    splash.show_progress("Loading...")

    # Simulate loading time
    QTimer.singleShot(3000, splash.close)

    editor = EzapEditor()
    editor.show()
    splash.finish(editor)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
