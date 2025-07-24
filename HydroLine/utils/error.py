# utils/error.py


from qgis.PyQt.QtWidgets import QAction, QMessageBox
import logging
from ..logs.logs_config import setup_logging

setup_logging()

def afficher_message_epsg():
    """
    Affiche une boîte de dialogue avertissant de la nécessité de mettre le projet en EPSG:2154.
    """
    logging.warning("Erreur dans la conversion. L'EPSG doit être 2154 pour le projet QGIS")
    QMessageBox.warning(
        None,
        "Attention projet QGIS",
        ("Erreur de conversion des coordonnées.\n"
         "Veuillez assurer que votre projet QGIS est configuré sur EPSG:2154 pour éviter "
         "les erreurs de transformation des points.")
    )

def afficher_changer_vers_mode_convexe():
    logging.warning("Le mode concave est en développement, ne pas utiliser")
    QMessageBox.warning(
        None,
        "Attention option instable",
        ("Le mode convexe est fiable. Le mode concave \n"
         "est en développement !")
    )

def afficher_erreur_interpolation(message="Une erreur s'est produite lors de l'interpolation IDW."):
    """
    Affiche une boîte de message d'erreur pour l'interpolation.
    """
    QMessageBox.critical(None, "Erreur", message)