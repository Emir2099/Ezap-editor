from PyQt5.QtWidgets import QSplashScreen, QLabel, QApplication
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QRect

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