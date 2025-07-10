
# dialogs/slider_dialog.py



from PyQt5.QtWidgets import QDialog, QVBoxLayout, QSlider, QLabel, QPushButton
from PyQt5.QtCore import Qt


class SliderDialog(QDialog):
    """
    Boîte de dialogue pour gérer les sliders, notamment pour la tolérance de simplification.

    Cette classe crée une interface utilisateur avec un slider permettant de sélectionner une valeur
    de tolérance de simplification dans une plage spécifiée.

    Attributes
    ----------
    step : int
        Intervalle fixe du slider, en unités entières.
    slider : QSlider
        Slider pour la sélection de la tolérance.
    label : QLabel
        Étiquette affichant la valeur actuelle du slider.
    ok_button : QPushButton
        Bouton pour confirmer la sélection.

    Methods
    --------
    update_label(value)
        Met à jour l'étiquette affichée en fonction de la valeur du slider.
    get_value()
        Retourne la valeur actuelle du slider.
    """

    def __init__(self, min_value=0, max_value=20, step=0.5, parent=None):
        super(SliderDialog, self).__init__(parent)

        self.step = int(step * 10)
        min_int = int(min_value * 10)
        max_int = int(max_value * 10)

        self.setWindowTitle("Choisissez la tolérance avec un slider")

        layout = QVBoxLayout()

        self.slider = QSlider()
        self.slider.setOrientation(Qt.Horizontal)
        self.slider.setMinimum(min_int)
        self.slider.setMaximum(max_int)
        self.slider.setSingleStep(self.step)
        self.slider.setValue(min_int)

        self.label = QLabel(f"Tolérance : {min_value:.1f}")
        self.slider.valueChanged.connect(self.update_label)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)

        layout.addWidget(self.label)
        layout.addWidget(self.slider)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def update_label(self, value):
        """
        Met à jour l'étiquette affichée en fonction de la valeur du slider.

        Parameters
        ----------
        value : int
            Valeur actuelle du slider en unités entières.
        """
        float_value = value / 10.0
        self.label.setText(f"Tolérance : {float_value:.1f}")

    def get_value(self):
        """
        Retourne la valeur actuelle du slider.

        Convertit la valeur entière du curseur en un nombre float

        Returns
        -------
        float
            Valeur de tolérance sélectionnée, convertie en nombre flottant.
        """
        return self.slider.value() / 10.0
