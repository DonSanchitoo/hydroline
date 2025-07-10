
# dialogs/parametres_dialog.py


from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFrame
from qgis.PyQt.QtCore import Qt, QObject, QCoreApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap, QDesktopServices
from PyQt5.QtCore import QUrl
from qgis.PyQt import uic

import os


class ParametresDialog(QDialog):
    """
    Permet de gérer l'affichage et la gestion de la boîte de dialogue des paramètres pour l'ensemble du plugin.

    Cette classe initialise l'interface utilisateur, charge les ressources depuis les fichiers, et gère les
    actions utilisateur pour ajuster les paramètres du plugin.

    Attributes
    ----------
    images : list of str
        Liste des noms d'image affichés dans la boîte de dialogue.
    current_image_index : int
        Index actuel de l'image affichée.
    timer : QTimer
        Timer pour changer périodiquement l'image affichée.

    Methods
    -------
    open_pdf()
        Ouvre le fichier PDF d'aide utilisateur.
    update_image()
        Met à jour l'affichage de l'image en fonction de l'index actuel.
    next_image()
        Passe à l'image suivante dans la liste des images.
    setup_infolabel()
        Initialise l'affichage de l'image d'information.
    set_values(mode, distance_seuil, graphique_3d_checked, field_settings)
        Définit les valeurs des paramètres dans l'interface.
    get_selected_mode()
        Retourne le mode sélectionné par l'utilisateur.
    is_graphique_3d_checked()
        Indique si le graphique 3D est activé.
    mode_changed(index)
        Met à jour l'état du mode tracé en fonction de l'index sélectionné.
    get_field_settings()
        Retourne les paramètres de champ définis par l'utilisateur.
    """

    def __init__(self, parent=None):
        super(ParametresDialog, self).__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'settings.ui'), self)
        self.ModeTrace.addItem("Mode Automatique (Distance)")
        self.ModeTrace.addItem("Mode Manuel (Touche 'T')")
        self.ModeTrace.currentIndexChanged.connect(self.mode_changed)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.images = [f'logo{i}.png' for i in range(1, 7)]
        self.current_image_index = 0
        self.setup_infolabel()

        self.update_image()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_image)
        self.timer.start(600)

        self.pushButtonOpenPDF.clicked.connect(self.open_pdf)

    def open_pdf(self):
        """
        Ouvre le fichier PDF d'aide utilisateur.

        Cette méthode utilise le service de bureau pour ouvrir le fichier PDF local avec des informations d'aide.
        """

        pdf_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'aide.pdf')
        QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))

    def update_image(self):
        """
        Met à jour l'affichage de l'image dans le label approprié.

        Charge l'image suivante de la liste et la redimensionne pour l'afficher correctement dans le label `logoLabel`.
        """

        png_path = os.path.join(os.path.dirname(__file__), '..', 'sscreen', self.images[self.current_image_index])
        pixmap = QPixmap(png_path)

        if not pixmap.isNull():
            pixmap = pixmap.scaled(self.logoLabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logoLabel.setPixmap(pixmap)
            self.logoLabel.setFrameShape(QFrame.NoFrame)
            self.logoLabel.setFrameShadow(QFrame.Plain)

    def next_image(self):
        """
        Passe à l'image suivante dans la liste des images à afficher.

        Cette méthode met à jour l'index de l'image et appelle `update_image` pour refléter le changement d'image.
        """

        # Passer à l'image suivante
        self.current_image_index = (self.current_image_index + 1) % len(self.images)
        self.update_image()

    def setup_infolabel(self):
        """
        Initialise l'affichage de l'image d'information.

        Cette méthode charge l'image d'information depuis le dossier `docs` et l'affiche dans le label `Infolabel`.
        """

        image_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'info.png')
        pixmap = QPixmap(image_path)

        if not pixmap.isNull():
            pixmap = pixmap.scaled(self.Infolabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.Infolabel.setPixmap(pixmap)
            self.Infolabel.setFrameShape(QFrame.NoFrame)
            self.Infolabel.setFrameShadow(QFrame.Plain)

    def set_values(self, mode, distance_seuil, graphique_3d_checked, field_settings):
        """
        Définit les valeurs des paramètres de l'interface en fonction des données fournies.

        Parameters
        ----------
        mode : int
            Mode de sélection, 1 pour Automatique, 2 pour Manuel.
        distance_seuil : float
            Distance seuil pour le traitement.
        graphique_3d_checked : bool
            Indicateur pour activer ou désactiver le graphique 3D.
        field_settings : dict
            Dictionnaire contenant les paramètres des champs avec des valeurs booléennes.
        """

        self.ModeTrace.setCurrentIndex(0 if mode == 1 else 1)

        self.mode_changed(self.ModeTrace.currentIndex())
        self.graphique3D.setChecked(graphique_3d_checked)

        self.radioButton_OBJECTID_Oui.setChecked(field_settings.get('OBJECTID', True))
        self.radioButton_OBJECTID_Non.setChecked(not field_settings.get('OBJECTID', True))

        self.radioButton_SHAPE_LENGTH_Oui.setChecked(field_settings.get('SHAPE_LENGTH', True))
        self.radioButton_SHAPE_LENGTH_Non.setChecked(not field_settings.get('SHAPE_LENGTH', True))

        self.radioButton_HORADATEUR_Oui.setChecked(field_settings.get('HORADATEUR', True))
        self.radioButton_HORADATEUR_Non.setChecked(not field_settings.get('HORADATEUR', True))

    def get_selected_mode(self):
        """
        Retourne le mode sélectionné par l'utilisateur.

        Returns
        -------
        int
            1 pour 'Mode Automatique', 2 pour 'Mode Manuel'.
        """

        # Retourner 1 pour 'Mode Automatique', 2 pour 'Mode Manuel'
        return 1 if self.ModeTrace.currentIndex() == 0 else 2

    def is_graphique_3d_checked(self):
        """
        Indique si le graphique 3D est activé.

        Returns
        -------
        bool
            True si le graphique 3D est coché, False sinon.
        """

        return self.graphique3D.isChecked()

    def mode_changed(self, index):
        """
        Met à jour l'état du mode tracé en fonction de l'index sélectionné.

        Parameters
        ----------
        index : int
            Index du mode sélectionné, 0 pour Automatique, 1 pour Manuel.
        """

        is_automatique = (index == 0)

    def get_field_settings(self):
        """
        Retourne les paramètres de champ définis par l'utilisateur.

        Returns
        -------
        dict
            Un dictionnaire contenant les états des paramètres de champ avec des valeurs booléennes.
        """

        return {
            'OBJECTID': self.radioButton_OBJECTID_Oui.isChecked(),
            'Denomination': self.radioButton_Denomination_Oui.isChecked(),
            'SHAPE_LENGTH': self.radioButton_SHAPE_LENGTH_Oui.isChecked(),
            'HORADATEUR': self.radioButton_HORADATEUR_Oui.isChecked()

        }