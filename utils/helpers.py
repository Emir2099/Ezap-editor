import re
from PyQt5.QtWidgets import QMessageBox

def validate_input(text, parent=None):
    if not text.strip():
        show_error_message("Input cannot be empty", parent)
        return False
    return True

def confirm_action(action_name, parent=None):
    reply = QMessageBox.question(parent, 'Confirmation', f'Are you sure you want to {action_name}?',
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    return reply == QMessageBox.Yes

def show_error_message(message, parent=None):
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Critical)
    msg.setText("Error")
    msg.setInformativeText(message)
    msg.setWindowTitle("Error")
    msg.exec_()

def extract_error_line(error_message):
    match = re.search(r'File.*line (\d+)', error_message)
    if match:
        return int(match.group(1))
    return None 