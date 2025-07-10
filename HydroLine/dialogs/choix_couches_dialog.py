
# dialogs/Choix_couches_dialog.py


from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox,
    QCheckBox, QDialogButtonBox, QPushButton, QInputDialog
)
from qgis._core import QgsRasterLayer, QgsMeshLayer, QgsVectorLayer
from qgis.core import QgsProject, QgsMapLayer, QgsWkbTypes



class ChoixCouchesDialogPourTrace(QDialog):
    """
    Permet de gérer l'affichage des différentes dialogs indispensables aux outils du plugin
    """
    def __init__(self, parent=None):
        super(ChoixCouchesDialogPourTrace, self).__init__(parent)
        self.setWindowTitle("Sélectionner les couches")

        # Layout principal
        layout = QVBoxLayout()

        # Sélection du MNT
        self.label_mnt = QLabel("Choisir le MNT de travail :")
        self.combo_mnt = QComboBox()
        self.populate_mnt_layers()
        layout.addWidget(self.label_mnt)
        layout.addWidget(self.combo_mnt)

        # Sélection de la couche de polyligne
        self.label_polyline = QLabel("Choisir la couche de polyligne :")
        self.combo_polyline = QComboBox()
        self.populate_polyline_layers()
        layout.addWidget(self.label_polyline)
        layout.addWidget(self.combo_polyline)


        # Checkbox pour nouvelle couche
        self.checkbox_new_layer = QCheckBox("Nouvelle couche de travail")
        layout.addWidget(self.checkbox_new_layer)

        # Boutons OK / Annuler
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

        # Connecter les signaux
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.combo_polyline.currentIndexChanged.connect(self.on_polyline_selection_changed)

        # Initialiser l'état de la checkbox
        self.update_checkbox_state()

    def populate_mnt_layers(self):
        """Remplit la comboBox avec les couches raster disponibles."""
        self.combo_mnt.clear()
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.RasterLayer:
                self.combo_mnt.addItem(layer.name(), layer)

    def populate_polyline_layers(self):
        """Remplit la comboBox avec les couches de polyligne disponibles."""
        self.combo_polyline.clear()
        self.combo_polyline.addItem("--- Aucune ---", None)  # Option pour aucune couche
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.LineGeometry:
                self.combo_polyline.addItem(layer.name(), layer)

    def on_polyline_selection_changed(self, index):
        """Active ou désactive la checkbox en fonction de la sélection."""
        layer = self.combo_polyline.itemData(index)
        if layer is not None:
            self.checkbox_new_layer.setChecked(False)
            self.checkbox_new_layer.setEnabled(False)
        else:
            self.checkbox_new_layer.setEnabled(True)

    def update_checkbox_state(self):
        """Met à jour l'état de la checkbox en fonction de la sélection initiale."""
        index = self.combo_polyline.currentIndex()
        self.on_polyline_selection_changed(index)

    def get_selected_mnt_layer(self):
        """Retourne la couche MNT sélectionnée."""
        return self.combo_mnt.itemData(self.combo_mnt.currentIndex())

    def get_selected_polyline_layer(self):
        """Retourne la couche de polyligne sélectionnée ou None."""
        return self.combo_polyline.itemData(self.combo_polyline.currentIndex())

    def is_new_layer_checked(self):
        """Indique si la case 'Nouvelle couche de travail' est cochée."""
        return self.checkbox_new_layer.isChecked()


class DialogueSelectionCouchesPourProlongement(QDialog):
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

        # Nouvelle combobox pour la couche d'emprise
        self.combobox_emprise = QComboBox()
        self.combobox_emprise.addItem("--- Aucune ---")
        self.combobox_emprise.addItems([
            couche.name()
            for couche in QgsProject.instance().mapLayers().values()
            if isinstance(couche, QgsVectorLayer) and couche.geometryType() == QgsWkbTypes.PolygonGeometry
        ])
        layout_principal.addWidget(QLabel('Sélectionnez la couche d\'emprise (facultatif : si sélectionnée, le champ Absc_proj sera ignoré) :'))
        layout_principal.addWidget(self.combobox_emprise)

        bouton_ok = QPushButton('OK')
        bouton_ok.clicked.connect(self.accept)
        layout_principal.addWidget(bouton_ok)

        self.setLayout(layout_principal)


class DialogueSelectionEpoint(QDialog):
    """
    Boîte de dialogue pour permettre à l'utilisateur de sélectionner les couches de points et le paramètre alpha.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner les couches de points et paramètre alpha")

        # Layout principal
        layout_principal = QVBoxLayout()

        # Sélection de la couche de points
        self.combo_points = QComboBox()
        self.combo_points.addItems([
            couche.name()
            for couche in QgsProject.instance().mapLayers().values()
            if isinstance(couche, QgsVectorLayer) and couche.geometryType() == QgsWkbTypes.PointGeometry
        ])
        layout_principal.addWidget(QLabel('Sélectionnez la couche de points :'))
        layout_principal.addWidget(self.combo_points)

        # Boutons OK / Annuler
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout_principal.addWidget(self.button_box)

        self.setLayout(layout_principal)

        # Connecter les signaux
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def get_selected_points_layer(self):
        """Retourne la couche de points sélectionnée."""
        layer_name = self.combo_points.currentText()
        return QgsProject.instance().mapLayersByName(layer_name)[0]

    def get_alpha_value(self):
        """Demande à l'utilisateur de saisir le paramètre alpha et le renvoie."""
        alpha_utilisateur, ok = QInputDialog.getDouble(
            self, "Paramètre Alpha", "Choisissez la valeur d'alpha :", 8, 0.1, 100, 1
        )
        if ok:
            return alpha_utilisateur
        return None