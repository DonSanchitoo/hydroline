# -*- coding: utf-8 -*-
"""
Module Epoint.py
Ce module réalise le calcul de l'emprise (alpha shape) sur une couche de points.
Il utilise la méthode de triangulation de Delaunay et ajuste les arêtes en fonction du facteur alpha.
"""

import math, random
import numpy as np
from itertools import combinations

from .alphashape import alphashape
from qgis.core import (Qgis, QgsProject, QgsWkbTypes, QgsVectorLayer,
                       QgsFeature, QgsGeometry, QgsFillSymbol, QgsSingleSymbolRenderer)
from qgis.PyQt.QtWidgets import QMessageBox, QInputDialog
from shapely.geometry import MultiPoint, MultiLineString
from shapely.ops import polygonize, unary_union
import scipy.spatial


class EmprisePointsTool:
    """
    Classe qui représente l'outil d'emprise des points.
    Cette classe permet de calculer l'emprise en utilisant une méthode alpha shape sur une couche de points.
    Elle génère un polygone qui représente la zone de l'emprise entourant les points sélectionnés ou tous les points d'une couche.
    """
    def __init__(self, parent=None):
        """
        Initialise l'outil avec le widget parent.

        Args:
            parent: widget parent (pour les messages et les boîtes de dialog).
        """
        self.parent = parent

    def run(self, layer, alpha):
        """
        Exécute l'outil d'emprise sur la couche de points spécifiée avec le paramètre alpha donné.

        Args:
            layer (QgsVectorLayer): La couche de points sur laquelle l'emprise doit être calculée.
            alpha (float): Le paramètre alpha utilisé pour le calcul de l'alpha shape.
        """
        ########################################
        # Récupération des points pour l'emprise
        ########################################

        # Vérification du type de couche pour s'assurer qu'elle est une couche de points.
        if not layer or layer.geometryType() != QgsWkbTypes.PointGeometry:
            QMessageBox.critical(self.parent, "EmprisePoint", "Veuillez sélectionner une couche de points active.")
            return

        # Récupération des points sélectionnés ou de tous les points de la couche.
        if layer.selectedFeatureCount() > 0:
            entite_pour_emprise = [points_selec for points_selec in layer.selectedFeatures()]  # Points sélectionnés
        else:
            entite_pour_emprise = [all_points for all_points in layer.getFeatures()]  # Tous les points

        # Vérification du nombre de points pour la création d'un polygone.
        if len(entite_pour_emprise) < 3:
            QMessageBox.critical(self.parent, "EmprisePoint", "3 points pour un polygone")
            return

        ##########################################
        # Préparation et calcul pour la fonction alpha_shape
        ##########################################

        # Conversion des géométries des entités en tuples de coordonnées.
        liste_points = []
        for entite in entite_pour_emprise:
            point = entite.geometry().asPoint()
            x = point.x()
            y = point.y()
            liste_points.append((x, y))

        # Échantillonnage aléatoire de 500 points si la couche contient un grand nombre de points.
        sample_points = random.sample(liste_points, min(500, len(liste_points)))

        # Calcul de la distance moyenne entre les points échantillonnés.
        distances = []
        for p1, p2 in combinations(sample_points, 2):
            distances.append(np.linalg.norm(np.array(p1) - np.array(p2)))  # Calcul de distances
        distance_moyenne = np.mean(distances) if distances else 0

        # Calcul du facteur alpha basé sur la distance moyenne.
        facteur_alpha = alpha / distance_moyenne if distance_moyenne > 0 else 1.0

        try:
            # Calcul de l'emprise en utilisant la fonction alphashape.
            emprise_coord_points_polygon = alphashape(liste_points, facteur_alpha)
        except Exception as e:
            QMessageBox.critical(self.parent, "EmprisePoint", f"Erreur lors du calcul de l'alpha shape: {e}")
            return

        # Extraction des coordonnées du polygone représentant l'emprise.
        coord_polygon = emprise_coord_points_polygon.wkt

        ##########################################
        # Création du polygone
        ##########################################

        # Demande à l'utilisateur de nommer la couche de polygone créée.
        nom_couche, ok = QInputDialog.getText(
            self.parent,
            "Couches d'emprise",
            "Donner un nom à votre couche :"
        )
        if not ok:
            return

        # Création de la couche vectorielle pour le polygone.
        couche_polygon_emprise = QgsVectorLayer("Polygon?crs=" + layer.crs().authid(), nom_couche, "memory")
        provider = couche_polygon_emprise.dataProvider()
        # Création d'une nouvelle entité pour le polygone avec ses coordonnées.
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromWkt(coord_polygon))
        provider.addFeatures([feat])
        couche_polygon_emprise.updateExtents()

        # Définition de la symbologie du polygone (couleur, transparence, contour).
        symbologie = QgsFillSymbol.createSimple({
            'color': '255,0,0,100',  # couleur rouge avec transparence
            'outline_color': '255,0,0',  # contour rouge
            'outline_width': '1.0'  # Épaisseur du contour
        })

        # Application de la symbologie à la couche.
        rendu_symbo_couche = QgsSingleSymbolRenderer(symbologie)
        couche_polygon_emprise.setRenderer(rendu_symbo_couche)

        # Ajout de la couche au projet QGIS.
        QgsProject.instance().addMapLayer(couche_polygon_emprise)


        # Zoom sur l'étendue de la nouvelle couche dans le canevas.
        canvas = self.parent.canvas
        canvas.setExtent(couche_polygon_emprise.extent())
        canvas.refresh()

        # Notification de la réussite de la création du polygone.
        QMessageBox.information(self.parent, "EmprisePoint", "Polygone d'emprise créé avec succès.")


def Ep(parent, layer, alpha):
    """
    Fonction pour démarrer l'outil EmprisePointsTool.

    Args:
        parent: Le widget parent (par exemple, self dans votre classe principale).
        layer: La couche sélectionnée sur laquelle travailler.
        alpha: Le paramètre alpha utilisé pour le calcul de l'alpha shape.

    """
    try:
        tool = EmprisePointsTool(parent)
        tool.run(layer, alpha)
    except Exception as e:
        QMessageBox.critical(parent, "Erreur", f"Une erreur est survenue : {e}")

