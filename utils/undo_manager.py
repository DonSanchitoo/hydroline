# undo_manager.py

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
    def __init__(self):
        self.undo_stack = []

    def add_action(self, action):
        self.undo_stack.append(action)

    def can_undo(self):
        return bool(self.undo_stack)

    def undo(self):
        if self.undo_stack:
            action = self.undo_stack.pop()
            action.undo()
        else:
            print("Aucune action à annuler.")


class AddPointsAction:
    def __init__(self, outil, points, mode='normal'):
        self.outil = outil
        self.points = points  # Liste des points ajoutés
        self.mode = mode

    def undo(self):
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
