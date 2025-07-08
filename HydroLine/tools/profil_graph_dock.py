"""
tools/profil_graph_dock.py

Module de l'outil GraphZ de visualisation de profil sur polylignes ZM
"""
import os
import tempfile
import webbrowser

from ..external import img2pdf
from ..external.pyqtgraph import PlotWidget
from ..external.pyqtgraph.exporters import ImageExporter
from ..external import pyqtgraph as pg

import numpy as np
import plotly.graph_objects as go
from PyQt5 import QtGui
from osgeo import gdal
from qgis.PyQt.QtCore import Qt, pyqtSignal, QFileInfo
from qgis.PyQt.QtWidgets import (
    QDockWidget, QVBoxLayout, QWidget, QPushButton,
    QComboBox, QLabel, QFileDialog, QMessageBox, QGridLayout
)
from qgis.core import (
    QgsProject, QgsMapLayer, QgsWkbTypes,
    QgsPointXY, QgsGeometry, QgsFeature, QgsVectorLayer, QgsCoordinateTransform
)
from qgis.gui import QgsMapTool, QgsRubberBand


class ProfilGraphDock(QDockWidget):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profil Z")
        self.canvas = canvas

        # Créer le widget principal
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # Création du layout pour les contrôles
        control_layout = QGridLayout()

        # Indice de colonne
        col = 0

        # Menu déroulant pour choisir la couche de polyligne Z
        self.layer_combo_box = QComboBox()
        self.layer_combo_box.addItem("Sélectionner une couche")
        self.populate_layers()
        self.layer_combo_box.currentIndexChanged.connect(self.on_layer_changed)
        control_layout.addWidget(self.layer_combo_box, 0, col + 1)
        col += 2

        # Menu déroulant pour choisir le mode 2D ou 3D
        self.view_mode_combo_box = QComboBox()
        self.view_mode_combo_box.addItem("Choisir un mode")
        self.view_mode_combo_box.addItem("2D")
        self.view_mode_combo_box.addItem("3D")
        self.view_mode_combo_box.currentIndexChanged.connect(self.on_view_mode_changed)
        control_layout.addWidget(self.view_mode_combo_box, 0, col + 1)
        col += 2

        # Menu déroulant pour choisir la couche raster (MNT)
        self.raster_combo_box = QComboBox()
        self.raster_combo_box.addItem("Sélectionner un MNT")
        self.populate_raster_layers()
        self.raster_combo_box.currentIndexChanged.connect(self.on_raster_layer_changed)
        control_layout.addWidget(self.raster_combo_box, 0, col + 1)
        self.raster_combo_box.hide()
        col += 2

        # Bouton pour exporter le graphique en PNG ou PDF
        self.export_button = QPushButton("Exporter")
        self.export_button.clicked.connect(self.export_graph)
        self.export_button.setEnabled(False)
        control_layout.addWidget(self.export_button, 0, col)

        main_layout.addLayout(control_layout)

        # Ajouter PyQtGraph pour le graphique
        self.graph_widget = PlotWidget()
        self.graph_widget.setBackground('w')  # Fond blanc
        self.graph_widget.showGrid(x=True, y=True, alpha=0.3)  # Quadrillage gris clair
        main_layout.addWidget(self.graph_widget)

        # Configurer le layout principal
        main_widget.setLayout(main_layout)
        self.setWidget(main_widget)

        # Initialiser l'outil de carte pour l'identification des entités
        self.map_tool = None
        self.previous_map_tool = None  # Pour stocker l'outil précédent
        self.selected_layer = None
        self.selected_raster_layer = None  # MNT

        # Initialiser pour le suivi du curseur
        self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.rubber_band.setColor(Qt.red)
        self.rubber_band.setWidth(5)

        # Lignes infinies pour le suivi de la souris
        self.cross_vertical_line = pg.InfiniteLine(angle=90, pen=pg.mkPen('k', width=1), name='cross_vertical')
        self.cross_horizontal_line = pg.InfiniteLine(angle=0, pen=pg.mkPen('k', width=1), name='cross_horizontal')
        self.cross_vertical_line.setZValue(10)
        self.cross_horizontal_line.setZValue(10)
        self.graph_widget.addItem(self.cross_vertical_line)
        self.graph_widget.addItem(self.cross_horizontal_line)

        # Étiquettes de texte pour les valeurs X et Y avec fond blanc et texte noir
        self.x_label = pg.TextItem('', anchor=(0, 1), color='k', fill=pg.mkBrush('w'))
        self.y_label = pg.TextItem('', anchor=(1, 0), color='k', fill=pg.mkBrush('w'))
        self.x_label.setZValue(11)
        self.y_label.setZValue(11)
        self.graph_widget.addItem(self.x_label)
        self.graph_widget.addItem(self.y_label)

        self.points = []

    def populate_layers(self):
        """Remplit le combo box avec les couches de polylignes Z disponibles."""
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer and QgsWkbTypes.hasZ(layer.wkbType()):
                self.layer_combo_box.addItem(layer.name())

    def populate_raster_layers(self):
        """Remplit le combo box avec les couches raster (MNT) disponibles."""
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.RasterLayer:
                self.raster_combo_box.addItem(layer.name())

    def on_view_mode_changed(self, index):
        mode = self.view_mode_combo_box.currentText()
        if mode == '3D':
            self.raster_combo_box.show()
        else:
            self.raster_combo_box.hide()

    def on_layer_changed(self, index):
        """Appelée lorsque la couche sélectionnée dans le combo box change."""
        if index == 0:
            # Aucune couche sélectionnée
            self.selected_layer = None
            if self.map_tool is not None:
                self.canvas.unsetMapTool(self.map_tool)
                self.map_tool = None
            return

        layer_name = self.layer_combo_box.currentText()
        layers = QgsProject.instance().mapLayersByName(layer_name)
        if layers:
            self.selected_layer = layers[0]
            # Sauvegarder l'outil de carte actuel
            self.previous_map_tool = self.canvas.mapTool()
            # Configurer l'outil de carte pour identifier les entités sur la couche sélectionnée
            self.map_tool = IdentifyLineTool(self.canvas, self.selected_layer)
            self.map_tool.feature_identified.connect(self.on_feature_identified)
            self.canvas.setMapTool(self.map_tool)
            self.export_button.setEnabled(False)
        else:
            self.selected_layer = None
            if self.map_tool is not None:
                self.canvas.unsetMapTool(self.map_tool)
                self.map_tool = None

    def closeEvent(self, event):
        """Gestion de la fermeture du dock."""
        # Désactiver l'outil de carte
        if self.map_tool is not None:
            self.canvas.unsetMapTool(self.map_tool)
            self.map_tool = None
        # Restaurer l'outil de carte précédent si nécessaire
        if self.previous_map_tool is not None:
            self.canvas.setMapTool(self.previous_map_tool)
            self.previous_map_tool = None
        # Supprimer les éléments graphiques (rubber bands)
        self.rubber_band.hide()
        self.canvas.scene().removeItem(self.rubber_band)
        # Appeler la méthode closeEvent parente
        super().closeEvent(event)

    def on_raster_layer_changed(self, index):
        """Appelée lorsque la couche raster sélectionnée change."""
        if index == 0:
            self.selected_raster_layer = None
        else:
            layer_name = self.raster_combo_box.currentText()
            layers = QgsProject.instance().mapLayersByName(layer_name)
            if layers:
                self.selected_raster_layer = layers[0]
            else:
                self.selected_raster_layer = None

    def show_3d_view(self, feature):
        """Affiche la visualisation 3D."""
        ProfilGraph3D(feature, self.selected_layer, self.selected_raster_layer)

    def on_feature_identified(self, feature):
        """Appelée lorsqu'une polyligne est cliquée sur le canevas."""
        mode = self.view_mode_combo_box.currentText()
        if mode == '2D':
            self.update_graph(feature.geometry())
            self.export_button.setEnabled(True)
        elif mode == '3D':
            if self.selected_raster_layer is None:
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner un MNT pour le mode 3D.")
                return
            self.show_3d_view(feature)

    def update_graph(self, geometry):
        """Met à jour le graphique avec la géométrie donnée."""
        points = list(geometry.vertices())

        if len(points) < 2:
            return

        distances = []
        elevations = []
        cumulative_distance = 0

        for i, point in enumerate(points):
            if i == 0:
                cumulative_distance = 0
            else:
                distance = point.distance(points[i - 1])
                cumulative_distance += distance
            distances.append(cumulative_distance)
            elevations.append(point.z())

        self.distances = distances  # Les valeurs X du graphique
        self.elevations = elevations  # Les valeurs Y du graphique

        # Mise à jour du graphique
        self.graph_widget.clearPlots()
        self.graph_widget.plot(distances, elevations, pen=pg.mkPen('r', width=2))  # Courbe en rouge
        self.graph_widget.setLabel('left', 'Altitude', units='m')
        self.graph_widget.setLabel('bottom', 'Distance cumulée', units='m')
        self.graph_widget.showGrid(x=True, y=True, alpha=0.3)

        # Enregistre les points pour le suivi de la souris
        self.points = points

        # Ajuster les limites de l'axe Y
        y_min = min(elevations)
        y_max = max(elevations)
        if y_min == y_max:
            y_min -= 1
            y_max += 1
        else:
            y_margin = 0.1 * (y_max - y_min)
            y_min -= y_margin
            y_max += y_margin
        self.graph_widget.setYRange(y_min, y_max)

        # Ajuster les limites de l'axe X
        x_min = min(distances)
        x_max = max(distances)
        self.graph_widget.setXRange(x_min, x_max)

        # Définir les limites de la ViewBox pour empêcher le dézoom au-delà des données
        vb = self.graph_widget.getViewBox()
        vb.setLimits(
            xMin=x_min, xMax=x_max, yMin=y_min, yMax=y_max,
            minXRange=(x_max - x_min) * 0.1,
            maxXRange=(x_max - x_min) * 2,
            minYRange=(y_max - y_min) * 0.1,
            maxYRange=(y_max - y_min) * 2
        )

        # Déconnexion des signaux s'ils sont déjà connectés
        try:
            self.graph_widget.scene().sigMouseMoved.disconnect(self.mouse_moved)
            self.graph_widget.scene().sigMouseClicked.disconnect(self.mouse_clicked)
        except TypeError:
            pass  # Les signaux n'étaient pas connectés auparavant

        # Activer le suivi et les clics de la souris
        self.graph_widget.scene().sigMouseMoved.connect(self.mouse_moved)
        self.graph_widget.scene().sigMouseClicked.connect(self.mouse_clicked)

    def mouse_moved(self, evt):
        try:
            pos = evt
            if self.graph_widget.sceneBoundingRect().contains(pos):
                mouse_point = self.graph_widget.plotItem.vb.mapSceneToView(pos)
                x_mouse = mouse_point.x()
                y_mouse = mouse_point.y()

                data_items = self.graph_widget.plotItem.listDataItems()
                if data_items:
                    data_item = data_items[0]
                    x_data, y_data = data_item.getData()
                    if len(x_data) == 0:
                        return
                    x_array = np.array(x_data)
                    y_array = np.array(y_data)

                    # Trouvez l'indice du x le plus proche de x_mouse
                    idx = (np.abs(x_array - x_mouse)).argmin()
                    x_nearest = x_array[idx]
                    y_nearest = y_array[idx]

                    # Mettez à jour les crosshairs
                    self.cross_vertical_line.setPos(x_nearest)
                    self.cross_horizontal_line.setPos(y_nearest)
                    self.cross_vertical_line.show()
                    self.cross_horizontal_line.show()

                    # Obtenez la plage de vues actuelle
                    (x_min, x_max), (y_min, y_max) = self.graph_widget.plotItem.viewRange()

                    # Calculer 10% de la plage pour le décalage
                    x_margin = 0.1 * (x_max - x_min)
                    y_margin = 0.1 * (y_max - y_min)

                    # Ajuster les positions des étiquettes
                    x_label_x = x_nearest
                    x_label_y = y_max - y_margin  # Positionner en haut avec une marge
                    y_label_x = x_min + x_margin  # Positionner à gauche avec une marge
                    y_label_y = y_nearest

                    # S'assurer que les étiquettes restent dans le cadre horizontalement
                    if x_label_x > x_max - x_margin:
                        x_label_x = x_max - x_margin
                    elif x_label_x < x_min + x_margin:
                        x_label_x = x_min + x_margin

                    if y_label_y > y_max - y_margin:
                        y_label_y = y_max - y_margin
                    elif y_label_y < y_min + y_margin:
                        y_label_y = y_min + y_margin

                    # Mettez à jour les étiquettes
                    self.x_label.setPos(x_label_x, x_label_y)
                    self.x_label.setText(f"X : {x_nearest:.2f} m")
                    self.x_label.show()

                    self.y_label.setPos(y_label_x, y_label_y)
                    self.y_label.setText(f"Z : {y_nearest:.2f} m")
                    self.y_label.show()

                    # Mettez à jour le curseur sur la carte pour refléter la position
                    if 0 <= idx < len(self.points):
                        map_point = self.points[idx]
                        self.update_map_cursor(map_point)
                else:
                    # Cachez les crosshairs et les étiquettes s'il n'y a pas de données
                    self.cross_vertical_line.hide()
                    self.cross_horizontal_line.hide()
                    self.x_label.hide()
                    self.y_label.hide()
            else:
                # Cachez les crosshairs et les étiquettes si la souris est en dehors du graphique
                self.cross_vertical_line.hide()
                self.cross_horizontal_line.hide()
                self.x_label.hide()
                self.y_label.hide()
        except Exception as e:
            print(f"Erreur dans mouse_moved : {e}")

    def mouse_clicked(self, evt):
        """Gestion du clic sur le graphique."""
        pos = evt.scenePos()
        if self.graph_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.graph_widget.plotItem.vb.mapSceneToView(pos)
            x_mouse = mouse_point.x()
            y_mouse = mouse_point.y()

            data_items = self.graph_widget.plotItem.listDataItems()
            if data_items:
                data_item = data_items[0]
                x_data, y_data = data_item.getData()
                if len(x_data) == 0:
                    return
                x_array = np.array(x_data)
                y_array = np.array(y_data)

                # Trouvez l'indice du x le plus proche de x_mouse
                idx = (np.abs(x_array - x_mouse)).argmin()
                x_nearest = x_array[idx]
                y_nearest = y_array[idx]

                # Ajouter le point sur la carte
                if 0 <= idx < len(self.points):
                    map_point = self.points[idx]
                    self.set_point_on_map(QgsPointXY(map_point.x(), map_point.y()))

    def set_point_on_map(self, point):
        """Ajoute le point cliqué sur le graphique à la carte QGIS."""
        layers = QgsProject.instance().mapLayersByName('profile_points')
        if layers:
            layer = layers[0]
        else:
            # Créez une nouvelle couche si elle n'existe pas
            crs = QgsProject.instance().crs().authid()
            layer = QgsVectorLayer(f"Point?crs={crs}", "profile_points", "memory")
            QgsProject.instance().addMapLayer(layer)
        provider = layer.dataProvider()
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        provider.addFeatures([feature])
        layer.updateExtents()
        layer.triggerRepaint()

    def update_map_cursor(self, map_point):
        """Met à jour le curseur sur la carte QGIS pour refléter la position sur le graphique."""
        self.rubber_band.reset(QgsWkbTypes.PointGeometry)
        map_point_xy = QgsPointXY(map_point.x(), map_point.y())
        self.rubber_band.addPoint(map_point_xy)
        self.rubber_band.show()

    def export_graph(self):
        """Exporte le graphique actuel en PNG ou PDF sans les éléments interactifs."""
        options = "Image PNG (*.png);;Document PDF (*.pdf)"
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Enregistrer le graphique", "", options
        )
        if file_path:
            # Cacher les crosshairs et les étiquettes avant l'export
            self.cross_vertical_line.hide()
            self.cross_horizontal_line.hide()
            self.x_label.hide()
            self.y_label.hide()

            # Rafraîchir le graphique pour s'assurer que les éléments sont cachés
            QtGui.QApplication.processEvents()

            # Déterminer le chemin du fichier PNG temporaire
            file_info = QFileInfo(file_path)
            if selected_filter == "Image PNG (*.png)":
                png_export_path = file_path
            else:
                # Pour le PDF, on crée d'abord un PNG temporaire
                png_export_path = file_info.path() + '/' + file_info.baseName() + '_temp.png'

            # Exporter le graphique en PNG
            exporter = ImageExporter(self.graph_widget.plotItem)
            exporter.export(png_export_path)

            if selected_filter == "Document PDF (*.pdf)":
                try:
                    # Convertir le PNG en PDF
                    with open(png_export_path, 'rb') as f:
                        img_data = f.read()
                    with open(file_path, 'wb') as f:
                        f.write(img2pdf.convert(img_data))
                    # Supprimer le PNG temporaire
                    os.remove(png_export_path)
                except Exception as e:
                    QMessageBox.warning(self, "Erreur", f"Une erreur s'est produite lors de la conversion en PDF : {e}")

            # Réafficher les crosshairs et les étiquettes après l'export
            self.cross_vertical_line.show()
            self.cross_horizontal_line.show()
            self.x_label.show()
            self.y_label.show()

class IdentifyLineTool(QgsMapTool):
    feature_identified = pyqtSignal(object)

    def __init__(self, canvas, layer):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.setCursor(Qt.CrossCursor)

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        min_distance = float('inf')
        nearest_feature = None

        for feat in self.layer.getFeatures():
            geom = feat.geometry()
            distance = geom.distance(QgsGeometry.fromPointXY(QgsPointXY(point)))
            if distance < min_distance:
                min_distance = distance
                nearest_feature = feat

        if nearest_feature:
            self.feature_identified.emit(nearest_feature)


class ProfilGraph3D(QWidget):
    def __init__(self, feature, polyline_layer, raster_layer, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profil 3D")
        self.feature = feature
        self.polyline_layer = polyline_layer
        self.raster_layer = raster_layer

        # Construire la visualisation 3D
        self.create_3d_visualization()

    def create_3d_visualization(self):
        # Obtenir le SCR des couches
        polyline_crs = self.polyline_layer.crs()
        raster_crs = self.raster_layer.crs()

        # Obtenir la géométrie de la polyligne
        geom = self.feature.geometry()

        # Vérifier si une transformation de coordonnées est nécessaire
        if polyline_crs != raster_crs:
            transform = QgsCoordinateTransform(polyline_crs, raster_crs, QgsProject.instance())
            geom.transform(transform)

        # Créer un buffer (zone tampon) de 30 mètres autour de la polyligne
        buffer_distance = 30  # 30 mètres
        buffered_geom = geom.buffer(buffer_distance, segments=8)  # Augmenter 'segments' pour une meilleure précision

        # Obtenir l'emprise du buffer
        extent = buffered_geom.boundingBox()

        # Ouvrir le MNT avec GDAL
        raster_path = self.raster_layer.dataProvider().dataSourceUri()
        ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
        if ds is None:
            QMessageBox.warning(self, "Erreur", "Impossible d'ouvrir le fichier raster.")
            return
        band = ds.GetRasterBand(1)
        gt = ds.GetGeoTransform()
        inv_gt = gdal.InvGeoTransform(gt)

        # Calculer les indices des pixels correspondants
        x_min = extent.xMinimum()
        x_max = extent.xMaximum()
        y_min = extent.yMinimum()
        y_max = extent.yMaximum()

        ulx, uly = map(int, gdal.ApplyGeoTransform(inv_gt, x_min, y_max))
        lrx, lry = map(int, gdal.ApplyGeoTransform(inv_gt, x_max, y_min))

        # Gérer les valeurs hors limites
        ulx = max(0, min(ulx, ds.RasterXSize - 1))
        uly = max(0, min(uly, ds.RasterYSize - 1))
        lrx = max(0, min(lrx, ds.RasterXSize - 1))
        lry = max(0, min(lry, ds.RasterYSize - 1))

        xsize = abs(lrx - ulx)
        ysize = abs(lry - uly)

        if xsize == 0 or ysize == 0:
            QMessageBox.warning(self, "Erreur", "La zone est en dehors du MNT.")
            return

        # Lire la partie du MNT correspondant au buffer
        dem_data = band.ReadAsArray(min(ulx, lrx), min(uly, lry), xsize, ysize).astype(np.float32)
        if dem_data is None:
            QMessageBox.warning(self, "Erreur", "Erreur lors de la lecture du MNT.")
            return

        # Ajuster la géotransformation
        new_gt = (
            gt[0] + min(ulx, lrx) * gt[1],
            gt[1],
            gt[2],
            gt[3] + min(uly, lry) * gt[5],
            gt[4],
            gt[5]
        )

        ncols = dem_data.shape[1]
        nrows = dem_data.shape[0]

        x = np.arange(ncols) * new_gt[1] + new_gt[0]
        y = np.arange(nrows) * new_gt[5] + new_gt[3]
        x_grid, y_grid = np.meshgrid(x, y)

        # Gérer les valeurs NoData
        no_data_value = band.GetNoDataValue()
        if no_data_value is not None:
            dem_data[dem_data == no_data_value] = np.nan

        z_grid = dem_data

        # Vérifier les valeurs Z du MNT
        if np.isnan(z_grid).all():
            QMessageBox.warning(self, "Erreur", "Le MNT ne contient pas de données valides dans cette zone.")
            return

        # Obtenir les coordonnées de la polyligne
        points = list(geom.vertices())
        if not points:
            QMessageBox.warning(self, "Erreur", "La polyligne ne contient pas de points.")
            return

        line_x = [p.x() for p in points]
        line_y = [p.y() for p in points]
        line_z = [p.z() for p in points]

        # Vérifier les valeurs Z de la polyligne
        if all(z == 0 or np.isnan(z) for z in line_z):
            # Si les valeurs Z sont manquantes ou nulles, extraire les altitudes du MNT
            line_z = []
            for x_pt, y_pt in zip(line_x, line_y):
                # Convertir les coordonnées géographiques en indices de pixels
                px, py = gdal.ApplyGeoTransform(inv_gt, x_pt, y_pt)
                px = int(px) - min(ulx, lrx)
                py = int(py) - min(uly, lry)
                if 0 <= px < ncols and 0 <= py < nrows:
                    z_val = z_grid[py, px]
                    line_z.append(z_val)
                else:
                    line_z.append(np.nan)

        else:
            # Sinon, utiliser les valeurs Z de la polyligne
            line_z = [z if not np.isnan(z) else 0 for z in line_z]

        # Créer la figure Plotly
        fig = go.Figure()

        # Ajouter la surface du MNT avec les contours
        fig.add_trace(go.Surface(
            x=x_grid,
            y=y_grid,
            z=z_grid,
            colorscale='Viridis',
            colorbar=dict(title='Élévation'),
            opacity=0.8,
            contours=dict(
                z=dict(
                    show=True,
                    usecolormap=True,
                    highlightcolor='limegreen',
                    project_z=True
                )
            )
        ))

        # Ajouter la polyligne
        fig.add_trace(go.Scatter3d(
            x=line_x,
            y=line_y,
            z=line_z,
            mode='lines+markers',
            line=dict(color='red', width=6),
            marker=dict(size=4, color='red'),
            name='Polyligne Z'
        ))

        # Mettre à jour la mise en page
        fig.update_layout(
            scene=dict(
                xaxis_title='X',
                yaxis_title='Y',
                zaxis_title='Z',
                aspectmode='cube',
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.5)
                )
            ),
            title='Profil 3D',
            autosize=True,
            width=800,
            height=600,
            margin=dict(l=65, r=50, b=65, t=90)
        )

        # Enregistrer la figure Plotly en tant que fichier HTML temporaire
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as tmp_file:
            fig.write_html(tmp_file.name, include_plotlyjs='cdn')
            tmp_file_name = tmp_file.name

        # Ouvrir le fichier HTML dans le navigateur par défaut
        webbrowser.open_new_tab('file://' + tmp_file_name)





