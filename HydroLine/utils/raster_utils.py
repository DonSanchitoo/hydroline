
# utils/raster_utils.py


import os
import tempfile

import numpy as np
import processing
from osgeo import gdal
from qgis._core import QgsRasterLayer


def filtre_moyen_raster(couche_raster_entree, kernel_size=3):
    """
    Applique un filtre moyen à la couche raster d'entrée pour lisser les valeurs.

    Parameters
    ----------
    couche_raster_entree : QgsRasterLayer
        La couche raster d'entrée à filtrer.
    kernel_size : int, optional
        La taille du noyau pour le filtre moyen, par défaut 3.

    Returns
    -------
    QgsRasterLayer or None
        La couche raster filtrée ou None si le traitement échoue.
    """


    input_path = couche_raster_entree.source()
    input_dataset = gdal.Open(input_path, gdal.GA_ReadOnly)
    if input_dataset is None:
        return None
    input_band = input_dataset.GetRasterBand(1)

    input_array = input_band.ReadAsArray()
    if input_array is None:
        return None


    kernel = np.ones((kernel_size, kernel_size), dtype=float) / (kernel_size * kernel_size)
    try:
        from scipy.signal import convolve2d
        output_array = convolve2d(input_array, kernel, mode='same', boundary='symm')
    except ImportError:
        pad_size = kernel_size // 2
        padded_array = np.pad(input_array, pad_size, mode='edge')

        output_array = np.zeros_like(input_array, dtype=float)

        # Boucler sur l'array pour appliquer le filtre
        for i in range(output_array.shape[0]):
            for j in range(output_array.shape[1]):
                # Extraire la sous-matrice
                sub_array = padded_array[i:i + kernel_size, j:j + kernel_size]
                # Calculer la moyenne
                output_array[i, j] = np.sum(sub_array * kernel)

    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, 'filtered_raster.tif')

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

    output_dataset.SetGeoTransform(input_dataset.GetGeoTransform())
    output_dataset.SetProjection(input_dataset.GetProjection())

    output_band = output_dataset.GetRasterBand(1)
    output_band.WriteArray(output_array)
    output_band.FlushCache()

    input_dataset = None
    output_dataset = None

    output_raster_layer = QgsRasterLayer(output_path, 'MNT_HydroLine')

    if not output_raster_layer.isValid():
        return None

    return output_raster_layer


def generer_ombrage(couche_raster_entree):
    """
    Génère un ombrage à partir de la couche raster d'entrée.

    Parameters
    ----------
    couche_raster_entree : QgsRasterLayer
        La couche raster d'origine.

    Returns
    -------
    QgsRasterLayer or None
        La couche raster d'ombrage ou None si le traitement échoue.
    """

    params = {
        'INPUT': couche_raster_entree.source(),
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
    output = processing.run("gdal:hillshade", params)
    couche_ombrage = QgsRasterLayer(output['OUTPUT'], 'Ombrage_HydroLine')
    return couche_ombrage if couche_ombrage.isValid() else None


def fusionner_et_arrondir_rasters(couches_raster, precision_decimales=1):
    """
    Combine plusieurs rasters en un seul et arrondit les valeurs du raster résultant.

    Parameters
    ----------
    couches_raster : list of QgsRasterLayer
        Liste de couches raster à fusionner.
    precision_decimales : int, optional
        Nombre de décimales pour arrondir les valeurs, par défaut 1.

    Returns
    -------
    QgsRasterLayer or None
        La couche raster fusionnée et arrondie ou None si le traitement échoue.
    """

    raster_sources = [layer.source() for layer in couches_raster]

    merge_params = {
        'INPUT': raster_sources,
        'PCT': False,
        'SEPARATE': False,
        'NODATA_INPUT': None,
        'NODATA_OUTPUT': None,
        'OPTIONS': '',
        'DATA_TYPE': 6,  # Float32
        'OUTPUT': 'TEMPORARY_OUTPUT'
    }
    fusion_output = processing.run("gdal:merge", merge_params)
    couche_fusionnee = QgsRasterLayer(fusion_output['OUTPUT'], 'Raster_Combine_HydroLine')

    if not couche_fusionnee.isValid():
        return None

    calc_params = {
        'INPUT_A': couche_fusionnee.source(),
        'BAND_A': 1,
        'FORMULA': f'round(A, {precision_decimales})',
        'OUTPUT': 'TEMPORARY_OUTPUT',
        'RTYPE': 6  # Float32
    }
    calc_output = processing.run("gdal:rastercalculator", calc_params)
    couche_arrondie = QgsRasterLayer(calc_output['OUTPUT'], 'MNT_Raster_HydroLine')
    return couche_arrondie if couche_arrondie.isValid() else None


def generer_ombrage_invisible(couche_raster_entree):
    """
    Génère un ombrage à partir de la couche raster d'entrée sans l'ajouter au projet.

    Parameters
    ----------
    couche_raster_entree : QgsRasterLayer
        La couche raster d'origine.

    Returns
    -------
    QgsRasterLayer or None
        La couche raster d'ombrage ou None si le traitement échoue.
    """

    params = {
        'INPUT': couche_raster_entree.source(),
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
    output = processing.run("gdal:hillshade", params, feedback=None)
    couche_ombrage = QgsRasterLayer(output['OUTPUT'], 'Ombrage')

    # Ne pas ajouter la couche au projet
    return couche_ombrage if couche_ombrage.isValid() else None
