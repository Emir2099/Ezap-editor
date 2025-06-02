import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer

from ui.ezcode_window import EZCode
from editor.splash import SplashScreen


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

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()