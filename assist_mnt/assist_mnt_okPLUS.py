"""
Assist_mnt.py

"""
import importlib
import math

import os
import sys
from osgeo import gdal
from qgis._core import QgsProcessing, QgsPoint

# Ajouter le répertoire du plugin au PYTHONPATH
chemin_plugin = os.path.dirname(__file__)
if chemin_plugin not in sys.path:
    sys.path.append(chemin_plugin)


from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QFrame
from PyQt5.QtGui import QPixmap

from PyQt5.QtCore import QUrl, QTimer

import matplotlib
import numpy as np
import processing
from qgis.PyQt.QtCore import QCoreApplication, Qt, QObject, QPoint, QVariant
from qgis.core import QgsField
from qgis.PyQt.QtGui import QIcon, QColor, QPainter
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QMenu, QToolButton, QInputDialog, QDockWidget, QWidget, QVBoxLayout, QComboBox, QApplication
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsCoordinateReferenceSystem,
    QgsRasterTransparency,
    QgsMapLayer,
    QgsProcessingFeedback,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsCoordinateTransform,
    edit
)
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QSlider, QLabel, QPushButton, QGridLayout
from qgis.gui import QgsMapTool, QgsRubberBand
from PyQt5.QtWidgets import QInputDialog
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl

# Importer le module rupturedepente et le recharger
import rupturedepente
import profilgraph
import sscreen
importlib.reload(sscreen)
importlib.reload(rupturedepente)
importlib.reload(profilgraph)

from rupturedepente import OutilRupturePente
from profilgraph import ProfilGraphDock
from sscreen.sscreen import SplashScreen
from sscreen.sscreen_load import SplashScreenLoad

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg



class AssistMnt(QObject):
    """
    Plugin QGIS pour l'assistance sur MNT.

    Args:
        interface_qgis (QgisInterface): L'interface QGIS principale.
    """

    def __init__(self, interface_qgis):
        """Initialise le plugin."""
        super().__init__()
        self.interface_qgis = interface_qgis
        self.canvas = interface_qgis.mapCanvas()
        self.chemin_plugin = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.traduire(u'&Assist MNT')
        self.barre_outils = None  # La barre d'outils sera créée plus tard
        self.barre_outils_visible = False
        self.outil_trace_crete = None
        self.fenetre_profil = None
        self.liste_modes = None
        self.action_liste_modes = None
        self.graphique_3d_active = True
        self.couche_crete = None
        self.couche_rupture = None
        QgsProject.instance().layerWillBeRemoved.connect(self.on_layer_will_be_removed)
        self.field_settings = {
            'OBJECTID': True,
            'Denomination':True,
            'SHAPE_LENGTH': True,
            'HORADATEUR': True
        }
        self.splash_screen = None


    def traduire(self, message):
        """
        Traduit un message en utilisant l'API de traduction Qt.

        Args:
            message (str): Le message à traduire.

        Returns:
            str: Le message traduit.
        """
        return QCoreApplication.translate('AssistMnt', message)

    def on_layer_will_be_removed(self, layer_id):
        if self.couche_rupture and self.couche_rupture.id() == layer_id:
            self.couche_rupture = None
        if self.couche_crete and self.couche_crete.id() == layer_id:
            self.couche_crete = None

    def initGui(self):
        """Configure le menu initial."""
        chemin_icones = self.chemin_plugin

        # Créer le menu "Hydroline"
        self.menu_hydroline = QMenu("Hydroline", self.interface_qgis.mainWindow())

        # Créer l'action "Paramètres" avec une icône et l'ajouter au menu
        self.action_settings = QAction(
            QIcon(os.path.join(chemin_icones, "icon_setting.png")),
            self.traduire(u'Paramètres'),
            self.interface_qgis.mainWindow()
        )
        self.action_settings.triggered.connect(self.ouvrir_parametres)
        self.menu_hydroline.addAction(self.action_settings)

        # Créer l'action "Assistance au tracé" avec une icône
        self.action_assistance_trace = QAction(
            QIcon(os.path.join(chemin_icones, "icon_toolbox.png")),
            "Assistance au tracé",
            self.interface_qgis.mainWindow()
        )
        self.action_assistance_trace.triggered.connect(self.basculer_visibilite_barre_outils)
        self.menu_hydroline.addAction(self.action_assistance_trace)

        # Ajouter les autres actions
        chemin_icon_prolongement = os.path.join(self.chemin_plugin, "icon_prolongement.png")
        chemin_icon_profilgraph = os.path.join(self.chemin_plugin, "icon_profilgraph.png")

        self.action_prolongement = QAction(
            QIcon(chemin_icon_prolongement),
            "Prolongement de profil",
            self.interface_qgis.mainWindow()
        )
        self.action_prolongement.triggered.connect(self.lancer_prolongement)
        self.menu_hydroline.addAction(self.action_prolongement)

        self.action_profilgraph = QAction(
            QIcon(chemin_icon_profilgraph),
            "GraphZ",
            self.interface_qgis.mainWindow()
        )
        self.action_profilgraph.triggered.connect(self.lancer_GraphZ)
        self.menu_hydroline.addAction(self.action_profilgraph)

        # Ajouter le menu "Hydroline" à la barre de menus principale
        self.interface_qgis.mainWindow().menuBar().addMenu(self.menu_hydroline)

    def setup_toolbar_actions(self):
        """Configure les actions de la barre d'outils."""
        chemin_icones = self.chemin_plugin

        # Créer le bouton MNTvisu et l'ajouter à la barre d'outils
        self.action_mntvisu = QAction(
            QIcon(os.path.join(chemin_icones, "icon_2dm.png")),
            self.traduire(u'MNTvisu'),
            self.interface_qgis.mainWindow()
        )
        self.action_mntvisu.triggered.connect(self.afficher_mnt)
        self.barre_outils.addAction(self.action_mntvisu)

        # Configuration MNT
        self.menu_configuration = QMenu()
        self.menu_configuration.setTitle("Configuration MNT")

        self.action_tracer_seuils = QAction("Tracé de seuils", self.interface_qgis.mainWindow())
        self.action_tracer_seuils.triggered.connect(self.afficher_outils_seuils)
        self.menu_configuration.addAction(self.action_tracer_seuils)

        self.action_tracer_rupture = QAction("Tracé de rupture de pente", self.interface_qgis.mainWindow())
        self.action_tracer_rupture.triggered.connect(self.afficher_outil_rupture_pente)
        self.menu_configuration.addAction(self.action_tracer_rupture)

        self.action_reinitialiser = QAction("Réinitialiser", self.interface_qgis.mainWindow())
        self.action_reinitialiser.triggered.connect(self.reinitialiser_barre_outils)
        self.menu_configuration.addAction(self.action_reinitialiser)

        # Ajouter le menu à la barre d'outils
        self.bouton_menu = QToolButton()
        self.bouton_menu.setText("Configuration MNT")
        self.bouton_menu.setMenu(self.menu_configuration)
        self.bouton_menu.setPopupMode(QToolButton.InstantPopup)
        self.action_bouton_menu = self.barre_outils.addWidget(self.bouton_menu)

        # Garder une référence aux actions de la barre d'outils
        self.actions = [self.action_mntvisu, self.action_bouton_menu]

    def basculer_visibilite_barre_outils(self):
        """
        Bascule la visibilité de la barre d'outils. Affiche le splash screen seulement lors de l'ouverture.
        """
        # Vérifier si la barre d'outils est déjà visible
        is_currently_visible = self.barre_outils_visible

        if not is_currently_visible:
            # La barre d'outils n'est pas visible, on va l'ouvrir
            # Afficher le splash screen
            self.splash_screen = SplashScreen()
            self.splash_screen.setParent(self.interface_qgis.mainWindow())
            self.splash_screen.finished.connect(self.lancer_outil)
            self.splash_screen.show()
        else:
            # La barre d'outils est visible, on la cache
            if self.barre_outils is not None:
                self.barre_outils.setVisible(False)
            self.barre_outils_visible = False

    def lancer_outil(self):
        """
        Fonction appelée lorsque le splash screen est terminé.
        """
        self.splash_screen.deleteLater()
        self.splash_screen = None

        # Créer la barre d'outils si elle n'existe pas déjà
        if self.barre_outils is None:
            self.barre_outils = self.interface_qgis.addToolBar('Assist MNT')
            self.barre_outils.setObjectName('Assist MNT')
            self.setup_toolbar_actions()  # Configure les actions de la barre d'outils

        # Afficher la barre d'outils
        self.barre_outils_visible = True
        self.barre_outils.setVisible(True)

    def ligne_crete_suivante(self):
        """Valide la polyligne actuelle et commence une nouvelle."""
        if self.outil_trace_crete is not None:
            self.outil_trace_crete.confirmer_polyligne()
        else:
            QMessageBox.warning(None, "Avertissement", "Aucun tracé en cours.")

    def ligne_rupture_suivante(self):
        """Valide la polyligne actuelle et commence une nouvelle."""
        if self.outil_rupture_pente is not None:
            self.outil_rupture_pente.confirmer_polyligne()
        else:
            QMessageBox.warning(None, "Avertissement", "Aucun tracé en cours.")

    def lancer_GraphZ(self):
        """Ouvre le dock de profil graphique."""
        self.prof_graph_dock = ProfilGraphDock(self.canvas, self.interface_qgis.mainWindow())
        self.interface_qgis.addDockWidget(Qt.BottomDockWidgetArea, self.prof_graph_dock)

    def unload(self):
        """Supprime la barre d'outils du plugin et ses boutons de l'interface QGIS."""
        if self.barre_outils is not None:
            # Supprimer les actions de la barre d'outils
            for action in self.actions:
                self.barre_outils.removeAction(action)
            # Retirer la barre d'outils de l'interface
            self.interface_qgis.mainWindow().removeToolBar(self.barre_outils)
            self.barre_outils = None

        # Supprimer le menu "Hydroline" de la barre des menus
        barre_menus = self.interface_qgis.mainWindow().menuBar()
        barre_menus.removeAction(self.menu_hydroline.menuAction())

        # Supprimer la fenêtre de profil si elle est présente
        if self.fenetre_profil is not None:
            self.interface_qgis.removeDockWidget(self.fenetre_profil)
            self.fenetre_profil = None

    def ouvrir_parametres(self):
        """Ouvre la fenêtre de paramètres."""
        dialog = ParametresDialog(self.interface_qgis.mainWindow())
        # Définir les valeurs actuelles
        if self.outil_trace_crete:
            current_mode = self.outil_trace_crete.mode
            distance_seuil = self.outil_trace_crete.distance_seuil
        else:
            current_mode = 1
            distance_seuil = 10

        # Passer l'état actuel du graphique 3D et les paramètres des champs
        dialog.set_values(current_mode, distance_seuil, self.graphique_3d_active, self.field_settings)

        if dialog.exec_():
            # L'utilisateur a cliqué sur OK
            selected_mode = dialog.get_selected_mode()
            graphique_3d = dialog.is_graphique_3d_checked()
            self.graphique_3d_active = graphique_3d  # Mettre à jour l'état
            self.field_settings = dialog.get_field_settings()  # Mettre à jour les paramètres des champs

            # Mettre à jour les couches existantes
            self.mettre_a_jour_champs(self.couche_crete)
            self.mettre_a_jour_champs(self.couche_rupture)

            # Appliquer les paramètres
            if self.outil_trace_crete:
                self.outil_trace_crete.definir_mode(selected_mode, distance_seuil)
                # Mettre à jour les préférences des champs dans l'outil de tracé
                self.outil_trace_crete.field_settings = self.field_settings

                # Gérer l'affichage du graphique 3D si nécessaire
                if graphique_3d:
                    if self.fenetre_profil is None:
                        self.fenetre_profil = FenetreProfilElevation(self.interface_qgis.mainWindow())
                        self.interface_qgis.addDockWidget(Qt.RightDockWidgetArea, self.fenetre_profil)
                        self.outil_trace_crete.definir_fenetre_profil(self.fenetre_profil)
                else:
                    if self.fenetre_profil is not None:
                        self.interface_qgis.removeDockWidget(self.fenetre_profil)
                        self.fenetre_profil = None
                        self.outil_trace_crete.definir_fenetre_profil(None)
            # Appliquer les paramètres à l'outil de rupture de pente si nécessaire
            if hasattr(self, 'outil_rupture_pente') and self.outil_rupture_pente:
                self.outil_rupture_pente.field_settings = self.field_settings
        else:
            # L'utilisateur a cliqué sur Annuler
            pass

    def mettre_a_jour_champs(self, couche):
        if couche is not None:
            champs_presentes = [field.name() for field in couche.fields()]
            ids_a_mettre_a_jour = []
            with edit(couche):
                for feature in couche.getFeatures():
                    attrs = feature.attributes()
                    changed = False
                    for index, field_name in enumerate(champs_presentes):
                        if not self.field_settings.get(field_name, True):
                            if attrs[index] is not None:
                                feature[field_name] = None
                                changed = True
                    if changed:
                        couche.updateFeature(feature)

    def effacer_actions_barre_outils(self):
        """Supprime toutes les actions de la barre d'outils sauf MNTvisu et le menu."""
        # Actions à conserver
        actions_a_conserver = [self.action_mntvisu, self.action_bouton_menu]

        # Actions à supprimer
        actions_a_supprimer = [action for action in self.barre_outils.actions() if action not in actions_a_conserver]

        for action in actions_a_supprimer:
            self.barre_outils.removeAction(action)
            if action in self.actions and action not in actions_a_conserver:
                self.actions.remove(action)

    def lancer_prolongement(self):
        """Lance l'outil de prolongement de profil."""
        import prolongement
        self.interface_qgis.mainWindow().statusBar().showMessage("Chargement prolongement profil...", 2000)
        prolongement.main()


    def afficher_outils_seuils(self):
        """Affiche les boutons pour le tracé de seuils."""
        # Effacer les actions existantes sauf MNTvisu et le menu
        self.effacer_actions_barre_outils()

        chemin_icones = self.chemin_plugin

        # Bouton pour démarrer le MNT
        self.action_demarrer_mnt = QAction(QIcon(os.path.join(chemin_icones, "icon_seuil.png")), self.traduire(u'Démarrer MNT'),
                                           self.interface_qgis.mainWindow())
        self.action_demarrer_mnt.triggered.connect(self.demarrer_mnt)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_demarrer_mnt)
        self.actions.append(self.action_demarrer_mnt)

        # Bouton pour la simplification
        self.bouton_simplification = QToolButton()
        self.bouton_simplification.setText("Simplification")
        self.bouton_simplification.setCheckable(True)
        self.bouton_simplification.toggled.connect(self.basculer_simplification)
        self.action_bouton_simplification = self.barre_outils.insertWidget(self.action_bouton_menu, self.bouton_simplification)
        self.actions.append(self.action_bouton_simplification)


        # Bouton pour le mode de tracé libre
        self.action_tracer_libre = QAction(QIcon(os.path.join(chemin_icones, "icon_toggle.png")),
                                           self.traduire(u'Tracé Libre'), self.interface_qgis.mainWindow())
        self.action_tracer_libre.setCheckable(True)
        self.action_tracer_libre.toggled.connect(self.basculer_tracer_libre)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_tracer_libre)
        self.actions.append(self.action_tracer_libre)

        # Bouton pour "lignes de crêtes suivante"
        self.action_ligne_crete_suivante = QAction(
            QIcon(os.path.join(chemin_icones, "icon_next.png")),
            self.traduire(u'Lignes de crêtes suivante'),
            self.interface_qgis.mainWindow()
        )
        self.action_ligne_crete_suivante.triggered.connect(self.ligne_crete_suivante)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_ligne_crete_suivante)
        self.actions.append(self.action_ligne_crete_suivante)

        # Bouton pour arrêter le MNT
        self.action_arreter_mnt = QAction(QIcon(os.path.join(chemin_icones, "icon_stop.png")), self.traduire(u'Arrêter MNT'),
                                          self.interface_qgis.mainWindow())
        self.action_arreter_mnt.triggered.connect(self.arreter_mnt)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_arreter_mnt)
        self.actions.append(self.action_arreter_mnt)

    def afficher_outil_rupture_pente(self):
        """Affiche les boutons pour le tracé de rupture de pente."""
        # Effacer les actions existantes sauf MNTvisu et le menu
        self.effacer_actions_barre_outils()

        chemin_icones = self.chemin_plugin

        # Bouton pour démarrer la rupture de pente
        self.action_demarrer_rupture = QAction(QIcon(os.path.join(chemin_icones, "icon_rupture.png")),
                                               self.traduire(u'Démarrer rupture de pente'),
                                               self.interface_qgis.mainWindow())
        self.action_demarrer_rupture.triggered.connect(self.demarrer_rupture_pente)
        # Insérer l'action avant le bouton du menu
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_demarrer_rupture)
        self.actions.append(self.action_demarrer_rupture)

        # Bouton pour la simplification
        self.bouton_simplification_pente = QToolButton()
        self.bouton_simplification_pente.setText("Simplification")
        self.bouton_simplification_pente.setCheckable(True)
        self.bouton_simplification_pente.toggled.connect(self.basculer_simplification_rupture_pente)
        # Insérer le widget avant le bouton du menu
        self.action_bouton_simplification = self.barre_outils.insertWidget(self.action_bouton_menu,
                                                                           self.bouton_simplification_pente)
        self.actions.append(self.action_bouton_simplification)

        # Bouton pour "ligne de rupture suivante"
        self.action_ligne_rupture_suivante = QAction(
            QIcon(os.path.join(chemin_icones, "icon_next.png")),
            self.traduire(u'Ligne de rupture suivante'),
            self.interface_qgis.mainWindow()
        )
        self.action_ligne_rupture_suivante.triggered.connect(self.ligne_rupture_suivante)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_ligne_rupture_suivante)
        self.actions.append(self.action_ligne_rupture_suivante)

        # Bouton pour arrêter la rupture de pente
        self.action_arreter_rupture = QAction(QIcon(os.path.join(chemin_icones, "icon_stop.png")),
                                              self.traduire(u'Stop rupture'),
                                              self.interface_qgis.mainWindow())
        self.action_arreter_rupture.triggered.connect(self.arreter_rupture)
        # Insérer l'action avant le bouton du menu
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_arreter_rupture)
        self.actions.append(self.action_arreter_rupture)

        # Menu déroulant pour le mode
        self.mode_combobox = QComboBox()
        self.mode_combobox.addItem("Concave")
        self.mode_combobox.addItem("Convexe")
        self.mode_combobox.currentIndexChanged.connect(self.changer_mode_rupture)

        # Insérer le widget avant le bouton du menu
        self.action_mode_combobox = self.barre_outils.insertWidget(self.action_bouton_menu, self.mode_combobox)
        self.actions.append(self.action_mode_combobox)

    def basculer_simplification_rupture_pente(self, coche):
        """Active ou désactive la simplification pour l'outil de rupture de pente."""
        if hasattr(self, 'outil_rupture_pente') and self.outil_rupture_pente:
            if coche:
                dialog = SliderDialog()
                if dialog.exec_() == QDialog.Accepted:
                    tolerance = dialog.get_value()
                    self.outil_rupture_pente.tolerance_simplification = tolerance
                else:
                    self.bouton_simplification_pente.setChecked(False)
                    return
            self.outil_rupture_pente.definir_simplification(coche)
        else:
            QMessageBox.warning(None, "Avertissement",
                                "Veuillez d'abord activer l'outil avec le bouton Démarrer rupture de pente.")
            self.bouton_simplification_pente.setChecked(False)

    def reinitialiser_barre_outils(self):
        """Réinitialise la barre d'outils à son état initial."""
        # Effacer les actions existantes sauf MNTvisu et le menu
        self.effacer_actions_barre_outils()

        # Réinitialiser les outils actifs
        if self.outil_trace_crete is not None:
            self.outil_trace_crete.reinitialiser()
            self.outil_trace_crete = None
            self.canvas.unsetMapTool(self.canvas.mapTool())

    def basculer_simplification(self, coche):
        if self.outil_trace_crete is not None:
            if coche:
                dialog = SliderDialog()
                if dialog.exec_() == QDialog.Accepted:
                    tolerance = dialog.get_value()
                    self.outil_trace_crete.tolerance_simplification = tolerance
                else:
                    self.bouton_simplification.setChecked(False)
                    return
            self.outil_trace_crete.definir_simplification(coche)
        else:
            QMessageBox.warning(None, "Avertissement", "Veuillez d'abord activer l'outil avec le bouton Démarrer MNT.")
            self.bouton_simplification.setChecked(False)

    def basculer_tracer_libre(self, coche):
        """Active ou désactive le mode de tracé libre."""
        if self.outil_trace_crete is not None:
            self.outil_trace_crete.definir_mode_trace_libre(coche)
        else:
            QMessageBox.warning(None, "Avertissement", "Veuillez d'abord activer l'outil avec le bouton Démarrer MNT.")
            # Désactiver le bouton si l'outil n'est pas actif
            self.action_tracer_libre.setChecked(False)


    def mean_filter_raster(self, input_raster_layer, kernel_size=3):
        """
        Applique un filtre moyen à la couche raster d'entrée.

        Args:
            input_raster_layer (QgsRasterLayer): La couche raster d'entrée à filtrer.
            kernel_size (int): La taille du noyau pour le filtre moyen.

        Returns:
            QgsRasterLayer: La couche raster filtrée.
        """

        from osgeo import gdal
        import numpy as np
        import tempfile
        import os

        # Obtenir le chemin source de la couche raster
        input_path = input_raster_layer.source()

        # Ouvrir le raster en utilisant GDAL
        input_dataset = gdal.Open(input_path, gdal.GA_ReadOnly)
        if input_dataset is None:
            return None

        # Obtenir la bande raster
        input_band = input_dataset.GetRasterBand(1)

        # Lire les données raster en tant que tableau NumPy
        input_array = input_band.ReadAsArray()
        if input_array is None:
            return None

        # Appliquer le filtre moyen en utilisant NumPy
        # Créer le noyau
        kernel = np.ones((kernel_size, kernel_size), dtype=float) / (kernel_size * kernel_size)
        # Appliquer la convolution en utilisant scipy.signal.convolve2d si disponible
        try:
            from scipy.signal import convolve2d
            output_array = convolve2d(input_array, kernel, mode='same', boundary='symm')
        except ImportError:
            # Si scipy n'est pas disponible, utiliser une convolution manuelle
            # Padding de l'array pour gérer les bords
            pad_size = kernel_size // 2
            padded_array = np.pad(input_array, pad_size, mode='edge')

            # Initialiser l'array de sortie
            output_array = np.zeros_like(input_array, dtype=float)

            # Boucler sur l'array pour appliquer le filtre
            for i in range(output_array.shape[0]):
                for j in range(output_array.shape[1]):
                    # Extraire la sous-matrice
                    sub_array = padded_array[i:i + kernel_size, j:j + kernel_size]
                    # Calculer la moyenne
                    output_array[i, j] = np.sum(sub_array * kernel)

        # Créer un fichier temporaire pour le raster de sortie
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, 'filtered_raster.tif')

        # Créer le dataset de sortie
        driver = gdal.GetDriverByName('GTiff')
        output_dataset = driver.Create(
            output_path,
            input_dataset.RasterXSize,
            input_dataset.RasterYSize,
            1,
            gdal.GDT_Float32
        )
        if output_dataset is None:
            return None

        # Copier les informations de géoréférencement
        output_dataset.SetGeoTransform(input_dataset.GetGeoTransform())
        output_dataset.SetProjection(input_dataset.GetProjection())

        # Écrire l'array de sortie dans la bande raster
        output_band = output_dataset.GetRasterBand(1)
        output_band.WriteArray(output_array)
        output_band.FlushCache()

        # Fermer les datasets
        input_dataset = None
        output_dataset = None

        # Créer une nouvelle couche raster à partir du chemin de sortie
        output_raster_layer = QgsRasterLayer(output_path, 'Raster Filtré')

        if not output_raster_layer.isValid():
            return None

        return output_raster_layer

    def afficher_mnt(self):
        """Affiche le MNT avec ombrage et style, en gérant les couches raster et TIN."""

        self.splash_screenLoad = SplashScreenLoad()
        self.splash_screenLoad.setParent(self.interface_qgis.mainWindow())
        self.splash_screenLoad.show()

        QApplication.processEvents()


        code_epsg = 2154  # RGF93 / Lambert-93

        # Obtenir les couches sélectionnées
        couches_selectionnees = self.interface_qgis.layerTreeView().selectedLayers()

        if not couches_selectionnees:
            QMessageBox.warning(None, "Avertissement", "Aucune couche sélectionnée.")
            # Fermer le splash screen si aucune couche n'est sélectionnée
            self.splash_screenLoad.close()
            return

        retour = QgsProcessingFeedback()

        # Séparer les couches raster et les couches TIN (Mesh)
        couches_raster = []
        couches_tin = []

        for couche in couches_selectionnees:
            if couche.type() == QgsMapLayer.RasterLayer:
                couches_raster.append(couche)
            elif couche.type() == QgsMapLayer.MeshLayer:
                couches_tin.append(couche)
            else:
                QMessageBox.warning(None, "Avertissement", f"Type de couche non supporté : {couche.name()}")
                # Fermer le splash screen si type de couche non pris en charge
                self.splash_screenLoad.close()
                return

        #### Traitement des couches TIN ####
        QApplication.processEvents()
        for couche_tin in couches_tin:
            # Obtenir le chemin physique du TIN
            tin_path = couche_tin.publicSource()
            nom_couche = couche_tin.name()

            # Obtenir le CRS de la couche TIN
            crs_tin = couche_tin.crs()

            # Rasteriser le TIN
            parametres_meshrasterize = {
                'INPUT': tin_path,
                'DATASET_GROUPS': [0],  # Ajustez ce paramètre si nécessaire
                'DATASET_TIME': {'type': 'static'},
                'EXTENT': None,
                'PIXEL_SIZE': 1.0,  # Vous pouvez ajuster la résolution si nécessaire
                'CRS_OUTPUT': crs_tin,  # Conserver le CRS du TIN
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }

            resultat_rasterize = processing.run("native:meshrasterize", parametres_meshrasterize, feedback=retour)
            couche_raster = QgsRasterLayer(resultat_rasterize['OUTPUT'], f"{nom_couche}_raster")

            if not couche_raster.isValid():
                QMessageBox.critical(None, "Erreur", f"Échec de la conversion du TIN en raster : {couche_tin.name()}")
                # Fermer le splash screen si la conversion échoue
                self.splash_screenLoad.close()
                return

            # Appliquer le filtre moyen au raster dérivé du TIN
            couche_raster_filtre = self.mean_filter_raster(couche_raster, kernel_size=3)
            if couche_raster_filtre is None:
                QMessageBox.critical(None, "Erreur",
                                     f"Échec de l'application du filtre moyen au raster : {couche_tin.name()}")
                # Fermer le splash screen si le filtre échoue
                self.splash_screenLoad.close()
                return

            # Appliquer le style 'styleQGIS.qml' à la couche raster filtrée
            chemin_style = os.path.join(self.chemin_plugin, 'styleQGIS.qml')
            if os.path.exists(chemin_style):
                couche_raster_filtre.loadNamedStyle(chemin_style)
                couche_raster_filtre.triggerRepaint()
            else:
                QMessageBox.warning(None, "Avertissement", "Le fichier de style 'styleQGIS.qml' est introuvable.")

            # Ajouter la couche raster filtrée avec le CRS du TIN
            couche_raster_filtre.setCrs(crs_tin)
            QgsProject.instance().addMapLayer(couche_raster_filtre)

            # Générer un ombrage pour la couche raster filtrée
            parametres_ombrage = {
                'INPUT': couche_raster_filtre.source(),
                'BAND': 1,
                'Z_FACTOR': 1.0,
                'SCALE': 1.0,
                'AZIMUTH': 315.0,
                'ALTITUDE': 45.0,
                'COMPUTE_EDGES': False,
                'ZEVENBERGEN': False,
                'MULTIDIRECTIONAL': False,
                'COMBINED': False,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }

            resultat_ombrage = processing.run("gdal:hillshade", parametres_ombrage, feedback=retour)
            couche_ombrage = QgsRasterLayer(resultat_ombrage['OUTPUT'], f'Ombrage_{nom_couche}')
            couche_ombrage.setCrs(crs_tin)

            if not couche_ombrage.isValid():
                QMessageBox.critical(None, "Erreur", f"Échec de la création de l'ombrage pour {nom_couche}.")
                # Fermer le splash screen si l'ombrage échoue
                self.splash_screenLoad.close()
                return

            # Ajouter la couche d'ombrage en dessous de la couche raster filtrée
            QgsProject.instance().addMapLayer(couche_ombrage, False)
            racine = QgsProject.instance().layerTreeRoot()
            noeud_raster = racine.findLayer(couche_raster_filtre.id())
            racine.insertLayer(racine.children().index(noeud_raster) + 1, couche_ombrage)

            # Rendre les pixels avec une valeur de 0 totalement transparents
            transparence = couche_raster_filtre.renderer().rasterTransparency()
            pixel_transparent = QgsRasterTransparency.TransparentSingleValuePixel()
            pixel_transparent.min = 0
            pixel_transparent.max = 0
            liste_pixels_transparents = [pixel_transparent]
            transparence.setTransparentSingleValuePixelList(liste_pixels_transparents)
            couche_raster_filtre.triggerRepaint()

            # Appliquer le mode de fusion 'Multiply' à la couche raster filtrée
            couche_raster_filtre.setBlendMode(QPainter.CompositionMode_Multiply)
            couche_raster_filtre.triggerRepaint()

            # Supprimer la couche TIN après conversion
            QgsProject.instance().removeMapLayer(couche_tin.id())

            # Rafraîchir la symbologie de la couche dans l'arbre des couches
            layer_tree_view = self.interface_qgis.layerTreeView()
            layer_tree_view.refreshLayerSymbology(couche_raster_filtre.id())

        #### Traitement des autres couches raster ####
        QApplication.processEvents()
        if couches_raster:
            # Assigner EPSG 2154 à chaque couche raster sélectionnée
            crs = QgsCoordinateReferenceSystem(code_epsg)
            for couche in couches_raster:
                if couche.crs() != crs:
                    couche.setCrs(crs)
                    couche.triggerRepaint()

            # Si plusieurs couches raster sont présentes, les combiner en une seule couche raster
            if len(couches_raster) > 1:
                # Rassembler les chemins des fichiers des couches raster
                chemins_raster = [couche.source() for couche in couches_raster]

                # Définir les paramètres pour l'algorithme 'gdal:merge'
                parametres_fusion = {
                    'INPUT': chemins_raster,
                    'PCT': False,
                    'SEPARATE': False,
                    'NODATA_INPUT': None,
                    'NODATA_OUTPUT': None,
                    'OPTIONS': '',
                    'DATA_TYPE': 6,  # Float32
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }

                # Exécuter l'algorithme de fusion
                resultat_fusion = processing.run("gdal:merge", parametres_fusion, feedback=retour)
                couche_fusionnee = QgsRasterLayer(resultat_fusion['OUTPUT'], 'Raster_Combine')

                if not couche_fusionnee.isValid():
                    QMessageBox.critical(None, "Erreur", "Échec de la création du raster combiné.")
                    # Fermer le splash screen si la fusion échoue
                    self.splash_screenLoad.close()
                    return

                # Appliquer un calcul raster pour arrondir à 1 décimale (Float32)
                parametres_calcul = {
                    'INPUT_A': couche_fusionnee.source(),
                    'BAND_A': 1,
                    'FORMULA': 'round(A, 1)',
                    'OUTPUT': 'TEMPORARY_OUTPUT',
                    'RTYPE': 6  # Float32
                }

                resultat_calcul = processing.run("gdal:rastercalculator", parametres_calcul, feedback=retour)
                couche_arrondie = QgsRasterLayer(resultat_calcul['OUTPUT'], 'Raster Final Arrondi')

                if not couche_arrondie.isValid():
                    QMessageBox.critical(None, "Erreur", "Échec de l'arrondi à 1 décimale.")
                    # Fermer le splash screen si l'arrondi échoue
                    self.splash_screenLoad.close()
                    return

                couche_arrondie.setCrs(crs)
                QgsProject.instance().addMapLayer(couche_arrondie)
                couche_combinee = couche_arrondie  # on remplace définitivement
            else:
                # Une seule couche raster, l'utiliser directement
                couche_combinee = couches_raster[0]

            # --- Appliquer le filtre moyen au raster combiné ou unique ---
            couche_combinee_filtre = self.mean_filter_raster(couche_combinee, kernel_size=3)
            if couche_combinee_filtre is None:
                QMessageBox.critical(None, "Erreur", "Échec de l'application du filtre moyen au raster.")
                # Fermer le splash screen si le filtre échoue
                self.splash_screenLoad.close()
                return

            # Générer un ombrage de la couche raster filtrée
            parametres_ombrage = {
                'INPUT': couche_combinee_filtre.source(),
                'BAND': 1,
                'Z_FACTOR': 1.0,
                'SCALE': 1.0,
                'AZIMUTH': 315.0,
                'ALTITUDE': 45.0,
                'COMPUTE_EDGES': False,
                'ZEVENBERGEN': False,
                'MULTIDIRECTIONAL': False,
                'COMBINED': False,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }

            resultat_ombrage = processing.run("gdal:hillshade", parametres_ombrage, feedback=retour)
            couche_ombrage = QgsRasterLayer(resultat_ombrage['OUTPUT'], 'Ombrage')
            couche_ombrage.setCrs(crs)

            if not couche_ombrage.isValid():
                QMessageBox.critical(None, "Erreur", "Échec de la création de l'ombrage.")
                # Fermer le splash screen si l'ombrage échoue
                self.splash_screenLoad.close()
                return

            # Appliquer le style 'styleQGIS.qml' à la couche raster filtrée
            chemin_style = os.path.join(self.chemin_plugin, 'styleQGIS.qml')
            if os.path.exists(chemin_style):
                couche_combinee_filtre.loadNamedStyle(chemin_style)
                couche_combinee_filtre.triggerRepaint()
            else:
                QMessageBox.warning(None, "Avertissement", "Le fichier de style 'styleQGIS.qml' est introuvable.")

            # Ajouter la couche raster filtrée au projet
            QgsProject.instance().addMapLayer(couche_combinee_filtre)

            # Ajouter la couche d'ombrage en dessous de la couche raster filtrée
            QgsProject.instance().addMapLayer(couche_ombrage, False)
            racine = QgsProject.instance().layerTreeRoot()
            noeud_raster = racine.findLayer(couche_combinee_filtre.id())
            racine.insertLayer(racine.children().index(noeud_raster) + 1, couche_ombrage)

            # Rendre les pixels avec une valeur de 0 totalement transparents
            transparence = couche_combinee_filtre.renderer().rasterTransparency()
            pixel_transparent = QgsRasterTransparency.TransparentSingleValuePixel()
            pixel_transparent.min = 0
            pixel_transparent.max = 0
            liste_pixels_transparents = [pixel_transparent]
            transparence.setTransparentSingleValuePixelList(liste_pixels_transparents)
            couche_combinee_filtre.triggerRepaint()

            # Appliquer le mode de fusion 'Multiply' à la couche raster filtrée
            couche_combinee_filtre.setBlendMode(QPainter.CompositionMode_Multiply)
            couche_combinee_filtre.triggerRepaint()

            # Supprimer les couches raster de base non filtrées si elles ont été fusionnées
            if len(couches_raster) > 1 or couches_raster[0] != couche_combinee_filtre:
                for couche in couches_raster:
                    QgsProject.instance().removeMapLayer(couche.id())

        self.splash_screenLoad.close()

    def demarrer_rupture_pente(self):
        """Activation de l'outil de tracé de rupture de pente."""
        # Afficher la boîte de dialogue pour sélectionner le MNT et la couche de polyligne
        dialog = ChoixCouchesDialog(self.interface_qgis.mainWindow())
        result = dialog.exec_()
        if result == QDialog.Accepted:
            couche_mnt = dialog.get_selected_mnt_layer()
            couche_rupture_selectionnee = dialog.get_selected_polyline_layer()
            nouvelle_couche = dialog.is_new_layer_checked()
        else:
            # L'utilisateur a annulé
            return

        if couche_mnt is None:
            QMessageBox.warning(None, "Avertissement", "Vous devez sélectionner un MNT.")
            return

        # Déterminer le mode sélectionné ('concave' ou 'convexe')
        if hasattr(self, 'mode_combobox'):
            mode_selectionne = 'concave' if self.mode_combobox.currentIndex() == 0 else 'convexe'
        else:
            # Par défaut, utiliser 'concave'
            mode_selectionne = 'concave'
            QMessageBox.warning(None, "Avertissement",
                                "Le mode de rupture de pente n'a pas été défini. Utilisation du mode 'concave' par défaut.")

        # Déterminer la couche de rupture de pente à utiliser
        if couche_rupture_selectionnee is not None:
            self.couche_rupture = couche_rupture_selectionnee
        elif nouvelle_couche:
            # Créer une nouvelle couche de rupture de pente
            crs = self.canvas.mapSettings().destinationCrs()
            self.couche_rupture = QgsVectorLayer(f"MultiLineStringZ?crs={crs.authid()}", "Ruptures de Pente", "memory")
            if not self.couche_rupture.isValid():
                QMessageBox.critical(None, "Erreur",
                                     "Impossible de créer la couche vectorielle pour les ruptures de pente.")
                return
            # Ajouter les champs à la couche en fonction des préférences
            champs = []
            if self.field_settings.get('OBJECTID', True):
                champs.append(QgsField('OBJECTID', QVariant.Int))
            if self.field_settings.get('Denomination', True):
                champs.append(QgsField('Denomination', QVariant.String))
            if self.field_settings.get('SHAPE_LENGTH', True):
                champs.append(QgsField('SHAPE_LENGTH', QVariant.Double))
            if self.field_settings.get('HORADATEUR', True):
                champs.append(QgsField('HORADATEUR', QVariant.String))

            self.couche_rupture.dataProvider().addAttributes(champs)
            self.couche_rupture.updateFields()

            # Ajouter la couche au projet
            QgsProject.instance().addMapLayer(self.couche_rupture)
            # Modifier la symbologie si nécessaire
            symbole = self.couche_rupture.renderer().symbol()
            symbole.setColor(QColor('#FF0000'))  # Couleur rouge pour les ruptures de pente
            symbole.setWidth(1)
        else:
            QMessageBox.warning(None, "Avertissement",
                                "Vous devez sélectionner une couche de polyligne ou cocher 'Nouvelle couche de travail'.")
            return

        # Créer une instance de l'outil de rupture de pente
        self.outil_rupture_pente = OutilRupturePente(self.canvas, couche_mnt, mode=mode_selectionne)

        # Passer la couche vectorielle à l'outil de dessin
        self.outil_rupture_pente.definir_couche_vectorielle(self.couche_rupture)

        # Définir l'outil actif
        self.canvas.setMapTool(self.outil_rupture_pente)

    def changer_mode_rupture(self, index):
        """Change le mode de rupture de pente."""
        if hasattr(self, 'outil_rupture_pente') and self.outil_rupture_pente is not None:
            mode = 'concave' if index == 0 else 'convexe'
            self.outil_rupture_pente.definir_mode(mode)
            # Pas besoin de recalculer le raster de courbure
        else:
            QMessageBox.warning(None, "Avertissement",
                                "Veuillez d'abord activer l'outil avec le bouton Démarrer rupture de pente.")


    def arreter_rupture(self):
        """Désactivation de l'outil de rupture de pente et création de la couche temporaire."""

        if self.outil_rupture_pente is None or self.outil_rupture_pente.liste_points is None:
            QMessageBox.warning(None, "Avertissement", "Aucun tracé en cours.")
            return

        # Confirmer la dernière polyligne si elle n'a pas été déjà confirmée
        if self.outil_rupture_pente.polyligne_confirmee is not None:
            self.outil_rupture_pente.confirmer_polyligne()


        # Utiliser les points originaux pour obtenir le Z du MNT
        points_originaux = self.outil_rupture_pente.liste_points
        points_avec_z = []

        for point in points_originaux:
            z = self.outil_rupture_pente.obtenir_elevation_au_point(point)
            if z is not None:
                point_z = QgsPoint(point.x(), point.y(), z)
            else:
                point_z = QgsPoint(point.x(), point.y(), 0)  # Valeur par défaut
            points_avec_z.append(point_z)

        # Créer la géométrie de la polyligne avec le Z original
        polyligne_z = QgsGeometry.fromPolyline(points_avec_z)

        entite = QgsFeature()
        entite.setGeometry(polyligne_z)
        entite.setAttributes([1])

        # Nettoyer et réinitialiser l'outil
        self.outil_rupture_pente.reinitialiser()
        self.outil_rupture_pente.nettoyer_ressources()
        self.outil_rupture_pente = None
        self.canvas.unsetMapTool(self.canvas.mapTool())

    def demarrer_mnt(self):
        """Activation de l'outil de tracé."""
        # Afficher la boîte de dialogue pour sélectionner le MNT et la couche de polyligne
        dialog = ChoixCouchesDialog(self.interface_qgis.mainWindow())
        result = dialog.exec_()
        if result == QDialog.Accepted:
            couche_mnt = dialog.get_selected_mnt_layer()
            couche_crete_selectionnee = dialog.get_selected_polyline_layer()
            nouvelle_couche = dialog.is_new_layer_checked()
        else:
            # L'utilisateur a annulé
            return

        if couche_mnt is None:
            QMessageBox.warning(None, "Avertissement", "Vous devez sélectionner un MNT.")
            return

        # Déterminer la couche de crête à utiliser
        if couche_crete_selectionnee is not None:
            self.couche_crete = couche_crete_selectionnee
        elif nouvelle_couche:
            # Créer une nouvelle couche de crête
            crs = self.canvas.mapSettings().destinationCrs()
            self.couche_crete = QgsVectorLayer(f"MultiLineStringZ?crs={crs.authid()}", "Lignes de Crête", "memory")
            if not self.couche_crete.isValid():
                QMessageBox.critical(None, "Erreur",
                                     "Impossible de créer la couche vectorielle pour les lignes de crête.")
                return
            # Ajouter les champs à la couche en fonction des préférences
            champs = []
            if self.field_settings.get('OBJECTID', True):
                champs.append(QgsField('OBJECTID', QVariant.Int))
            if self.field_settings.get('Denomination', True):
                champs.append(QgsField('Denomination', QVariant.String))
            if self.field_settings.get('SHAPE_LENGTH', True):
                champs.append(QgsField('SHAPE_LENGTH', QVariant.Double))
            if self.field_settings.get('HORADATEUR', True):
                champs.append(QgsField('HORADATEUR', QVariant.String))

            self.couche_crete.dataProvider().addAttributes(champs)
            self.couche_crete.updateFields()

            # Ajouter la couche au projet
            QgsProject.instance().addMapLayer(self.couche_crete)
            # Modifier la symbologie si nécessaire
            symbole = self.couche_crete.renderer().symbol()
            symbole.setColor(QColor('#00FF00'))
            symbole.setWidth(1)
        else:
            QMessageBox.warning(None, "Avertissement",
                                "Vous devez sélectionner une couche de polyligne ou cocher 'Nouvelle couche de travail'.")
            return

        # Créer une instance de l'outil de tracé
        self.outil_trace_crete = OutilTraceCrete(self.canvas, couche_mnt)
        # Passer la couche vectorielle à l'outil de dessin
        self.outil_trace_crete.definir_couche_vectorielle(self.couche_crete)
        self.canvas.setMapTool(self.outil_trace_crete)

        # Gérer l'affichage du graphique 3D si nécessaire
        if self.graphique_3d_active:
            if self.fenetre_profil is None:
                self.fenetre_profil = FenetreProfilElevation(self.interface_qgis.mainWindow())
                self.interface_qgis.addDockWidget(Qt.RightDockWidgetArea, self.fenetre_profil)
            # Passer la fenêtre de profil à l'outil de dessin
            self.outil_trace_crete.definir_fenetre_profil(self.fenetre_profil)
        else:
            # Assurer que l'outil connaît l'absence de fenêtre de profil
            self.outil_trace_crete.definir_fenetre_profil(None)

        # Définir le mode par défaut
        self.outil_trace_crete.definir_mode(1)  # Mode 1 par défaut

    def changer_mode(self, index):
        """Change le mode de l'outil en fonction de la sélection."""
        if self.outil_trace_crete is not None:
            if index == 0:
                # Mode Automatique (Distance)
                self.interface_qgis.mainWindow().statusBar().showMessage("Changement du mode de tracé dynamique...", 1000)
                self.liste_modes.setCurrentIndex(1)
            elif index == 1:
                # Mode Manuel
                self.outil_trace_crete.definir_mode(2)
        else:
            QMessageBox.warning(None, "Avertissement", "Veuillez d'abord activer l'outil avec le bouton Démarrer MNT.")

    def arreter_mnt(self):
        """Désactivation de l'outil et création de la couche temporaire."""
        if self.outil_trace_crete is None:
            QMessageBox.warning(None, "Avertissement", "Aucun tracé en cours.")
            return

        # Confirmer la dernière polyligne si elle n'a pas été déjà confirmée
        if self.outil_trace_crete.polyligne_confirmee is not None:
            self.outil_trace_crete.confirmer_polyligne()

        # Si en mode tracé libre, quitter ce mode pour enregistrer les points
        if self.outil_trace_crete.mode_trace_libre:
            self.outil_trace_crete.definir_mode_trace_libre(False)
            self.action_tracer_libre.setChecked(False)

        # Créer une couche vectorielle temporaire pour la polyligne confirmée avec géométrie en Z
        crs = self.canvas.mapSettings().destinationCrs()
        couche_temporaire = QgsVectorLayer(f"MultiLineStringZ?crs={crs.authid()}", "Ligne de Crête", "memory")

        if not couche_temporaire.isValid():
            QMessageBox.critical(None, "Erreur", "Impossible de créer la couche vectorielle temporaire.")
            return

        fournisseur_donnees = couche_temporaire.dataProvider()

        if self.outil_trace_crete.polyligne_confirmee is not None:
            # Construire la polyligne en 3D avec les valeurs Z du MNT
            points_avec_z = []
            for point in self.outil_trace_crete.liste_points:
                z = self.outil_trace_crete.obtenir_elevation_au_point(point)
                if z is not None:
                    point_z = QgsPoint(point.x(), point.y(), z)
                    points_avec_z.append(point_z)
                else:
                    point_z = QgsPoint(point.x(), point.y(), 0)
                    points_avec_z.append(point_z)

            # Créer la géométrie de la polyligne en 3D
            polyligne_z = QgsGeometry.fromPolyline(points_avec_z)

            entite = QgsFeature()
            entite.setGeometry(polyligne_z)
            entite.setAttributes([1])
            fournisseur_donnees.addFeature(entite)
            couche_temporaire.updateExtents()
            # Ajouter la couche temporaire au projet
            QgsProject.instance().addMapLayer(couche_temporaire)
        else:
            QMessageBox.warning(None, "Avertissement", "Aucune polyligne confirmée à enregistrer.")

        # Modifier la symbologie pour que la polyligne soit verte fluo
        symbole = couche_temporaire.renderer().symbol()
        symbole.setColor(QColor('#00FF00'))  # Code couleur souhaité
        symbole.setWidth(1)  # Ajuster la largeur de la polyligne si nécessaire

        # Nettoyer et réinitialiser l'outil
        self.outil_trace_crete.reinitialiser()
        self.outil_trace_crete.nettoyer_ressources_1()
        self.outil_trace_crete = None
        self.canvas.unsetMapTool(self.canvas.mapTool())

        # Fermer la fenêtre de profil
        if self.fenetre_profil is not None:
            self.interface_qgis.removeDockWidget(self.fenetre_profil)
            self.fenetre_profil = None

class OutilTraceCrete(QgsMapTool):
    """
    Outil de dessin de ligne de crête avec assistance dynamique sur MNT.

    Args:
        canvas (QgsMapCanvas): Le canevas de la carte.
        couche_raster (QgsRasterLayer): La couche raster MNT.
    """

    def __init__(self, canvas, couche_raster):
        """Initialise l'outil de tracé."""
        super().__init__(canvas)
        self.canvas = canvas
        self.couche_raster = couche_raster
        self.id_counter = 1  # Compteur pour l'ID des polylignes
        self.data_loaded = False

        # Pré-calcul des transformations de coordonnées
        self.crs_canvas = self.canvas.mapSettings().destinationCrs()
        self.crs_raster = self.couche_raster.crs()
        self.transformation_vers_raster = QgsCoordinateTransform(self.crs_canvas, self.crs_raster, QgsProject.instance())
        self.transformation_depuis_raster = QgsCoordinateTransform(self.crs_raster, self.crs_canvas, QgsProject.instance())

        self.liste_points = []  # Liste pour stocker les points de la polyligne
        self.chemin_dynamique = None
        self.polyligne_confirmee = None  # Polyligne confirmée unique
        self.mode_trace_libre = False
        self.points_trace_libre = []
        self.fenetre_profil = None
        self.simplification_activee = False
        self.tolerance_simplification = 2.0
        self.mode = 1  # Mode par défaut
        self.distance_seuil = 10  # Distance seuil par défaut en mètres
        self.dernier_point_deplacement = None  # Dernier point où le calcul a été effectué

        # Bande élastique pour la ligne dynamique
        self.bande_dynamique = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_dynamique.setColor(QColor(255, 255, 0))
        self.bande_dynamique.setWidth(2)
        self.bande_dynamique.setLineStyle(Qt.DashLine)

        # Bande élastique pour la polyligne confirmée
        self.bande_confirmee = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_confirmee.setColor(QColor(0, 0, 255))
        self.bande_confirmee.setWidth(3)

        # Bande élastique pour le tracé libre
        self.bande_trace_libre = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_trace_libre.setColor(QColor(0, 255, 0))
        self.bande_trace_libre.setWidth(3)

        # Afficher le Splash Screen
        self.splash_screen_load = SplashScreenLoad()
        self.splash_screen_load.setParent(self.canvas.parent())
        self.splash_screen_load.show()

        # Démarrer le chargement des données raster en arrière-plan
        self.raster_loading_thread = RasterLoadingThread(self.couche_raster)
        self.raster_loading_thread.raster_loaded.connect(self.on_raster_loaded)
        self.raster_loading_thread.start()

    def on_raster_loaded(self, tableau_raster, gt, inv_gt, raster_lignes, raster_colonnes):
        """Callback lorsque le chargement du raster est terminé."""
        self.tableau_raster = tableau_raster
        self.gt = gt
        self.inv_gt = inv_gt
        self.raster_lignes = raster_lignes
        self.raster_colonnes = raster_colonnes
        self.data_loaded = True

        # Fermer le Splash Screen
        self.splash_screen_load.close()

    def definir_couche_vectorielle(self, couche_vectorielle):
        self.couche_vectorielle = couche_vectorielle

    def confirmer_polyligne(self):
        """Confirme la polyligne actuelle et l'ajoute à la couche vectorielle."""
        if self.polyligne_confirmee is not None and self.couche_vectorielle is not None:
            # Construire la polyligne en 3D avec les valeurs Z du MNT
            points_avec_z = []
            for point in self.liste_points:
                z = self.obtenir_elevation_au_point(point)
                if z is not None:
                    point_z = QgsPoint(point.x(), point.y(), z)
                    points_avec_z.append(point_z)
                else:
                    point_z = QgsPoint(point.x(), point.y(), 0)
                    points_avec_z.append(point_z)
            # Créer la géométrie de la polyligne en 3D
            polyligne_z = QgsGeometry.fromPolyline(points_avec_z)

            entite = QgsFeature()
            entite.setGeometry(polyligne_z)

            # Construire les attributs en fonction des préférences
            attributs = []
            champs_presentes = [field.name() for field in self.couche_vectorielle.fields()]
            if 'OBJECTID' in champs_presentes:
                attributs.append(self.id_counter)
            if 'Denomination' in champs_presentes:
                # Demander à l'utilisateur de saisir un nom
                nom, ok = QInputDialog.getText(None, "Entrer un nom", "Dénomination de la polyligne :")
                if ok and nom:
                    attributs.append(nom)
                else:
                    # Si l'utilisateur annule ou ne saisit pas de nom, mettre une chaîne vide
                    attributs.append('')
            if 'SHAPE_LENGTH' in champs_presentes:
                longueur = polyligne_z.length()
                attributs.append(longueur)
            if 'HORADATEUR' in champs_presentes:
                from datetime import datetime
                horadateur = datetime.now().strftime('%d/%m/%y')
                attributs.append(horadateur)


            entite.setAttributes(attributs)
            self.couche_vectorielle.dataProvider().addFeature(entite)
            self.couche_vectorielle.updateExtents()
            self.id_counter += 1
            # Réinitialiser l'outil pour un nouveau tracé
            self.reinitialiser()
        else:
            QMessageBox.warning(None, "Avertissement", "Aucune polyligne confirmée à enregistrer.")

    def charger_donnees_raster(self):
        """Charge les données raster en mémoire pour un accès rapide."""
        # Ouvrir le raster avec GDAL
        source = self.couche_raster.dataProvider().dataSourceUri()
        self.dataset = gdal.Open(source)

        if self.dataset is None:
            return

        # Obtenir la géotransformation et son inverse
        self.gt = self.dataset.GetGeoTransform()
        self.inv_gt = gdal.InvGeoTransform(self.gt)

        if self.inv_gt is None:
            return

        # Lire les données du raster dans un tableau NumPy
        bande_raster = self.dataset.GetRasterBand(1)
        self.tableau_raster = bande_raster.ReadAsArray()

        if self.tableau_raster is None:
            return

        # Obtenir les dimensions du raster
        self.raster_lignes, self.raster_colonnes = self.tableau_raster.shape

    def definir_fenetre_profil(self, fenetre):
        """Assigne la fenêtre du profil d'élévation."""
        self.fenetre_profil = fenetre
        if self.fenetre_profil is not None:
            self.fenetre_profil.definir_outil_trace_crete(self)


    def definir_mode(self, mode, distance_seuil=None):
        """Définit le mode de fonctionnement de l'outil."""
        self.mode = mode
        if distance_seuil is not None:
            self.distance_seuil = distance_seuil
        self.dernier_point_deplacement = None  # Réinitialiser le dernier point de mouvement

    def definir_simplification(self, activee):
        """Active ou désactive la simplification du tracé."""
        self.simplification_activee = activee
        self.mettre_a_jour_bande_dynamique()

    def mettre_a_jour_bande_dynamique(self):
        """Met à jour la bande élastique dynamique en appliquant ou non la simplification."""
        if self.chemin_dynamique:
            if self.simplification_activee:
                geometrie_simplifiee = self.simplifier_geometrie(self.chemin_dynamique)
                self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
                self.bande_dynamique.addGeometry(geometrie_simplifiee, None)
            else:
                self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
                self.bande_dynamique.addGeometry(self.chemin_dynamique, None)

    def definir_mode_trace_libre(self, tracelibre):
        """Bascule le mode de tracé libre."""
        if tracelibre:
            # Entrer en mode tracé libre
            self.mode_trace_libre = True
            self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
            if self.liste_points:
                point_depart = self.liste_points[-1]
                self.points_trace_libre = [point_depart]
                self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
                self.bande_trace_libre.addPoint(point_depart)
            else:
                self.points_trace_libre = []
        else:
            # Sortir du mode tracé libre
            self.mode_trace_libre = False
            self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
            if len(self.points_trace_libre) >= 2:
                # Ajouter les points tracés librement à liste_points
                nouveaux_points = self.points_trace_libre[1:]
                self.liste_points.extend(nouveaux_points)
                # Mettre à jour la polyligne confirmée
                self.polyligne_confirmee = QgsGeometry.fromPolylineXY(self.liste_points)
                self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                self.bande_confirmee.addGeometry(self.polyligne_confirmee, None)
            self.points_trace_libre = []

    def calculer_chemin_dijkstra(self, cost_raster, start, end):
        import heapq

        height, width = cost_raster.shape
        visited = np.full((height, width), False)
        distances = np.full((height, width), np.inf)
        previous = np.full((height, width, 2), -1, dtype=int)

        # File prioritaire pour l'ensemble ouvert
        heap = []

        sy, sx = start
        ey, ex = end

        distances[sy, sx] = 0
        heapq.heappush(heap, (0, (sy, sx)))

        # Directions (8-connectivité)
        neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1),
                     (-1, -1), (-1, 1), (1, -1), (1, 1)]

        while heap:
            current_distance, (cy, cx) = heapq.heappop(heap)

            if (cy, cx) == (ey, ex):
                # Destination trouvée
                break

            if visited[cy, cx]:
                continue

            visited[cy, cx] = True

            for dy, dx in neighbors:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < height and 0 <= nx < width:
                    if not visited[ny, nx] and cost_raster[ny, nx] != np.inf:
                        # Coût de mouvement
                        if dy != 0 and dx != 0:
                            movement_cost = math.sqrt(2)
                        else:
                            movement_cost = 1
                        total_cost = current_distance + cost_raster[ny, nx] * movement_cost
                        if total_cost < distances[ny, nx]:
                            distances[ny, nx] = total_cost
                            previous[ny, nx] = [cy, cx]
                            heapq.heappush(heap, (total_cost, (ny, nx)))

        # Reconstruire le chemin
        path = []
        cy, cx = ey, ex
        if distances[cy, cx] == np.inf:
            return None  # Chemin non trouvé

        while (cy, cx) != (sy, sx):
            path.append((cy, cx))
            cy, cx = previous[cy, cx]
            if cy == -1:
                return None  # Chemin non trouvé

        path.append((sy, sx))
        path.reverse()
        return path

    def lisser_chemin(self, points, intensite=0.1):
        """
        Applique un lissage à une liste de points.
        Intensité de 0 (pas de lissage) à 1 (lissage maximal).
        """
        if len(points) < 3:
            return points

        # Par exemple, utiliser l'algorithme de Chaikin
        for _ in range(int(intensite * 1)):  # Ajuster le nombre d'itérations
            new_points = [points[0]]
            for i in range(len(points) - 1):
                q = QgsPointXY(
                    0.75 * points[i].x() + 0.25 * points[i + 1].x(),
                    0.75 * points[i].y() + 0.25 * points[i + 1].y()
                )
                r = QgsPointXY(
                    0.25 * points[i].x() + 0.75 * points[i + 1].x(),
                    0.25 * points[i].y() + 0.75 * points[i + 1].y()
                )
                new_points.extend([q, r])
            new_points.append(points[-1])
            points = new_points
        return points

    def canvasPressEvent(self, event):
        """Gestion des clics de souris."""
        if not self.data_loaded:
            QMessageBox.information(None, "Chargement en cours",
                                    "Veuillez patienter, le chargement des données est en cours.")
            return

        point_carte = self.toMapCoordinates(event.pos())

        if self.mode_trace_libre:
            # Mode tracé libre
            self.points_trace_libre.append(point_carte)
            self.bande_trace_libre.addPoint(point_carte)
        else:
            if not self.liste_points:
                # Premier clic : ajouter le point de départ
                self.liste_points.append(point_carte)
            else:
                # Confirmer le segment actuel
                if self.chemin_dynamique:
                    nouveaux_points = self.chemin_dynamique.asPolyline()[1:]  # Exclure le premier point
                    self.liste_points.extend(nouveaux_points)
                    self.polyligne_confirmee = QgsGeometry.fromPolylineXY(self.liste_points)
                    self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                    self.bande_confirmee.addGeometry(self.polyligne_confirmee, None)
                    self.chemin_dynamique = None
                    self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
                # Réinitialiser le dernier point de mouvement
                self.dernier_point_deplacement = None
                # Réinitialiser le graphique
                if self.fenetre_profil:
                    self.fenetre_profil.reinitialiser()

    def canvasMoveEvent(self, event):
        """Gestion des mouvements de souris."""
        if not self.data_loaded:
            return

        if self.mode_trace_libre:
            # Mode tracé libre
            point_actuel = self.toMapCoordinates(event.pos())
            if self.points_trace_libre:
                self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
                for point in self.points_trace_libre:
                    self.bande_trace_libre.addPoint(point)
                self.bande_trace_libre.addPoint(point_actuel)
        else:
            if self.liste_points:
                point_actuel = self.toMapCoordinates(event.pos())
                # Comportement par défaut
                if self.mode == 1:
                    if self.dernier_point_deplacement is None:
                        self.dernier_point_deplacement = self.liste_points[-1]
                    distance = self.dernier_point_deplacement.distance(point_actuel)
                    if distance >= self.distance_seuil:
                        # Calculer le chemin de plus haute altitude
                        geometrie_chemin = self.calculer_chemin_plus_haut(self.liste_points[-1], point_actuel)
                        if geometrie_chemin:
                            # Appliquer la simplification si activée
                            if self.simplification_activee:
                                geometrie_simplifiee = self.simplifier_geometrie(geometrie_chemin)
                                self.chemin_dynamique = geometrie_simplifiee
                            else:
                                self.chemin_dynamique = geometrie_chemin
                            # Afficher la polyligne dynamique
                            self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
                            self.bande_dynamique.addGeometry(self.chemin_dynamique, None)
                            # Mettre à jour le profil d'élévation avec le segment dynamique
                            if self.fenetre_profil:
                                self.mettre_a_jour_profil(self.chemin_dynamique)
                            # Mettre à jour le dernier point de mouvement
                            self.dernier_point_deplacement = point_actuel
                    else:
                        pass  # Ne pas recalculer si la distance n'est pas atteinte
                else:
                    pass  # Gérer les autres modes si nécessaire

    def keyPressEvent(self, event):
        """Gestion des touches du clavier."""
        if self.mode == 2 and event.key() == Qt.Key_T:
            if self.liste_points:
                point_depart = self.liste_points[-1]
                position_souris = self.canvas.mouseLastXY()
                point_actuel = self.toMapCoordinates(QPoint(position_souris.x(), position_souris.y()))
                # Calculer le chemin de plus haute altitude
                geometrie_chemin = self.calculer_chemin_plus_haut(point_depart, point_actuel)
                if geometrie_chemin:
                    # Appliquer la simplification si activée
                    if self.simplification_activee:
                        geometrie_simplifiee = self.simplifier_geometrie(geometrie_chemin)
                        self.chemin_dynamique = geometrie_simplifiee
                    else:
                        self.chemin_dynamique = geometrie_chemin
                    # Afficher la polyligne dynamique
                    self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
                    self.bande_dynamique.addGeometry(self.chemin_dynamique, None)
                    # Mettre à jour le profil d'élévation avec le segment dynamique
                    if self.fenetre_profil:
                        self.mettre_a_jour_profil(self.chemin_dynamique)
        else:
            super().keyPressEvent(event)  # Autres touches

    def mettre_a_jour_profil(self, x_coords, y_coords, distances, elevations, index_marqueur):
        """Met à jour le graphique 3D du profil d'élévation."""
        self.ax.clear()

        # Déterminer l'étendue de la zone à afficher
        buffer = 50  # mètres, ajustez selon vos besoins
        xmin = min(x_coords) - buffer
        xmax = max(x_coords) + buffer
        ymin = min(y_coords) - buffer
        ymax = max(y_coords) + buffer

        # Créer une grille
        num_points = 100  # Ajustez selon vos besoins
        X = np.linspace(xmin, xmax, num_points)
        Y = np.linspace(ymin, ymax, num_points)
        X_grid, Y_grid = np.meshgrid(X, Y)

        # Obtenir les valeurs Z du MNT
        Z_grid = self.outil_trace_crete.obtenir_elevation_aux_points(X_grid, Y_grid)

        # Tracer la surface 3D
        self.ax.plot_surface(X_grid, Y_grid, Z_grid, edgecolor='royalblue', lw=0.5,
                             rstride=10, cstride=10, alpha=0.6, cmap='terrain')

        # Ajouter les projections de contours
        zmin = np.nanmin(Z_grid)
        zmax = np.nanmax(Z_grid)
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='z', offset=zmin, cmap='terrain')
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='x', offset=xmin, cmap='terrain')
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='y', offset=ymax, cmap='terrain')

        # Tracer votre parcours
        self.ax.plot(
            x_coords,
            y_coords,
            elevations,
            color='black',
            label='Parcours'
        )

        # Ajuster les limites
        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(ymin, ymax)
        self.ax.set_zlim(zmin, zmax)

        self.ax.set_xlabel("X (Longitude)")
        self.ax.set_ylabel("Y (Latitude)")
        self.ax.set_zlabel("Élévation (m)")
        self.ax.set_title("Profil d'Élévation 3D")
        self.ax.legend()
        self.canvas.draw()

    def obtenir_elevation_au_point(self, point):
        """Obtient l'élévation du raster au point donné."""
        if self.crs_raster != self.crs_canvas:
            point = self.transformation_vers_raster.transform(point)
        x = point.x()
        y = point.y()
        px, py = gdal.ApplyGeoTransform(self.inv_gt, x, y)
        px = int(px)
        py = int(py)
        if 0 <= px < self.raster_colonnes and 0 <= py < self.raster_lignes:
            elevation = self.tableau_raster[py, px]
            return float(elevation)
        else:
            return None

    def calculer_chemin_plus_haut(self, point_depart, point_arrivee):
        """Calcule le chemin de plus haute altitude entre deux points."""
        if not self.data_loaded:
            return None
        if self.crs_raster != self.crs_canvas:
            point_depart = self.transformation_vers_raster.transform(point_depart)
            point_arrivee = self.transformation_vers_raster.transform(point_arrivee)

        depart_px = gdal.ApplyGeoTransform(self.inv_gt, point_depart.x(), point_depart.y())
        arrivee_px = gdal.ApplyGeoTransform(self.inv_gt, point_arrivee.x(), point_arrivee.y())
        depart_px = (int(round(depart_px[0])), int(round(depart_px[1])))
        arrivee_px = (int(round(arrivee_px[0])), int(round(arrivee_px[1])))

        # Vérifier si les points sont dans les limites du raster
        if not (0 <= depart_px[0] < self.raster_colonnes and 0 <= depart_px[1] < self.raster_lignes):
            return None
        if not (0 <= arrivee_px[0] < self.raster_colonnes and 0 <= arrivee_px[1] < self.raster_lignes):
            return None

        # Initialiser le chemin
        pixels_chemin = [depart_px]
        pixel_courant = depart_px
        iterations_max = 10000
        iterations = 0

        while pixel_courant != arrivee_px and iterations < iterations_max:
            iterations += 1
            cx, cy = pixel_courant

            # Récupérer les voisins dans un rayon de 2 pixels
            voisins = [
                (cx + dx, cy + dy)
                for dx in [-2, -1, 0, 1, 2]
                for dy in [-2, -1, 0, 1, 2]
                if (dx != 0 or dy != 0) and
                0 <= cx + dx < self.raster_colonnes and
                0 <= cy + dy < self.raster_lignes
            ]

            if not voisins:
                break

            # Calculer l'angle vers le point final
            dx_fin = arrivee_px[0] - cx
            dy_fin = arrivee_px[1] - cy
            angle_vers_fin = np.arctan2(dy_fin, dx_fin)

            def difference_angle(a1, a2):
                return abs((a1 - a2 + np.pi) % (2 * np.pi) - np.pi)

            # Filtrer les voisins dans la direction générale
            voisins_dans_direction = []
            for nx, ny in voisins:
                ndx = nx - cx
                ndy = ny - cy
                angle_voisin = np.arctan2(ndy, ndx)
                difference = difference_angle(angle_voisin, angle_vers_fin)
                if difference <= np.pi / 2:  # 90 degrés
                    voisins_dans_direction.append((nx, ny, difference))

            if not voisins_dans_direction:
                voisins_dans_direction = [
                    (nx, ny, difference_angle(np.arctan2(ny - cy, nx - cx), angle_vers_fin))
                    for nx, ny in voisins
                ]

            elevation_courante = self.tableau_raster[cy, cx]
            candidats_voisins = []
            for nx, ny, difference_angle_valeur in voisins_dans_direction:
                elevation_voisin = self.tableau_raster[ny, nx]
                candidats_voisins.append({
                    'position': (nx, ny),
                    'elevation': elevation_voisin,
                    'difference_angle': difference_angle_valeur
                })

            # Sélectionner le prochain pixel
            voisins_plus_hauts = [n for n in candidats_voisins if n['elevation'] > elevation_courante]

            if len(voisins_plus_hauts) == 1:
                prochain_px = voisins_plus_hauts[0]['position']
            elif len(voisins_plus_hauts) > 1:
                elevation_max = max(n['elevation'] for n in voisins_plus_hauts)
                voisins_maximums = [n for n in voisins_plus_hauts if n['elevation'] == elevation_max]
                prochain_px = self.resoudre_egalite(voisins_maximums, arrivee_px)
            else:
                voisins_egaux = [n for n in candidats_voisins if n['elevation'] == elevation_courante]
                if len(voisins_egaux) >= 1:
                    prochain_px = self.resoudre_egalite(voisins_egaux, arrivee_px)
                else:
                    difference_min = min(elevation_courante - n['elevation'] for n in candidats_voisins)
                    voisins_plus_bas = [n for n in candidats_voisins if (elevation_courante - n['elevation']) == difference_min]
                    prochain_px = self.resoudre_egalite(voisins_plus_bas, arrivee_px)

            if prochain_px == pixel_courant or prochain_px in pixels_chemin:
                break

            pixels_chemin.append(prochain_px)
            pixel_courant = prochain_px

        # Convertir les pixels en coordonnées
        liste_points = []
        for px, py in pixels_chemin:
            x, y = gdal.ApplyGeoTransform(self.gt, px + 0.5, py + 0.5)
            point = QgsPointXY(x, y)
            if self.crs_raster != self.crs_canvas:
                point = self.transformation_depuis_raster.transform(point)
            liste_points.append(point)

        # Créer la géométrie
        geometrie_chemin = QgsGeometry.fromPolylineXY(liste_points)

        if self.simplification_activee:
            geometrie_chemin = geometrie_chemin.simplify(self.tolerance_simplification)

        return geometrie_chemin

    def resoudre_egalite(self, candidats, arrivee_px):
        """Départage les candidats en cas d'égalité."""
        distance_min = float('inf')
        meilleur_candidat = None
        for candidat in candidats:
            nx, ny = candidat['position']
            distance = np.hypot(arrivee_px[0] - nx, arrivee_px[1] - ny)
            if distance < distance_min:
                distance_min = distance
                meilleur_candidat = candidat
        return meilleur_candidat['position']

    def reinitialiser(self):
        """Réinitialise l'outil pour un nouveau tracé."""
        self.liste_points = []
        self.chemin_dynamique = None
        self.polyligne_confirmee = None
        self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
        self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
        self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
        self.points_trace_libre = []
        self.mode_trace_libre = False
        self.dernier_point_deplacement = None

        if self.fenetre_profil:
            self.fenetre_profil.ax.clear()
            self.fenetre_profil.canvas.draw()

    def simplifier_geometrie(self, geometrie):
        """Simplifie la géométrie en préservant les points critiques."""
        points = geometrie.asPolyline()

        if len(points) < 3:
            return geometrie

        # Identifier les points critiques (altitude maximale)
        elevations = [self.obtenir_elevation_au_point(p) for p in points]
        elevation_maximale = max(elevations)
        points_critiques = [points[i] for i, elev in enumerate(elevations) if elev == elevation_maximale]

        # Appliquer l'algorithme de simplification
        points_simplifies = self.douglas_peucker_avec_critiques(points, self.tolerance_simplification, points_critiques)

        return QgsGeometry.fromPolylineXY(points_simplifies)

    def douglas_peucker_avec_critiques(self, points, tol, points_critiques):
        """Simplifie une polyligne en conservant les points critiques."""
        if len(points) < 3:
            return points

        debut, fin = points[0], points[-1]
        dist_max = 0
        index = 0

        for i in range(1, len(points) - 1):
            if points[i] in points_critiques:
                continue
            dist = self.distance_perpendiculaire(points[i], debut, fin)
            if dist > dist_max:
                index = i
                dist_max = dist

        if dist_max > tol:
            gauche = self.douglas_peucker_avec_critiques(points[:index + 1], tol, points_critiques)
            droite = self.douglas_peucker_avec_critiques(points[index:], tol, points_critiques)
            return gauche[:-1] + droite
        else:
            points_segment = points[1:-1]
            if any(p in points_critiques for p in points_segment):
                return points
            else:
                return [debut, fin]

    def distance_perpendiculaire(self, point, debut, fin):
        """Calcule la distance perpendiculaire du point à la ligne debut-fin."""
        if debut == fin:
            return self.distance_euclidienne(point, debut)
        else:
            num = abs((fin.y() - debut.y()) * point.x() - (fin.x() - debut.x()) * point.y() +
                      fin.x() * debut.y() - fin.y() * debut.x())
            den = ((fin.y() - debut.y()) ** 2 + (fin.x() - debut.x()) ** 2) ** 0.5
            return num / den

    def distance_euclidienne(self, p1, p2):
        """Calcule la distance euclidienne entre deux points."""
        return ((p1.x() - p2.x()) ** 2 + (p1.y() - p2.y()) ** 2) ** 0.5

    def obtenir_elevation_aux_points(self, x_array, y_array):
        """Obtient les élévations du raster aux points donnés."""
        if self.crs_raster != self.crs_canvas:
            # Transformer les points
            transformer = QgsCoordinateTransform(self.crs_canvas, self.crs_raster, QgsProject.instance())
            points = [QgsPointXY(x, y) for x, y in zip(x_array.flatten(), y_array.flatten())]
            points_transformed = [transformer.transform(p) for p in points]
            x_array_transformed = np.array([p.x() for p in points_transformed]).reshape(x_array.shape)
            y_array_transformed = np.array([p.y() for p in points_transformed]).reshape(y_array.shape)
        else:
            x_array_transformed = x_array
            y_array_transformed = y_array

        # Calculer les coordonnées pixels
        gt = self.inv_gt  # InvGeoTransform
        px_array = gt[0] + gt[1] * x_array_transformed + gt[2] * y_array_transformed
        py_array = gt[3] + gt[4] * x_array_transformed + gt[5] * y_array_transformed

        px_array = px_array.astype(int)
        py_array = py_array.astype(int)

        # Masque pour les points valides
        mask = (px_array >= 0) & (px_array < self.raster_colonnes) & (py_array >= 0) & (py_array < self.raster_lignes)
        elevations = np.full(x_array.shape, np.nan)
        elevations[mask] = self.tableau_raster[py_array[mask], px_array[mask]]

        return elevations

    def mettre_a_jour_profil(self, geometrie):
        """Met à jour le profil d'élévation avec le segment dynamique."""
        if geometrie is None:
            return

        points = geometrie.asPolyline()

        elevations = []
        coordonnees_x = []
        coordonnees_y = []
        distances = []
        distance_totale = 0
        point_precedent = None

        for point in points:
            coordonnees_x.append(point.x())
            coordonnees_y.append(point.y())
            elevation = self.obtenir_elevation_au_point(point)
            elevations.append(elevation if elevation is not None else 0)

            if point_precedent is not None:
                segment = QgsGeometry.fromPolylineXY([point_precedent, point])
                distance = segment.length()
                distance_totale += distance
            else:
                distance = 0
            distances.append(distance_totale)
            point_precedent = point

        # Appeler la méthode dans fenetre_profil en passant la longueur totale
        self.fenetre_profil.mettre_a_jour_profil(
            coordonnees_x,
            y_coords=coordonnees_y,
            elevations=elevations,
            longueur_segment=distance_totale
        )

    def nettoyer_ressources_1(self):
        """Nettoyage des ressources et réinitialisation de l'outil."""
        self.reinitialiser()

        # Libérer le dataset GDAL
        if hasattr(self, 'dataset'):
            self.dataset.FlushCache()
            self.dataset = None

        # Libérer les grands tableaux NumPy
        if hasattr(self, 'tableau_raster'):
            del self.tableau_raster
            self.tableau_raster = None


class FenetreProfilElevation(QDockWidget):
    """
    Fenêtre pour afficher le profil d'élévation en 3D.

    Args:
        parent (QWidget): Le widget parent.
    """

    def __init__(self, parent=None):
        """Initialise la fenêtre de profil d'élévation."""
        super().__init__("Profil d'Élévation 3D", parent)


        # Créer une figure Matplotlib en 3D
        self.figure = plt.figure()
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)

        # Configurer le widget principal
        widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        widget.setLayout(layout)
        self.setWidget(widget)

    def reinitialiser(self):
        """Réinitialise le graphique."""
        self.ax.clear()
        self.canvas.draw()

    def definir_outil_trace_crete(self, outil_trace_crete):
        self.outil_trace_crete = outil_trace_crete

    def on_mouse_move(self, event):
        """Affiche l'altitude au passage de la souris."""
        if event.inaxes == self.ax:
            # Obtenir les coordonnées X, Y du pointeur de la souris
            x_mouse = event.xdata
            y_mouse = event.ydata

            if x_mouse is not None and y_mouse is not None:
                # Obtenir l'élévation correspondante
                Z_grid = self.Z_grid  # Sauvegardez Z_grid dans self.Z_grid lors de la mise à jour du profil
                X_grid = self.X_grid
                Y_grid = self.Y_grid

                # Trouver les indices les plus proches dans la grille
                idx = (np.abs(self.X_grid[0] - x_mouse)).argmin()
                idy = (np.abs(self.Y_grid[:, 0] - y_mouse)).argmin()

                elevation = Z_grid[idy, idx]
                # Afficher l'altitude
                # Vous pouvez afficher dans la barre de statut, ou mettre à jour une annotation sur le graphique
                # Exemple de mise à jour de la barre de statut
                self.parent().statusBar().showMessage(f"Altitude : {elevation:.2f} m")

    def mettre_a_jour_profil(self, x_coords, y_coords, elevations, longueur_segment):
        """Met à jour le graphique 3D du profil d'élévation."""
        self.ax.clear()

        # Ajuster le buffer en fonction de la longueur du segment dynamique
        buffer_factor = 0.1  # Par exemple, 10% de la longueur du segment
        buffer_min = 20  # Valeur minimale du buffer en mètres
        buffer = max(buffer_min, longueur_segment * buffer_factor)

        # Ajuster le nombre de points du maillage en fonction de la longueur
        # Plus le segment est court, plus la résolution est élevée
        if longueur_segment <= 100:
            num_points = 250  # Résolution élevée pour les segments courts
        elif longueur_segment <= 500:
            num_points = 200
        elif longueur_segment <= 1000:
            num_points = 150
        else:
            num_points = 100  # Résolution plus faible pour les segments longs

        # Calculer les limites du graphique pour inclure tout le segment dynamique
        xmin = min(x_coords) - buffer
        xmax = max(x_coords) + buffer
        ymin = min(y_coords) - buffer
        ymax = max(y_coords) + buffer

        # Créer la grille
        X = np.linspace(xmin, xmax, num_points)
        Y = np.linspace(ymin, ymax, num_points)
        X_grid, Y_grid = np.meshgrid(X, Y)

        # Obtenir les valeurs Z du MNT
        Z_grid = self.outil_trace_crete.obtenir_elevation_aux_points(X_grid, Y_grid)

        # Sauvegarder les grilles pour on_mouse_move
        self.X_grid = X_grid
        self.Y_grid = Y_grid
        self.Z_grid = Z_grid

        # Tracer la surface 3D
        self.ax.plot_surface(X_grid, Y_grid, Z_grid, edgecolor='gray', lw=0.2,
                             rstride=10, cstride=10, alpha=0.6, cmap='terrain',
                             zorder=1)

        # Ajouter les projections de contours
        zmin = np.nanmin(Z_grid)
        zmax = np.nanmax(Z_grid)

        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='z', offset=zmin, cmap='terrain',
                         zorder=2)
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='x', offset=xmin, cmap='terrain',
                         zorder=2)
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='y', offset=ymax, cmap='terrain',
                         zorder=2)

        # Tracer le segment dynamique
        self.ax.plot(
            x_coords,
            y_coords,
            elevations,
            color='red',
            label='Segment dynamique',
            linewidth=5,
            marker='x',
            markersize=1,
            markeredgecolor='black',
            markerfacecolor='yellow',
            zorder=10
        )

        # Ajuster les limites
        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(ymin, ymax)
        self.ax.set_zlim(zmin, zmax)

        # Ajuster les labels et le titre
        self.ax.set_xlabel("X (Longitude)")
        self.ax.set_ylabel("Y (Latitude)")
        self.ax.set_zlabel("Élévation (m)")
        self.ax.set_title("Assistance topographique 3D")
        self.ax.legend()

        self.ax.dist = 7  # Vous pouvez ajuster cette valeur

        self.canvas.draw()




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
        pdf_path = os.path.join(os.path.dirname(__file__), 'docs', 'aide.pdf')
        QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))

    def update_image(self):
        png_path = os.path.join(os.path.dirname(__file__), 'sscreen', self.images[self.current_image_index])
        pixmap = QPixmap(png_path)

        # Charger et redimensionner l'image à la taille du `QLabel`
        if not pixmap.isNull():
            pixmap = pixmap.scaled(self.logoLabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logoLabel.setPixmap(pixmap)
            self.logoLabel.setFrameShape(QFrame.NoFrame)
            self.logoLabel.setFrameShadow(QFrame.Plain)
        else:
            print(f"Failed to load image at path: {png_path}")

    def next_image(self):
        # Passer à l'image suivante
        self.current_image_index = (self.current_image_index + 1) % len(self.images)
        self.update_image()

    def setup_infolabel(self):
        image_path = os.path.join(os.path.dirname(__file__), 'docs', 'info.png')
        pixmap = QPixmap(image_path)

        if not pixmap.isNull():
            pixmap = pixmap.scaled(self.Infolabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.Infolabel.setPixmap(pixmap)
            self.Infolabel.setFrameShape(QFrame.NoFrame)
            self.Infolabel.setFrameShadow(QFrame.Plain)
        else:
            print(f"Failed to load image at path: {image_path}")

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
# Création de l'application Qt
if __name__ == '__main__':
    app = QApplication(sys.argv)
    dialog = ParametresDialog()
    dialog.show()
    sys.exit(app.exec_())


class SliderDialog(QDialog):
    def __init__(self, min_value=0, max_value=20, step=0.5, parent=None):
        super(SliderDialog, self).__init__(parent)

        # Convert step to integer since QSlider works with integers
        self.step = int(step * 10)
        min_int = int(min_value * 10)
        max_int = int(max_value * 10)

        self.setWindowTitle("Choisissez la tolérance avec un slider")

        layout = QVBoxLayout()

        self.slider = QSlider()
        self.slider.setOrientation(Qt.Horizontal)
        self.slider.setMinimum(min_int)
        self.slider.setMaximum(max_int)
        self.slider.setSingleStep(self.step)
        self.slider.setValue(min_int)

        self.label = QLabel(f"Tolérance : {min_value:.1f}")
        self.slider.valueChanged.connect(self.update_label)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)

        layout.addWidget(self.label)
        layout.addWidget(self.slider)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def update_label(self, value):
        float_value = value / 10.0
        self.label.setText(f"Tolérance : {float_value:.1f}")

    def get_value(self):
        return self.slider.value() / 10.0


from PyQt5.QtCore import QThread, pyqtSignal

class RasterLoadingThread(QThread):
    raster_loaded = pyqtSignal(np.ndarray, tuple, tuple, int, int)  # Emitting the loaded raster data and other params

    def __init__(self, couche_raster, parent=None):
        super().__init__(parent)
        self.couche_raster = couche_raster

    def run(self):
        try:
            # Ouvrir le raster avec GDAL
            source = self.couche_raster.dataProvider().dataSourceUri()
            dataset = gdal.Open(source)

            if dataset is None:
                return

            # Obtenir la géotransformation et son inverse
            gt = dataset.GetGeoTransform()
            inv_gt = gdal.InvGeoTransform(gt)

            if inv_gt is None:
                return

            # Lire les données du raster dans un tableau NumPy
            bande_raster = dataset.GetRasterBand(1)
            tableau_raster = bande_raster.ReadAsArray()

            if tableau_raster is None:
                return

            # Obtenir les dimensions du raster
            raster_lignes, raster_colonnes = tableau_raster.shape

            # Émettre les données
            self.raster_loaded.emit(tableau_raster, gt, inv_gt, raster_lignes, raster_colonnes)
        except Exception as e:
            print(f"Erreur lors du chargement du raster: {e}")



from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QCheckBox, QDialogButtonBox
from qgis.core import QgsProject, QgsMapLayer, QgsWkbTypes

class ChoixCouchesDialog(QDialog):
    def __init__(self, parent=None):
        super(ChoixCouchesDialog, self).__init__(parent)
        self.setWindowTitle("Sélectionner les couches")

        # Layout principal
        layout = QVBoxLayout()

        # Sélection du MNT
        self.label_mnt = QLabel("Choisir le MNT de travail :")
        self.combo_mnt = QComboBox()
        self.populate_mnt_layers()
        layout.addWidget(self.label_mnt)
        layout.addWidget(self.combo_mnt)

        # Sélection de la couche de polyligne
        self.label_polyline = QLabel("Choisir la couche de polyligne :")
        self.combo_polyline = QComboBox()
        self.populate_polyline_layers()
        layout.addWidget(self.label_polyline)
        layout.addWidget(self.combo_polyline)

        # Checkbox pour nouvelle couche
        self.checkbox_new_layer = QCheckBox("Nouvelle couche de travail")
        layout.addWidget(self.checkbox_new_layer)

        # Boutons OK / Annuler
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

        # Connecter les signaux
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.combo_polyline.currentIndexChanged.connect(self.on_polyline_selection_changed)

        # Initialiser l'état de la checkbox
        self.update_checkbox_state()

    def populate_mnt_layers(self):
        """Remplit la comboBox avec les couches raster disponibles."""
        self.combo_mnt.clear()
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.RasterLayer:
                self.combo_mnt.addItem(layer.name(), layer)

    def populate_polyline_layers(self):
        """Remplit la comboBox avec les couches de polyligne disponibles."""
        self.combo_polyline.clear()
        self.combo_polyline.addItem("--- Aucune ---", None)  # Option pour aucune couche
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.LineGeometry:
                self.combo_polyline.addItem(layer.name(), layer)

    def on_polyline_selection_changed(self, index):
        """Active ou désactive la checkbox en fonction de la sélection."""
        layer = self.combo_polyline.itemData(index)
        if layer is not None:
            self.checkbox_new_layer.setChecked(False)
            self.checkbox_new_layer.setEnabled(False)
        else:
            self.checkbox_new_layer.setEnabled(True)

    def update_checkbox_state(self):
        """Met à jour l'état de la checkbox en fonction de la sélection initiale."""
        index = self.combo_polyline.currentIndex()
        self.on_polyline_selection_changed(index)

    def get_selected_mnt_layer(self):
        """Retourne la couche MNT sélectionnée."""
        return self.combo_mnt.itemData(self.combo_mnt.currentIndex())

    def get_selected_polyline_layer(self):
        """Retourne la couche de polyligne sélectionnée ou None."""
        return self.combo_polyline.itemData(self.combo_polyline.currentIndex())

    def is_new_layer_checked(self):
        """Indique si la case 'Nouvelle couche de travail' est cochée."""
        return self.checkbox_new_layer.isChecked()

