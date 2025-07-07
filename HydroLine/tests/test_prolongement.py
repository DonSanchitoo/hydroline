# tests/test_prolongement.py
from unittest.mock import MagicMock

from ..external import pytest
from qgis._core import QgsField, QgsWkbTypes, QgsRasterLayer
from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY
from qgis.PyQt.QtCore import Qt, QObject, QCoreApplication, QVariant
from ..tools.prolongement import ProlongementDesProfils



@pytest.fixture
def setup_layers(qgis_app):
    """Fixture pour charger des couches de test."""

    # 1. Créer une couche MNT raster factice
    # Ici, nous utilisons une chaîne vide pour simuler une couche raster valide.
    mnt_layer = QgsRasterLayer("", "Test MNT")

    # Vérifier que la couche raster est initialisée
    assert mnt_layer.isValid(), "La couche MNT raster n'est pas valide."

    # Mock le data provider pour avoir la méthode 'identify'
    mock_data_provider = MagicMock()
    mnt_layer.setDataProvider(mock_data_provider)

    def mock_identify(point, format):
        """Mock de la méthode 'identify'"""
        mock_identify_instance = MagicMock()
        mock_identify_instance.isValid.return_value = True
        # Simuler des valeurs Z différentes selon le point
        if point.x() == 5 and point.y() == 5:
            mock_identify_instance.results.return_value = {1: None}  # Simuler Z = None
        else:
            mock_identify_instance.results.return_value = {1: 150.0}  # Simuler Z valide
        return mock_identify_instance

    mock_data_provider.identify.side_effect = mock_identify

    # 2. Créer une couche de points bathymétriques avec Absc_proj
    points_layer = QgsVectorLayer("Point?crs=EPSG:2154", "Test Points", "memory")
    prov_pts = points_layer.dataProvider()
    prov_pts.addAttributes([
        QgsField("OBJECTID", QVariant.Int),
        QgsField("Z", QVariant.Double),
        QgsField("Absc_proj", QVariant.Double)
    ])
    points_layer.updateFields()

    # 3. Créer une couche de lignes de profil
    lignes_layer = QgsVectorLayer("LineString?crs=EPSG:2154", "Test Lignes", "memory")
    prov_lignes = lignes_layer.dataProvider()
    prov_lignes.addAttributes([QgsField("id", QVariant.Int)])
    lignes_layer.updateFields()

    # 4. Ajouter les couches au projet QGIS
    QgsProject.instance().addMapLayer(mnt_layer)
    QgsProject.instance().addMapLayer(points_layer)
    QgsProject.instance().addMapLayer(lignes_layer)

    return {
        "mnt": mnt_layer,
        "points": points_layer,
        "lignes": lignes_layer
    }


@pytest.fixture
def prolongement_class(setup_layers):
    """Fixture pour initialiser la classe ProlongementDesProfils avec des couches de test."""
    traitement = ProlongementDesProfils()
    traitement.couche_mnt = setup_layers["mnt"]
    traitement.couche_points = setup_layers["points"]
    traitement.couche_lignes = setup_layers["lignes"]
    # Simuler l'absence de couche d'emprise et présence du champ Absc_proj
    traitement.couche_emprise = None
    traitement.index_objectid = traitement.couche_points.fields().indexFromName('OBJECTID')
    traitement.index_z = traitement.couche_points.fields().indexFromName('Z')
    traitement.index_abscisse_proj = traitement.couche_points.fields().indexFromName('Absc_proj')
    return traitement


def test_initialisation(prolongement_class):
    """Test de l'initialisation de la classe ProlongementDesProfils."""
    assert prolongement_class is not None


def test_traiter_ligne_with_absc_proj(prolongement_class):
    """Test de la méthode traiter_ligne avec le champ Absc_proj."""
    # Créer une ligne de test
    feature_ligne = QgsFeature()
    geometry_ligne = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(10, 10)])
    feature_ligne.setGeometry(geometry_ligne)
    feature_ligne.setAttributes([1])
    prolongement_class.couche_lignes.dataProvider().addFeatures([feature_ligne])

    # Ajouter des points de test
    feature_point1 = QgsFeature()
    feature_point1.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(2, 2)))
    feature_point1.setAttributes([1, 100.0, 2.0])

    feature_point2 = QgsFeature()
    feature_point2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(8, 8)))
    feature_point2.setAttributes([2, 200.0, 8.0])

    prolongement_class.couche_points.dataProvider().addFeatures([feature_point1, feature_point2])

    # Traitement de la ligne
    nouveaux_points = prolongement_class.traiter_ligne(feature_ligne)
    logging.info(f'Nombre de nouveaux points générés: {len(nouveaux_points)}')

    # Assertions
    assert len(nouveaux_points) > 0, "Aucun point n'a été généré."
    for pt in nouveaux_points:
        assert pt.geometry().type() == QgsWkbTypes.PointGeometry, "Géométrie incorrecte pour le point généré."
        # Vérifiez que les points générés sont en dehors de la plage Absc_proj
        absc_proj = pt.attributes()[prolongement_class.index_abscisse_proj]
        # Puisque nous traitons uniquement les segments à l'extérieur de 2 et 8, les nouveaux points doivent être en dehors
        assert absc_proj < 2.0 or absc_proj > 8.0, f"Point généré avec Absc_proj invalide: {absc_proj}"


def test_traiter_segment_raster_handling_none_z(prolongement_class):
    """Test de la méthode traiter_segment_raster pour gérer les valeurs Z None."""
    # Créer un segment de test
    geom_segment = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(10, 10)])

    # Appeler la méthode
    nouveaux_points = prolongement_class.traiter_segment_raster(geom_segment)
    logging.info(f'Nombre de nouveaux points générés: {len(nouveaux_points)}')

    # Assert que les points avec Z None sont ignorés
    for pt in nouveaux_points:
        z = pt.attributes()[prolongement_class.index_z]
        assert z is not None, "Un point a une valeur Z None, ce qui est incorrect."
