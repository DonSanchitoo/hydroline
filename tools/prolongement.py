"""
tools/prolongement.py

Module pour prolonger les profils en dehors des zones bathymétriques en utilisant les données MNT ou TIN.
Ce script permet de générer des points le long des profils en prolongeant les lignes existantes,
en tenant compte de la pente du terrain pour ajuster l'espacement des points (pour MNT raster),
ou en ajoutant des points aux intersections avec les arêtes du maillage (pour TIN).
"""

import os
import logging
import processing
from qgis.PyQt.QtWidgets import QMessageBox
from qgis._core import QgsLineString
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsMeshLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsFeatureRequest,
    QgsSpatialIndex,
    QgsCoordinateReferenceSystem,
    QgsRaster,
    QgsWkbTypes
)
from PyQt5.QtWidgets import QDialog
from ..dialogs.choix_couches_dialog import DialogueSelectionCouchesPourProlongement

# Configuration du logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Obtenez le chemin du fichier actuel
plugin_dir = os.path.dirname(__file__)

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
        self.couche_emprise = None  # Nouvelle couche d'emprise
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
        try:
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
        except Exception as e:
            QMessageBox.critical(None, 'Erreur', f'Une erreur est survenue : {str(e)}')
            logging.error(f'Erreur lors de l\'exécution: {str(e)}')

    def afficher_dialogue_selection_couches(self):
        """
        Affiche la boîte de dialogue pour sélectionner les couches.

        Returns:
        bool: True si l'utilisateur a validé, False sinon.
        """
        dialogue = DialogueSelectionCouchesPourProlongement()
        if dialogue.exec_() == QDialog.Accepted:
            nom_couche_mnt = dialogue.combobox_mnt.currentText()
            nom_couche_points = dialogue.combobox_points_bathy.currentText()
            nom_couche_lignes = dialogue.combobox_profils_traces.currentText()
            nom_couche_emprise = dialogue.combobox_emprise.currentText()

            self.couche_mnt = QgsProject.instance().mapLayersByName(nom_couche_mnt)[0]
            self.couche_points = QgsProject.instance().mapLayersByName(nom_couche_points)[0]
            self.couche_lignes = QgsProject.instance().mapLayersByName(nom_couche_lignes)[0]

            if nom_couche_emprise != '--- Aucune ---':
                self.couche_emprise = QgsProject.instance().mapLayersByName(nom_couche_emprise)[0]
            else:
                self.couche_emprise = None

            # Vérifier si le MNT est un raster ou un TIN
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

        self.index_objectid = self.couche_points.fields().indexFromName('OBJECTID')
        self.index_z = self.couche_points.fields().indexFromName('Z')
        self.index_abscisse_proj = self.couche_points.fields().indexFromName('Absc_proj')

        if self.index_objectid == -1 or self.index_z == -1:
            raise ValueError("Le champ OBJECTID ou Z n'est pas disponible dans la couche de points.")

        if self.couche_emprise is None and self.index_abscisse_proj == -1:
            QMessageBox.warning(
                None,
                'Champ ou couche manquant',
                'Le champ Absc_proj est absent de la couche de points, et aucune couche d\'emprise n\'a été sélectionnée. '
                'Veuillez sélectionner une couche d\'emprise dans la boîte de dialogue et réessayer.'
            )
            raise ValueError("Le champ Absc_proj est absent, et aucune couche d'emprise n'a été fournie.")

        # Construire les index pour les champs (si nécessaires)
        # Exemple: vous pouvez ajouter des index pour accélérer les recherches si besoin

    def creer_nouvelle_couche(self):
        """
        Crée une nouvelle couche en mémoire pour les nouveaux points.
        """
        self.couche_points_nouveaux = QgsVectorLayer(f'Point?crs={self.crs.authid()}', 'Points_Combinés', 'memory')
        self.fournisseur_donnees = self.couche_points_nouveaux.dataProvider()
        self.fournisseur_donnees.addAttributes(self.champs)
        self.couche_points_nouveaux.updateFields()
        logging.info('Nouvelle couche de points combinés créée en mémoire.')

    def ajouter_points_existants(self):
        """
        Ajoute les points existants de la couche de points à la nouvelle couche.
        """
        elements_existants = list(self.couche_points.getFeatures())
        self.fournisseur_donnees.addFeatures(elements_existants)
        logging.info(f'{len(elements_existants)} points existants ajoutés à la nouvelle couche.')

        self.index_points_existants = QgsSpatialIndex(self.couche_points.getFeatures())

    def parcourir_lignes_profil(self):
        """
        Traite chaque profil de la couche par itération pour générer les nouveaux points le long des segments.
        """
        total_lignes = self.couche_lignes.featureCount()
        compteur_lignes = 0
        logging.info(f'Commence le traitement des {total_lignes} lignes de profil.')

        for ligne in self.couche_lignes.getFeatures():
            compteur_lignes += 1
            ligne_id = ligne.id()
            logging.debug(f'Traitement de la ligne ID: {ligne_id}')
            nouveaux_points_ligne = self.traiter_ligne(ligne)

            self.nouveaux_points_par_ligne[ligne_id] = nouveaux_points_ligne

            if self.mnt_est_raster and len(nouveaux_points_ligne) > 400:
                self.lignes_depassees.append(ligne_id)
                logging.warning(f'Ligne ID {ligne_id} dépasse le nombre maximal de points (400).')

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

        # Si une couche d'emprise est sélectionnée, on l'utilise pour déterminer les segments à traiter
        if self.couche_emprise is not None:
            segments_a_traiter = []

            # Combiner toutes les géométries de l'emprise
            emprise_geom = QgsGeometry.unaryUnion([feat.geometry() for feat in self.couche_emprise.getFeatures()])
            logging.debug(f'Combinaison des géométries de l\'emprise.')

            # Découper la ligne en parties à l'intérieur et à l'extérieur de l'emprise
            difference = geom_ligne.difference(emprise_geom)
            logging.debug(f'Découpage de la ligne ID {ligne.id()} avec l\'emprise.')

            if difference.isEmpty():
                # La ligne est entièrement à l'intérieur de l'emprise, aucun nouveau point à ajouter
                logging.debug(f'La ligne ID {ligne.id()} est entièrement à l\'intérieur de l\'emprise.')
                return nouveaux_points_ligne
            elif difference.type() == QgsWkbTypes.LineGeometry or difference.type() == QgsWkbTypes.MultiLineGeometry:
                # Les parties en dehors de l'emprise sont les segments à traiter
                if difference.isMultipart():
                    lignes_diff = difference.asMultiPolyline()
                    logging.debug(f'Découpage multipart de la ligne ID {ligne.id()}. Segments trouvés: {len(lignes_diff)}.')
                    for ligne_part in lignes_diff:
                        segment_geom = QgsGeometry.fromPolylineXY([QgsPointXY(pt) for pt in ligne_part])
                        segments_a_traiter.append(segment_geom)
                else:
                    segments_a_traiter.append(difference)
                    logging.debug(f'Découpage simple de la ligne ID {ligne.id()}.')
            else:
                # Si le résultat est un point ou autre, on ne traite pas
                logging.debug(f'La ligne ID {ligne.id()} a une différence de type inattendu: {difference.type()}')
                return nouveaux_points_ligne
        elif self.index_abscisse_proj != -1:
            # Si le champ Absc_proj est disponible, on utilise la logique basée sur Absc_proj
            requete = QgsFeatureRequest().setFilterRect(geom_ligne.boundingBox())
            points_proches = [
                pt for pt in self.couche_points.getFeatures(requete)
                if geom_ligne.interpolate(geom_ligne.lineLocatePoint(pt.geometry())).distance(pt.geometry()) < 1e-6
            ]
            logging.debug(f'Requête de points proches pour la ligne ID {ligne.id()}: {len(points_proches)} trouvés.')

            if not points_proches:
                segments_a_traiter = [geom_ligne]
                logging.debug(f'Aucun point proche trouvé pour la ligne ID {ligne.id()}. Traitement de toute la ligne.')
            else:
                valeurs_abscisse_proj = [pt.attributes()[self.index_abscisse_proj] for pt in points_proches]
                points_abscisse_zero = [pt for pt in points_proches if pt.attributes()[self.index_abscisse_proj] == 0]
                abscisse_proj_max = max(valeurs_abscisse_proj)
                points_abscisse_max = [pt for pt in points_proches if pt.attributes()[self.index_abscisse_proj] == abscisse_proj_max]

                if not points_abscisse_zero or not points_abscisse_max:
                    segments_a_traiter = [geom_ligne]
                    logging.debug(f'Points avec Absc_proj = 0 ou Absc_proj_max manquants pour la ligne ID {ligne.id()}. Traitement de toute la ligne.')
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
                            logging.debug(f'Segment avant bathymétrie pour la ligne ID {ligne.id()} ajouté.')
                    if fin_bathy < longueur_totale:
                        segment_apres = self.extraire_sous_ligne(geom_ligne, fin_bathy, longueur_totale)
                        if segment_apres:
                            segments_a_traiter.append(segment_apres)
                            logging.debug(f'Segment après bathymétrie pour la ligne ID {ligne.id()} ajouté.')
        else:
            # Si ni couche d'emprise ni champ Absc_proj, on affiche une erreur (normalement déjà géré dans initialiser_couches)
            logging.debug(f'La ligne ID {ligne.id()} n\'a ni couche d\'emprise ni champ Absc_proj.')
            return nouveaux_points_ligne

        # Traiter chaque segment à traiter
        for segment_geom in segments_a_traiter:
            if self.mnt_est_raster:
                nouveaux_points_segment = self.traiter_segment_raster(segment_geom)
            else:
                nouveaux_points_segment = self.traiter_segment_tin(segment_geom)
            nouveaux_points_ligne.extend(nouveaux_points_segment)

        logging.debug(f'{len(nouveaux_points_ligne)} nouveaux points générés pour la ligne ID {ligne.id()}.')
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

            segment = QgsGeometry.fromPolylineXY([QgsPointXY(prev_point), QgsPointXY(curr_point)])  # MODIFICATION
            seg_length = segment.length()

            if seg_length == 0:
                # Ignorer les segments de longueur nulle
                total_length += seg_length
                prev_point = curr_point
                continue

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

            # S'assurer que les fractions sont valides
            if start_frac > end_frac:
                start_frac, end_frac = end_frac, start_frac

            start_geom = segment.interpolate(start_frac * seg_length)
            end_geom = segment.interpolate(end_frac * seg_length)

            if start_geom.isNull() or end_geom.isNull():
                # Ignorer les interpolations invalides
                total_length += seg_length
                prev_point = curr_point
                continue

            # Assurez-vous que les points sont des QgsPointXY
            start_point = QgsPointXY(start_geom.asPoint())
            end_point = QgsPointXY(end_geom.asPoint())

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
            logging.warning(f'Identification MNT invalide au point: {point_courant}')
            return nouveaux_points_segment
        valeurs_mnt = identifiant_mnt.results()
        if not valeurs_mnt:
            logging.warning(f'Aucune valeur MNT trouvée au point: {point_courant}')
            return nouveaux_points_segment
        z_precedent = list(valeurs_mnt.values())[0]

        # Vérifier que z_precedent n'est pas None
        if z_precedent is None:
            logging.warning(f'Valeur MNT initiale est None au point: {point_courant}')
            return nouveaux_points_segment

        while distance_parcourue <= longueur_segment:
            point_geom_courant = geom_segment.interpolate(distance_parcourue)
            point_courant = point_geom_courant.asPoint()
            identifiant_mnt = self.couche_mnt.dataProvider().identify(point_courant, QgsRaster.IdentifyFormatValue)
            if not identifiant_mnt.isValid():
                logging.warning(f'Identification MNT invalide au point: {point_courant}')
                break
            valeurs_mnt = identifiant_mnt.results()
            if not valeurs_mnt:
                logging.warning(f'Aucune valeur MNT trouvée au point: {point_courant}')
                break
            z_courant = list(valeurs_mnt.values())[0]

            # Vérifier que z_courant n'est pas None
            if z_courant is None:
                logging.warning(f'Valeur MNT est None au point: {point_courant}. Passage au point suivant.')
                # Passer ce point et continuer
                distance_parcourue += self.min_espacement_initial
                z_precedent = z_courant
                continue

            # Calcul de la différence d'élévation
            difference_elevation = abs(z_courant - z_precedent)

            # Calcul de la pente en utilisant l'espacement actuel
            # Utilisation de l'espacement actuel pour une pente plus précise
            pente = difference_elevation / self.min_espacement_initial if self.min_espacement_initial != 0 else 0

            # Calcul de l'espacement basé sur la pente
            espacement = max(
                self.min_espacement_initial,
                min(
                    self.max_espacement_initial,
                    self.max_espacement_initial / (1 + self.k_initial * pente) if (1 + self.k_initial * pente) != 0 else self.max_espacement_initial
                )
            )

            # Créer le nouveau point
            feature_point = QgsFeature()
            feature_point.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point_courant)))
            attributs = [None] * len(self.champs)
            attributs[self.index_objectid] = None
            attributs[self.index_z] = z_courant
            feature_point.setAttributes(attributs)
            nouveaux_points_segment.append(feature_point)
            logging.debug(f'Point ajouté à {point_courant} avec Z={z_courant}')

            # Mettre à jour les variables
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
                    points_intersection = [QgsPointXY(intersection.asPoint())]  # MODIFICATION
                elif intersection.type() == QgsWkbTypes.MultiPointGeometry:
                    points_intersection = [QgsPointXY(pt) for pt in intersection.asMultiPoint()]  # MODIFICATION
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
                    feature_point.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point)))  # MODIFICATION
                    attributs = [None] * len(self.champs)
                    attributs[self.index_objectid] = None
                    attributs[self.index_z] = z_value
                    feature_point.setAttributes(attributs)
                    nouveaux_points_segment.append(feature_point)
                    logging.debug(f'Intersections: Point ajouté à {point} avec Z={z_value}')

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
            logging.warning(f'Échantillonnage MNT échoué au point: {point_xy}')
            return None
        return z_value

    def ajuster_densite(self):
        """
        Ajuste la densité des points si certaines lignes dépassent le nombre maximal de points (pour MNT raster).
        """
        total_points_initial = len(self.tous_nouveaux_points)
        logging.info(f'Nombre total de points générés initialement: {total_points_initial}')

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
                    ligne = next(self.couche_lignes.getFeatures(requete), None)
                    if ligne is None:
                        logging.warning(f'Ligne ID {ligne_id} non trouvée lors de l\'ajustement de densité.')
                        continue

                    # Ajuster les paramètres d'espacement
                    self.min_espacement_initial = 1.0
                    self.max_espacement_initial = 6.0

                    nouveaux_points_ligne = self.traiter_ligne(ligne)
                    self.nouveaux_points_par_ligne[ligne_id] = nouveaux_points_ligne
                    nouvelle_taille_par_ligne[ligne_id] = len(nouveaux_points_ligne)
                    logging.info(f'Ligne ID {ligne_id}: {len(nouveaux_points_ligne)} points après ajustement.')

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
                logging.info(f'Nombre de points après ajustement: {total_points_final}')

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

        logging.info(f'OBJECTID assignés aux nouveaux points, de {max_objectid + 1} à {max_objectid + len(self.tous_nouveaux_points)}.')

    def ajouter_points_a_la_couche(self):
        """
        Ajoute les nouveaux points à la couche en mémoire.
        """
        self.fournisseur_donnees.addFeatures(self.tous_nouveaux_points)
        self.couche_points_nouveaux.updateExtents()
        logging.info(f'{len(self.tous_nouveaux_points)} nouveaux points ajoutés à la couche combinée.')

    def finaliser(self):
        """
        Finalise le traitement en ajoutant la nouvelle couche au projet.
        """
        QgsProject.instance().addMapLayer(self.couche_points_nouveaux)
        QMessageBox.information(None, 'Traitement terminé', 'Le traitement est terminé.')
        logging.info('Nouvelle couche de points combinés ajoutée au projet.')

def main():
    """
    Point d'entrée du script.
    """
    traitement = ProlongementDesProfils()
    traitement.executer()

# Appeler la fonction main pour exécuter le script
if __name__ == '__main__':
    main()