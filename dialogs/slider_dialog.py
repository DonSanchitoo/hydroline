"""
dialogs/slider_dialog.py

Permet de gérer les sliders notamment pour la tolérence de simplification
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QSlider, QLabel, QPushButton
from PyQt5.QtCore import Qt


class SliderDialog(QDialog):
    def __init__(self, min_value=0, max_value=20, step=0.5, parent=None):
        super(SliderDialog, self).__init__(parent)

        # Convert step to integer since QSlider works with integers
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
        float_value = value / 10.0
        self.label.setText(f"Tolérance : {float_value:.1f}")

    def get_value(self):
        return self.slider.value() / 10.0
