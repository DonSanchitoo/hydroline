# prolongement.py

"""
Module pour prolonger les profils en dehors des zones bathymétriques en utilisant les données MNT ou TIN.
Ce script permet de générer des points le long des profils en prolongeant les lignes existantes,
en tenant compte de la pente du terrain pour ajuster l'espacement des points (pour MNT raster),
ou en ajoutant des points aux intersections avec les arêtes du maillage (pour TIN).
"""

import os

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox
)
from qgis._core import QgsLineString
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsMeshLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsFields,
    QgsFeatureRequest,
    QgsSpatialIndex,
    QgsCoordinateReferenceSystem,
    QgsRaster,
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext
)
import processing
from qgis.core import (
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingFeatureSourceDefinition
)


# Obtenez le chemin du fichier actuel
plugin_dir = os.path.dirname(__file__)


class DialogueSelectionCouches(QDialog):
    """
    Boîte de dialogue pour permettre à l'utilisateur de sélectionner les couches nécessaires au traitement.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Sélectionnez les couches')

        layout_principal = QVBoxLayout()

        self.combobox_mnt = QComboBox()
        self.combobox_mnt.addItems([
            couche.name()
            for couche in QgsProject.instance().mapLayers().values()
            if isinstance(couche, (QgsRasterLayer, QgsMeshLayer))
        ])
        layout_principal.addWidget(QLabel('Sélectionnez le raster MNT ou le TIN :'))
        layout_principal.addWidget(self.combobox_mnt)

        self.combobox_points_bathy = QComboBox()
        self.combobox_points_bathy.addItems([
            couche.name()
            for couche in QgsProject.instance().mapLayers().values()
            if isinstance(couche, QgsVectorLayer) and couche.geometryType() == QgsWkbTypes.PointGeometry
        ])
        layout_principal.addWidget(QLabel('Sélectionnez la couche de points bathymétriques :'))
        layout_principal.addWidget(self.combobox_points_bathy)

        self.combobox_profils_traces = QComboBox()
        self.combobox_profils_traces.addItems([
            couche.name()
            for couche in QgsProject.instance().mapLayers().values()
            if isinstance(couche, QgsVectorLayer) and couche.geometryType() == QgsWkbTypes.LineGeometry
        ])
        layout_principal.addWidget(QLabel('Sélectionnez la couche de profils tracés :'))
        layout_principal.addWidget(self.combobox_profils_traces)

        bouton_ok = QPushButton('OK')
        bouton_ok.clicked.connect(self.accept)
        layout_principal.addWidget(bouton_ok)

        self.setLayout(layout_principal)


class ProlongementDesProfils:
    """
    Classe principale pour le traitement de prolongement des profils.
    """

    def __init__(self):
        """
        Initialise les attributs nécessaires pour le traitement.
        """
        self.couche_mnt = None
        self.couche_points = None
        self.couche_lignes = None
        self.champs = None
        self.crs = QgsCoordinateReferenceSystem('EPSG:2154')
        self.couche_points_nouveaux = None
        self.fournisseur_donnees = None
        self.index_points_existants = None
        self.index_objectid = None
        self.index_z = None
        self.index_abscisse_proj = None
        self.mnt_est_raster = True
        self.nouveaux_points_par_ligne = {}
        self.min_espacement_initial = 0.5
        self.max_espacement_initial = 2.0
        self.k_initial = 500
        self.lignes_depassees = []
        self.tous_nouveaux_points = []

    def executer(self):
        """
        Lance le processus complet de prolongement des profils.
        """
        if not self.afficher_dialogue_selection_couches():
            return

        self.initialiser_couches()
        self.creer_nouvelle_couche()
        self.ajouter_points_existants()
        self.parcourir_lignes_profil()
        if self.mnt_est_raster:
            self.ajuster_densite()
        self.attribuer_objectid_aux_nouveaux_points()
        self.ajouter_points_a_la_couche()
        self.finaliser()

    def afficher_dialogue_selection_couches(self):
        """
        Affiche la boîte de dialogue pour sélectionner les couches.

        Returns:
        bool: True si l'utilisateur a validé, False sinon.
        """
        dialogue = DialogueSelectionCouches()
        if dialogue.exec_() == QDialog.Accepted:
            nom_couche_mnt = dialogue.combobox_mnt.currentText()
            nom_couche_points = dialogue.combobox_points_bathy.currentText()
            nom_couche_lignes = dialogue.combobox_profils_traces.currentText()

            self.couche_mnt = QgsProject.instance().mapLayersByName(nom_couche_mnt)[0]
            self.couche_points = QgsProject.instance().mapLayersByName(nom_couche_points)[0]
            self.couche_lignes = QgsProject.instance().mapLayersByName(nom_couche_lignes)[0]

            # Vérifiez si le MNT est un raster ou un TIN
            if isinstance(self.couche_mnt, QgsRasterLayer):
                self.mnt_est_raster = True
            elif isinstance(self.couche_mnt, QgsMeshLayer):
                self.mnt_est_raster = False
            else:
                QMessageBox.warning(
                    None,
                    'Type de couche non supporté',
                    'La couche MNT sélectionnée n\'est ni un raster ni un TIN.'
                )
                return False

            return True
        else:
            return False

    def initialiser_couches(self):
        """
        Initialise les couches et les champs nécessaires.
        """
        self.champs = self.couche_points.fields()

    def creer_nouvelle_couche(self):
        """
        Crée une nouvelle couche en mémoire pour les nouveaux points.
        """
        self.couche_points_nouveaux = QgsVectorLayer(f'Point?crs={self.crs.authid()}', 'Points_Combinés', 'memory')
        self.fournisseur_donnees = self.couche_points_nouveaux.dataProvider()
        self.fournisseur_donnees.addAttributes(self.champs)
        self.couche_points_nouveaux.updateFields()

    def ajouter_points_existants(self):
        """
        Ajoute les points existants de la couche de points à la nouvelle couche.
        """
        elements_existants = list(self.couche_points.getFeatures())
        self.fournisseur_donnees.addFeatures(elements_existants)

        self.index_points_existants = QgsSpatialIndex(self.couche_points.getFeatures())

        self.index_objectid = self.couche_points.fields().indexFromName('OBJECTID')
        self.index_z = self.couche_points.fields().indexFromName('Z')
        self.index_abscisse_proj = self.couche_points.fields().indexFromName('Absc_proj')
        if self.index_objectid == -1 or self.index_z == -1 or self.index_abscisse_proj == -1:
            raise ValueError("Le champ OBJECTID, Z ou Absc_proj n'est pas disponible dans la couche de points.")

    def parcourir_lignes_profil(self):
        """
        Traite chaque profil de la couche par itération pour générer les nouveaux points le long des segments.
        """
        total_lignes = self.couche_lignes.featureCount()
        compteur_lignes = 0

        for ligne in self.couche_lignes.getFeatures():
            compteur_lignes += 1
            ligne_id = ligne.id()
            nouveaux_points_ligne = self.traiter_ligne(ligne)

            self.nouveaux_points_par_ligne[ligne_id] = nouveaux_points_ligne

            if self.mnt_est_raster and len(nouveaux_points_ligne) > 400:
                self.lignes_depassees.append(ligne_id)

            self.tous_nouveaux_points.extend(nouveaux_points_ligne)

    def traiter_ligne(self, ligne):
        """
        Traite une ligne spécifique pour générer les nouveaux points.

        Args:
        ligne (QgsFeature): La ligne à traiter.

        Returns:
        list: Liste des nouveaux points générés pour la ligne.
        """
        nouveaux_points_ligne = []

        geom_ligne = ligne.geometry()

        requete = QgsFeatureRequest().setFilterRect(geom_ligne.boundingBox())
        points_proches = [
            pt for pt in self.couche_points.getFeatures(requete)
            if geom_ligne.interpolate(geom_ligne.lineLocatePoint(pt.geometry())).distance(pt.geometry()) < 1e-6
        ]

        if not points_proches:
            segments_a_traiter = [geom_ligne]
        else:
            valeurs_abscisse_proj = [pt.attributes()[self.index_abscisse_proj] for pt in points_proches]

            points_abscisse_zero = [pt for pt in points_proches if pt.attributes()[self.index_abscisse_proj] == 0]
            abscisse_proj_max = max(valeurs_abscisse_proj)
            points_abscisse_max = [pt for pt in points_proches if pt.attributes()[self.index_abscisse_proj] == abscisse_proj_max]

            if not points_abscisse_zero or not points_abscisse_max:
                segments_a_traiter = [geom_ligne]
            else:
                positions_along_line_zero = [geom_ligne.lineLocatePoint(pt.geometry()) for pt in points_abscisse_zero]
                positions_along_line_max = [geom_ligne.lineLocatePoint(pt.geometry()) for pt in points_abscisse_max]

                debut_bathy = min(positions_along_line_zero)
                fin_bathy = max(positions_along_line_max)

                if debut_bathy > fin_bathy:
                    debut_bathy, fin_bathy = fin_bathy, debut_bathy

                longueur_totale = geom_ligne.length()

                segments_a_traiter = []
                if debut_bathy > 0:
                    segment_avant = self.extraire_sous_ligne(geom_ligne, 0, debut_bathy)
                    if segment_avant:
                        segments_a_traiter.append(segment_avant)
                if fin_bathy < longueur_totale:
                    segment_apres = self.extraire_sous_ligne(geom_ligne, fin_bathy, longueur_totale)
                    if segment_apres:
                        segments_a_traiter.append(segment_apres)

        for segment_geom in segments_a_traiter:
            if self.mnt_est_raster:
                nouveaux_points_segment = self.traiter_segment_raster(segment_geom)
            else:
                nouveaux_points_segment = self.traiter_segment_tin(segment_geom)
            nouveaux_points_ligne.extend(nouveaux_points_segment)

        return nouveaux_points_ligne

    def extraire_sous_ligne(self, geom_ligne, distance_debut, distance_fin):
        """
        Extrait une sous-partie de la ligne entre deux distances données, en conservant les valeurs Z.

        Args:
        geom_ligne (QgsGeometry): La géométrie de la ligne d'origine.
        distance_debut (float): Distance de début sur la ligne.
        distance_fin (float): Distance de fin sur la ligne.

        Returns:
        QgsGeometry: La sous-partie de la ligne correspondant aux distances, avec valeurs Z conservées.
        """
        longueur_ligne = geom_ligne.length()
        if distance_debut >= longueur_ligne or distance_fin <= 0 or distance_debut >= distance_fin:
            return None

        if distance_debut < 0:
            distance_debut = 0
        if distance_fin > longueur_ligne:
            distance_fin = longueur_ligne

        new_line = []
        total_length = 0.0

        # Utiliser un itérateur de vertices pour parcourir la géométrie et conserver les valeurs Z
        iter_vertices = geom_ligne.vertices()
        prev_point = next(iter_vertices, None)
        if prev_point is None:
            return None

        while True:
            curr_point = next(iter_vertices, None)
            if curr_point is None:
                break

            segment = QgsGeometry.fromPolyline([prev_point, curr_point])
            seg_length = segment.length()
            seg_start = total_length
            seg_end = total_length + seg_length

            if seg_end < distance_debut:
                total_length += seg_length
                prev_point = curr_point
                continue
            if seg_start > distance_fin:
                break

            # Segment qui chevauche l'intervalle
            start_frac = 0.0
            end_frac = 1.0
            if seg_start < distance_debut:
                start_frac = (distance_debut - seg_start) / seg_length
            if seg_end > distance_fin:
                end_frac = (distance_fin - seg_start) / seg_length

            start_point = segment.interpolate(start_frac * seg_length).asPoint()
            end_point = segment.interpolate(end_frac * seg_length).asPoint()

            if not new_line or new_line[-1] != start_point:
                new_line.append(start_point)
            new_line.append(end_point)

            total_length += seg_length
            prev_point = curr_point

            if total_length >= distance_fin:
                break

        if len(new_line) >= 2:
            # Construire la nouvelle géométrie en conservant les valeurs Z
            line_string = QgsLineString(new_line)
            sous_ligne = QgsGeometry(line_string)
            return sous_ligne
        else:
            return None

    def traiter_segment_raster(self, geom_segment):
        """
        Traite un segment pour générer des points le long de celui-ci en fonction de la pente (MNT raster).

        Args:
        geom_segment (QgsGeometry): La géométrie du segment à traiter.

        Returns:
        list: Liste des nouveaux points générés pour le segment.
        """
        nouveaux_points_segment = []
        longueur_segment = geom_segment.length()
        if longueur_segment == 0:
            return nouveaux_points_segment

        distance_parcourue = 0.0
        point_geom_courant = geom_segment.interpolate(distance_parcourue)
        point_courant = point_geom_courant.asPoint()
        identifiant_mnt = self.couche_mnt.dataProvider().identify(point_courant, QgsRaster.IdentifyFormatValue)
        if not identifiant_mnt.isValid():
            return nouveaux_points_segment
        valeurs_mnt = identifiant_mnt.results()
        if not valeurs_mnt:
            return nouveaux_points_segment
        z_precedent = list(valeurs_mnt.values())[0]

        while distance_parcourue <= longueur_segment:
            point_geom_courant = geom_segment.interpolate(distance_parcourue)
            point_courant = point_geom_courant.asPoint()
            identifiant_mnt = self.couche_mnt.dataProvider().identify(point_courant, QgsRaster.IdentifyFormatValue)
            if not identifiant_mnt.isValid():
                break
            valeurs_mnt = identifiant_mnt.results()
            if not valeurs_mnt:
                break
            z_courant = list(valeurs_mnt.values())[0]

            difference_elevation = abs(z_courant - z_precedent)
            distance_horizontale = max(distance_parcourue, 0.0001)
            pente = difference_elevation / distance_horizontale

            espacement = max(
                self.min_espacement_initial,
                min(self.max_espacement_initial, self.max_espacement_initial / (1 + self.k_initial * pente))
            )

            feature_point = QgsFeature()
            feature_point.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point_courant)))
            attributs = [None] * len(self.champs)
            attributs[self.index_objectid] = None
            attributs[self.index_z] = z_courant
            feature_point.setAttributes(attributs)
            nouveaux_points_segment.append(feature_point)

            distance_parcourue += espacement
            z_precedent = z_courant

            if distance_parcourue > longueur_segment:
                break

        return nouveaux_points_segment

    def traiter_segment_tin(self, geom_segment):
        """
        Traite un segment pour générer des points aux intersections avec les arêtes du TIN.

        Args:
        geom_segment (QgsGeometry): La géométrie du segment à traiter.

        Returns:
        list: Liste des nouveaux points générés pour le segment.
        """
        nouveaux_points_segment = []

        # Utiliser l'algorithme 'native:exportmeshedges' pour extraire les arêtes du maillage
        params = {
            'INPUT': self.couche_mnt,
            'DATASET_GROUPS': [],
            'DATASET_TIME': {'type': 'static'},
            'VECTOR_OPTION': 0,
            'OUTPUT': 'TEMPORARY_OUTPUT'  # Sortie en mémoire
        }

        result = processing.run('native:exportmeshedges', params)
        edges_layer = result['OUTPUT']

        # Créer un index spatial pour les arêtes
        index_edges = QgsSpatialIndex(edges_layer.getFeatures())

        # Récupérer les arêtes proches du segment
        bbox_segment = geom_segment.boundingBox()
        edge_ids = index_edges.intersects(bbox_segment)

        if not edge_ids:
            return nouveaux_points_segment

        # Récupérer les arêtes pertinentes
        requete = QgsFeatureRequest(edge_ids)
        edges_features = [edge for edge in edges_layer.getFeatures(requete)]

        # Parcourir chaque arête et vérifier l'intersection avec le segment
        for edge in edges_features:
            geom_edge = edge.geometry()
            intersection = geom_segment.intersection(geom_edge)
            if not intersection.isEmpty():
                # Selon le type de géométrie résultante, extraire le(s) point(s) d'intersection
                if intersection.type() == QgsWkbTypes.PointGeometry:
                    points_intersection = [intersection.asPoint()]
                elif intersection.type() == QgsWkbTypes.MultiPointGeometry:
                    points_intersection = intersection.asMultiPoint()
                elif intersection.type() == QgsWkbTypes.LineGeometry:
                    # Si l'intersection est une ligne (colinéarité), vous pouvez gérer cela si nécessaire
                    continue
                else:
                    continue

                for point in points_intersection:
                    # Obtenir la valeur Z au point d'intersection
                    z_value = self.obtenir_z_tin(point)
                    if z_value is None:
                        continue

                    feature_point = QgsFeature()
                    feature_point.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point)))
                    attributs = [None] * len(self.champs)
                    attributs[self.index_objectid] = None
                    attributs[self.index_z] = z_value
                    feature_point.setAttributes(attributs)
                    nouveaux_points_segment.append(feature_point)

        return nouveaux_points_segment

    def obtenir_z_tin(self, point_xy):
        """
        Obtient la valeur Z du TIN au point donné.

        Args:
        point_xy (QgsPointXY): Le point pour lequel obtenir la valeur Z.

        Returns:
        float: La valeur Z, ou None si non disponible.
        """
        # Utiliser le dataProvider pour identifier la valeur Z au point donné
        mesh_dp = self.couche_mnt.dataProvider()
        z_value, ok = mesh_dp.sample(point_xy, -1)  # -1 pour la valeur de temps par défaut
        if not ok:
            return None
        return z_value

    def ajuster_densite(self):
        """
        Ajuste la densité des points si certaines lignes dépassent le nombre maximal de points (pour MNT raster).
        """
        total_points_initial = len(self.tous_nouveaux_points)

        if self.lignes_depassees:
            reponse = QMessageBox.question(
                None,
                'Densité de points excessive',
                "On dépasse les 400 points ajoutés par polyligne plusieurs fois. Voulez-vous ajuster la densité ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reponse == QMessageBox.Yes:
                nouvelle_taille_par_ligne = {}
                for ligne_id in self.lignes_depassees:
                    requete = QgsFeatureRequest(ligne_id)
                    ligne = next(self.couche_lignes.getFeatures(requete))

                    self.min_espacement_initial = 1.0
                    self.max_espacement_initial = 6.0

                    nouveaux_points_ligne = self.traiter_ligne(ligne)

                    self.nouveaux_points_par_ligne[ligne_id] = nouveaux_points_ligne
                    nouvelle_taille_par_ligne[ligne_id] = len(nouveaux_points_ligne)

                self.tous_nouveaux_points = []
                for points_ligne in self.nouveaux_points_par_ligne.values():
                    self.tous_nouveaux_points.extend(points_ligne)

                total_points_final = len(self.tous_nouveaux_points)
                difference_points = total_points_initial - total_points_final

                QMessageBox.information(
                    None,
                    'Réduction du nombre de points',
                    f'On passe de {total_points_initial} points à {total_points_final} points, soit une réduction de {difference_points} points.'
                )

    def attribuer_objectid_aux_nouveaux_points(self):
        """
        Assigne des valeurs OBJECTID aux nouveaux points générés.
        """
        max_objectid = 0
        for feature in self.couche_points.getFeatures():
            objectid = feature.attributes()[self.index_objectid]
            if objectid is not None and objectid > max_objectid:
                max_objectid = objectid

        for idx, feature in enumerate(self.tous_nouveaux_points):
            feature.setAttribute(self.index_objectid, max_objectid + idx + 1)

    def ajouter_points_a_la_couche(self):
        """
        Ajoute les nouveaux points à la couche en mémoire.
        """
        self.fournisseur_donnees.addFeatures(self.tous_nouveaux_points)
        self.couche_points_nouveaux.updateExtents()

    def finaliser(self):
        """
        Finalise le traitement en ajoutant la nouvelle couche au projet.
        """
        QgsProject.instance().addMapLayer(self.couche_points_nouveaux)
        QMessageBox.information(None, 'Traitement terminé', 'Le traitement est terminé.')


def main():
    """
    Point d'entrée du script.
    """
    traitement = ProlongementDesProfils()
    traitement.executer()


# Appeler la fonction main pour exécuter le script
if __name__ == '__main__':
    main()