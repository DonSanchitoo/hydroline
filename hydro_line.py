"""
Assist_mnt.py

"""
import os
import sys

import processing
from qgis.PyQt.QtCore import Qt, QObject, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon, QColor, QPainter
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QMenu, QToolButton, QApplication, QComboBox, QDialog, QCheckBox
from qgis._core import QgsRasterLayer
from qgis.core import (
    QgsProject,
    QgsProcessingFeedback,
    QgsField,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPoint,
    QgsCoordinateReferenceSystem,
    QgsMapLayer,
    edit
)

from .dialogs.choix_couches_dialog import ChoixCouchesDialogPourTrace, DialogueSelectionEpoint
from .dialogs.parametres_dialog import ParametresDialog
from .dialogs.slider_dialog import SliderDialog
from .sscreen.sscreen import SplashScreen
from .sscreen.sscreen_load import SplashScreenLoad
from .tools import prolongement
from .tools.fenetre_profil_elevation import FenetreProfilElevation
from .tools.outil_rupture_pente import OutilRupturePente
from .tools.outil_trace_crete import OutilTraceCrete
from .tools.profil_graph_dock import ProfilGraphDock
from .utils.raster_utils import filtre_moyen_raster, generer_ombrage, fusionner_et_arrondir_rasters
from .external.SIGPACK import Epoint


class HydroLine(QObject):
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
        chemin_icones = os.path.join(self.chemin_plugin, "icon")

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
        chemin_icon_prolongement = os.path.join(self.chemin_plugin, "icon", "icon_prolongement.png")
        chemin_icon_profilgraph = os.path.join(self.chemin_plugin, "icon", "icon_profilgraph.png")
        chemin_icon_Epoint = os.path.join(self.chemin_plugin, "icon", "icon_alphaShape.png")

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

        self.action_Epoint = QAction(
            QIcon(chemin_icon_Epoint),
            "AlphaShape : Enveloppe sur semis de points",
            self.interface_qgis.mainWindow()
        )
        self.action_Epoint.triggered.connect(self.lancer_Epoint)
        self.menu_hydroline.addAction(self.action_Epoint)

        # Ajouter le menu "Hydroline" à la barre de menus principale
        self.interface_qgis.mainWindow().menuBar().addMenu(self.menu_hydroline)

    def setup_toolbar_actions(self):
        """Configure les actions de la barre d'outils."""
        chemin_icones = os.path.join(self.chemin_plugin, "icon")

        # Créer le bouton MNTvisu et l'ajouter à la barre d'outils
        self.action_mntvisu = QAction(
            QIcon(os.path.join(chemin_icones, "icon_2dm.png")),
            self.traduire(u'Data Preparation'),
            self.interface_qgis.mainWindow()
        )
        self.action_mntvisu.triggered.connect(self.preparation_mnt)
        self.barre_outils.addAction(self.action_mntvisu)

        # Configuration MNT
        self.menu_configuration = QMenu()
        self.menu_configuration.setTitle("Configuration MNT")

        self.action_tracer_seuils = QAction(
            QIcon(os.path.join(chemin_icones, "icon_option1.png")),
            "Tracé de lignes extrêmes",
            self.interface_qgis.mainWindow()
        )
        self.action_tracer_seuils.triggered.connect(self.afficher_outils_points_extremes)
        self.menu_configuration.addAction(self.action_tracer_seuils)

        # Ajouter une icône pour l'action "Tracé de rupture de pente"
        self.action_tracer_rupture = QAction(
            QIcon(os.path.join(chemin_icones, "icon_option2.png")),
            "Tracé de rupture de pente",
            self.interface_qgis.mainWindow()
        )
        self.action_tracer_rupture.triggered.connect(self.afficher_outil_rupture_pente)
        self.menu_configuration.addAction(self.action_tracer_rupture)

        self.action_reinitialiser = QAction(
            QIcon(os.path.join(chemin_icones, "icon_option3.png")),
            "Réinitialiser",
            self.interface_qgis.mainWindow())
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

    def ligne_extreme_suivante(self):
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

            # Appliquer les paramètres à l'outil de tracé de crête
            if self.outil_trace_crete:
                self.outil_trace_crete.definir_mode(selected_mode, distance_seuil)
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

                # Gérer l'affichage du graphique 3D si nécessaire
                if graphique_3d:
                    if self.fenetre_profil is None:
                        self.fenetre_profil = FenetreProfilElevation(self.interface_qgis.mainWindow())
                        self.interface_qgis.addDockWidget(Qt.RightDockWidgetArea, self.fenetre_profil)
                    self.outil_rupture_pente.definir_fenetre_profil(self.fenetre_profil)
                else:
                    if self.fenetre_profil is not None:
                        self.interface_qgis.removeDockWidget(self.fenetre_profil)
                        self.fenetre_profil = None
                    self.outil_rupture_pente.definir_fenetre_profil(None)
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
        self.interface_qgis.mainWindow().statusBar().showMessage("Chargement prolongement profil...", 2000)
        prolongement.main()

    def lancer_Epoint(self):
        self.interface_qgis.mainWindow().statusBar().showMessage(
            "Chargement de l'outil enveloppe sur semis de point 'alphashape'...", 2000)

        # Ouvrir la boîte de dialogue pour sélectionner la couche et saisir le paramètre alpha
        dialog = DialogueSelectionEpoint(self.interface_qgis.mainWindow())
        if dialog.exec_() == QDialog.Accepted:
            couche_points = dialog.get_selected_points_layer()
            alpha = dialog.get_alpha_value()

            if couche_points is None or alpha is None:
                QMessageBox.warning(self.interface_qgis.mainWindow(), "Avertissement",
                                    "Sélection ou valeur alpha incorrecte.")
                return

            # Passer la couche et l'alpha à l'outil Epoint
            Epoint.Ep(self.interface_qgis.mainWindow(), couche_points, alpha)
        else:
            QMessageBox.information(self.interface_qgis.mainWindow(), "Information", "Opération annulée.")

    def afficher_outils_points_extremes(self):
        """Affiche les boutons pour le tracé de seuils."""
        # Effacer les actions existantes sauf MNTvisu et le menu
        self.effacer_actions_barre_outils()

        chemin_icones = os.path.join(self.chemin_plugin, "icon")

        # Bouton pour démarrer le MNT
        self.action_demarrer_mnt = QAction(QIcon(os.path.join(chemin_icones, "icon_seuil.png")), self.traduire(u'Lancer outil'),
                                           self.interface_qgis.mainWindow())
        self.action_demarrer_mnt.triggered.connect(self.demarrer_points_extremes)
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

        # Bouton pour "Points Bas"
        self.checkbox_points_bas = QCheckBox("Points Bas")
        self.checkbox_points_bas.stateChanged.connect(self.basculer_points_bas)
        self.action_checkbox_points_bas = self.barre_outils.insertWidget(self.action_bouton_menu,
                                                                         self.checkbox_points_bas)
        self.actions.append(self.action_checkbox_points_bas)

        # Bouton pour "lignes de crêtes suivante"
        self.action_ligne_crete_suivante = QAction(
            QIcon(os.path.join(chemin_icones, "icon_next.png")),
            self.traduire(u'Ajouter la polyligne active à la couche / Démarrer une autre'),
            self.interface_qgis.mainWindow()
        )
        self.action_ligne_crete_suivante.triggered.connect(self.ligne_extreme_suivante)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_ligne_crete_suivante)
        self.actions.append(self.action_ligne_crete_suivante)

        # Bouton pour arrêter le MNT
        self.action_arreter_mnt = QAction(QIcon(os.path.join(chemin_icones, "icon_stop.png")), self.traduire(u'Terminer et enregistrer la couche temporairement'),
                                          self.interface_qgis.mainWindow())
        self.action_arreter_mnt.triggered.connect(self.arreter_points_extremes)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_arreter_mnt)
        self.actions.append(self.action_arreter_mnt)

    def afficher_outil_rupture_pente(self):
        """Affiche les boutons pour le tracé de rupture de pente."""
        # Effacer les actions existantes sauf MNTvisu et le menu
        self.effacer_actions_barre_outils()

        chemin_icones = os.path.join(self.chemin_plugin, "icon")

        # Bouton pour démarrer la rupture de pente
        self.action_demarrer_rupture = QAction(QIcon(os.path.join(chemin_icones, "icon_rupture.png")),
                                               self.traduire(u'Lancer outil'),
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

        # Bouton pour le mode "tracé libre"
        self.action_tracer_libre_rupture = QAction(
            QIcon(os.path.join(chemin_icones, "icon_toggle.png")),
            self.traduire(u'Tracé Libre'),
            self.interface_qgis.mainWindow()
        )
        self.action_tracer_libre_rupture.setCheckable(True)
        self.action_tracer_libre_rupture.toggled.connect(self.basculer_tracer_libre_rupture)
        # Insérer l'action avant le bouton du menu
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_tracer_libre_rupture)
        self.actions.append(self.action_tracer_libre_rupture)

        # Bouton pour "ligne de rupture suivante"
        self.action_ligne_rupture_suivante = QAction(
            QIcon(os.path.join(chemin_icones, "icon_next.png")),
            self.traduire(u'Ajouter la polyligne active à la couche / Démarrer une autre'),
            self.interface_qgis.mainWindow()
        )
        self.action_ligne_rupture_suivante.triggered.connect(self.ligne_rupture_suivante)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_ligne_rupture_suivante)
        self.actions.append(self.action_ligne_rupture_suivante)

        # Bouton pour arrêter la rupture de pente
        self.action_arreter_rupture = QAction(QIcon(os.path.join(chemin_icones, "icon_stop.png")),
                                              self.traduire(u'Terminer et enregistrer la couche temporairement'),
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

    def basculer_points_bas(self, state):
        """Active ou désactive le mode Points Bas dans l'outil."""
        if self.outil_trace_crete is not None:
            active = state == Qt.Checked
            self.outil_trace_crete.set_points_bas(active)
        else:
            QMessageBox.warning(None, "Avertissement", "Veuillez d'abord activer l'outil avec le bouton Lancer outil.")
            # Désactiver la case à cocher si l'outil n'est pas actif
            self.checkbox_points_bas.setChecked(False)

    def basculer_tracer_libre_rupture(self, coche):
        """Active ou désactive le mode de tracé libre pour rupture de pente."""
        if hasattr(self, 'outil_rupture_pente') and self.outil_rupture_pente:
            self.outil_rupture_pente.definir_mode_trace_libre(coche)
        else:
            QMessageBox.warning(None, "Avertissement",
                                "Veuillez d'abord activer l'outil avec le bouton Démarrer rupture de pente.")
            # Désactiver le bouton si l'outil n'est pas actif
            self.action_tracer_libre_rupture.setChecked(False)

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

    def preparation_mnt(self):
        """Affiche le MNT avec ombrage et style, en gérant les couches raster et TIN."""

        self.splash_screenLoad = SplashScreenLoad()
        self.splash_screenLoad.setParent(self.interface_qgis.mainWindow())
        self.splash_screenLoad.show()

        QApplication.processEvents()

        code_epsg = 2154  # RGF93 / Lambert-93
        couches_selectionnees = self.interface_qgis.layerTreeView().selectedLayers()

        if not couches_selectionnees:
            QMessageBox.warning(None, "Avertissement", "Aucune couche sélectionnée.")
            self.splash_screenLoad.close()
            return

        retour = QgsProcessingFeedback()

        couches_raster = []
        couches_tin = []

        for couche in couches_selectionnees:
            if couche.type() == QgsMapLayer.RasterLayer:
                couches_raster.append(couche)
            elif couche.type() == QgsMapLayer.MeshLayer:
                couches_tin.append(couche)
            else:
                QMessageBox.warning(None, "Avertissement", f"Type de couche non supporté : {couche.name()}")
                self.splash_screenLoad.close()
                return

        for couche_tin in couches_tin:
            tin_path = couche_tin.publicSource()
            nom_couche = couche_tin.name()
            crs_tin = couche_tin.crs()

            parametres_meshrasterize = {
                'INPUT': tin_path,
                'DATASET_GROUPS': [0],
                'DATASET_TIME': {'type': 'static'},
                'EXTENT': None,
                'PIXEL_SIZE': 1.0,
                'CRS_OUTPUT': crs_tin,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }

            resultat_rasterize = processing.run("native:meshrasterize", parametres_meshrasterize, feedback=retour)
            couche_raster = QgsRasterLayer(resultat_rasterize['OUTPUT'], f"{nom_couche}_raster")

            if not couche_raster.isValid():
                QMessageBox.critical(None, "Erreur", f"Échec de la conversion du TIN en raster : {couche_tin.name()}")
                self.splash_screenLoad.close()
                return

            couche_raster_filtre = filtre_moyen_raster(couche_raster, kernel_size=3)
            if couche_raster_filtre is None:
                QMessageBox.critical(None, "Erreur",
                                     f"Échec de l'application du filtre moyen au raster : {couche_tin.name()}")
                self.splash_screenLoad.close()
                return

            chemin_style = os.path.join(self.chemin_plugin, 'styleQGIS.qml')
            if os.path.exists(chemin_style):
                couche_raster_filtre.loadNamedStyle(chemin_style)
                couche_raster_filtre.triggerRepaint()
            else:
                QMessageBox.warning(None, "Avertissement", "Le fichier de style 'styleQGIS.qml' est introuvable.")

            couche_raster_filtre.setCrs(crs_tin)
            QgsProject.instance().addMapLayer(couche_raster_filtre)

            couche_ombrage = generer_ombrage(couche_raster_filtre)
            if not couche_ombrage.isValid():
                QMessageBox.critical(None, "Erreur", f"Échec de la création de l'ombrage pour {nom_couche}.")
                self.splash_screenLoad.close()
                return

            couche_ombrage.setCrs(crs_tin)
            QgsProject.instance().addMapLayer(couche_ombrage, False)
            racine = QgsProject.instance().layerTreeRoot()
            noeud_raster = racine.findLayer(couche_raster_filtre.id())
            racine.insertLayer(racine.children().index(noeud_raster) + 1, couche_ombrage)

            QgsProject.instance().removeMapLayer(couche_tin.id())
            layer_tree_view = self.interface_qgis.layerTreeView()
            layer_tree_view.refreshLayerSymbology(couche_raster_filtre.id())

        if couches_raster:
            crs = QgsCoordinateReferenceSystem(code_epsg)
            for couche in couches_raster:
                if couche.crs() != crs:
                    couche.setCrs(crs)
                    couche.triggerRepaint()

            if len(couches_raster) > 1:
                couche_combinee = fusionner_et_arrondir_rasters(couches_raster, precision_decimales=1)
                if not couche_combinee.isValid():
                    QMessageBox.critical(None, "Erreur", "Échec de la création du raster combiné.")
                    self.splash_screenLoad.close()
                    return
            else:
                couche_combinee = couches_raster[0]

            couche_combinee_filtre = filtre_moyen_raster(couche_combinee, kernel_size=3)
            if couche_combinee_filtre is None:
                QMessageBox.critical(None, "Erreur", "Échec de l'application du filtre moyen au raster.")
                self.splash_screenLoad.close()
                return

            couche_ombrage = generer_ombrage(couche_combinee_filtre)
            if not couche_ombrage.isValid():
                QMessageBox.critical(None, "Erreur", "Échec de la création de l'ombrage.")
                self.splash_screenLoad.close()
                return

            chemin_style = os.path.join(self.chemin_plugin, 'styleQGIS.qml')
            if os.path.exists(chemin_style):
                couche_combinee_filtre.loadNamedStyle(chemin_style)
                couche_combinee_filtre.triggerRepaint()
            else:
                QMessageBox.warning(None, "Avertissement", "Le fichier de style 'styleQGIS.qml' est introuvable.")

            QgsProject.instance().addMapLayer(couche_combinee_filtre)
            QgsProject.instance().addMapLayer(couche_ombrage, False)
            racine = QgsProject.instance().layerTreeRoot()
            noeud_raster = racine.findLayer(couche_combinee_filtre.id())
            racine.insertLayer(racine.children().index(noeud_raster) + 1, couche_ombrage)

            if len(couches_raster) > 1 or couches_raster[0] != couche_combinee_filtre:
                for couche in couches_raster:
                    QgsProject.instance().removeMapLayer(couche.id())

        self.splash_screenLoad.close()

    def demarrer_rupture_pente(self):
        """Activation de l'outil de tracé de rupture de pente."""
        # Afficher la boîte de dialogue pour sélectionner le MNT et la couche de polyligne
        dialog = ChoixCouchesDialogPourTrace(self.interface_qgis.mainWindow())
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

        # Gérer l'affichage du graphique 3D si nécessaire
        if self.graphique_3d_active:
            if self.fenetre_profil is None:
                self.fenetre_profil = FenetreProfilElevation(self.interface_qgis.mainWindow())
                self.interface_qgis.addDockWidget(Qt.RightDockWidgetArea, self.fenetre_profil)
            # Passer la fenêtre de profil à l'outil de dessin
            self.outil_rupture_pente.definir_fenetre_profil(self.fenetre_profil)
        else:
            # Assurer que l'outil connaît l'absence de fenêtre de profil
            self.outil_rupture_pente.definir_fenetre_profil(None)

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

        # Sortir du mode tracé libre si actif
        if self.outil_rupture_pente.mode_trace_libre:
            self.outil_rupture_pente.definir_mode_trace_libre(False)
            self.action_tracer_libre_rupture.setChecked(False)

        # Confirmer la dernière polyligne si elle n'a pas été déjà confirmée
        if self.outil_rupture_pente.polyligne_confirmee is not None:
            self.outil_rupture_pente.confirmer_polyligne()


        # Utiliser les points originaux pour obtenir le Z du MNT
        points_originaux = self.outil_rupture_pente.liste_points
        points_avec_z = []

        for point in points_originaux:
            z = self.outil_rupture_pente.obtenir_elevation_au_point_unique(point)
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

    def demarrer_points_extremes(self):
        """Activation de l'outil de tracé."""
        # Afficher la boîte de dialogue pour sélectionner le MNT et la couche de polyligne
        dialog = ChoixCouchesDialogPourTrace(self.interface_qgis.mainWindow())
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

    def arreter_points_extremes(self):
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
                z = self.outil_trace_crete.obtenir_elevation_au_point_unique(point)
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

# Création de l'application Qt
if __name__ == '__main__':
    app = QApplication(sys.argv)
    dialog = ParametresDialog()
    dialog.show()
    sys.exit(app.exec_())





