# utils/error.py


from qgis.PyQt.QtWidgets import QAction, QMessageBox

def afficher_message_epsg():
    """
    Affiche une boîte de dialogue avertissant de la nécessité de mettre le projet en EPSG:2154.
    """
    QMessageBox.warning(
        None,
        "Attention projet QGIS",
        ("Erreur de conversion des coordonnées.\n"
         "Veuillez assurer que votre projet QGIS est configuré sur EPSG:2154 pour éviter "
         "les erreurs de transformation des points.")
    )

def afficher_changer_vers_mode_convexe():
    QMessageBox.warning(
        None,
        "Attention option instable",
        ("Le mode convexe est fiable. Le mode concave \n"
         "est en développement !")
    )
