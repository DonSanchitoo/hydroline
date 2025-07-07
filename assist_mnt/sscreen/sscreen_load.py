"""
sscreen/sscreen_load.py
"""

import os

from PyQt5.QtCore import QPropertyAnimation, QSequentialAnimationGroup, Qt
from PyQt5.QtGui import QPixmap, QGuiApplication, QFont
from PyQt5.QtWidgets import QWidget, QLabel, QGraphicsOpacityEffect


class SplashScreenLoad(QWidget):
    def __init__(self, parent=None):
        super(SplashScreenLoad, self).__init__(parent)

        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        screen = QGuiApplication.primaryScreen()
        screen_size = screen.size()
        width = 400
        height = 400
        self.setGeometry(
            (screen_size.width() - width) // 2,
            (screen_size.height() - height) // 2,
            width,
            height
        )

        # Image de fond (load2.png) qui reste affichée
        self.background_label = QLabel(self)
        self.background_label.setAlignment(Qt.AlignCenter)
        self.background_label.setGeometry(0, 80, width, height - 150)

        # Image animée (load1.png) avec effet de fondu
        self.moving_label = QLabel(self)
        self.moving_label.setAlignment(Qt.AlignCenter)
        self.moving_label.setGeometry(0, 80, width, height - 150)

        self.version_label = QLabel(self)
        self.version_label.setAlignment(Qt.AlignCenter)
        self.version_label.setGeometry(190, 20, width, -80)
        self.version_label.setText("Version 1.0 2025")
        self.version_label.setFont(QFont("Arial", 8, QFont.Bold))
        self.version_label.setStyleSheet("color: black;")

        self.setAttribute(Qt.WA_TranslucentBackground)

        # Charger et appliquer l'image de fond
        background_path = os.path.join(os.path.dirname(__file__), 'load2.png')
        background_pixmap = QPixmap(background_path)
        self.background_label.setPixmap(background_pixmap.scaled(
            width,
            height - 150,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))

        # Charger et appliquer l'image animée
        moving_path = os.path.join(os.path.dirname(__file__), 'load1.png')
        moving_pixmap = QPixmap(moving_path)
        self.moving_label.setPixmap(moving_pixmap.scaled(
            width,
            height - 150,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))

        self.opacity_effect = QGraphicsOpacityEffect()
        self.moving_label.setGraphicsEffect(self.opacity_effect)

        self.start_animation()

    def start_animation(self):
        transition_time = 1000  # Durée de chaque cycle de fondu (en ms)

        self.opacity_effect.setOpacity(0)

        # Animation d'apparition
        anim_in = QPropertyAnimation(self.opacity_effect, b'opacity')
        anim_in.setDuration(transition_time)
        anim_in.setStartValue(0)
        anim_in.setEndValue(1)

        # Animation de disparition
        anim_out = QPropertyAnimation(self.opacity_effect, b'opacity')
        anim_out.setDuration(transition_time)
        anim_out.setStartValue(1)
        anim_out.setEndValue(0)

        # Grouper les animations pour un cycle de fondu complet
        self.anim_group = QSequentialAnimationGroup()
        self.anim_group.addAnimation(anim_in)
        self.anim_group.addAnimation(anim_out)
        self.anim_group.setLoopCount(-1)  # Boucle indéfinie, continuera jusqu'à la fermeture du Widget

        self.anim_group.start()
