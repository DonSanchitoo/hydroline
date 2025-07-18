
# tools/outil_trace_crete.py


import os
import sys

from osgeo import gdal
from qgis._core import QgsPoint

from ..threads.raster_loading_thread import RasterLoadingThread

# Ajouter le répertoire du plugin au PYTHONPATH
chemin_plugin = os.path.dirname(__file__)
if chemin_plugin not in sys.path:
    sys.path.append(chemin_plugin)
from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QDialog, QFrame
from PyQt5.QtGui import QPixmap

from PyQt5.QtCore import QUrl, QTimer, pyqtSignal


from qgis.PyQt.QtCore import QCoreApplication, Qt, QObject, QPoint, QVariant
from qgis.PyQt.QtGui import QIcon, QColor, QPainter
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QMenu, QToolButton, QInputDialog, QDockWidget, QWidget, QVBoxLayout, QComboBox, QApplication
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsCoordinateTransform
)
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QSlider, QLabel, QPushButton, QGridLayout
from qgis.gui import QgsRubberBand
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QDialog

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl

from .base_map_tool import BaseMapTool
from qgis.core import QgsGeometry, QgsFeature, QgsPoint, QgsWkbTypes, QgsPointXY
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QColor
import numpy as np
import math

from .outil_points_bas import select_next_pixel_bas as select_next_pixel_points_bas
from ..utils.undo_manager import UndoManager, AddPointsAction
from ..utils.error import afficher_message_epsg


class OutilTraceCrete(BaseMapTool):
    """
    Outil de dessin de ligne de crête avec assistance dynamique sur MNT.

    Cette classe permet d'interagir avec le Modèle Numérique de Terrain pour tracer des lignes de crête
    en utilisant des calculs dynamiques basés sur l'altitude des pixels.

    Attributes
    ----------
    canvas : QgsMapCanvas
        Le canevas de la carte.
    couche_raster : QgsRasterLayer
        La couche raster contenant le MNT.
    id_counter : int
        Compteur utilisé pour assigner des identifiants aux polylignes.
    data_loaded : bool
        Indicateur montrant si les données du raster ont été chargées avec succès.
    points_bas_active : bool
        Indicateur du mode de tracé utilisant les points bas, par défaut False.
    select_next_pixel_func : function
        Fonction utilisée pour sélectionner le prochain pixel pendant le tracé.
    undo_manager : UndoManager
        Gestionnaire d'annulation des actions réalisées sur le tracé.
    liste_points : list of QgsPoint
        Liste des points actuellement tracés.
    chemin_dynamique : QgsGeometry or None
        Géométrie représentative du chemin dynamique en cours de tracé.
    polyligne_confirmee : QgsGeometry or None
        Géométrie de la polyligne confirmée.
    mode_trace_libre : bool
        Indicateur pour le mode de tracé libre, par défaut False.
    points_trace_libre : list of QgsPoint
        Liste de points tracés en mode libre.
    fenetre_profil : FenetreProfilElevation or None
        Fenêtre contenant le graphique de profil d'altitude.
    simplification_activee : bool
        Indicateur si la simplification est activée, par défaut False.
    tolerance_simplification : float
        Tolérance utilisée pour la simplification du tracé, par défaut 2.0.
    mode : int
        Mode de tracé indiquant la stratégie, par défaut 1 (automatique).
    distance_seuil : float
        Distance seuil utilisée pour les calculs, par défaut 10 mètres.
    dernier_point_deplacement : QgsPoint or None
        Dernier point ayant servi à un calcul lié aux déplacements.

    Methods
    -------
    activate()
        Active l'outil en installant le filtre d'événement.
    deactivate()
        Désactive l'outil en supprimant le filtre d'événement.
    eventFilter(obj, event)
        Gère les événements filtrés pour les actions clavier.
    keyPressEvent(event)
        Gère les touches du clavier pour les actions spécifiques.
    on_raster_loaded(tableau_raster, gt, inv_gt, raster_lignes, raster_colonnes)
        Callback exécuté lorsque le chargement du raster est terminé.
    set_points_bas(active)
        Active ou désactive le mode Points Bas.
    obtenir_elevation_aux_points_multiples(x_array, y_array)
        Obtient les élévations du raster aux coordonnées données.
    definir_couche_vectorielle(couche_vectorielle)
        Définit la couche vectorielle où enregistrer les polylignes tracées.
    confirmer_polyligne()
        Confirme la polyligne actuelle et l'ajoute à la couche vectorielle.
    definir_fenetre_profil(fenetre)
        Assigne la fenêtre du profil d'élévation.
    definir_mode(mode, distance_seuil)
        Définit le mode de fonctionnement de l'outil et la distance seuil.
    definir_simplification(activee)
        Active ou désactive la simplification du tracé.
    mettre_a_jour_bande_dynamique()
        Met à jour la bande élastique dynamique en tenant compte de la simplification.
    definir_mode_trace_libre(tracelibre)
        Active ou désactive le mode de tracé libre.
    lisser_chemin(points, intensite)
        Applique un lissage aux points du chemin, selon une intensité.
    undo_last_action()
        Annule la dernière action réalisée.
    remove_last_point()
        Retire le dernier point ajouté à la polyligne.
    canvasPressEvent(event)
        Gère les événements de clic de souris sur le canevas.
    canvasMoveEvent(event)
        Gère les événements de déplacement de la souris sur le canevas.
    keyPressEvent(event)
        Gère les actions lorsque des touches clavier sont pressées.
    mettre_a_jour_profil(x_coords, y_coords, distances, elevations, index_marqueur)
        Met à jour le graphique du profil d'élévation en 3D basé sur les données fournies.
    obtenir_elevation_au_point(point)
        Obtient l'élévation du raster au point donné.
    select_next_pixel_points_hauts(courant, candidats_voisins, elevation_courante, arrivee_px, resoudre_egalite)
        Sélectionne le prochain pixel en favorisant les points hauts.
    calculer_chemin_extreme(point_depart, point_arrivee)
        Calcule le chemin de plus haute ou plus basse altitude entre deux points.
    resoudre_egalite(candidats, arrivee_px)
        Départage les candidats en cas d'égalité.
    reinitialiser()
        Réinitialise l'outil pour un nouveau tracé.
    simplifier_geometrie(geometrie)
        Simplifie la géométrie tout en conservant certains points critiques.
    douglas_peucker_avec_critiques(points, tol, points_critiques)
        Simplifie une polyligne en conservant des points critiques.
    distance_perpendiculaire(point, debut, fin)
        Calcule la distance perpendiculaire du point à la ligne donnée.
    distance_euclidienne(p1, p2)
        Calcule la distance euclidienne entre deux points.
    obtenir_elevation_aux_points(x_array, y_array)
        Obtient les élévations du raster aux points spécifiés.
    mettre_a_jour_profil(geometrie)
        Met à jour le profil d'élévation avec le segment dynamique.
    """

    def __init__(self, canvas, couche_raster):
        """
        Initialise l'outil de tracé de crête.

        Parameters
        ----------
        canvas : QgsMapCanvas
            Le canevas de la carte utilisé comme contexte pour le tracé.
        couche_raster : QgsRasterLayer
            La couche raster contenant le MNT pour la référence d'altitude.
        """

        super().__init__(canvas, couche_raster)
        self.canvas = canvas
        self.couche_raster = couche_raster
        self.id_counter = 1  # Compteur pour l'ID des polylignes
        self.data_loaded = False
        self.points_bas_active = False
        self.select_next_pixel_func = self.select_next_pixel_points_hauts
        self.undo_manager = UndoManager()
        self.warned_crs_mismatch = False

        self.crs_canvas = self.canvas.mapSettings().destinationCrs()
        self.crs_raster = self.couche_raster.crs()
        self.transformation_vers_raster = QgsCoordinateTransform(self.crs_canvas, self.crs_raster, QgsProject.instance())
        self.transformation_depuis_raster = QgsCoordinateTransform(self.crs_raster, self.crs_canvas, QgsProject.instance())

        self.liste_points = []
        self.chemin_dynamique = None
        self.polyligne_confirmee = None
        self.mode_trace_libre = False
        self.points_trace_libre = []
        self.fenetre_profil = None
        self.simplification_activee = False
        self.tolerance_simplification = 2.0
        self.mode = 1  # Mode par défaut
        self.distance_seuil = 10
        self.dernier_point_deplacement = None

        self.bande_dynamique = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_dynamique.setColor(QColor(255, 255, 0))
        self.bande_dynamique.setWidth(2)
        self.bande_dynamique.setLineStyle(Qt.DashLine)

        self.bande_confirmee = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_confirmee.setColor(QColor(0, 0, 255))
        self.bande_confirmee.setWidth(3)

        self.bande_trace_libre = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_trace_libre.setColor(QColor(0, 255, 0))
        self.bande_trace_libre.setWidth(3)

        self.raster_loading_thread = RasterLoadingThread(self.couche_raster)
        self.raster_loading_thread.raster_loaded.connect(self.on_raster_loaded)
        self.raster_loading_thread.start()

    mode_trace_libre_changed = pyqtSignal(bool)

    def activate(self):
        """
        Active l'outil de tracé.

        Met le focus sur le canevas de la carte et installe un filtre d'événement
        pour détecter les interactions clavier.
        """
        super().activate()
        self.canvas.setFocus()
        self.canvas.installEventFilter(self)

    def deactivate(self):
        """
        Désactive l'outil de tracé.

        Supprime le filtre d'événement du canevas pour arrêter la détection
        des interactions clavier.
        """
        self.canvas.removeEventFilter(self)
        super().deactivate()

    def eventFilter(self, obj, event):
        """
        Filtre les événements du canevas pour déclencher des actions basées sur les touches clavier.

        Permet d'activer/désactiver le mode tracé libre, confirmer les polylignes
        et annuler la dernière action à travers des raccourcis clavier.

        Parameters
        ----------
        obj : QObject
            Objet qui génère l'événement.
        event : QEvent
            Événement à filtrer.

        Returns
        -------
        bool
            True si l'événement est traité par le filtre, sinon False.
        """

        if obj == self.canvas and event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_S:
                self.definir_mode_trace_libre(not self.mode_trace_libre)
                return True
            elif key == Qt.Key_C:
                self.confirmer_polyligne()
                return True
            elif key == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
                self.undo_last_action()
                return True
        return False

    def keyPressEvent(self, event):
        """
        Gère les événements de pression de touche pour le tracé libre.

        Active/désactive le mode tracé libre si la lettre 'S' est pressée.

        Parameters
        ----------
        event : QKeyEvent
            Événement de pression de touche.
        """

        if event.key() == Qt.Key_S:
            self.definir_mode_trace_libre(not self.mode_trace_libre)
        else:
            super().keyPressEvent(event)

    def on_raster_loaded(self, tableau_raster, gt, inv_gt, raster_lignes, raster_colonnes):
        """
        Callback après le chargement du raster.

        Configure les données de raster et ferme l'écran de démarrage.

        Parameters
        ----------
        tableau_raster : np.ndarray
            Tableau des données raster chargées.
        gt : tuple
            Géotransformation du raster.
        inv_gt : tuple
            Inverse de la géotransformation du raster.
        raster_lignes : int
            Nombre de lignes dans le raster.
        raster_colonnes : int
            Nombre de colonnes dans le raster.
        """
        self.tableau_raster = tableau_raster
        self.gt = gt
        self.inv_gt = inv_gt
        self.raster_lignes = raster_lignes
        self.raster_colonnes = raster_colonnes
        self.data_loaded = True

        self.splash_screen_load.close()

    def set_points_bas(self, active):
        """
        Active ou désactive le mode Points Bas.

        Change la fonction de sélection de pixel en fonction du mode choisi.

        Parameters
        ----------
        active : bool
            True pour activer le mode Points Bas, False pour le désactiver.
        """
        self.points_bas_active = active
        if self.points_bas_active:
            self.select_next_pixel_func = select_next_pixel_points_bas
        else:
            self.select_next_pixel_func = self.select_next_pixel_points_hauts


    def definir_couche_vectorielle(self, couche_vectorielle):
        """
        Définit la couche vectorielle où enregistrer les polylignes tracées.

        Parameters
        ----------
        couche_vectorielle : QgsVectorLayer
            La couche vectorielle pour stocker les tracés.
        """
        self.couche_vectorielle = couche_vectorielle

    def confirmer_polyligne(self):
        """
        Confirme la polyligne actuelle et l'ajoute à la couche vectorielle.

        Convertit la polyligne en 3D si la simplification est activée,
        et enregistre ses attributs dans la couche vectorielle.
        """
        if self.polyligne_confirmee is not None and self.couche_vectorielle is not None:
            self.polyligne_originale = QgsGeometry.fromPolyline(self.liste_points)

            if self.simplification_activee:
                simplified_geom = self.polyligne_confirmee

                densified_simplified_geom = simplified_geom.densifyByDistance(
                    1)

                simplified_points = densified_simplified_geom.asPolyline()
                simplified_cumulative = [0]
                for i in range(1, len(simplified_points)):
                    dist = simplified_points[i - 1].distance(simplified_points[i])
                    simplified_cumulative.append(simplified_cumulative[-1] + dist)
                total_simplified_length = simplified_cumulative[-1]

                original_points = self.polyligne_originale.asPolyline()
                original_cumulative = [0]
                for i in range(1, len(original_points)):
                    dist = original_points[i - 1].distance(original_points[i])
                    original_cumulative.append(original_cumulative[-1] + dist)
                total_original_length = original_cumulative[-1]

                points_avec_z = []

                for i, point in enumerate(simplified_points):
                    prop = simplified_cumulative[i] / total_simplified_length
                    original_dist = prop * total_original_length
                    for j in range(1, len(original_cumulative)):
                        if original_cumulative[j] >= original_dist:
                            prev_dist = original_cumulative[j - 1]
                            next_dist = original_cumulative[j]
                            t = (original_dist - prev_dist) / (next_dist - prev_dist) if next_dist != prev_dist else 0
                            # Interpoler la valeur Z sur la polyligne originale
                            z_prev = self.obtenir_elevation_au_point(original_points[j - 1])
                            z_next = self.obtenir_elevation_au_point(original_points[j])
                            z = z_prev + t * (z_next - z_prev) if z_next is not None and z_prev is not None else 0
                            break
                    else:
                        z = self.obtenir_elevation_au_point(original_points[-1]) or 0
                    point_z = QgsPoint(point.x(), point.y(), z)
                    points_avec_z.append(point_z)

                polyligne_z = QgsGeometry.fromPolyline(points_avec_z)
            else:
                points_avec_z = []
                for point in self.liste_points:
                    z = self.obtenir_elevation_au_point(point)
                    if z is not None:
                        point_z = QgsPoint(point.x(), point.y(), z)
                    else:
                        point_z = QgsPoint(point.x(), point.y(), 0)
                    points_avec_z.append(point_z)
                polyligne_z = QgsGeometry.fromPolyline(points_avec_z)

            entite = QgsFeature()
            entite.setGeometry(polyligne_z)

            attributs = []
            champs_presentes = [field.name() for field in self.couche_vectorielle.fields()]
            if 'OBJECTID' in champs_presentes:
                attributs.append(self.id_counter)
            if 'Denomination' in champs_presentes:
                nom, ok = QInputDialog.getText(None, "Entrer un nom", "Dénomination de la polyligne :")
                if ok and nom:
                    attributs.append(nom)
                else:
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
            self.reinitialiser()
        else:
            QMessageBox.warning(None, "Avertissement", "Aucune polyligne confirmée à enregistrer.")

    def definir_fenetre_profil(self, fenetre):
        """
        Assigne la fenêtre du profil d'élévation à l'outil.

        Parameters
        ----------
        fenetre : FenetreProfilElevation
            Fenêtre pour afficher le profil d'élévation.
        """
        self.fenetre_profil = fenetre
        if self.fenetre_profil is not None:
            self.fenetre_profil.definir_outil(self)

    def definir_mode(self, mode, distance_seuil=None):
        """
        Définit le mode de fonctionnement de l'outil et réinitialise le point de mouvement si nécessaire.

        Parameters
        ----------
        mode : int
            Mode opérationnel de l'outil (par exemple, automatique ou manuel).
        distance_seuil : float, optional
            Distance seuil utilisée pour les calculs, par défaut None.
        """
        self.mode = mode
        if distance_seuil is not None:
            self.distance_seuil = distance_seuil
        self.dernier_point_deplacement = None  # Réinitialiser le dernier point de mouvement

    def definir_simplification(self, activee):
        """
        Active ou désactive la simplification du tracé.

        Parameters
        ----------
        activee : bool
            True pour activer la simplification, False pour la désactiver.
        """
        self.simplification_activee = activee
        self.mettre_a_jour_bande_dynamique()

    def mettre_a_jour_bande_dynamique(self):
        """
        Met à jour la bande élastique dynamique et applique la simplification si activée.
        """
        if self.chemin_dynamique:
            if self.simplification_activee:
                geometrie_simplifiee = self.simplifier_geometrie(self.chemin_dynamique)
                self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
                self.bande_dynamique.addGeometry(geometrie_simplifiee, None)
            else:
                self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
                self.bande_dynamique.addGeometry(self.chemin_dynamique, None)

    def definir_mode_trace_libre(self, tracelibre):
        """
        Active ou désactive le mode de tracé libre.

        Parameters
        ----------
        tracelibre : bool
            True pour activer le mode tracé libre, False pour le désactiver.

        Notes
        -----
        Lorsque le mode tracé libre est activé, ajoute les points tracés librement à la liste
        principale à la sortie du mode.
        """

        if tracelibre:
            self.mode_trace_libre = True
            self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
            if self.liste_points:
                point_depart = self.liste_points[-1]
                self.points_trace_libre = [point_depart]
                self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
                self.bande_trace_libre.addPoint(QgsPointXY(point_depart))  # Conversion en QgsPointXY
            else:
                self.points_trace_libre = []
        else:
            self.mode_trace_libre = False
            self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
            if len(self.points_trace_libre) >= 2:
                nouveaux_points = self.points_trace_libre[1:]
                nouveaux_points_qgspoint = []
                for p in nouveaux_points:
                    elevation = self.obtenir_elevation_au_point(p)
                    if elevation is not None:
                        point_z = QgsPoint(p.x(), p.y(), elevation)
                    else:
                        point_z = QgsPoint(p.x(), p.y(), 0)
                    nouveaux_points_qgspoint.append(point_z)

                action = AddPointsAction(self, nouveaux_points_qgspoint)
                self.undo_manager.add_action(action)

                self.liste_points.extend(nouveaux_points_qgspoint)
                self.polyligne_confirmee = QgsGeometry.fromPolyline(self.liste_points)
                self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                self.bande_confirmee.addGeometry(self.polyligne_confirmee, None)
                self.points_trace_libre = []

    def undo_last_action(self):
        """
        Annule la dernière action enregistrée.

        Notes
        -----
        Si aucune action n'est disponible pour l'annulation, informe l'utilisateur.
        """
        if not self.undo_manager.can_undo():
            QMessageBox.information(None, "Information", "Aucune action à annuler.")
        else:
            self.undo_manager.undo()

    def remove_last_point(self):
        """
        Supprime le dernier point ajouté à la liste de la polyligne.

        Notes
        -----
        Met à jour la polyligne confirmée et réinitialise le chemin dynamique si nécessaire.
        Informe l'utilisateur si aucun point n'est disponible pour la suppression.
        """
        if self.liste_points:
            self.liste_points.pop()

            if self.liste_points:
                self.polyligne_confirmee = QgsGeometry.fromPolyline(self.liste_points)
                self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                self.bande_confirmee.addGeometry(self.polyligne_confirmee, None)
            else:
                self.polyligne_confirmee = None
                self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
            self.chemin_dynamique = None
            self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
        else:
            QMessageBox.information(None, "Information", "Aucun point à annuler.")

    def canvasPressEvent(self, event):
        """
        Gère les événements de clic de souris sur le canevas.

        Ajoute des points à la liste de la polyligne et gère le mode tracé libre.

        Parameters
        ----------
        event : QMouseEvent
            Événement du clic de la souris.
        """

        point_carte_xy = self.toMapCoordinates(event.pos())
        point_carte = QgsPoint(point_carte_xy.x(), point_carte_xy.y())
        elevation = self.obtenir_elevation_au_point(point_carte)
        if elevation is not None:
            point_carte.setZ(elevation)
        else:
            point_carte.setZ(0)

        if self.mode_trace_libre:
            # Mode tracé libre
            self.points_trace_libre.append(point_carte)
            self.bande_trace_libre.addPoint(QgsPointXY(point_carte))
            # Créer une action d'annulation pour ce point
            action = AddPointsAction(self, [point_carte], mode='trace_libre')
            self.undo_manager.add_action(action)
        else:
            if not self.liste_points:
                # Premier clic : ajouter le point de départ
                self.liste_points.append(point_carte)
                # Créer une action d'annulation pour ce point
                action = AddPointsAction(self, [point_carte])
                self.undo_manager.add_action(action)
            else:
                if self.chemin_dynamique:
                    # Utiliser la géométrie simplifiée si la simplification est activée
                    if self.simplification_activee:
                        geometrie_a_utiliser = self.simplifier_geometrie(self.chemin_dynamique)
                    else:
                        geometrie_a_utiliser = self.chemin_dynamique

                    # Extraire les nouveaux points (en excluant le premier point)
                    nouveaux_points = geometrie_a_utiliser.asPolyline()[1:]

                    # Convertir les nouveaux points en objets QgsPoint avec Z
                    converted_points = []
                    for p in nouveaux_points:
                        elevation = self.obtenir_elevation_au_point(p)
                        if elevation is not None:
                            p_z = QgsPoint(p.x(), p.y(), elevation)
                        else:
                            p_z = QgsPoint(p.x(), p.y(), 0)
                        converted_points.append(p_z)

                    # Créer une action d'annulation pour ces points
                    action = AddPointsAction(self, converted_points)
                    self.undo_manager.add_action(action)

                    # Ajouter les points à la liste
                    self.liste_points.extend(converted_points)
                    # Mettre à jour la polyligne confirmée
                    self.polyligne_confirmee = QgsGeometry.fromPolyline(self.liste_points)
                    self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                    self.bande_confirmee.addGeometry(self.polyligne_confirmee, None)
                    self.chemin_dynamique = None
                    self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)

    def canvasMoveEvent(self, event):
        """
        Gestion des mouvements de la souris sur le canevas.

        Met à jour le tracé libre ou calcule le chemin de plus haute altitude
        en fonction du mode activé.

        Parameters
        ----------
        event : QMouseEvent
            Événement de déplacement de la souris.
        """
        if not self.data_loaded:
            return

        if self.mode_trace_libre:
            point_actuel_xy = self.toMapCoordinates(event.pos())
            point_actuel = QgsPoint(point_actuel_xy.x(), point_actuel_xy.y())
            elevation = self.obtenir_elevation_au_point(point_actuel)
            if elevation is not None:
                point_actuel.setZ(elevation)
            else:
                point_actuel.setZ(0)
            if self.points_trace_libre:
                self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
                for point in self.points_trace_libre:
                    self.bande_trace_libre.addPoint(QgsPointXY(point))
                self.bande_trace_libre.addPoint(QgsPointXY(point_actuel))

        else:
            if self.liste_points:
                point_actuel_xy = self.toMapCoordinates(event.pos())
                point_actuel = QgsPoint(point_actuel_xy.x(), point_actuel_xy.y())
                elevation = self.obtenir_elevation_au_point(point_actuel)
                if elevation is not None:
                    point_actuel.setZ(elevation)
                else:
                    point_actuel.setZ(0)
                if self.mode == 1:
                    if self.dernier_point_deplacement is None and self.liste_points:
                        self.dernier_point_deplacement = self.liste_points[-1]
                    if self.dernier_point_deplacement:  # Ajoutez une vérification ici
                        distance = self.dernier_point_deplacement.distance(point_actuel)
                        if distance >= self.distance_seuil:
                            geometrie_chemin = self.calculer_chemin_extreme(self.liste_points[-1], point_actuel)
                            if geometrie_chemin:
                                # Appliquer la simplification si activée
                                if self.simplification_activee:
                                    geometrie_simplifiee = self.simplifier_geometrie(geometrie_chemin)
                                    self.chemin_dynamique = geometrie_simplifiee
                                else:
                                    self.chemin_dynamique = geometrie_chemin
                                self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
                                self.bande_dynamique.addGeometry(self.chemin_dynamique, None)
                                if self.fenetre_profil:
                                    self.mettre_a_jour_profil_segment(self.chemin_dynamique)
                                self.dernier_point_deplacement = point_actuel
                    else:
                        pass
                else:
                    pass

    def mettre_a_jour_profil(self, x_coords, y_coords, distances, elevations, index_marqueur):
        """
        Met à jour le graphique 3D du profil d'élévation.

        Affiche les données d'élévation et ajuste les limites basées sur les coordonnées fournies.

        Parameters
        ----------
        x_coords : np.ndarray
            Coordonnées en x des points du tracé.
        y_coords : np.ndarray
            Coordonnées en y des points du tracé.
        distances : np.ndarray
            Distances cumulées le long du tracé.
        elevations : np.ndarray
            Élévations des points le long du tracé.
        index_marqueur : int
            Index du marqueur à mettre en évidence, s'il y a lieu.
        """
        self.ax.clear()
        buffer = 50
        xmin = min(x_coords) - buffer
        xmax = max(x_coords) + buffer
        ymin = min(y_coords) - buffer
        ymax = max(y_coords) + buffer

        num_points = 100
        X = np.linspace(xmin, xmax, num_points)
        Y = np.linspace(ymin, ymax, num_points)
        X_grid, Y_grid = np.meshgrid(X, Y)

        Z_grid = self.outil.obtenir_elevation_aux_points_multiples(X_grid, Y_grid)


        self.ax.plot_surface(X_grid, Y_grid, Z_grid, edgecolor='royalblue', lw=0.5,
                             rstride=10, cstride=10, alpha=0.6, cmap='terrain')

        zmin = np.nanmin(Z_grid)
        zmax = np.nanmax(Z_grid)
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='z', offset=zmin, cmap='terrain')
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='x', offset=xmin, cmap='terrain')
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='y', offset=ymax, cmap='terrain')

        self.ax.plot(
            x_coords,
            y_coords,
            elevations,
            color='black',
            label='Parcours'
        )

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
        """
        Obtient l'élévation du raster au point donné.

        Parameters
        ----------
        point : QgsPoint
            Point pour lequel obtenir l'élévation.

        Returns
        -------
        float or None
            Élévation au point donné en unités raster, ou None si en dehors des limites.
        """
        try :
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
        except TypeError as e:
            if "unexpected type 'QgsPoint'" in str(e):
                afficher_message_epsg()
                self.reinitialiser()
            return None

    def select_next_pixel_points_hauts(self, courant, candidats_voisins, elevation_courante, arrivee_px,
                                       resoudre_egalite):
        """
        Sélectionne le prochain pixel en suivant les points hauts parmi les voisins.

        Parameters
        ----------
        courant : tuple
            Pixel courant avec ses coordonnées (x, y).
        candidats_voisins : list of dict
            Liste des voisins candidats avec leurs informations.
        elevation_courante : float
            Élévation du pixel courant.
        arrivee_px : tuple
            Coordonnées du pixel d'arrivée.
        resoudre_egalite : function
            Fonction pour départager les voisins en cas d'égalité.

        Returns
        -------
        tuple
            Coordonnées du prochain pixel choisi.
        """

        voisins_plus_hauts = [n for n in candidats_voisins if n['elevation'] > elevation_courante]

        if voisins_plus_hauts:
            # Sélectionner le voisin avec l'élévation la plus haute
            elevation_max = max(n['elevation'] for n in voisins_plus_hauts)
            voisins_maximums = [n for n in voisins_plus_hauts if n['elevation'] == elevation_max]
            prochain_px = resoudre_egalite(voisins_maximums, arrivee_px)
        else:
            # Si aucun voisin plus haut, chercher les voisins à élévation égale
            voisins_egaux = [n for n in candidats_voisins if n['elevation'] == elevation_courante]
            if voisins_egaux:
                prochain_px = resoudre_egalite(voisins_egaux, arrivee_px)
            else:
                # Sinon, monter vers le voisin le plus haut possible
                elevation_max = max(n['elevation'] for n in candidats_voisins)
                voisins_maximums = [n for n in candidats_voisins if n['elevation'] == elevation_max]
                prochain_px = resoudre_egalite(voisins_maximums, arrivee_px)

        return prochain_px

    def calculer_chemin_extreme(self, point_depart, point_arrivee):
        """
        Calcule le chemin de plus haute ou le plus bas altitude entre deux points.

        Parameters
        ----------
        point_depart : QgsPoint
            Point de départ du chemin.
        point_arrivee : QgsPoint
            Point d'arrivée du chemin.

        Returns
        -------
        QgsGeometry or None
            Géométrie du chemin en 3D si calculé avec succès, ou None si échec ou en dehors des limites.
        """
        if not self.data_loaded:
            return None


        if self.crs_raster != self.crs_canvas:
            point_depart = self.transformation_vers_raster.transform(point_depart)
            point_arrivee = self.transformation_vers_raster.transform(point_arrivee)

        depart_px = gdal.ApplyGeoTransform(self.inv_gt, point_depart.x(), point_depart.y())
        arrivee_px = gdal.ApplyGeoTransform(self.inv_gt, point_arrivee.x(), point_arrivee.y())
        depart_px = (int(round(depart_px[0])), int(round(depart_px[1])))
        arrivee_px = (int(round(arrivee_px[0])), int(round(arrivee_px[1])))

        if not (0 <= depart_px[0] < self.raster_colonnes and 0 <= depart_px[1] < self.raster_lignes):
            return None
        if not (0 <= arrivee_px[0] < self.raster_colonnes and 0 <= arrivee_px[1] < self.raster_lignes):
            return None

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
                # Si aucun voisin dans la direction générale, considérer tous les voisins
                voisins_dans_direction = [
                    (nx, ny, difference_angle(np.arctan2(ny - cy, nx - cx), angle_vers_fin))
                    for nx, ny in voisins
                ]

            elevation_courante = self.tableau_raster[cy, cx]

            # Créer la liste des candidats voisins
            candidats_voisins = []
            for nx, ny, difference_angle_valeur in voisins_dans_direction:
                elevation_voisin = self.tableau_raster[ny, nx]
                candidats_voisins.append({
                    'position': (nx, ny),
                    'elevation': elevation_voisin,
                    'difference_angle': difference_angle_valeur
                })

            # Sélectionner le prochain pixel en utilisant la fonction appropriée
            prochain_px = self.select_next_pixel_func(
                pixel_courant,
                candidats_voisins,
                elevation_courante,
                arrivee_px,
                self.resoudre_egalite  # Passer la méthode resoudre_egalite
            )

            if prochain_px == pixel_courant or prochain_px in pixels_chemin:
                break  # Éviter les boucles infinies

            pixels_chemin.append(prochain_px)
            pixel_courant = prochain_px

        # Conversion des pixels en coordonnées spatiales
        liste_points = []
        for px, py in pixels_chemin:
            x, y = gdal.ApplyGeoTransform(self.gt, px + 0.5, py + 0.5)
            point = QgsPointXY(x, y)
            if self.crs_raster != self.crs_canvas:
                point = self.transformation_depuis_raster.transform(point)
            liste_points.append(point)

        # Créer la géométrie de la polyligne
        geometrie_chemin = QgsGeometry.fromPolylineXY(liste_points)

        if self.simplification_activee:
            geometrie_chemin = geometrie_chemin.simplify(self.tolerance_simplification)

        return geometrie_chemin

    def resoudre_egalite(self, candidats, arrivee_px):
        """
        Départage les candidats en cas d'égalité de choix.

        Parameters
        ----------
        candidats : list of dict
            Liste des candidats avec leurs coordonnées.
        arrivee_px : tuple
            Coordonnées du pixel d'arrivée.

        Returns
        -------
        tuple
            Coordonnées du meilleur candidat choisi.
        """

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
        """
        Réinitialise l'outil pour un nouveau tracé.

        Efface les points, bandes élastiques, et réinitialise le profil d'élévation.
        """

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
        """
        Simplifie la géométrie en préservant les points critiques d'altitude maximale.

        Parameters
        ----------
        geometrie : QgsGeometry
            Géométrie à simplifier.

        Returns
        -------
        QgsGeometry
            Géométrie simplifiée conservant les points critiques.
        """

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
        """
        Simplifie une polyligne en conservant des points critiques.

        Parameters
        ----------
        points : list of QgsPoint
            Points de la polyligne à simplifier.
        tol : float
            Tolérance pour la simplification.
        points_critiques : list of QgsPoint
            Points critiques à conserver.

        Returns
        -------
        list of QgsPoint
            Points de la polyligne simplifiée.
        """

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
        """
        Calcule la distance perpendiculaire du point à la ligne début-fin.

        Parameters
        ----------
        point : QgsPoint
            Point pour lequel calculer la distance.
        debut : QgsPoint
            Début de la ligne.
        fin : QgsPoint
            Fin de la ligne.

        Returns
        -------
        float
            Distance perpendiculaire entre le point et la ligne.
        """

        if debut == fin:
            return self.distance_euclidienne(point, debut)
        else:
            num = abs((fin.y() - debut.y()) * point.x() - (fin.x() - debut.x()) * point.y() +
                      fin.x() * debut.y() - fin.y() * debut.x())
            den = ((fin.y() - debut.y()) ** 2 + (fin.x() - debut.x()) ** 2) ** 0.5
            return num / den

    def distance_euclidienne(self, p1, p2):
        """
        Calcule la distance euclidienne entre deux points.

        Parameters
        ----------
        p1 : QgsPoint
            Premier point.
        p2 : QgsPoint
            Deuxième point.

        Returns
        -------
        float
            Distance euclidienne entre les deux points.
        """

        return ((p1.x() - p2.x()) ** 2 + (p1.y() - p2.y()) ** 2) ** 0.5

    def mettre_a_jour_profil_segment(self, geometrie):
        """
        Met à jour le profil d'élévation avec le segment dynamique.

        Parameters
        ----------
        geometrie : QgsGeometry
            Géométrie du segment dynamique du profil d'élévation.
        """

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
