
# sscreen/sscreen.py


import os

from PyQt5.QtCore import QTimer, Qt, QPropertyAnimation, pyqtSignal
from PyQt5.QtGui import QPixmap, QGuiApplication, QFont
from PyQt5.QtWidgets import QWidget, QLabel, QGraphicsOpacityEffect


class SplashScreen(QWidget):
    """
    Classe gérant l'affichage d'un écran de démarrage avec des logos et des textes dynamiques.

    Cette classe affiche une séquence d'images et de textes afin de fournir une introduction à l'application.
    L'écran reste en haut de toutes les fenêtres et s'affiche sans cadre jusqu'à ce que la séquence soit terminée.

    Attributes
    ----------
    finished : pyqtSignal
        Signal émis lorsque l'affichage de l'écran de démarrage est terminé.

    current_index : int
        Index actuel de l'image en cours d'affichage.

    text_index : int
        Index actuel du texte dynamique en cours d'affichage.

    logos : list of QPixmap
        Liste pixmap des logos à afficher.

    dynamic_texts : list of tuple
        Liste de tuples contenant le texte dynamique et sa durée d'affichage.

    opacity_effect1 : QGraphicsOpacityEffect
        Effet d'opacité appliqué sur le premier label d'image.

    opacity_effect2 : QGraphicsOpacityEffect
        Effet d'opacité appliqué sur le second label d'image.

    text_opacity_effect : QGraphicsOpacityEffect
        Effet d'opacité appliqué sur le label de texte dynamique.

    Methods
    -------
    show_next_logo()
        Affiche le logo suivant dans la séquence et met à jour le texte dynamique.
    """

    finished = pyqtSignal()

    def __init__(self, parent=None):
        """
        Initialise l'écran de démarrage avec les paramètres requis.

        Parameters
        ----------
        parent : QWidget, optional
            Widget parent, par défaut None.
        """

        super(SplashScreen, self).__init__(parent)

        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        screen = QGuiApplication.primaryScreen()
        screen_size = screen.size()
        width = 500
        height = 500
        self.setGeometry(
            (screen_size.width() - width) // 2,
            (screen_size.height() - height) // 2,
            width,
            height
        )

        self.label1 = QLabel(self)
        self.label1.setAlignment(Qt.AlignCenter)
        self.label1.setGeometry(0, 80, width, height - 150)

        self.label2 = QLabel(self)
        self.label2.setAlignment(Qt.AlignCenter)
        self.label2.setGeometry(0, 80, width, height - 150)

        self.version_label = QLabel(self)
        self.version_label.setAlignment(Qt.AlignCenter)
        self.version_label.setGeometry(190, 20, width, -80)
        self.version_label.setText("Version 1.0 2025")
        self.version_label.setFont(QFont("Arial", 8, QFont.Bold))
        self.version_label.setStyleSheet("color: black;")

        # Dynamic text setup
        self.dynamic_text_label = QLabel(self)
        self.dynamic_text_label.setAlignment(Qt.AlignCenter)
        self.dynamic_text_label.setGeometry(50, height - 175, 400,
                                            50)  # Further adjusted y-position to move text higher
        self.dynamic_text_label.setFont(QFont("Arial", 10))  # Smaller font size, normal weight
        self.dynamic_text_label.setStyleSheet("color: black;")

        self.dynamic_texts = [
            ("Initialisation de l'outil", 500),
            ("Vérification des dépendances Python", 1500),
            ("Hydroline prêt", 1000)
        ]

        self.setAttribute(Qt.WA_TranslucentBackground)

        self.logos = []
        for i in range(1, 7):
            logo_path = os.path.join(os.path.dirname(__file__), f'logo{i}.png')
            pixmap = QPixmap(logo_path)
            pixmap = pixmap.scaled(
                width,
                height - 150,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.logos.append(pixmap)

        self.current_index = -1
        self.text_index = 0

        self.opacity_effect1 = QGraphicsOpacityEffect()
        self.label1.setGraphicsEffect(self.opacity_effect1)
        self.opacity_effect1.setOpacity(1)

        self.opacity_effect2 = QGraphicsOpacityEffect()
        self.label2.setGraphicsEffect(self.opacity_effect2)
        self.opacity_effect2.setOpacity(0)

        self.text_opacity_effect = QGraphicsOpacityEffect()
        self.version_label.setGraphicsEffect(self.text_opacity_effect)
        self.text_opacity_effect.setOpacity(1)

        self.show_next_logo()

    def show_next_logo(self):
        """
        Affiche le logo suivant dans la séquence d'affichage et met à jour le texte dynamique.

        Cette méthode gère la transition des logos avec un effet de fondu enchaîné et passe au texte
        dynamique suivant lorsque la séquence d'images est en cours.
        """

        self.current_index += 1

        transition_time = 3000 // len(self.logos)

        if self.text_index < len(self.dynamic_texts):
            text, delay = self.dynamic_texts[self.text_index]
            self.dynamic_text_label.setText(text)
            self.text_index += 1
            transition_time = delay

        if self.current_index == 0:
            self.label1.setPixmap(self.logos[self.current_index])
            QTimer.singleShot(transition_time, self.show_next_logo)
        elif self.current_index < len(self.logos):
            if self.current_index % 2 == 1:
                self.label2.setPixmap(self.logos[self.current_index])
                self.opacity_effect1.setOpacity(1)
                self.opacity_effect2.setOpacity(0)

                self.anim1 = QPropertyAnimation(self.opacity_effect1, b'opacity')
                self.anim1.setDuration(transition_time // 2)
                self.anim1.setStartValue(1)
                self.anim1.setEndValue(0)

                self.anim2 = QPropertyAnimation(self.opacity_effect2, b'opacity')
                self.anim2.setDuration(transition_time // 2)
                self.anim2.setStartValue(0)
                self.anim2.setEndValue(1)

                self.anim1.start()
                self.anim2.start()

            else:
                self.label1.setPixmap(self.logos[self.current_index])
                self.opacity_effect1.setOpacity(0)
                self.opacity_effect2.setOpacity(1)

                self.anim1 = QPropertyAnimation(self.opacity_effect1, b'opacity')
                self.anim1.setDuration(transition_time // 2)
                self.anim1.setStartValue(0)
                self.anim1.setEndValue(1)

                self.anim2 = QPropertyAnimation(self.opacity_effect2, b'opacity')
                self.anim2.setDuration(transition_time // 2)
                self.anim2.setStartValue(1)
                self.anim2.setEndValue(0)

                self.anim1.start()
                self.anim2.start()

            QTimer.singleShot(transition_time, self.show_next_logo)
        else:
            self.close()
            self.finished.emit()
