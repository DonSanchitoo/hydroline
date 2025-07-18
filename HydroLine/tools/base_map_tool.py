
# tools/base_map_tool.py


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
from ..utils.error import afficher_message_epsg


class BaseMapTool(QgsMapTool):
    """
    Classe de base pour les outils de carte nécessitant la gestion des données raster (MNT).

    Cette classe gère le chargement du raster en arrière-plan, les transformations de coordonnées,
    et fournit des méthodes utilitaires pour accéder aux données du raster.

    Attributes
    ----------
    canvas : QgsMapCanvas
        Le canevas de la carte.
    couche_raster : QgsRasterLayer
        La couche raster (MNT).
    data_loaded : bool
        Indicateur si les données de raster ont été chargées avec succès.
    crs_canvas : QgsCoordinateReferenceSystem
        Système de coordonnées du canevas de la carte.
    crs_raster : QgsCoordinateReferenceSystem
        Système de coordonnées du raster.
    transformation_vers_raster : QgsCoordinateTransform
        Transformation de coordonnées du canevas vers le raster.
    transformation_depuis_raster : QgsCoordinateTransform
        Transformation de coordonnées du raster vers le canevas.

    Methods
    -------
    on_pentes_calculees_error(error_message)
        Traite les erreurs liées aux calculs de pentes.
    on_raster_loaded(tableau_raster, gt, inv_gt, raster_lignes, raster_colonnes)
        Callback exécuté lorsque le chargement du raster est terminé.
    charger_donnees_raster()
        Charge les données raster en mémoire pour un accès rapide.
    obtenir_elevation_au_point_unique(point)
        Obtient l'élévation du raster au point donné.
    obtenir_elevation_aux_points_multiples(x_array, y_array)
        Obtient les élévations du raster pour des arrays de coordonnées x et y.
    nettoyer_ressources()
        Nettoyage des ressources et réinitialisation de l'outil.
    """

    def __init__(self, canvas, couche_raster):
        """
        Initialise l'outil de carte avec les attributs nécessaires pour gérer les données raster.

        Parameters
        ----------
        canvas : QgsMapCanvas
            Le canevas de la carte.
        couche_raster : QgsRasterLayer
            La couche raster (MNT).
        """
        super().__init__(canvas)
        self.canvas = canvas
        self.couche_raster = couche_raster
        self.data_loaded = False
        self.crs_warning_displayed = False

        self.crs_canvas = self.canvas.mapSettings().destinationCrs()
        self.crs_raster = self.couche_raster.crs()
        self.transformation_vers_raster = QgsCoordinateTransform(
            self.crs_canvas, self.crs_raster, QgsProject.instance()
        )
        self.transformation_depuis_raster = QgsCoordinateTransform(
            self.crs_raster, self.crs_canvas, QgsProject.instance()
        )

        self.splash_screen_load = SplashScreenLoad()
        self.splash_screen_load.setParent(self.canvas.parent())
        self.splash_screen_load.show()

        self.charger_donnees_raster()
        self.data_loaded = True

        self.splash_screen_load.close()

    def on_pentes_calculees_error(self, error_message):
        """
        Traite les erreurs liées aux calculs de pentes.

        Parameters
        ----------
        error_message : str
            Message d'erreur à afficher dans une boîte de dialogue.
        """
        self.splash_screen_load.close()
        QMessageBox.critical(None, "Erreur", error_message)

    def on_raster_loaded(self, tableau_raster, gt, inv_gt, raster_lignes, raster_colonnes):
        """
        Exécute le traitement final après le chargement du raster.

        Parameters
        ----------
        tableau_raster : np.ndarray
            Tableau contenant les données du raster.
        gt : tuple
            Géotransformation associée au raster.
        inv_gt : tuple
            Inverse de la géotransformation associée au raster.
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

    def charger_donnees_raster(self):
        """
        Charge les données raster en mémoire pour un accès rapide.

        Cette méthode utilise GDAL pour ouvrir et lire les données du raster, et pour obtenir
        la géotransformation et ses dimensions.
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

    def obtenir_elevation_au_point_unique(self, point):
        """
        Obtient l'élévation du raster au point donné.

        Parameters
        ----------
        point : QgsPointXY
            Point pour lequel obtenir l'élévation.

        Returns
        -------
        float or None
            Élévation à la position donnée, ou None si le point est en-dehors des limites du raster.
        """
        try:
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
            if not self.crs_warning_displayed:
                QgsMessageLog.logMessage("Erreur de transformation des coordonnées. Le projet doit-être en epsg:2154",
                                         level=Qgis.Critical)
                afficher_message_epsg()
                self.crs_warning_displayed = True
            self.reinitialiser()
            return None

    def obtenir_elevation_aux_points_multiples(self, x_array, y_array):
        """
        Obtient les élévations du raster pour des arrays de coordonnées x et y.

        Parameters
        ----------
        x_array : np.ndarray
            Tableau des coordonnées x des points.
        y_array : np.ndarray
            Tableau des coordonnées y des points.

        Returns
        -------
        np.ndarray
            Élévations au niveau des positions données en utilisant le tableau de raster.
        """

        if self.crs_raster != self.crs_canvas:
            transformer = self.transformation_vers_raster
            points = [QgsPointXY(x, y) for x, y in zip(x_array.flatten(), y_array.flatten())]
            points_transformed = [transformer.transform(p) for p in points]
            x_array_transformed = np.array([p.x() for p in points_transformed]).reshape(x_array.shape)
            y_array_transformed = np.array([p.y() for p in points_transformed]).reshape(y_array.shape)
        else:
            x_array_transformed = x_array
            y_array_transformed = y_array

        gt = self.inv_gt
        px_array = gt[0] + gt[1] * x_array_transformed + gt[2] * y_array_transformed
        py_array = gt[3] + gt[4] * x_array_transformed + gt[5] * y_array_transformed

        px_array = px_array.astype(int)
        py_array = py_array.astype(int)

        mask = (px_array >= 0) & (px_array < self.raster_colonnes) & (py_array >= 0) & (py_array < self.raster_lignes)
        elevations = np.full(x_array.shape, np.nan)
        elevations[mask] = self.tableau_raster[py_array[mask], px_array[mask]]

        return elevations

    def nettoyer_ressources_1(self):
        """
            Nettoyages des ressources et réinitialisation de l'outil.

            Cette méthode libère les ressources associées au dataset GDAL et aux grands tableaux NumPy
            pour réduire la consommation de mémoire.
        """
        self.reinitialiser()

        # Libérer le dataset GDAL
        if hasattr(self, 'dataset'):
            self.dataset.FlushCache()
            self.dataset = None

        # Libérer les grands tableaux NumPy
        if hasattr(self, 'tableau_raster'):
            del self.tableau_raster
            self.tableau_raster = None