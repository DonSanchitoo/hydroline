"""
tools/base_map_tool.py

"""
import numpy as np
from PyQt5.QtCore import Qt
from osgeo import gdal
from qgis._core import QgsPointXY
from qgis.core import (
    QgsCoordinateTransform,
    QgsProject
)
from qgis.gui import QgsMapTool
from qgis.PyQt.QtWidgets import QMessageBox, QInputDialog

from ..threads.calcul_pentes_thread import CalculPentesThread
from ..sscreen.sscreen_load import SplashScreenLoad
# from ..threads.raster_loading_thread import RasterLoadingThread


class BaseMapTool(QgsMapTool):
    """
    Classe de base pour les outils de carte nécessitant la gestion des données raster (MNT).
    Cette classe gère le chargement du raster en arrière-plan, les transformations de coordonnées,
    et fournit des méthodes utilitaires pour accéder aux données du raster.

    Args:
        canvas (QgsMapCanvas): Le canevas de la carte.
        couche_raster (QgsRasterLayer): La couche raster (MNT).
    """

    def __init__(self, canvas, couche_raster):
        """Initialise l'outil de base."""
        super().__init__(canvas)
        self.canvas = canvas
        self.couche_raster = couche_raster
        self.data_loaded = False

        # Pré-calcul des transformations de coordonnées
        self.crs_canvas = self.canvas.mapSettings().destinationCrs()
        self.crs_raster = self.couche_raster.crs()
        self.transformation_vers_raster = QgsCoordinateTransform(
            self.crs_canvas, self.crs_raster, QgsProject.instance()
        )
        self.transformation_depuis_raster = QgsCoordinateTransform(
            self.crs_raster, self.crs_canvas, QgsProject.instance()
        )

        # Afficher le Splash Screen de chargement
        self.splash_screen_load = SplashScreenLoad()
        self.splash_screen_load.setParent(self.canvas.parent())
        self.splash_screen_load.show()

        # Charger les données raster
        self.charger_donnees_raster()

        # Démarrer le calcul des pentes dans un thread
        self.calcul_pentes_thread = CalculPentesThread(self.tableau_raster, self.gt)
        self.calcul_pentes_thread.result_ready.connect(self.on_pentes_calculees)
        self.calcul_pentes_thread.error_occurred.connect(self.on_pentes_calculees_error)
        self.calcul_pentes_thread.start()


    def on_pentes_calculees(self, pentes_locales_degres):
        """Appelé lorsque le calcul des pentes est terminé."""
        self.pentes_locales_degres = pentes_locales_degres
        self.calcul_termine = True
        # Fermer le Splash Screen
        self.splash_screen_load.close()

    def on_pentes_calculees_error(self, error_message):
        """Gère les erreurs survenues lors du calcul des pentes."""
        self.splash_screen_load.close()
        QMessageBox.critical(None, "Erreur", error_message)


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

    def obtenir_elevation_aux_points_multiples(self, x_array, y_array):
        """Obtient les élévations du raster pour des arrays de coordonnées x et y."""
        if self.crs_raster != self.crs_canvas:
            # Transformer les points
            transformer = self.transformation_vers_raster
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