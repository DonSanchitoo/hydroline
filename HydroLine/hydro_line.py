
# /HydroLine.py

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

    Ce plugin fournit plusieurs outils pour visualiser, tracer et prolonger des lignes de crête et de rupture de pente
    sur un Modèle Numérique de Terrain (MNT) au sein de QGIS.

    Attributes
    ----------
    interface_qgis : QgisInterface
        L'interface principale de QGIS.
    canvas : QgsMapCanvas
        Canevas pour le traçage et l'interaction avec les cartes.
    chemin_plugin : str
        Chemin vers le répertoire du plugin contenant les ressources.
    actions : list of QAction
        Liste des actions disponibles pour le plugin.
    ...

    Methods
    -------
    traduire(message)
        Traduit un message en utilisant l'API de traduction Qt.
    on_layer_will_be_removed(layer_id)
        Gestionnaire appelé lorsqu'une couche est supprimée du projet.
    initGui()
        Configure le menu initial pour le plugin.
    setup_toolbar_actions()
        Configure les actions de la barre d'outils du plugin.
    basculer_visibilite_barre_outils()
        Bascule la visibilité de la barre d'outils et affiche le splash screen à l'ouverture.
    lancer_outil()
        Lance les outils du plugin après l'affichage du splash screen.
    ligne_extreme_suivante()
        Valide la polyligne actuelle et commence une nouvelle.
    ligne_rupture_suivante()
        Valide la polyligne actuelle et commence une nouvelle.
    lancer_GraphZ()
        Ouvre le dock de profil graphique.
    unload()
        Supprime la barre d'outils et les boutons du plugin de l'interface QGIS.
    ouvrir_parametres()
        Ouvre la fenêtre de paramètres du plugin et configure les outils en fonction des réglages.
    mettre_a_jour_champs(couche)
        Met à jour les champs de la couche sélectionnée selon les réglages actifs.
    effacer_actions_barre_outils()
        Supprime toutes les actions de la barre d'outils sauf pour MNTvisu et le menu.
    lancer_prolongement()
        Lance l'outil de prolongement de profil.
    lancer_Epoint()
        Lance l'outil enveloppe sur semis de points en utilisant alphashape.
    afficher_outils_points_extremes()
        Affiche les boutons de la barre d'outils pour le tracé et la simplification de seuils.
    afficher_outil_rupture_pente()
        Affiche les boutons de la barre d'outils pour le tracé de rupture de pente.
    basculer_points_bas(state)
        Active ou désactive le mode Points Bas dans l'outil.
    basculer_tracer_libre_rupture(coche)
        Active ou désactive le mode de tracé libre pour la rupture de pente.
    basculer_simplification_rupture_pente(coche)
        Active ou désactive la simplification de tracé pour l'outil de rupture de pente.
    reinitialiser_barre_outils()
        Réinitialise la barre d'outils à son état initial.
    basculer_simplification(coche)
        Active ou désactive la simplification de tracé.
    basculer_tracer_libre(coche)
        Active ou désactive le mode de tracé libre.
    preparation_mnt()
        Affiche le MNT avec ombrage, styles prédéfinis et gère les couches raster et TIN.
    demarrer_rupture_pente()
        Activation de l'outil de tracé de rupture de pente.
    changer_mode_rupture(index)
        Change le mode de rupture de pente en fonction de la sélection.
    arreter_rupture()
        Désactivation de l'outil de rupture de pente et création de la couche temporaire.
    demarrer_points_extremes()
        Activation de l'outil de tracé.
    changer_mode(index)
        Change le mode de l'outil en fonction de la sélection.
    arreter_points_extremes()
        Désactivation de l'outil et création de la couche temporaire.
    """

    def __init__(self, interface_qgis):
        """
        Initialise le plugin HydroLine avec les attributs nécessaires pour le fonctionnement.

        Parameters
        ----------
        interface_qgis : QgisInterface
            L'interface principale de QGIS pour plugin interaction.
        """

        super().__init__()
        self.interface_qgis = interface_qgis
        self.canvas = interface_qgis.mapCanvas()
        self.chemin_plugin = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.traduire(u'&Assist MNT')
        self.barre_outils = None
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

        Parameters
        ----------
        message : str
            Le message à traduire.

        Returns
        -------
        str
            Le message traduit.
        """

        return QCoreApplication.translate('AssistMnt', message)

    def on_layer_will_be_removed(self, layer_id):
        """
        Gestionnaire appelé lorsqu'une couche est supprimée du projet, met à jour les attributs en conséquence.

        Parameters
        ----------
        layer_id : str
            Identifiant ID de la couche supprimée.
        """

        if self.couche_rupture and self.couche_rupture.id() == layer_id:
            self.couche_rupture = None
        if self.couche_crete and self.couche_crete.id() == layer_id:
            self.couche_crete = None

    def initGui(self):
        """
        Configure le menu initial du plugin dans l'interface QGIS.
        """

        chemin_icones = os.path.join(self.chemin_plugin, "icon")

        # Créer le menu "Hydroline"
        self.menu_hydroline = QMenu("Hydroline", self.interface_qgis.mainWindow())

        self.action_settings = QAction(
            QIcon(os.path.join(chemin_icones, "icon_setting.png")),
            self.traduire(u'Paramètres'),
            self.interface_qgis.mainWindow()
        )
        self.action_settings.triggered.connect(self.ouvrir_parametres)
        self.menu_hydroline.addAction(self.action_settings)

        self.action_assistance_trace = QAction(
            QIcon(os.path.join(chemin_icones, "icon_toolbox.png")),
            "Assistance au tracé",
            self.interface_qgis.mainWindow()
        )
        self.action_assistance_trace.triggered.connect(self.basculer_visibilite_barre_outils)
        self.menu_hydroline.addAction(self.action_assistance_trace)

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

        # Menu "Hydroline" à la barre de menus
        self.interface_qgis.mainWindow().menuBar().addMenu(self.menu_hydroline)

    def setup_toolbar_actions(self):
        """
        Configure les actions de la barre d'outils du plugin.
        """

        chemin_icones = os.path.join(self.chemin_plugin, "icon")

        self.action_mntvisu = QAction(
            QIcon(os.path.join(chemin_icones, "icon_2dm.png")),
            self.traduire(u'Data Preparation'),
            self.interface_qgis.mainWindow()
        )
        self.action_mntvisu.triggered.connect(self.preparation_mnt)
        self.barre_outils.addAction(self.action_mntvisu)

        self.menu_configuration = QMenu()
        self.menu_configuration.setTitle("Configuration MNT")

        self.action_tracer_seuils = QAction(
            QIcon(os.path.join(chemin_icones, "icon_option1.png")),
            "Tracé de lignes extrêmes",
            self.interface_qgis.mainWindow()
        )
        self.action_tracer_seuils.triggered.connect(self.afficher_outils_points_extremes)
        self.menu_configuration.addAction(self.action_tracer_seuils)

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

        # menu à la barre d'outils
        self.bouton_menu = QToolButton()
        self.bouton_menu.setText("Configuration MNT")
        self.bouton_menu.setMenu(self.menu_configuration)
        self.bouton_menu.setPopupMode(QToolButton.InstantPopup)
        self.action_bouton_menu = self.barre_outils.addWidget(self.bouton_menu)

        self.actions = [self.action_mntvisu, self.action_bouton_menu]

    def basculer_visibilite_barre_outils(self):
        """
        Bascule la visibilité de la barre d'outils, et affiche le splash screen seulement à l'ouverture.
        """

        is_currently_visible = self.barre_outils_visible

        if not is_currently_visible:
            self.splash_screen = SplashScreen()
            self.splash_screen.setParent(self.interface_qgis.mainWindow())
            self.splash_screen.finished.connect(self.lancer_outil)
            self.splash_screen.show()
        else:
            if self.barre_outils is not None:
                self.barre_outils.setVisible(False)
            self.barre_outils_visible = False

    def lancer_outil(self):
        """
        Fonction appelée lorsque le splash screen est terminé, qui initialise les outils du plugin.
        """

        self.splash_screen.deleteLater()
        self.splash_screen = None

        if self.barre_outils is None:
            self.barre_outils = self.interface_qgis.addToolBar('Assist MNT')
            self.barre_outils.setObjectName('Assist MNT')
            self.setup_toolbar_actions()

        self.barre_outils_visible = True
        self.barre_outils.setVisible(True)

    def ligne_extreme_suivante(self):
        """
        Valide la polyligne en cours et commence une nouvelle ligne de crête.
        """

        if self.outil_trace_crete is not None:
            self.outil_trace_crete.confirmer_polyligne()
        else:
            QMessageBox.warning(None, "Avertissement", "Aucun tracé en cours.")

    def ligne_rupture_suivante(self):
        """
        Valide la polyligne en cours et commence une nouvelle ligne de rupture de pente.
        """

        if self.outil_rupture_pente is not None:
            self.outil_rupture_pente.confirmer_polyligne()
        else:
            QMessageBox.warning(None, "Avertissement", "Aucun tracé en cours.")

    def lancer_GraphZ(self):
        """
        Ouvre le dock de profil graphique.
        """

        self.prof_graph_dock = ProfilGraphDock(self.canvas, self.interface_qgis.mainWindow())
        self.interface_qgis.addDockWidget(Qt.BottomDockWidgetArea, self.prof_graph_dock)

    def unload(self):
        """
        Supprime la barre d'outils du plugin et ses boutons de l'interface QGIS.
        """

        if self.barre_outils is not None:
            for action in self.actions:
                self.barre_outils.removeAction(action)
            self.interface_qgis.mainWindow().removeToolBar(self.barre_outils)
            self.barre_outils = None

        barre_menus = self.interface_qgis.mainWindow().menuBar()
        barre_menus.removeAction(self.menu_hydroline.menuAction())
        if self.fenetre_profil is not None:
            self.interface_qgis.removeDockWidget(self.fenetre_profil)
            self.fenetre_profil = None

    def ouvrir_parametres(self):
        """
        Ouvre la fenêtre de paramètres et ajuste les réglages des outils du plugin.
        """

        dialog = ParametresDialog(self.interface_qgis.mainWindow())
        if self.outil_trace_crete:
            current_mode = self.outil_trace_crete.mode
            distance_seuil = self.outil_trace_crete.distance_seuil
        else:
            current_mode = 1
            distance_seuil = 10

        dialog.set_values(current_mode, distance_seuil, self.graphique_3d_active, self.field_settings)

        if dialog.exec_():
            selected_mode = dialog.get_selected_mode()
            graphique_3d = dialog.is_graphique_3d_checked()
            self.graphique_3d_active = graphique_3d
            self.field_settings = dialog.get_field_settings()

            self.mettre_a_jour_champs(self.couche_crete)
            self.mettre_a_jour_champs(self.couche_rupture)

            if self.outil_trace_crete:
                self.outil_trace_crete.definir_mode(selected_mode, distance_seuil)
                self.outil_trace_crete.field_settings = self.field_settings
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

            if hasattr(self, 'outil_rupture_pente') and self.outil_rupture_pente:
                self.outil_rupture_pente.field_settings = self.field_settings
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
            pass

    def mettre_a_jour_champs(self, couche):
        """
        Met à jour les champs de la couche sélectionnée en fonction des réglages actifs.

        Parameters
        ----------
        couche : QgsVectorLayer
            Couche dont les champs doivent être mis à jour.
        """

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
        """
        Supprime toutes les actions de la barre d'outils sauf pour MNTvisu et le menu.
        """

        actions_a_conserver = [self.action_mntvisu, self.action_bouton_menu]

        actions_a_supprimer = [action for action in self.barre_outils.actions() if action not in actions_a_conserver]

        for action in actions_a_supprimer:
            self.barre_outils.removeAction(action)
            if action in self.actions and action not in actions_a_conserver:
                self.actions.remove(action)

    def lancer_prolongement(self):
        """
        Lance l'outil de prolongement de profil.
        """

        self.interface_qgis.mainWindow().statusBar().showMessage("Chargement prolongement profil...", 2000)
        prolongement.main()

    def lancer_Epoint(self):
        """
        Lance l'outil enveloppe sur semis de points avec alphashape.
        """

        self.interface_qgis.mainWindow().statusBar().showMessage(
            "Chargement de l'outil enveloppe sur semis de point 'alphashape'...", 2000)

        dialog = DialogueSelectionEpoint(self.interface_qgis.mainWindow())
        if dialog.exec_() == QDialog.Accepted:
            couche_points = dialog.get_selected_points_layer()
            alpha = dialog.get_alpha_value()

            if couche_points is None or alpha is None:
                QMessageBox.warning(self.interface_qgis.mainWindow(), "Avertissement",
                                    "Sélection ou valeur alpha incorrecte.")
                return

            Epoint.Ep(self.interface_qgis.mainWindow(), couche_points, alpha)
        else:
            QMessageBox.information(self.interface_qgis.mainWindow(), "Information", "Opération annulée.")

    def lancer_rupture_pente(self):
        """
        Activation de l'outil de tracé de rupture de pente avec création de la couche vectorielle.
        """
        dialog = ChoixCouchesDialogPourTrace(self.interface_qgis.mainWindow())
        result = dialog.exec_()
        if result == QDialog.Accepted:
            couche_mnt = dialog.get_selected_mnt_layer()
            couche_rupture_selectionnee = dialog.get_selected_polyline_layer()
            nouvelle_couche = dialog.is_new_layer_checked()
        else:
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

        if couche_rupture_selectionnee is not None:
            self.couche_rupture = couche_rupture_selectionnee
        elif nouvelle_couche:
            crs = self.canvas.mapSettings().destinationCrs()
            self.couche_rupture = QgsVectorLayer(f"MultiLineStringZ?crs={crs.authid()}", "Ruptures de Pente", "memory")
            if not self.couche_rupture.isValid():
                QMessageBox.critical(None, "Erreur",
                                     "Impossible de créer la couche vectorielle pour les ruptures de pente.")
                return
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

            QgsProject.instance().addMapLayer(self.couche_rupture)
            symbole = self.couche_rupture.renderer().symbol()
            symbole.setColor(QColor('#FF0000'))
            symbole.setWidth(1)
        else:
            QMessageBox.warning(None, "Avertissement",
                                "Vous devez sélectionner une couche de polyligne ou cocher 'Nouvelle couche de travail'.")
            return

        self.outil_rupture_pente = OutilRupturePente(self.canvas, couche_mnt, mode=mode_selectionne)
        # Connecter le signal
        self.outil_rupture_pente.mode_trace_libre_changed.connect(self.action_tracer_libre_rupture.setChecked)

        self.outil_rupture_pente = OutilRupturePente(self.canvas, couche_mnt, mode=mode_selectionne)

        self.outil_rupture_pente.definir_couche_vectorielle(self.couche_rupture)

        self.canvas.setMapTool(self.outil_rupture_pente)

        if self.graphique_3d_active:
            if self.fenetre_profil is None:
                self.fenetre_profil = FenetreProfilElevation(self.interface_qgis.mainWindow())
                self.interface_qgis.addDockWidget(Qt.RightDockWidgetArea, self.fenetre_profil)
            self.outil_rupture_pente.definir_fenetre_profil(self.fenetre_profil)
        else:
            self.outil_rupture_pente.definir_fenetre_profil(None)

    def lancer_points_extremes(self):
        """
        Activation de l'outil de tracé pour lignes de crête avec création de la couche vectorielle.
        """
        dialog = ChoixCouchesDialogPourTrace(self.interface_qgis.mainWindow())
        result = dialog.exec_()
        if result == QDialog.Accepted:
            couche_mnt = dialog.get_selected_mnt_layer()
            couche_crete_selectionnee = dialog.get_selected_polyline_layer()
            nouvelle_couche = dialog.is_new_layer_checked()
        else:
            return

        if couche_mnt is None:
            QMessageBox.warning(None, "Avertissement", "Vous devez sélectionner un MNT.")
            return

        if couche_crete_selectionnee is not None:
            self.couche_crete = couche_crete_selectionnee
        elif nouvelle_couche:
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

            QgsProject.instance().addMapLayer(self.couche_crete)
            symbole = self.couche_crete.renderer().symbol()
            symbole.setColor(QColor('#00FF00'))
            symbole.setWidth(1)
        else:
            QMessageBox.warning(None, "Avertissement",
                                "Vous devez sélectionner une couche de polyligne ou cocher 'Nouvelle couche de travail'.")
            return

        self.outil_trace_crete = OutilTraceCrete(self.canvas, couche_mnt)
        # Connecter le signal
        self.outil_trace_crete.mode_trace_libre_changed.connect(self.action_tracer_libre.setChecked)

        self.outil_trace_crete.definir_couche_vectorielle(self.couche_crete)
        self.canvas.setMapTool(self.outil_trace_crete)

        if self.graphique_3d_active:
            if self.fenetre_profil is None:
                self.fenetre_profil = FenetreProfilElevation(self.interface_qgis.mainWindow())
                self.interface_qgis.addDockWidget(Qt.RightDockWidgetArea, self.fenetre_profil)
            self.outil_trace_crete.definir_fenetre_profil(self.fenetre_profil)
        else:
            self.outil_trace_crete.definir_fenetre_profil(None)

        self.outil_trace_crete.definir_mode(1)  # Mode 1 par défaut

    def afficher_outils_points_extremes(self):
        """
        Affiche les boutons pour le tracé de seuils et la simplification dans la barre d'outils.
        """

        self.effacer_actions_barre_outils()

        chemin_icones = os.path.join(self.chemin_plugin, "icon")

        # Bouton démarrer
        self.action_demarrer_mnt = QAction(QIcon(os.path.join(chemin_icones, "icon_seuil.png")), self.traduire(u'Lancer outil'),
                                           self.interface_qgis.mainWindow())
        self.action_demarrer_mnt.triggered.connect(self.lancer_points_extremes)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_demarrer_mnt)
        self.actions.append(self.action_demarrer_mnt)

        # Bouton simplification
        self.bouton_simplification = QToolButton()
        self.bouton_simplification.setText("Simplification")
        self.bouton_simplification.setCheckable(True)
        self.bouton_simplification.toggled.connect(self.basculer_simplification_crete)
        self.action_bouton_simplification = self.barre_outils.insertWidget(self.action_bouton_menu, self.bouton_simplification)
        self.actions.append(self.action_bouton_simplification)


        # Bouton tracé libre
        self.action_tracer_libre = QAction(QIcon(os.path.join(chemin_icones, "icon_toggle.png")),
                                           self.traduire(u'Tracé Libre : Touche S'), self.interface_qgis.mainWindow())
        self.action_tracer_libre.setCheckable(True)
        self.action_tracer_libre.toggled.connect(self.basculer_tracer_libre_crete)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_tracer_libre)
        self.actions.append(self.action_tracer_libre)

        # Bouton pour "Points Bas"
        self.checkbox_points_bas = QCheckBox("Points Bas")
        self.checkbox_points_bas.stateChanged.connect(self.basculer_points_bas)
        self.action_checkbox_points_bas = self.barre_outils.insertWidget(self.action_bouton_menu,
                                                                         self.checkbox_points_bas)
        self.actions.append(self.action_checkbox_points_bas)

        self.action_ligne_crete_suivante = QAction(
            QIcon(os.path.join(chemin_icones, "icon_next.png")),
            self.traduire(u'Ajouter la polyligne active à la couche / Démarrer une autre : Touche D'),
            self.interface_qgis.mainWindow()
        )
        self.action_ligne_crete_suivante.triggered.connect(self.ligne_extreme_suivante)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_ligne_crete_suivante)
        self.actions.append(self.action_ligne_crete_suivante)

        self.action_arreter_mnt = QAction(QIcon(os.path.join(chemin_icones, "icon_stop.png")), self.traduire(u'Terminer et enregistrer la couche temporairement'),
                                          self.interface_qgis.mainWindow())
        self.action_arreter_mnt.triggered.connect(self.arreter_points_extremes)
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_arreter_mnt)
        self.actions.append(self.action_arreter_mnt)

    def afficher_outil_rupture_pente(self):
        """
        Affiche les boutons pour le tracé de rupture de pente dans la barre d'outils.
        """

        # Effacer les actions existantes sauf MNTvisu et le menu
        self.effacer_actions_barre_outils()

        chemin_icones = os.path.join(self.chemin_plugin, "icon")

        # Bouton pour démarrer la rupture de pente
        self.action_demarrer_rupture = QAction(QIcon(os.path.join(chemin_icones, "icon_rupture.png")),
                                               self.traduire(u'Lancer outil'),
                                               self.interface_qgis.mainWindow())
        self.action_demarrer_rupture.triggered.connect(self.lancer_rupture_pente)
        # Insérer l'action avant le bouton du menu
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_demarrer_rupture)
        self.actions.append(self.action_demarrer_rupture)

        # Bouton simplification
        self.bouton_simplification_pente = QToolButton()
        self.bouton_simplification_pente.setText("Simplification")
        self.bouton_simplification_pente.setCheckable(True)
        self.bouton_simplification_pente.toggled.connect(self.basculer_simplification_rupture_pente)
        # Insérer le widget avant le bouton du menu
        self.action_bouton_simplification = self.barre_outils.insertWidget(self.action_bouton_menu,
                                                                           self.bouton_simplification_pente)
        self.actions.append(self.action_bouton_simplification)

        # Bouton "tracé libre"
        self.action_tracer_libre_rupture = QAction(
            QIcon(os.path.join(chemin_icones, "icon_toggle.png")),
            self.traduire(u'Tracé Libre : Touche S'),
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
            self.traduire(u'Ajouter la polyligne active à la couche / Démarrer une autre : Touche D'),
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
        self.barre_outils.insertAction(self.action_bouton_menu, self.action_arreter_rupture)
        self.actions.append(self.action_arreter_rupture)

        # Menu mode
        self.mode_combobox = QComboBox()
        self.mode_combobox.addItem("Concave")
        self.mode_combobox.addItem("Convexe")
        self.mode_combobox.currentIndexChanged.connect(self.changer_mode_rupture)

        # Bouton du menu
        self.action_mode_combobox = self.barre_outils.insertWidget(self.action_bouton_menu, self.mode_combobox)
        self.actions.append(self.action_mode_combobox)

    def basculer_points_bas(self, state):
        """
        Active ou désactive le mode Points Bas dans l'outil trace crête.

        Parameters
        ----------
        state : Qt.CheckState
            État de la case à cocher pour Points Bas.
        """

        if self.outil_trace_crete is not None:
            active = state == Qt.Checked
            self.outil_trace_crete.set_points_bas(active)
        else:
            QMessageBox.warning(None, "Avertissement", "Veuillez d'abord activer l'outil avec le bouton Lancer outil.")
            self.checkbox_points_bas.setChecked(False)

    def basculer_tracer_libre_rupture(self, coche):
        """
        Active ou désactive le mode de tracé libre pour la rupture de pente.

        Parameters
        ----------
        coche : bool
            État activé ou désactivé du tracé libre.
        """

        if hasattr(self, 'outil_rupture_pente') and self.outil_rupture_pente:
            self.outil_rupture_pente.definir_mode_trace_libre(coche)
        else:
            QMessageBox.warning(None, "Avertissement",
                                "Veuillez d'abord activer l'outil avec le bouton Démarrer rupture de pente.")
            self.action_tracer_libre_rupture.setChecked(False)

    def basculer_simplification_rupture_pente(self, coche):
        """
        Active ou désactive la simplification de tracé pour l'outil de rupture de pente.

        Parameters
        ----------
        coche : bool
            État activé ou désactivé de la simplification.
        """

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
        """
        Réinitialise la barre d'outils à son état initial lors du lancement du plugin.
        """

        self.effacer_actions_barre_outils()

        if self.outil_trace_crete is not None:
            self.outil_trace_crete.reinitialiser()
            self.outil_trace_crete = None
            self.canvas.unsetMapTool(self.canvas.mapTool())

    def basculer_simplification_crete(self, coche):
        """
        Active ou désactive la simplification de tracé pour le outil trace crête.

        Parameters
        ----------
        coche : bool
            État activé ou désactivé de la simplification.
        """

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

    def basculer_tracer_libre_crete(self, coche):
        """
        Active ou désactive le mode de tracé libre pour le outil trace crête.

        Parameters
        ----------
        coche : bool
            État activé ou désactivé du tracé libre.
        """

        if self.outil_trace_crete is not None:
            self.outil_trace_crete.definir_mode_trace_libre(coche)
        else:
            QMessageBox.warning(None, "Avertissement", "Veuillez d'abord activer l'outil avec le bouton Démarrer MNT.")
            self.action_tracer_libre.setChecked(False)

    def preparation_mnt(self):
        """
        Affiche le MNT avec ombrage et style prédéfini, en gérant les couches raster et TIN.

        Note
        ----
        Utilise les méthodes `filtre_moyen_raster` et `generer_ombrage` pour le filtrage
        et l'ajout de l'ombrage au MNT.
        """
        self.splash_screenLoad = SplashScreenLoad()
        self.splash_screenLoad.setParent(self.interface_qgis.mainWindow())
        self.splash_screenLoad.show()

        QApplication.processEvents()

        code_epsg = 2154
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

    def changer_mode_rupture(self, index):
        """
        Change le mode de rupture de pente en fonction de la sélection du combo box.

        Parameters
        ----------
        index : int
            Index du mode sélectionné.
        """

        if hasattr(self, 'outil_rupture_pente') and self.outil_rupture_pente is not None:
            mode = 'concave' if index == 0 else 'convexe'
            self.outil_rupture_pente.definir_mode(mode)
        else:
            QMessageBox.warning(None, "Avertissement",
                                "Veuillez d'abord activer l'outil avec le bouton Démarrer rupture de pente.")

    def arreter_rupture(self):
        """
        Désactivation de l'outil de rupture de pente et création de la couche temporaire.
        """

        if self.outil_rupture_pente is None or self.outil_rupture_pente.liste_points is None:
            QMessageBox.warning(None, "Avertissement", "Aucun tracé en cours.")
            return

        if self.outil_rupture_pente.mode_trace_libre:
            self.outil_rupture_pente.definir_mode_trace_libre(False)
            self.action_tracer_libre_rupture.setChecked(False)

        if self.outil_rupture_pente.polyligne_confirmee is not None:
            self.outil_rupture_pente.confirmer_polyligne()

        points_originaux = self.outil_rupture_pente.liste_points
        points_avec_z = []

        for point in points_originaux:
            z = self.outil_rupture_pente.obtenir_elevation_au_point_unique(point)
            if z is not None:
                point_z = QgsPoint(point.x(), point.y(), z)
            else:
                point_z = QgsPoint(point.x(), point.y(), 0)
            points_avec_z.append(point_z)

        polyligne_z = QgsGeometry.fromPolyline(points_avec_z)

        entite = QgsFeature()
        entite.setGeometry(polyligne_z)
        entite.setAttributes([1])

        self.outil_rupture_pente.reinitialiser()
        self.outil_rupture_pente.nettoyer_ressources()
        self.outil_rupture_pente = None
        self.canvas.unsetMapTool(self.canvas.mapTool())

    def changer_mode(self, index):
        """
        Change le mode de l'outil de trace crête en fonction de la sélection du combo box.

        Parameters
        ----------
        index : int
            Index du mode sélectionné.
        """

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
        """
        Désactivation de l'outil de trace crête et création de la couche temporaire.
        """

        if self.outil_trace_crete is None:
            QMessageBox.warning(None, "Avertissement", "Aucun tracé en cours.")
            return

        if self.outil_trace_crete.polyligne_confirmee is not None:
            self.outil_trace_crete.confirmer_polyligne()

        if self.outil_trace_crete.mode_trace_libre:
            self.outil_trace_crete.definir_mode_trace_libre(False)
            self.action_tracer_libre.setChecked(False)

        crs = self.canvas.mapSettings().destinationCrs()
        couche_temporaire = QgsVectorLayer(f"MultiLineStringZ?crs={crs.authid()}", "Ligne de Crête", "memory")

        if not couche_temporaire.isValid():
            QMessageBox.critical(None, "Erreur", "Impossible de créer la couche vectorielle temporaire.")
            return

        fournisseur_donnees = couche_temporaire.dataProvider()

        if self.outil_trace_crete.polyligne_confirmee is not None:
            points_avec_z = []
            for point in self.outil_trace_crete.liste_points:
                z = self.outil_trace_crete.obtenir_elevation_au_point_unique(point)
                if z is not None:
                    point_z = QgsPoint(point.x(), point.y(), z)
                    points_avec_z.append(point_z)
                else:
                    point_z = QgsPoint(point.x(), point.y(), 0)
                    points_avec_z.append(point_z)

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

        symbole = couche_temporaire.renderer().symbol()
        symbole.setColor(QColor('#00FF00'))
        symbole.setWidth(1)

        self.outil_trace_crete.reinitialiser()
        self.outil_trace_crete.nettoyer_ressources_1()
        self.outil_trace_crete = None
        self.canvas.unsetMapTool(self.canvas.mapTool())

        if self.fenetre_profil is not None:
            self.interface_qgis.removeDockWidget(self.fenetre_profil)
            self.fenetre_profil = None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dialog = ParametresDialog()
    dialog.show()
    sys.exit(app.exec_())





