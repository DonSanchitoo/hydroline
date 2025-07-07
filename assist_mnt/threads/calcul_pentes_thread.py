# threads/calcul_pentes_thread.py

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
import dask.array as da

class CalculPentesThread(QThread):
    result_ready = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)

    def __init__(self, tableau_raster, gt, parent=None):
        super().__init__(parent)
        self.tableau_raster = tableau_raster
        self.gt = gt

    def run(self):
        """Exécute le calcul des pentes locales."""
        try:
            # Créer un Dask array à partir du NumPy array
            dask_array = da.from_array(self.tableau_raster, chunks=(1000, 1000))

            # Calculer le gradient en utilisant Dask
            grad_y, grad_x = da.gradient(dask_array, self.gt[1], -self.gt[5])
            magnitude = da.degrees(da.arctan(da.sqrt(grad_x ** 2 + grad_y ** 2)))

            # Calculer et charger en mémoire le tableau résultant
            pentes_locales_degres = magnitude.compute()

            # Émettre le signal avec le résultat
            self.result_ready.emit(pentes_locales_degres)
        except Exception as e:
            error_message = f"Erreur lors du calcul des pentes : {e}"
            print(error_message)
            self.error_occurred.emit(error_message)
