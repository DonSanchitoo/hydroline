"""
threads/raster_loading_thread.py

Place dans un thread secondaire le chargement des rasters
"""


import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtCore import QThread, pyqtSignal
from osgeo import gdal


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