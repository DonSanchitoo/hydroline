"""
dialogs/parametres_dialog.py

Permet de gérer l'affichage et la gestion de la dialog des paramètres pour l'ensemble du plugin
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFrame
from qgis.PyQt.QtCore import Qt, QObject, QCoreApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap, QDesktopServices
from PyQt5.QtCore import QUrl
from qgis.PyQt import uic

import os


class ParametresDialog(QDialog):
    def __init__(self, parent=None):
        super(ParametresDialog, self).__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'settings.ui'), self)
        self.ModeTrace.addItem("Mode Automatique (Distance)")
        self.ModeTrace.addItem("Mode Manuel (Touche 'T')")
        self.ModeTrace.currentIndexChanged.connect(self.mode_changed)

        # Connecter OK et Annuler
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)


        # Liste des noms d'image
        self.images = [f'logo{i}.png' for i in range(1, 7)]
        self.current_image_index = 0
        self.setup_infolabel()

        # Initialisation de l'image
        self.update_image()

        # Timer pour le changement d'image
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_image)
        self.timer.start(600)

        self.pushButtonOpenPDF.clicked.connect(self.open_pdf)

    def open_pdf(self):
        pdf_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'aide.pdf')
        QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))

    def update_image(self):
        png_path = os.path.join(os.path.dirname(__file__), '..', 'sscreen', self.images[self.current_image_index])
        pixmap = QPixmap(png_path)

        # Charger et redimensionner l'image à la taille du `QLabel`
        if not pixmap.isNull():
            pixmap = pixmap.scaled(self.logoLabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logoLabel.setPixmap(pixmap)
            self.logoLabel.setFrameShape(QFrame.NoFrame)
            self.logoLabel.setFrameShadow(QFrame.Plain)

    def next_image(self):
        # Passer à l'image suivante
        self.current_image_index = (self.current_image_index + 1) % len(self.images)
        self.update_image()

    def setup_infolabel(self):
        image_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'info.png')
        pixmap = QPixmap(image_path)

        if not pixmap.isNull():
            pixmap = pixmap.scaled(self.Infolabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.Infolabel.setPixmap(pixmap)
            self.Infolabel.setFrameShape(QFrame.NoFrame)
            self.Infolabel.setFrameShadow(QFrame.Plain)

    def set_values(self, mode, distance_seuil, graphique_3d_checked, field_settings):
        self.ModeTrace.setCurrentIndex(0 if mode == 1 else 1)
        # Activer ou désactiver le slider en fonction du mode
        self.mode_changed(self.ModeTrace.currentIndex())
        self.graphique3D.setChecked(graphique_3d_checked)
        # Mettre à jour l'état des boutons radio en fonction de field_settings
        self.radioButton_OBJECTID_Oui.setChecked(field_settings.get('OBJECTID', True))
        self.radioButton_OBJECTID_Non.setChecked(not field_settings.get('OBJECTID', True))

        self.radioButton_SHAPE_LENGTH_Oui.setChecked(field_settings.get('SHAPE_LENGTH', True))
        self.radioButton_SHAPE_LENGTH_Non.setChecked(not field_settings.get('SHAPE_LENGTH', True))

        self.radioButton_HORADATEUR_Oui.setChecked(field_settings.get('HORADATEUR', True))
        self.radioButton_HORADATEUR_Non.setChecked(not field_settings.get('HORADATEUR', True))

    def get_selected_mode(self):
    # Retourner 1 pour 'Mode Automatique', 2 pour 'Mode Manuel'
        return 1 if self.ModeTrace.currentIndex() == 0 else 2

    def is_graphique_3d_checked(self):
        return self.graphique3D.isChecked()

    def mode_changed(self, index):
        is_automatique = (index == 0)

    def get_field_settings(self):
        return {
            'OBJECTID': self.radioButton_OBJECTID_Oui.isChecked(),
            'Denomination': self.radioButton_Denomination_Oui.isChecked(),
            'SHAPE_LENGTH': self.radioButton_SHAPE_LENGTH_Oui.isChecked(),
            'HORADATEUR': self.radioButton_HORADATEUR_Oui.isChecked()

        }