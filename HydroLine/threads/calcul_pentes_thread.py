# threads/calcul_pentes_thread.py

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

class CalculPentesThread(QThread):
    """
    Thread pour calculer les pentes locales à partir d'un tableau de hillshade.

    Cette classe utilise Dask pour le calcul des gradients et des pentes locales de manière asynchrone,
    permettant ainsi de garder l'interface utilisateur réactive pendant le traitement.

    Attributes
    ----------
    hillshade_array : np.ndarray
        Tableau NumPy contenant les données de hillshade.
    gt : tuple
        Transformation géospatiale associée aux données, contenant des informations telles que la taille du pixel.
    result_ready : pyqtSignal
        Signal émis lorsque le calcul est terminé, contenant le tableau des pentes locales en degrés.

    Methods
    -------
    run()
        Exécute le calcul des pentes locales.
    """
    result_ready = pyqtSignal(np.ndarray)  # Signal émis lorsque le calcul est terminé

    def __init__(self, hillshade_array, gt, parent=None):
        """
        Initialise le thread de calcul des pentes locales.

        Parameters
        ----------
        hillshade_array : np.ndarray
            Tableau NumPy contenant les données de hillshade.
        gt : tuple
            Transformation géospatiale associée aux données, contenant des informations telles que la taille du pixel.
        parent : QObject, optional
            Objet parent pour le thread, par défaut None.
        """
        super().__init__(parent)
        self.hillshade_array = hillshade_array
        self.gt = gt

    def run(self):
        """
        Exécute le calcul des pentes locales.

        Cette méthode utilise Dask pour calculer les gradients et les pentes locales, puis émet un signal avec
        le résultat une fois le calcul terminé.
        """
        from ..external.dask import array as da

        try:
            dask_array = da.from_array(self.hillshade_array, chunks=(1000, 1000))  # Ajustez les chunks si nécessaire

            grad_y, grad_x = da.gradient(dask_array, self.gt[1], -self.gt[5])
            magnitude = da.degrees(da.arctan(da.sqrt(grad_x ** 2 + grad_y ** 2)))

            pentes_locales_degres = magnitude.compute()

            self.result_ready.emit(pentes_locales_degres)
        except Exception as e:
            print(f"Erreur lors du calcul des pentes : {e}")
