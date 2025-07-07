# tests/conftest.py



from ..external import pytest
import sys
import os
from qgis.core import QgsApplication


@pytest.fixture(scope='session', autouse=True)
def qgis_app():
    """Fixture pour initialiser QGIS avant les tests et la fermer après."""
    # Définir le chemin du préfixe de QGIS si nécessaire
    QGIS_PREFIX_PATH = "C:/Program Files/QGIS 3.34.15/apps/qgis-ltr"
    QgsApplication.setPrefixPath(QGIS_PREFIX_PATH, True)
    qgs = QgsApplication([], False)
    qgs.initQgis()

    yield qgs  # lancer le test

    qgs.exitQgis()


