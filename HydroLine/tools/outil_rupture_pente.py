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
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QMenu, QToolButton, QInputDialog, QDockWidget, QWidget, QVBoxLayout, QComboBox, QApplication
from qgis.gui import QgsMapTool, QgsRubberBand

from .base_map_tool import BaseMapTool
from ..threads.calcul_pentes_thread import CalculPentesThread
from ..utils.raster_utils import generer_ombrage_invisible


class OutilRupturePente(BaseMapTool):
    """
    Outil de dessin de rupture de pente (concave ou convexe) avec assistance dynamique sur MNT.

    Args:
        canvas (QgsMapCanvas): Le canevas de la carte.
        couche_raster (QgsRasterLayer): La couche raster MNT.
        mode (str): Le mode de rupture de pente ('concave' ou 'convexe').
    """

    def __init__(self, canvas, couche_raster, mode='convexe'):
        """Initialise l'outil de tracé de rupture de pente."""
        super().__init__(canvas, couche_raster)
        self.canvas = canvas
        self.couche_raster = couche_raster
        self.mode = mode # 'concave' ou 'convexe'
        self.simplification_activee = False
        self.tolerance_simplification = 2.0
        self.calcul_termine = False

        # Pré-calcul des transformations de coordonnées
        self.crs_canvas = self.canvas.mapSettings().destinationCrs()
        self.crs_raster = self.couche_raster.crs()
        self.transformation_vers_raster = QgsCoordinateTransform(self.crs_canvas, self.crs_raster, QgsProject.instance())
        self.transformation_depuis_raster = QgsCoordinateTransform(self.crs_raster, self.crs_canvas, QgsProject.instance())

        self.liste_points = [] # Liste pour stocker les points de la polyligne
        self.chemin_dynamique = None
        self.polyligne_confirmee = None # Polyligne confirmée unique

        # Bande élastique pour la ligne dynamique
        self.bande_dynamique = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_dynamique.setColor(QColor(255, 0, 0))
        self.bande_dynamique.setWidth(2)
        self.bande_dynamique.setLineStyle(Qt.DashLine)

        # Bande élastique pour la polyligne confirmée
        self.bande_confirmee = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_confirmee.setColor(QColor(0, 0, 255))
        self.bande_confirmee.setWidth(3)

        # Initialiser les variables pour le mode "tracé libre"
        self.mode_trace_libre = False
        self.points_trace_libre = []
        self.bande_trace_libre = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.bande_trace_libre.setColor(QColor(0, 255, 0))  # Couleur verte pour le tracé libre
        self.bande_trace_libre.setWidth(3)

        # Pré-chargement des données raster
        self.charger_donnees_raster()

        # Générer l'ombrage à partir du MNT en utilisant 'generer_ombrage'
        self.couche_ombrage = generer_ombrage_invisible(self.couche_raster)
        if self.couche_ombrage is None:
            QMessageBox.critical(None, "Erreur", "Impossible de générer l'ombrage pour le MNT.")
            return

        # Charger les données de l'ombrage (pour les calculs de pentes)
        self.charger_donnees_hillshade()

        # Démarrer le calcul des pentes locales dans un thread séparé
        self.calcul_pentes_thread = CalculPentesThread(self.tableau_hillshade, self.gt)
        self.calcul_pentes_thread.result_ready.connect(self.on_pentes_calculees)
        self.calcul_pentes_thread.start()


    def on_pentes_calculees(self, pentes_locales_degres):
        """Appelé lorsque le calcul des pentes est terminé."""
        self.pentes_locales_degres = pentes_locales_degres
        self.calcul_termine = True
        # Fermer le Splash Screen
        self.splash_screen_load.close()

    def definir_couche_vectorielle(self, couche_vectorielle):
        """Assigne la couche vectorielle où stocker les polylignes."""
        self.couche_vectorielle = couche_vectorielle
        # Initialise le compteur d'ID en fonction du nombre d'entités existantes
        self.id_counter = self.couche_vectorielle.featureCount() + 1

    def confirmer_polyligne(self):
        """Confirme la polyligne actuelle et l'ajoute à la couche vectorielle."""
        if self.polyligne_confirmee is not None and self.couche_vectorielle is not None:
            # Si la simplification est activée, simplifier la polyligne confirmée
            if self.simplification_activee:
                geometrie_a_sauvegarder = self.simplifier_geometrie(self.polyligne_confirmee)
            else:
                geometrie_a_sauvegarder = self.polyligne_confirmee

            # Construire la polyligne en 3D avec les valeurs Z du MNT
            points_avec_z = []
            if geometrie_a_sauvegarder.isMultipart():
                # Gérer le cas multipartie si nécessaire
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

            # Créer la géométrie de la polyligne avec les points simplifiés et les valeurs Z
            polyligne_z = QgsGeometry.fromPolyline(points_avec_z)

            # Créer une entité et définir sa géométrie et ses attributs
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

    def definir_simplification(self, activee):
        """Active ou désactive la simplification du tracé."""
        self.simplification_activee = activee
        self.mettre_a_jour_bande_dynamique()

    def definir_mode_trace_libre(self, tracelibre):
        """Active ou désactive le mode de tracé libre."""
        if tracelibre:
            # Entrer en mode tracé libre
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
            # Sortir du mode tracé libre
            self.mode_trace_libre = False
            self.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
            if len(self.points_trace_libre) >= 2:
                # Ajouter les points tracés librement à liste_points (sauf le point de départ)
                nouveaux_points = self.points_trace_libre[1:]
                self.liste_points.extend(nouveaux_points)
                # Mettre à jour la polyligne confirmée
                self.polyligne_confirmee = QgsGeometry.fromPolyline(self.liste_points)
                self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                self.bande_confirmee.addGeometry(self.polyligne_confirmee, None)
            self.points_trace_libre = []

    def charger_donnees_mnt(self):
        """Charge les données du MNT en mémoire pour un accès rapide."""
        # Ouvrir le raster MNT avec GDAL
        source = self.couche_raster.dataProvider().dataSourceUri()
        self.dataset = gdal.Open(source)

        if self.dataset is None:
            print("Impossible d'ouvrir le MNT.")
            return

        # Obtenir la géotransformation et son inverse
        self.mnt_gt = self.dataset.GetGeoTransform()
        self.mnt_inv_gt = gdal.InvGeoTransform(self.mnt_gt)

        if self.mnt_inv_gt is None:
            print("Impossible de calculer la géotransformation inverse pour le MNT.")
            return

        # Lire les données du MNT dans un tableau NumPy
        bande_raster = self.dataset.GetRasterBand(1)
        self.tableau_raster = bande_raster.ReadAsArray()

        if self.tableau_raster is None:
            print("Impossible de lire les données du MNT.")
            return

        # Obtenir les dimensions du raster MNT
        self.mnt_lignes, self.mnt_colonnes = self.tableau_raster.shape

    def charger_donnees_hillshade(self):
        """Charge les données de l'ombrage en mémoire pour un accès rapide."""
        # Ouvrir le raster d'ombrage avec GDAL
        source = self.couche_ombrage.dataProvider().dataSourceUri()
        self.hillshade_dataset = gdal.Open(source)

        if self.hillshade_dataset is None:
            print("Impossible d'ouvrir le raster d'ombrage.")
            return

        # Obtenir la géotransformation et son inverse
        self.gt = self.hillshade_dataset.GetGeoTransform()
        self.inv_gt = gdal.InvGeoTransform(self.gt)

        if self.inv_gt is None:
            print("Impossible de calculer la géotransformation inverse pour l'ombrage.")
            return

        # Lire les données de l'ombrage dans un tableau NumPy
        bande_raster = self.hillshade_dataset.GetRasterBand(1)
        self.tableau_hillshade = bande_raster.ReadAsArray()

        if self.tableau_hillshade is None:
            print("Impossible de lire les données du raster d'ombrage.")
            return

        # Obtenir les dimensions du raster d'ombrage
        self.raster_lignes, self.raster_colonnes = self.tableau_hillshade.shape

    def definir_fenetre_profil(self, fenetre):
        """Assigne la fenêtre du profil d'élévation."""
        self.fenetre_profil = fenetre
        if self.fenetre_profil is not None:
            self.fenetre_profil.definir_outil(self)

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

    def simplifier_geometrie(self, geometrie):
        """Simplifie la géométrie en préservant les points critiques."""
        if geometrie.isMultipart():
            QMessageBox.warning(None, "Avertissement", "La géométrie est multipartie, ce n'est pas supporté.")
            return geometrie
        else:
            # Obtenir l'objet QgsLineString
            line = geometrie.constGet()
            if isinstance(line, QgsLineString):
                points = [line.pointN(i) for i in range(line.numPoints())]
            else:
                QMessageBox.warning(None, "Avertissement", "La géométrie n'est pas une ligne.")
                return geometrie

        if len(points) < 3:
            return geometrie

        # Identifier les points critiques en fonction des élévations
        elevations = [p.z() for p in points]
        if self.mode == 'concave':
            elevation_minimale = min(elevations)
            points_critiques = [points[i] for i, elev in enumerate(elevations) if elev == elevation_minimale]
        else:
            elevation_maximale = max(elevations)
            points_critiques = [points[i] for i, elev in enumerate(elevations) if elev == elevation_maximale]

        # Appliquer l'algorithme de simplification
        points_simplifies = self.douglas_peucker_avec_critiques(points, self.tolerance_simplification, points_critiques)

        # Créer la géométrie simplifiée en 3D
        return QgsGeometry.fromPolyline(points_simplifies)

    def obtenir_pente_au_point(self, point):
        """Obtient la pente locale au point donné."""
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
        """Simplifie une polyligne en conservant les points critiques."""
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

        # Assurer que simplified_points contient des QgsPoint avec Z
        for idx in range(len(simplified_points)):
            p = simplified_points[idx]
            if not isinstance(p, QgsPoint):
                z = p.z() if hasattr(p, 'z') else 0
                simplified_points[idx] = QgsPoint(p.x(), p.y(), z)

        return simplified_points

    def distance_perpendiculaire(self, point, debut, fin):
        """Calcule la distance perpendiculaire du point à la ligne debut-fin en 2D."""
        if debut == fin:
            return self.distance_euclidienne(point, debut)
        else:
            x0, y0 = point.x(), point.y()
            x1, y1 = debut.x(), debut.y()
            x2, y2 = fin.x(), fin.y()
            num = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
            den = ((y2 - y1) ** 2 + (x2 - x1) ** 2) ** 0.5
            return num / den

    def definir_fenetre_profil(self, fenetre):
        """Assigne la fenêtre du profil d'élévation."""
        self.fenetre_profil = fenetre
        if self.fenetre_profil is not None:
            self.fenetre_profil.definir_outil(self)

    def mettre_a_jour_profil(self, geometrie):
        """Met à jour le profil d'élévation avec le segment dynamique."""
        if geometrie is None:
            return

        geom = geometrie.constGet()
        if isinstance(geom, QgsLineString):
            # Vérifier si la géométrie est en 3D
            if geom.is3D():
                # Extraire les points avec leurs valeurs Z
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
                # Créer un segment entre le point précédent et le point actuel
                segment = QgsGeometry.fromPolyline([point_precedent, point])  # Les points sont maintenant des QgsPoint
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
        """Calcule la distance euclidienne entre deux points en 2D."""
        dx = p1.x() - p2.x()
        dy = p1.y() - p2.y()
        return (dx * dx + dy * dy) ** 0.5

    def obtenir_elevation_au_point(self, point):
        """Obtient l’élévation du raster au point donné."""
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

    def charger_donnees_raster(self):
        """Charge les données raster en mémoire pour un accès rapide."""
        # Ouvrir le raster avec GDAL
        source = self.couche_raster.dataProvider().dataSourceUri()
        self.dataset = gdal.Open(source)

        if self.dataset is None:
            print("Impossible d'ouvrir le raster.")
            return

        # Obtenir la géotransformation et son inverse
        self.gt = self.dataset.GetGeoTransform()
        self.inv_gt = gdal.InvGeoTransform(self.gt)

        if self.inv_gt is None:
            print("Impossible de calculer la géotransformation inverse.")
            return

        # Lire les données du raster dans un tableau NumPy
        bande_raster = self.dataset.GetRasterBand(1)
        self.tableau_raster = bande_raster.ReadAsArray()

        if self.tableau_raster is None:
            print("Impossible de lire les données du raster.")
            return

        # Obtenir les dimensions du raster
        self.raster_lignes, self.raster_colonnes = self.tableau_raster.shape

    def calculer_pentes_locales(self):
        """Calcule la pente locale pour chaque pixel du raster en utilisant Dask."""
        import dask.array as da
        from osgeo import gdal_array

        # Ouvrir le raster
        source = self.couche_raster.dataProvider().dataSourceUri()
        raster = gdal_array.LoadFile(source)

        # Créer un Dask array à partir du NumPy array
        dask_array = da.from_array(raster, chunks=(1000, 1000)) # Ajuster la taille des chunks

        # Calculer le gradient en utilisant Dask
        grad_y, grad_x = da.gradient(dask_array, self.gt[1], -self.gt[5])
        magnitude = da.degrees(da.arctan(da.sqrt(grad_x ** 2 + grad_y ** 2)))

        # Calculer et charger en mémoire le tableau résultant
        self.pentes_locales_degres = magnitude.compute()

    def definir_mode(self, mode):
        """Définit le mode de fonctionnement de l'outil."""
        self.mode = mode

    def canvasPressEvent(self, event):
        if not self.calcul_termine:
            QMessageBox.information(None, "Calcul en cours", "Veuillez patienter, le calcul des pentes est en cours.")
            return

        point_xy = self.toMapCoordinates(event.pos())
        point_carte = QgsPoint(point_xy.x(), point_xy.y(), 0)

        if self.mode_trace_libre:
            # Mode tracé libre
            self.points_trace_libre.append(point_carte)
            self.bande_trace_libre.addPoint(QgsPointXY(point_carte))
        else:
            if not self.liste_points:
                # Premier clic : ajouter le point de départ
                self.liste_points.append(point_carte)
            else:
                # Confirmer le segment actuel
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

                    self.liste_points.extend(converted_points)
                    # Construire la polyligne confirmée à partir de `self.liste_points`
                    self.polyligne_confirmee = QgsGeometry.fromPolyline(self.liste_points)
                    self.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                    self.bande_confirmee.addGeometry(self.polyligne_confirmee, None)
                    self.chemin_dynamique = None
                    self.bande_dynamique.reset(QgsWkbTypes.LineGeometry)

    def canvasMoveEvent(self, event):
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

        # Sauvegarder les valeurs Z originales
        z_depart = point_depart.z()
        z_arrivee = point_arrivee.z()

        if self.crs_raster != self.crs_canvas:
            # Transformer les coordonnées X et Y en utilisant QgsPointXY
            point_depart_xy = QgsPointXY(point_depart.x(), point_depart.y())
            point_arrivee_xy = QgsPointXY(point_arrivee.x(), point_arrivee.y())

            # Appliquer la transformation vers le raster
            point_depart_xy_transforme = self.transformation_vers_raster.transform(point_depart_xy)
            point_arrivee_xy_transforme = self.transformation_vers_raster.transform(point_arrivee_xy)

            # Reconstituer les QgsPoint avec les valeurs Z originales
            point_depart = QgsPoint(point_depart_xy_transforme.x(), point_depart_xy_transforme.y(), z_depart)
            point_arrivee = QgsPoint(point_arrivee_xy_transforme.x(), point_arrivee_xy_transforme.y(), z_arrivee)

        depart_px = gdal.ApplyGeoTransform(self.inv_gt, point_depart.x(), point_depart.y())
        arrivee_px = gdal.ApplyGeoTransform(self.inv_gt, point_arrivee.x(), point_arrivee.y())
        depart_px = (int(round(depart_px[0])), int(round(depart_px[1])))
        arrivee_px = (int(round(arrivee_px[0])), int(round(arrivee_px[1])))

        # Vérifier si les points sont dans les limites du raster
        if not (0 <= depart_px[0] < self.raster_colonnes and 0 <= depart_px[1] < self.raster_lignes):
            return None
        if not (0 <= arrivee_px[0] < self.raster_colonnes and 0 <= arrivee_px[1] < self.raster_lignes):
            return None

        # Calcul des ruptures de pente spécifiques
        if self.mode == 'concave':
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
                print("Aucun voisin disponible.")
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

        # Créer la géométrie avec les points en 3D
        geometrie_chemin = QgsGeometry.fromPolyline(liste_points)

        return geometrie_chemin

    def nettoyer_ressources(self):
        """Nettoyage des ressources et réinitialisation de l'outil."""
        self.reinitialiser() # Réinitialiser les bandes élastiques et autres éléments temporaires

        # Libérer le dataset GDAL
        if hasattr(self, 'dataset'):
            self.dataset = None

        # Libérer les grands tableaux NumPy
        if hasattr(self, 'tableau_raster'):
            del self.tableau_raster
            self.tableau_raster = None

        if hasattr(self, 'pentes_locales'):
            del self.pentes_locales
            self.pentes_locales = None

        if hasattr(self, 'pentes_locales_degres'):
            del self.pentes_locales_degres
            self.pentes_locales_degres = None

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

    def charger_nouveau_mnt(self, couche_raster):
        """Change le MNT actif pour l'analyse et configure les ressources nécessaires."""
        # Nettoyage des ressources précédentes
        self.nettoyer_ressources()

        # Reconfigurer le nouvel MNT
        self.couche_raster = couche_raster
        self.crs_raster = self.couche_raster.crs()
        self.transformation_vers_raster = QgsCoordinateTransform(self.crs_canvas, self.crs_raster, QgsProject.instance())
        self.transformation_depuis_raster = QgsCoordinateTransform(self.crs_raster, self.crs_canvas, QgsProject.instance())

        # Pré-chargement des données raster
        self.charger_donnees_raster()

        # Calcul des pentes locales pour le nouveau MNT
        self.calculer_pentes_locales()

    def nettoyer_ressources(self):
        """Nettoyage des ressources et réinitialisation de l'outil."""
        self.reinitialiser()  # Réinitialiser les bandes élastiques et autres éléments temporaires

        # Libérer le dataset GDAL du MNT
        if hasattr(self, 'dataset'):
            self.dataset = None

        # Libérer le dataset GDAL de l'ombrage
        if hasattr(self, 'hillshade_dataset'):
            self.hillshade_dataset = None

        # Libérer les grands tableaux NumPy
        if hasattr(self, 'tableau_raster'):
            del self.tableau_raster
            self.tableau_raster = None

        if hasattr(self, 'tableau_hillshade'):
            del self.tableau_hillshade
            self.tableau_hillshade = None

        if hasattr(self, 'pentes_locales_degres'):
            del self.pentes_locales_degres
            self.pentes_locales_degres = None
