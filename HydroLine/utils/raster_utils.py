
# utils/raster_utils.py


import os
import tempfile

import numpy as np
import processing
from osgeo import gdal
from qgis.core import QgsRasterLayer, QgsProject, QgsVectorLayer, QgsMeshLayer, QgsCoordinateReferenceSystem, QgsWkbTypes
from scipy.ndimage import median_filter

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


import os
import tempfile

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

    temp_dir = tempfile.gettempdir()  # Utilisation du répertoire temporaire
    ombrage_filename = f"{os.path.splitext(os.path.basename(couche_raster_entree.source()))[0]}_ombrage.tif"
    output_path = os.path.join(temp_dir, ombrage_filename)

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
        'OUTPUT': output_path
    }
    output = processing.run("gdal:hillshade", params)
    couche_ombrage = QgsRasterLayer(output['OUTPUT'], 'Ombrage_HydroLine')

    if not couche_ombrage.isValid():
        return None

    return couche_ombrage



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

# utils/raster_utils.py



def filtre_median_raster(couche_raster_entree, kernel_size=5):
    """
    Applique un filtre médian à la couche raster d'entrée pour lisser les valeurs et éliminer les artefacts.

    Parameters
    ----------
    couche_raster_entree : QgsRasterLayer
        La couche raster d'entrée à filtrer.
    kernel_size : int, optional
        La taille du noyau pour le filtre médian, par défaut 5.

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

    try:
        output_array = median_filter(input_array, size=kernel_size)
    except Exception as e:
        print(f"Erreur lors de l'application du filtre médian : {e}")
        return None

    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, 'filtered_median_raster.tif')

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

def reprojeter_raster(couche_raster, code_epsg=2154):
    """
    Reprojette la couche raster vers le système de coordonnées spécifié.

    Parameters
    ----------
    couche_raster : QgsRasterLayer
        La couche raster à reprojeter.
    code_epsg : int, optional
        Le code EPSG vers lequel reprojeter, par défaut EPSG:2154.

    Returns
    -------
    QgsRasterLayer or None
        La couche raster reprojetée ou None si le traitement échoue.
    """
    crs = f"EPSG:{code_epsg}"
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir,
                               f"{os.path.splitext(os.path.basename(couche_raster.source()))[0]}_reprojected.tif")

    params = {
        'INPUT': couche_raster.source(),
        'TARGET_CRS': crs,
        'RESAMPLING': 0,
        'NODATA': None,
        'DATA_TYPE': 0,
        'OUTPUT': output_path
    }

    output = processing.run("gdal:warpreproject", params)
    couche_reprojete = QgsRasterLayer(output['OUTPUT'], f"{couche_raster.name()}_reprojected")
    return couche_reprojete if couche_reprojete.isValid() else None

def convertir_tin_en_raster(couche_tin, crs_target, pixel_size=1.0, feedback=None):
    """
    Convertit une couche TIN en raster.

    Parameters
    ----------
    couche_tin : QgsMapLayer
        La couche TIN à convertir.
    crs_target : str
        Le CRS cible (format string, par exemple "EPSG:2154").
    pixel_size : float, optional
        La taille des pixels pour le raster, par défaut 1.0.
    feedback : QgsProcessingFeedback, optional
        Un objet de feedback pour suivre le traitement.

    Returns
    -------
    QgsRasterLayer or None
        La couche raster résultante ou None si le traitement échoue.
    """
    temp_dir = tempfile.gettempdir()
    nom_couche = couche_tin.name()
    output_path = os.path.join(temp_dir, f"{nom_couche}_raster.tif")

    parametres_meshrasterize = {
        'INPUT': couche_tin.source(),
        'DATASET_GROUPS': [0],
        'DATASET_TIME': {'type': 'static'},
        'EXTENT': None,  # Utiliser l'étendue par défaut
        'PIXEL_SIZE': pixel_size,
        'CRS_OUTPUT': crs_target,
        'OUTPUT': output_path
    }

    try:
        resultat_rasterize = processing.run("native:meshrasterize", parametres_meshrasterize, feedback=feedback)
    except Exception as e:
        print(f"Erreur lors de la rasterisation du TIN : {e}")
        return None

    couche_raster = QgsRasterLayer(resultat_rasterize['OUTPUT'], f"{nom_couche}_raster")

    if not couche_raster.isValid():
        return None

    QgsProject.instance().addMapLayer(couche_raster, False)

    return couche_raster

def convertir_points_en_tin(couche_points, selected_field, crs_target='EPSG:2154', feedback=None):
    """
    Convertit une couche de points en un maillage TIN.

    Parameters
    ----------
    couche_points : QgsVectorLayer
        La couche de points à convertir en TIN.
    selected_field : str
        Le nom du champ à utiliser pour les valeurs d'altitude.
    crs_target : str, optional
        Le CRS cible, par défaut 'EPSG:2154'.
    feedback : QgsProcessingFeedback, optional
        Un objet de feedback pour suivre le traitement.

    Returns
    -------
    QgsMeshLayer or None
        Le maillage TIN résultant ou None si le traitement échoue.
    """

    try:
        # Obtenir l'index du champ selected_field
        attribute_index = couche_points.fields().indexFromName(selected_field)
        if attribute_index == -1:
            raise ValueError(f"Le champ '{selected_field}' n'existe pas dans la couche '{couche_points.name()}'.")

        parametres_tin = {
            'SOURCE_DATA': [{
                'source': couche_points.source(),
                'type': 0,  # 0 pour couche vectorielle
                'attributeIndex': attribute_index
            }],
            'MESH_FORMAT': 0,  # Format de sortie (0 pour '2DM')
            'CRS_OUTPUT': QgsCoordinateReferenceSystem(crs_target),
            'OUTPUT_MESH': 'TEMPORARY_OUTPUT'
        }

        resultat_tin = processing.run(
            "native:tinmeshcreation",
            parametres_tin,
            feedback=feedback
        )
        output_path = resultat_tin['OUTPUT_MESH']

        # Créer une couche MeshLayer à partir du fichier de sortie
        couche_tin = QgsMeshLayer(output_path, f"{couche_points.name()}_TIN", "mdal")

        if not couche_tin.isValid():
            feedback.reportError("Le maillage TIN résultant est invalide.")
            return None

        # Ajouter le TIN au projet sans l'afficher
        QgsProject.instance().addMapLayer(couche_tin, False)

        return couche_tin

    except Exception as e:
        feedback.reportError(f"Erreur lors de la création du TIN : {e}")
        return None
