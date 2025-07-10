# threads/raster_loading_thread.py

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtCore import QThread, pyqtSignal
from osgeo import gdal


class RasterLoadingThread(QThread):
    """
    Thread pour charger les données raster à partir d'une couche.

    Cette classe utilise GDAL pour récupérer les données raster et leurs géotransformations,
    permettant le traitement du chargement dans un thread séparé pour maintenir la réactivité de l'application.

    Attributes
    ----------
    couche_raster : QgsRasterLayer
        La couche raster à charger.
    raster_loaded : pyqtSignal
        Signal émis une fois le raster chargé, contenant le tableau des données, la géotransformation,
        son inverse, et les dimensions du raster.

    Methods
    -------
    run()
        Exécute le chargement des données raster.
    """
    raster_loaded = pyqtSignal(np.ndarray, tuple, tuple, int, int)  # Emitting the loaded raster data and other params

    def __init__(self, couche_raster, parent=None):
        """
        Initialise le thread de chargement du raster.

        Parameters
        ----------
        couche_raster : QgsRasterLayer
            La couche raster à charger.
        parent : QObject, optional
            Objet parent pour le thread, par défaut None.
        """

        super().__init__(parent)
        self.couche_raster = couche_raster

    def run(self):
        """
        Exécute le chargement des données raster.

        Utilise GDAL pour ouvrir et lire les données raster dans un tableau NumPy,
        tout en récupérant la géotransformation et ses dimensions, puis émet un signal avec ces données.
        """

        try:
            source = self.couche_raster.dataProvider().dataSourceUri()
            dataset = gdal.Open(source)

            if dataset is None:
                return

            gt = dataset.GetGeoTransform()
            inv_gt = gdal.InvGeoTransform(gt)

            if inv_gt is None:
                return

            bande_raster = dataset.GetRasterBand(1)
            tableau_raster = bande_raster.ReadAsArray()

            if tableau_raster is None:
                return

            raster_lignes, raster_colonnes = tableau_raster.shape


            self.raster_loaded.emit(tableau_raster, gt, inv_gt, raster_lignes, raster_colonnes)
        except Exception as e:
            print(f"Erreur lors du chargement du raster: {e}")