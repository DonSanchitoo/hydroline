# utils/undo_manager.py

from qgis.core import (
    QgsProject,
    QgsProcessingFeedback,
    QgsField,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPoint,
    QgsCoordinateReferenceSystem,
    QgsMapLayer,
    QgsWkbTypes,
    edit
)


class UndoManager:
    """
    Gestionnaire d'annulation pour enregistrer et annuler des actions dans une pile.

    Attributes
    ----------
    undo_stack : list
        Liste des actions pouvant être annulées.

    Methods
    -------
    add_action(action)
        Ajoute une action à la pile d'annulation.
    can_undo()
        Vérifie si des actions peuvent être annulées.
    undo()
        Annule la dernière action ajoutée à la pile.
    """

    def __init__(self):
        """
        Initialise le gestionnaire d'annulation avec une pile vide.
        """
        self.undo_stack = []

    def add_action(self, action):
        """
        Ajoute une action à la pile d'annulation.

        Parameters
        ----------
        action : AddPointsAction
            Action à ajouter à la pile.
        """

        self.undo_stack.append(action)

    def can_undo(self):
        """
        Vérifie si des actions peuvent être annulées.

        Returns
        -------
        bool
            True si des actions sont disponibles dans la pile pour annulation, False sinon.
        """

        return bool(self.undo_stack)

    def undo(self):
        """
        Annule la dernière action ajoutée à la pile.

        Notes
        -----
        Affiche un message si aucune action n'est disponible pour annulation.
        """

        if self.undo_stack:
            action = self.undo_stack.pop()
            action.undo()
        else:
            print("Aucune action à annuler.")


class AddPointsAction:
    """
    Action pour ajouter des points à une polyligne ou un tracé libre, permettant l'annulation.

    Attributes
    ----------
    outil : object
        L'outil associé à cette action.
    points : list of QgsPoint
        Liste des points ajoutés par cette action.
    mode : str
        Mode de l'action, soit 'normal' pour une polyligne confirmée, soit 'trace_libre'.

    Methods
    -------
    undo()
        Annule l'ajout de points, restaurant l'état précédent de la polyligne ou du tracé libre.
    """

    def __init__(self, outil, points, mode='normal'):
        """
        Initialise l'action en enregistrant l'outil et les points à ajouter.

        Parameters
        ----------
        outil : object
            L'outil associé à cette action.
        points : list of QgsPoint
            Liste des points ajoutés par cette action.
        mode : str, optional
            Mode de l'action, 'normal' par défaut.
        """

        self.outil = outil
        self.points = points  # Liste des points ajoutés
        self.mode = mode

    def undo(self):
        """
        Annule l'ajout de points, restaurant l'état précédent de la polyligne ou du tracé libre.

        Notes
        -----
        Supprime les points ajoutés des listes associées dans l'outil et met à jour les graphiques.
        """

        if self.mode == 'trace_libre':
            for p in reversed(self.points):
                if p in self.outil.points_trace_libre:
                    self.outil.points_trace_libre.remove(p)
            self.outil.bande_trace_libre.reset(QgsWkbTypes.LineGeometry)
            for p in self.outil.points_trace_libre:
                self.outil.bande_trace_libre.addPoint(p)
        else:
            for p in reversed(self.points):
                if p in self.outil.liste_points:
                    self.outil.liste_points.remove(p)
            if self.outil.liste_points:
                self.outil.polyligne_confirmee = QgsGeometry.fromPolyline(self.outil.liste_points)
                self.outil.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
                self.outil.bande_confirmee.addGeometry(self.outil.polyligne_confirmee, None)
            else:
                self.outil.polyligne_confirmee = None
                self.outil.bande_confirmee.reset(QgsWkbTypes.LineGeometry)
            self.outil.chemin_dynamique = None
            self.outil.bande_dynamique.reset(QgsWkbTypes.LineGeometry)
