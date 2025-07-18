# tools/outil_rupture_pente.py

import math
import os
import sys

from osgeo import gdal
import numpy as np

from qgis.PyQt.QtCore import Qt, QObject, QPoint
from qgis.PyQt.QtGui import QColor
from qgis._core import QgsFeature, QgsPoint, QgsLineString
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsWkbTypes,
    QgsGeometry,
    QgsPointXY,
)
from qgis.core import QgsMessageLog, Qgis



from PyQt5.QtCore import pyqtSignal
from qgis.core import QgsCsException
from PyQt5 import QtCore
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QMenu, QToolButton, QInputDialog, QDockWidget, QWidget, QVBoxLayout, QComboBox, QApplication
from qgis.gui import QgsMapTool, QgsRubberBand

from .base_map_tool import BaseMapTool
from ..threads.calcul_pentes_thread import CalculPentesThread
from ..utils.raster_utils import generer_ombrage_invisible
from ..utils.undo_manager import UndoManager, AddPointsAction
from ..utils.error import afficher_message_epsg, afficher_changer_vers_mode_convexe


class OutilRupturePente(BaseMapTool):
    """
    Outil de dessin de rupture de pente (concave ou convexe) avec assistance dynamique sur MNT.

    Cette classe gère le traçage de lignes dynamisées selon les ruptures de pentes sur un Modèle Numérique de Terrain,
    et inclut des fonctionnalités pour simplifier et confirmer les polylignes.

    Attributes
    ----------
    canvas : QgsMapCanvas
        Le canevas de la carte.
    couche_raster : QgsRasterLayer
        La couche raster MNT utilisée.
    mode : str, optional
        Le mode de rupture de pente ('concave' ou 'convexe'), par défaut 'convexe'.
    simplification_activee : bool
        Indicateur de simplification du tracé, par défaut False.
    tolerance_simplification : float
        Tolérance utilisée pour la simplification, par défaut 2.0.
    calcul_termine : bool
        Indicateur que le calcul des pentes est terminé, par défaut False.
    undo_manager : UndoManager
        Gestionnaire des actions pour annulation.
    liste_points : list of QgsPoint
        Liste des points de la polyligne tracée.
    bande_dynamique : QgsRubberBand
        Bande élastique pour la ligne dynamique avec tracé.
    bande_confirmee : QgsRubberBand
        Bande élastique pour la polyligne confirmée.
    mode_trace_libre : bool
        Indicateur du mode tracé libre, par défaut False.
    points_trace_libre : list of QgsPoint
        Liste des points tracés en mode libre.
    bande_trace_libre : QgsRubberBand
        Bande élastique pour le tracé libre.

    Methods
    -------
    on_pentes_calculees(pentes_locales_degres)
        Appelé lorsque le calcul des pentes est terminé.
    activate()
        Active l'outil en installant le filtre d'événement.
    deactivate()
        Désactive l'outil en supprimant le filtre d'événement.
    eventFilter(obj, event)
        Contrôle les événements claviers pour certaines actions.
    undo_last_action()
        Annule la dernière action enregistrée.
    remove_last_point()
        Supprime le dernier point confirmé.
    definir_couche_vectorielle(couche_vectorielle)
        Assigne la couche vectorielle où stocker les polylignes.
    confirmer_polyligne()
        Confirme la polyligne actuelle et l'ajoute à la couche vectorielle.
    definir_simplification(activee)
        Active ou désactive la simplification du tracé.
    definir_mode_trace_libre(tracelibre)
        Active ou désactive le mode de tracé libre.
    charger_donnees_mnt()
        Charge les données du MNT en mémoire pour un accès rapide.
    charger_donnees_hillshade()
        Charge les données de l'ombrage en mémoire pour un accès rapide.
    definir_fenetre_profil(fenetre)
        Assigne la fenêtre du profil d'élévation.
    mettre_a_jour_bande_dynamique()
        Met à jour la bande élastique dynamique en appliquant ou non la simplification.
    simplifier_geometrie(geometrie)
        Simplifie la géométrie en préservant les points critiques.
    obtenir_pente_au_point(point)
        Obtient la pente locale au point donné.
    douglas_peucker_avec_critiques(points, tol, points_critiques)
        Simplifie une polyligne en conservant les points critiques.
    distance_perpendiculaire(point, debut, fin)
        Calcule la distance perpendiculaire du point à la ligne début-fin en 2D.
    mettre_a_jour_profil(geometrie)
        Met à jour le profil d'élévation avec le segment dynamique.
    distance_euclidienne(p1, p2)
        Calcule la distance euclidienne entre deux points en 2D.
    obtenir_elevation_au_point(point)
        Obtient l’élévation du raster au point donné.
    charger_donnees_raster()
        Charge les données raster en mémoire pour un accès rapide.
    calculer_chemin_rupture_pente(point_depart, point_arrivee)
        Calcule le chemin de rupture de pente entre deux points.
    reinitialiser()
        Réinitialise l'outil pour un nouveau tracé.
    charger_nouveau_mnt(couche_raster)
        Change le MNT actif pour l'analyse et configure les ressources nécessaires.
    nettoyer_ressources()
        Nettoyage des ressources et réinitialisation de l'outil.
    """

    def __init__(self, canvas, couche_raster, mode='convexe'):
        """
        Initialise l'outil de tracé de rupture de pente.

        Parameters
        ----------
        canvas : QgsMapCanvas
            Le canevas de la carte.
        couche_raster : QgsRasterLayer
            La couche raster MNT utilisée.
        mode : str, optional
            Le mode de rupture de pente ('concave' ou 'convexe'), par défaut 'convexe'.
        """

        super().__init__(canvas, couche_raster)
        self.canvas = canvas
        self.couche_raster = couche_raster
        self.mode = mode # 'concave' ou 'convexe'
        self.simplification_activee = False
        self.tolerance_simplification = 2.0
        self.calcul_termine = False
        self.undo_manager = UndoManager()
        self.crs_warning_displayed = False

        self.crs_canvas = self.canvas.mapSettings().destinationCrs()
        self.crs_raster = self.couche_raster.crs()
        self.transformation_vers_raster = QgsCoordinateTransform(self.crs_canvas,
                                                                 self.crs_raster,
                                                                 QgsProject.instance())
        self.transformation_depuis_raster = QgsCoordinateTransform(self.crs_raster,
                                                                   self.crs_canvas,
                                                                   QgsProject.instance())

        self.liste_points = [] # Liste pour stocker les points de la polyligne
        self.chemin_dynamique = None
        self.polyligne_confirmee = None

        self.bande_dynamique = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_dynamique.setColor(QColor(255, 255, 0))
        self.bande_dynamique.setWidth(2)
        self.bande_dynamique.setLineStyle(Qt.DashLine)

        self.bande_confirmee = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_confirmee.setColor(QColor(0, 0, 255))
        self.bande_confirmee.setWidth(3)

        self.mode_trace_libre = False
        self.points_trace_libre = []
        self.bande_trace_libre = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_trace_libre.setColor(QColor(0, 255, 0))  # Couleur verte pour le tracé libre
        self.bande_trace_libre.setWidth(3)

        self.charger_donnees_raster()

        self.calcul_pentes_thread = CalculPentesThread(self.tableau_raster, self.gt)
        self.calcul_pentes_thread.result_ready.connect(self.on_pentes_calculees)
        self.calcul_pentes_thread.start()

        self.couche_ombrage = generer_ombrage_invisible(self.couche_raster)
        if self.couche_ombrage is None:
            QMessageBox.critical(None, "Erreur", "Impossible de générer l'ombrage pour le MNT.")
            return

        # Charger les données de l'ombrage (pour les calculs de pentes)
        self.charger_donnees_hillshade()

    mode_trace_libre_changed = pyqtSignal(bool)

    def on_pentes_calculees(self, pentes_locales_degres):
        """
        Appelé lorsque le calcul des pentes est terminé.

        Parameters
        ----------
        pentes_locales_degres : np.ndarray
            Tableau des pentes calculées en degrés.
        """
        self.pentes_locales_degres = pentes_locales_degres
        self.calcul_termine = True

        self.splash_screen_load.close()

    def activate(self):
        """
        Active l'outil en installant le filtre d'événement.
        """
        super().activate()
        self.canvas.setFocus()
        self.canvas.installEventFilter(self)

    def deactivate(self):
        """
        Désactive l'outil en supprimant le filtre d'événement.
        """
        self.canvas.removeEventFilter(self)
        super().deactivate()

    def eventFilter(self, obj, event):
        """
        Contrôle les événements claviers pour certaines actions.

        Parameters
        ----------
        obj : QObject
            Objet qui génère l'événement.
        event : QEvent
            Événement pour lequel le filtrage est effectué.

        Returns
        -------
        bool
            True si l'événement est traité, False sinon.
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

    def undo_last_action(self):
        """
        Annule la dernière action enregistrée.
        """
        if not self.undo_manager.can_undo():
            QMessageBox.information(None, "Information", "Aucune action à annuler.")
        else:
            self.undo_manager.undo()

    def remove_last_point(self):
        """
        Supprime le dernier point confirmé.
        """
        if self.liste_points:
            self.liste_points.pop()
            # Mettre à jour la polyligne confirmée et les bandes élastiques
            if self.liste_points:
                self.polyligne_confirmee = QgsGeometry.fromPolylineXY(self.liste_points)
                self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                self.bande_confirmee.addGeometry(self.polyligne_confirmee, None)
            else:
                self.polyligne_confirmee = None
                self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
            # Réinitialiser le chemin dynamique
            self.chemin_dynamique = None
            self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
        else:
            QMessageBox.information(None, "Information", "Aucun point à annuler.")

    def definir_couche_vectorielle(self, couche_vectorielle):
        """
        Assigne la couche vectorielle où stocker les polylignes.

        Parameters
        ----------
        couche_vectorielle : QgsVectorLayer
            La couche vectorielle pour stocker les tracés.
        """
        self.couche_vectorielle = couche_vectorielle
        self.id_counter = self.couche_vectorielle.featureCount() + 1

    def confirmer_polyligne(self):
        """
        Confirme la polyligne actuelle et l'ajoute à la couche vectorielle.
        """
        if self.polyligne_confirmee is not None and self.couche_vectorielle is not None:
            if self.simplification_activee:
                geometrie_a_sauvegarder = self.simplifier_geometrie(self.polyligne_confirmee)
            else:
                geometrie_a_sauvegarder = self.polyligne_confirmee


            points_avec_z = []
            if geometrie_a_sauvegarder.isMultipart():
                parties = geometrie_a_sauvegarder.asMultiPolyline()
                for partie in parties:
                    for point in partie:
                        z = self.obtenir_elevation_au_point(point)
                        if z is not None:
                            point_z = QgsPoint(point.x(), point.y(), z)
                        else:
                            point_z = QgsPoint(point.x(), point.y(), 0)
                        points_avec_z.append(point_z)
            else:
                line = geometrie_a_sauvegarder.constGet()
                if isinstance(line, QgsLineString):
                    for i in range(line.numPoints()):
                        point = line.pointN(i)
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

    def definir_mode_trace_libre(self, tracelibre):
        """
        Active ou désactive le mode de tracé libre.

        Parameters
        ----------
        tracelibre : bool
            True pour activer le mode tracé libre, False pour le désactiver.
        """
        self.mode_trace_libre = tracelibre
        self.mode_trace_libre_changed.emit(tracelibre)
        if tracelibre:
            self.mode_trace_libre = True
            self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
            if self.liste_points:
                point_depart = self.liste_points[-1]
                self.points_trace_libre = [point_depart]
                self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
                self.bande_trace_libre.addPoint(QgsPointXY(point_depart))
            else:
                self.points_trace_libre = []
        else:
            self.mode_trace_libre = False
            self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
            if len(self.points_trace_libre) >= 2:
                nouveaux_points = self.points_trace_libre[1:]
                action = AddPointsAction(self, nouveaux_points)
                self.undo_manager.add_action(action)
                self.liste_points.extend(nouveaux_points)
                self.polyligne_confirmee = QgsGeometry.fromPolyline(self.liste_points)
                self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                self.bande_confirmee.addGeometry(self.polyligne_confirmee, None)
            self.points_trace_libre = []

    def charger_donnees_hillshade(self):
        """
        Charge les données de l'ombrage en mémoire pour un accès rapide.
        """
        source = self.couche_ombrage.dataProvider().dataSourceUri()
        self.hillshade_dataset = gdal.Open(source)

        if self.hillshade_dataset is None:
            return

        self.gt = self.hillshade_dataset.GetGeoTransform()
        self.inv_gt = gdal.InvGeoTransform(self.gt)

        if self.inv_gt is None:
            return

        bande_raster = self.hillshade_dataset.GetRasterBand(1)
        self.tableau_hillshade = bande_raster.ReadAsArray()

        if self.tableau_hillshade is None:
            return

        self.raster_lignes, self.raster_colonnes = self.tableau_hillshade.shape

    def definir_fenetre_profil(self, fenetre):
        """
        Assigne la fenêtre du profil d'élévation.

        Parameters
        ----------
        fenetre : QWidget
            La fenêtre du profil d'élévation à associer à l'outil.
        """
        self.fenetre_profil = fenetre
        if self.fenetre_profil is not None:
            self.fenetre_profil.definir_outil(self)

    def mettre_a_jour_bande_dynamique(self):
        """
        Met à jour la bande élastique dynamique en appliquant ou non la simplification.
        """
        if self.chemin_dynamique:
            if self.simplification_activee:
                geometrie_simplifiee = self.simplifier_geometrie(self.chemin_dynamique)
                self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
                self.bande_dynamique.addGeometry(geometrie_simplifiee, None)
            else:
                self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
                self.bande_dynamique.addGeometry(self.chemin_dynamique, None)

    def simplifier_geometrie(self, geometrie):
        """
        Simplifie la géométrie en préservant les points critiques.

        Parameters
        ----------
        geometrie : QgsGeometry
            Géométrie à simplifier.

        Returns
        -------
        QgsGeometry
            Géométrie simplifiée conservant les points critiques.
        """

        if geometrie.isMultipart():
            QMessageBox.warning(None, "Avertissement", "La géométrie est multipartie, ce n'est pas supporté.")
            return geometrie
        else:
            line = geometrie.constGet()
            if isinstance(line, QgsLineString):
                points = [line.pointN(i) for i in range(line.numPoints())]
            else:
                QMessageBox.warning(None, "Avertissement", "La géométrie n'est pas une ligne.")
                return geometrie

        if len(points) < 3:
            return geometrie

        elevations = [p.z() for p in points]
        if self.mode == 'concave':
            afficher_changer_vers_mode_convexe()
            elevation_minimale = min(elevations)
            points_critiques = [points[i] for i, elev in enumerate(elevations) if elev == elevation_minimale]
        else:
            elevation_maximale = max(elevations)
            points_critiques = [points[i] for i, elev in enumerate(elevations) if elev == elevation_maximale]

        points_simplifies = self.douglas_peucker_avec_critiques(points, self.tolerance_simplification, points_critiques)

        return QgsGeometry.fromPolyline(points_simplifies)

    def obtenir_pente_au_point(self, point):
        """
        Obtient la pente locale au point donné.

        Parameters
        ----------
        point : QgsPoint
            Point pour lequel obtenir la pente.

        Returns
        -------
        float or None
            Pente locale en degrés au point donné, ou None si non disponible.
        """

        if self.crs_raster != self.crs_canvas:
            point = self.transformation_vers_raster.transform(point)
        x = point.x()
        y = point.y()
        px, py = gdal.ApplyGeoTransform(self.inv_gt, x, y)
        px = int(px)
        py = int(py)
        if 0 <= px < self.raster_colonnes and 0 <= py < self.raster_lignes:
            pente = self.pentes_locales_degres[py, px]
            return float(pente)
        else:
            return None

    def douglas_peucker_avec_critiques(self, points, tol, points_critiques):
        """
        Simplifie une polyligne en conservant les points critiques.

        Parameters
        ----------
        points : list of QgsPoint
            Points de la polyligne à simplifier.
        tol : float
            Tolérance pour la simplification.
        points_critiques : list of QgsPoint
            Points critiques à conserver lors de la simplification.

        Returns
        -------
        list of QgsPoint
            Points de la polyligne simplifiée.
        """
        if len(points) < 3:
            return points

        debut = points[0]
        fin = points[-1]

        dist_max = 0.0
        index = 0

        for i in range(1, len(points) - 1):
            if points[i] in points_critiques:
                continue
            dist = self.distance_perpendiculaire(points[i], debut, fin)
            if dist > dist_max:
                dist_max = dist
                index = i

        if dist_max > tol:
            # Scinder la polyligne et simplifier récursivement
            left_points = points[:index + 1]
            right_points = points[index:]

            gauche = self.douglas_peucker_avec_critiques(left_points, tol, points_critiques)
            droite = self.douglas_peucker_avec_critiques(right_points, tol, points_critiques)

            # Supprimer le point dupliqué à la jonction
            simplified_points = gauche[:-1] + droite
        else:
            # Décider de conserver les points intermédiaires en fonction des points critiques
            points_segment = points[1:-1]
            if any(p in points_critiques for p in points_segment):
                simplified_points = points
            else:
                simplified_points = [debut, fin]

        for idx in range(len(simplified_points)):
            p = simplified_points[idx]
            if not isinstance(p, QgsPoint):
                z = p.z() if hasattr(p, 'z') else 0
                simplified_points[idx] = QgsPoint(p.x(), p.y(), z)

        return simplified_points

    def distance_perpendiculaire(self, point, debut, fin):
        """
        Calcule la distance perpendiculaire du point à la ligne début-fin en 2D.

        Parameters
        ----------
        point : QgsPoint
            Point pour lequel calculer la distance.
        debut : QgsPoint
            Début de la ligne de référence.
        fin : QgsPoint
            Fin de la ligne de référence.

        Returns
        -------
        float
            Distance perpendiculaire du point à la ligne de référence.
        """
        if debut == fin:
            return self.distance_euclidienne(point, debut)
        else:
            x0, y0 = point.x(), point.y()
            x1, y1 = debut.x(), debut.y()
            x2, y2 = fin.x(), fin.y()
            num = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
            den = ((y2 - y1) ** 2 + (x2 - x1) ** 2) ** 0.5
            return num / den

    def mettre_a_jour_profil(self, geometrie):
        """
        Met à jour le profil d'élévation avec le segment dynamique.

        Parameters
        ----------
        geometrie : QgsGeometry
            Géométrie du segment dynamique pour le profil d'élévation.
        """
        if geometrie is None:
            return

        geom = geometrie.constGet()
        if isinstance(geom, QgsLineString):
            if geom.is3D():
                points = [geom.pointN(i) for i in range(geom.numPoints())]
            else:
                # La géométrie est en 2D, obtenir les valeurs Z à partir du raster
                points = []
                for i in range(geom.numPoints()):
                    pt_xy = geom.pointN(i)
                    z = self.obtenir_elevation_au_point_unique(pt_xy)
                    if z is not None:
                        point = QgsPoint(pt_xy.x(), pt_xy.y(), z)
                    else:
                        point = QgsPoint(pt_xy.x(), pt_xy.y(), 0)
                    points.append(point)
        else:
            QMessageBox.warning(None, "Erreur", "La géométrie n'est pas une ligne.")
            return

        if not points:
            QMessageBox.warning(None, "Erreur", "Aucun point dans la géométrie.")
            return

        elevations = []
        coordonnees_x = []
        coordonnees_y = []
        distances = []
        distance_totale = 0
        point_precedent = None

        for point in points:
            coordonnees_x.append(point.x())
            coordonnees_y.append(point.y())
            elevation = point.z() if point.z() else self.obtenir_elevation_au_point_unique(point)
            elevations.append(elevation if elevation is not None else 0)

            if point_precedent is not None:
                segment = QgsGeometry.fromPolyline([point_precedent, point])
                distance = segment.length()
                distance_totale += distance
            else:
                distance = 0
            distances.append(distance_totale)
            point_precedent = point

        # Appeler la méthode dans fenetre_profil en passant les coordonnées et les élévations
        self.fenetre_profil.mettre_a_jour_profil(
            coordonnees_x,
            y_coords=coordonnees_y,
            elevations=elevations,
            longueur_segment=distance_totale
        )

    def distance_euclidienne(self, p1, p2):
        """
        Calcule la distance euclidienne entre deux points en 2D.

        Parameters
        ----------
        p1 : QgsPoint
            Premier point pour le calcul.
        p2 : QgsPoint
            Deuxième point pour le calcul.

        Returns
        -------
        float
            Distance euclidienne entre les deux points.
        """

        dx = p1.x() - p2.x()
        dy = p1.y() - p2.y()
        return (dx * dx + dy * dy) ** 0.5

    def obtenir_elevation_au_point(self, point):
        """
        Obtient l’élévation du raster au point donné.

        Parameters
        ----------
        point : QgsPoint
            Point pour lequel obtenir l'élévation.

        Returns
        -------
        float or None
            Élévation au point donné, ou None si en dehors des limites.
        """
        try:
            original_z = point.z()
            point_xy = QgsPointXY(point.x(), point.y())

            if self.crs_raster != self.crs_canvas:
                point_xy_transforme = self.transformation_vers_raster.transform(point_xy)
                point = QgsPoint(point_xy_transforme.x(), point_xy_transforme.y(), original_z)
            else:
                point = point

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
        except QgsCsException as e:
            if not self.crs_warning_displayed:
                QgsMessageLog.logMessage("Erreur de transformation des coordonnées. Le projet doit-être en epsg:2154",
                                         level=Qgis.Critical)
                afficher_message_epsg()
                self.crs_warning_displayed = True
            self.reinitialiser()
            return None

    def charger_donnees_raster(self):
        """
        Charge les données raster en mémoire pour un accès rapide.
        """
        source = self.couche_raster.dataProvider().dataSourceUri()
        self.dataset = gdal.Open(source)

        if self.dataset is None:
            return

        self.gt = self.dataset.GetGeoTransform()
        self.inv_gt = gdal.InvGeoTransform(self.gt)

        if self.inv_gt is None:
            return

        bande_raster = self.dataset.GetRasterBand(1)
        self.tableau_raster = bande_raster.ReadAsArray()

        if self.tableau_raster is None:
            return

        self.raster_lignes, self.raster_colonnes = self.tableau_raster.shape

    def definir_mode(self, mode):
        """
        Définit le mode de fonctionnement de l'outil.
        """
        self.mode = mode

    def canvasPressEvent(self, event):
        """
        Gère l'événement de pression de la souris sur le canevas.

        Cette méthode traite les clics de souris pour ajouter des points à la polyligne, gérer le mode tracé libre,
        et confirmer les segments dynamiques de rupture de pente. Utilise une gestion d'annulation pour les points ajoutés.

        Parameters
        ----------
        event : QMouseEvent
            Événement de presse de la souris contenant les informations de position.
        """
        if not self.calcul_termine:
            QMessageBox.information(None, "Calcul en cours", "Veuillez patienter, le calcul des pentes est en cours.")
            return

        point_xy = self.toMapCoordinates(event.pos())
        point_carte = QgsPoint(point_xy.x(), point_xy.y(), 0)

        if self.mode_trace_libre:
            # Mode tracé libre
            self.points_trace_libre.append(point_carte)
            self.bande_trace_libre.addPoint(QgsPointXY(point_carte))
            # Créer une action pour ce point
            action = AddPointsAction(self, point_carte, mode='trace_libre')
            self.undo_manager.add_action(action)
        else:
            if not self.liste_points:
                # Premier clic : ajouter le point de départ
                self.liste_points.append(point_carte)
                # Créer une action pour ce point
                action = AddPointsAction(self, point_carte)
                self.undo_manager.add_action(action)
            else:
                # Confirmer le segment dynamique
                if self.chemin_dynamique:
                    # Utiliser la géométrie simplifiée si la simplification est activée
                    if self.simplification_activee:
                        geometrie_a_utiliser = self.simplifier_geometrie(self.chemin_dynamique)
                    else:
                        geometrie_a_utiliser = self.chemin_dynamique

                    # Extraire les nouveaux points (en excluant le premier point)
                    nouveaux_points = geometrie_a_utiliser.asPolyline()[1:]

                    # Convertir les nouveaux points en QgsPoint avec Z
                    converted_points = []
                    for p in nouveaux_points:
                        if isinstance(p, QgsPoint):
                            converted_points.append(p)
                        else:
                            z_value = p.z() if hasattr(p, 'z') else 0
                            p_converted = QgsPoint(p.x(), p.y(), z_value)
                            converted_points.append(p_converted)

                    # Créer une action pour ces points
                    action = AddPointsAction(self, converted_points)
                    self.undo_manager.add_action(action)

                    # Ajouter les points à la liste
                    self.liste_points.extend(converted_points)
                    # Construire la polyligne confirmée
                    self.polyligne_confirmee = QgsGeometry.fromPolyline(self.liste_points)
                    self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                    self.bande_confirmee.addGeometry(self.polyligne_confirmee, None)
                    self.chemin_dynamique = None
                    self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)

    def canvasMoveEvent(self, event):
        """
        Gère l'événement de déplacement de la souris sur le canevas.

        Cette méthode met à jour le tracé dynamique et libre sur le canevas lorsque la souris est déplacée,
        et calcule le chemin de rupture de pente le plus optimal.

        Parameters
        ----------
        event : QMouseEvent
            Événement de déplacement de la souris contenant les informations de position.
        """
        if not self.calcul_termine:
            return

        if self.mode_trace_libre:
            # Mode tracé libre
            point_actuel = self.toMapCoordinates(event.pos())
            if self.points_trace_libre:
                self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
                for point in self.points_trace_libre:
                    self.bande_trace_libre.addPoint(QgsPointXY(point))
                self.bande_trace_libre.addPoint(QgsPointXY(point_actuel))
        else:
            if self.liste_points:
                point_xy = self.toMapCoordinates(event.pos())
                point_actuel = QgsPoint(point_xy.x(), point_xy.y(), 0)
                geometrie_chemin = self.calculer_chemin_rupture_pente(self.liste_points[-1], point_actuel)
                if geometrie_chemin:
                    self.chemin_dynamique = geometrie_chemin
                    self.mettre_a_jour_bande_dynamique()
                    # Ajouter cet appel pour mettre à jour le profil topo 3D
                    if self.fenetre_profil:
                        self.mettre_a_jour_profil(self.chemin_dynamique)

    def calculer_chemin_rupture_pente(self, point_depart, point_arrivee):
        """
        Calcule le chemin de rupture de pente entre deux points.

        Parameters
        ----------
        point_depart : QgsPoint
            Point de départ du chemin.
        point_arrivee : QgsPoint
            Point d'arrivée du chemin.

        Returns
        -------
        QgsGeometry or None
            Géométrie du chemin de rupture de pente en 3D, ou None si échec.
        """
        z_depart = point_depart.z()
        z_arrivee = point_arrivee.z()

        if self.crs_raster != self.crs_canvas:
            point_depart_xy = QgsPointXY(point_depart.x(), point_depart.y())
            point_arrivee_xy = QgsPointXY(point_arrivee.x(), point_arrivee.y())

            point_depart_xy_transforme = self.transformation_vers_raster.transform(point_depart_xy)
            point_arrivee_xy_transforme = self.transformation_vers_raster.transform(point_arrivee_xy)

            point_depart = QgsPoint(point_depart_xy_transforme.x(), point_depart_xy_transforme.y(), z_depart)
            point_arrivee = QgsPoint(point_arrivee_xy_transforme.x(), point_arrivee_xy_transforme.y(), z_arrivee)

        depart_px = gdal.ApplyGeoTransform(self.inv_gt, point_depart.x(), point_depart.y())
        arrivee_px = gdal.ApplyGeoTransform(self.inv_gt, point_arrivee.x(), point_arrivee.y())
        depart_px = (int(round(depart_px[0])), int(round(depart_px[1])))
        arrivee_px = (int(round(arrivee_px[0])), int(round(arrivee_px[1])))

        if not (0 <= depart_px[0] < self.raster_colonnes and 0 <= depart_px[1] < self.raster_lignes):
            return None
        if not (0 <= arrivee_px[0] < self.raster_colonnes and 0 <= arrivee_px[1] < self.raster_lignes):
            return None

        if self.mode == 'concave':
            afficher_changer_vers_mode_convexe()
            pentes_utilisees = -self.pentes_locales_degres
        else:
            pentes_utilisees = self.pentes_locales_degres

        pixels_chemin = [depart_px]
        pixel_courant = depart_px
        iterations_max = 10000
        iterations = 0

        while pixel_courant != arrivee_px and iterations < iterations_max:
            iterations += 1
            cx, cy = pixel_courant

            voisins = [(cx + dx, cy + dy) for dx in [-3, -2, -1, 0, 1, 2, 3] for dy in [-3, -2, -1, 0, 1, 2, 3]
                       if (dx != 0 or dy != 0) and
                       0 <= cx + dx < self.raster_colonnes and
                       0 <= cy + dy < self.raster_lignes]

            if not voisins:
                break

            dx_fin = arrivee_px[0] - cx
            dy_fin = arrivee_px[1] - cy
            angle_vers_fin = np.arctan2(dy_fin, dx_fin)

            def difference_angle(a1, a2):
                return abs((a1 - a2 + np.pi) % (2 * np.pi) - np.pi)

            voisins_dans_direction = []
            for nx, ny in voisins:
                ndx = nx - cx
                ndy = ny - cy
                angle_voisin = np.arctan2(ndy, ndx)
                difference = difference_angle(angle_voisin, angle_vers_fin)
                if difference <= np.pi / 2:  # 90 degrés
                    voisins_dans_direction.append((nx, ny, difference))

            pente_courante = pentes_utilisees[cy, cx]
            candidats_voisins = []

            for nx, ny, difference_angle_valeur in voisins_dans_direction:
                pente_voisin = pentes_utilisees[ny, nx]
                delta_pente = pente_voisin - pente_courante
                candidats_voisins.append({
                    'position': (nx, ny),
                    'pente': pente_voisin,
                    'delta_pente': delta_pente,
                    'difference_angle': difference_angle_valeur
                })

            candidats_triees = sorted(candidats_voisins, key=lambda n: (-n['delta_pente'], n['difference_angle']))

            def resoudre_egalite(candidats):
                distance_min = float('inf')
                meilleur_candidat = None
                for candidat in candidats:
                    nx, ny = candidat['position']
                    distance = np.hypot(arrivee_px[0] - nx, arrivee_px[1] - ny)
                    if distance < distance_min:
                        distance_min = distance
                        meilleur_candidat = candidat
                return meilleur_candidat

            if candidats_triees:
                meilleur_candidat = candidats_triees[0]
                delta_pente_best = meilleur_candidat['delta_pente']
                candidats_egalite = [n for n in candidats_triees if n['delta_pente'] == delta_pente_best]
                if len(candidats_egalite) > 1:
                    meilleur_candidat = resoudre_egalite(candidats_egalite)
                prochain_px = meilleur_candidat['position']
            else:
                break

            if prochain_px == pixel_courant or prochain_px in pixels_chemin:
                break

            pixels_chemin.append(prochain_px)
            pixel_courant = prochain_px

        liste_points = []
        for px, py in pixels_chemin:
            x, y = gdal.ApplyGeoTransform(self.gt, px + 0.5, py + 0.5)
            point = QgsPoint(x, y)
            # Obtenir l'élévation au point
            z = self.obtenir_elevation_au_point(point)
            if z is None:
                z = 0  # Valeur par défaut si l'élévation n'est pas disponible
            point.setZ(z)
            if self.crs_raster != self.crs_canvas:
                # Transformer les coordonnées X et Y en utilisant QgsPointXY
                point_xy = QgsPointXY(point.x(), point.y())
                point_xy_transforme = self.transformation_depuis_raster.transform(point_xy)
                # Reconstituer le QgsPoint avec la valeur Z
                point = QgsPoint(point_xy_transforme.x(), point_xy_transforme.y(), point.z())
            liste_points.append(point)

        geometrie_chemin = QgsGeometry.fromPolyline(liste_points)

        return geometrie_chemin

    def reinitialiser(self):
        """
        Réinitialise l'outil pour un nouveau tracé.
        """
        self.liste_points = []
        self.chemin_dynamique = None
        self.polyligne_confirmee = None
        self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
        self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
        self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
        self.points_trace_libre = []
        self.mode_trace_libre = False

    def nettoyer_ressources(self):
        """
        Nettoyage des ressources et réinitialisation de l'outil.
        """
        self.reinitialiser()

        if hasattr(self, 'dataset'):
            self.dataset = None

        if hasattr(self, 'hillshade_dataset'):
            self.hillshade_dataset = None

        if hasattr(self, 'tableau_raster'):
            del self.tableau_raster
            self.tableau_raster = None

        if hasattr(self, 'tableau_hillshade'):
            del self.tableau_hillshade
            self.tableau_hillshade = None

        if hasattr(self, 'pentes_locales_degres'):
            del self.pentes_locales_degres
            self.pentes_locales_degres = None
