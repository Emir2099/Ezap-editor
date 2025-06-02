import re
from PyQt5.QtWidgets import QPlainTextEdit, QWidget
from PyQt5.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QPainter, QTextCursor
from PyQt5.QtCore import Qt

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return self.editor.line_number_area_width(), 0

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