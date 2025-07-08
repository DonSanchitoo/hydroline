# threads/calcul_pentes_thread.py

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

class CalculPentesThread(QThread):
    result_ready = pyqtSignal(np.ndarray)  # Signal émis lorsque le calcul est terminé

    def __init__(self, hillshade_array, gt, parent=None):
        super().__init__(parent)
        self.hillshade_array = hillshade_array
        self.gt = gt

    def run(self):
        """Exécute le calcul des pentes locales."""
        import dask.array as da

        try:
            # Créer un Dask array à partir du tableau NumPy
            dask_array = da.from_array(self.hillshade_array, chunks=(1000, 1000))  # Ajustez les chunks si nécessaire

            # Calculer le gradient en utilisant Dask
            grad_y, grad_x = da.gradient(dask_array, self.gt[1], -self.gt[5])
            magnitude = da.degrees(da.arctan(da.sqrt(grad_x ** 2 + grad_y ** 2)))

            # Calculer et charger en mémoire le tableau résultant
            pentes_locales_degres = magnitude.compute()

            # Émettre le signal avec le résultat
            self.result_ready.emit(pentes_locales_degres)
        except Exception as e:
            print(f"Erreur lors du calcul des pentes : {e}")
            # Optionnel : émettre un signal d'erreur ou gérer l'exception
