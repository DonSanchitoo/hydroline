
# tools/fenetre_profil_elevation.py

import numpy as np
from PyQt5.QtWidgets import QDockWidget, QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import matplotlib.pyplot as plt

from qgis.core import QgsMessageLog, Qgis



class FenetreProfilElevation(QDockWidget):
    """
    Fenêtre pour afficher le profil d'élévation en 3D.

    Cette classe crée une fenêtre dockable pour visualiser un profil d'élévation en trois dimensions,
    en utilisant Matplotlib pour le rendu graphique.

    Attributes
    ----------
    figure : matplotlib.figure.Figure
        Figure Matplotlib pour le rendu 3D.
    ax : matplotlib.axes._subplots.Axes3DSubplot
        Subplot 3D pour le tracé du profil d'élévation.
    canvas : FigureCanvasQTAgg
        Canvas contenant la figure Matplotlib.

    Methods
    -------
    reinitialiser()
        Réinitialise le graphique 3D.
    definir_outil(outil)
        Définit l'outil à utiliser pour obtenir les données d'élévation.
    on_mouse_move(event)
        Traite les mouvements de la souris sur le graphique.
    mettre_a_jour_profil(x_coords, y_coords, elevations, longueur_segment)
        Met à jour le graphique 3D du profil d'élévation.
    """

    def __init__(self, parent=None):
        """
        Initialise la fenêtre de profil d'élévation.

        Parameters
        ----------
        parent : QWidget, optional
            Widget parent, par défaut None.
        """

        super().__init__("Profil d'Élévation 3D", parent)

        self.figure = plt.figure()
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)

        widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        widget.setLayout(layout)
        self.setWidget(widget)

    def custom_print(*args):
        if sys.stdout:
            text = " ".join(map(str, args)) + "\n"
            sys.stdout.write(text)
        else:
            text = " ".join(map(str, args))
            QgsMessageLog.logMessage(text, level=Qgis.Info)

    def reinitialiser(self):
        """
        Réinitialise le graphique 3D.

        Cette méthode efface le contenu actuel du graphique et le redessine ensuite.
        """
        self.ax.clear()
        self.canvas.draw()

    def definir_outil(self, outil):
        """
        Définit l'outil à utiliser pour obtenir les données d'élévation.

        Parameters
        ----------
        outil : object
            Instance de l'outil utilisé pour accéder aux élévations MNT.
        """
        self.outil = outil

    def on_mouse_move(self, event):
        """
        Traite les mouvements de la souris sur le graphique.

        Quand la souris bouge sur le graphique, cette méthode affiche l'altitude correspondante
        dans la barre de statut du parent.

        Parameters
        ----------
        event : matplotlib.backend_bases.MouseEvent
            Événement de mouvement de la souris contenant les coordonnées de l'événement.
        """
        try:
            if event.inaxes == self.ax:
                x_mouse = event.xdata
                y_mouse = event.ydata
                if x_mouse is not None and y_mouse is not None:
                    # Assurez-vous que Z_grid est défini
                    if hasattr(self, 'Z_grid'):
                        # Exécuter la logique
                        idx = np.abs(self.X_grid[0] - x_mouse).argmin()
                        idy = np.abs(self.Y_grid[:, 0] - y_mouse).argmin()
                        elevation = self.Z_grid[idy, idx]
                        self.parent().statusBar().showMessage(f"Altitude : {elevation:.2f} m")
                    else:
                        raise RuntimeError(
                            "Z_grid n'est pas initialisé - assurez-vous que mettre_a_jour_profil() est appelé.")
        except AttributeError as e:
            import traceback
            logging.error(f"Erreur d'attribut : {traceback.format_exc()}")
            QMessageBox.critical(self, "Erreur EPSG", "Une erreur inattendue est survenue dans on_mouse_move. Relancer outil")
        except RuntimeError as e:
            logging.error(f"Erreur personnalisée : {str(e)}")
            QMessageBox.critical(self, "Erreur EPSG", "veuillez vérifier Z_grid. Relancer l'outil")

    def mettre_a_jour_profil(self, x_coords, y_coords, elevations, longueur_segment):
        """
        Met à jour le graphique 3D du profil d'élévation.

        Affiche les données d'élévation avec ou sans projection en fonction des coordonnées
        x, y, et des élévations fournit, et s'ajuste dynamiquement selon la longueur du segment.

        Parameters
        ----------
        x_coords : np.ndarray
            Coordonnées en x des points du segment dynamique.
        y_coords : np.ndarray
            Coordonnées en y des points du segment dynamique.
        elevations : np.ndarray
            Élévations des points du segment dynamique.
        longueur_segment : float
            Longueur du segment dynamique pour ajuster la résolution.
        """
        self.ax.clear()

        buffer_factor = 0.1
        buffer_min = 20
        buffer = max(buffer_min, longueur_segment * buffer_factor)

        if longueur_segment <= 100:
            num_points = 250  # Résolution élevée pour les segments courts
        elif longueur_segment <= 500:
            num_points = 200
        elif longueur_segment <= 1000:
            num_points = 150
        else:
            num_points = 100

        # Calculer les limites du graphique pour inclure tout le segment dynamique
        xmin = min(x_coords) - buffer
        xmax = max(x_coords) + buffer
        ymin = min(y_coords) - buffer
        ymax = max(y_coords) + buffer

        # Créer la grille
        X = np.linspace(xmin, xmax, num_points)
        Y = np.linspace(ymin, ymax, num_points)
        X_grid, Y_grid = np.meshgrid(X, Y)

        Z_grid = self.outil.obtenir_elevation_aux_points_multiples(X_grid, Y_grid)

        self.X_grid = X_grid
        self.Y_grid = Y_grid
        self.Z_grid = Z_grid

        self.ax.plot_surface(X_grid, Y_grid, Z_grid, edgecolor='gray', lw=0.2,
                             rstride=10, cstride=10, alpha=0.6, cmap='terrain',
                             zorder=1)

        zmin = np.nanmin(Z_grid)
        zmax = np.nanmax(Z_grid)

        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='z', offset=zmin, cmap='terrain',
                         zorder=2)
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='x', offset=xmin, cmap='terrain',
                         zorder=2)
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='y', offset=ymax, cmap='terrain',
                         zorder=2)

        self.ax.plot(
            x_coords,
            y_coords,
            elevations,
            color='red',
            label='Segment dynamique',
            linewidth=5,
            marker='x',
            markersize=1,
            markeredgecolor='black',
            markerfacecolor='yellow',
            zorder=10
        )

        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(ymin, ymax)
        self.ax.set_zlim(zmin, zmax)

        self.ax.set_xlabel("X (Longitude)")
        self.ax.set_ylabel("Y (Latitude)")
        self.ax.set_zlabel("Élévation (m)")
        self.ax.set_title("Assistance topographique 3D")
        self.ax.legend()

        self.ax.dist = 7

        self.canvas.draw()