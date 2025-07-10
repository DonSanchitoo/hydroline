
# tools/fenetre_profil_elevation.py

import numpy as np
from PyQt5.QtWidgets import QDockWidget, QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import matplotlib.pyplot as plt



class FenetreProfilElevation(QDockWidget):
    """
    Fenêtre pour afficher le profil d'élévation en 3D.

    Args:
        parent (QWidget): Le widget parent.
    """

    def __init__(self, parent=None):
        """Initialise la fenêtre de profil d'élévation."""
        super().__init__("Profil d'Élévation 3D", parent)


        # Créer une figure Matplotlib en 3D
        self.figure = plt.figure()
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)

        # Configurer le widget principal
        widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        widget.setLayout(layout)
        self.setWidget(widget)

    def reinitialiser(self):
        """
        Reset fonction
        Returns
        -------

        """

        self.ax.clear()
        self.canvas.draw()

    def definir_outil(self, outil):
        """
        Définit l'outil
        Parameters
        ----------
        outil

        Returns
        -------

        """
        self.outil = outil

    def on_mouse_move(self, event):
        """
        Quand la souris bouge
        Parameters
        ----------
        event

        Returns
        -------

        """
        if event.inaxes == self.ax:
            x_mouse = event.xdata
            y_mouse = event.ydata
            if x_mouse is not None and y_mouse is not None:
                # Obtenir l'élévation correspondante
                Z_grid = self.Z_grid
                X_grid = self.X_grid
                Y_grid = self.Y_grid

                # Trouver les indices les plus proches dans la grille
                idx = (np.abs(X_grid[0] - x_mouse)).argmin()
                idy = (np.abs(Y_grid[:, 0] - y_mouse)).argmin()

                elevation = Z_grid[idy, idx]

                # Afficher l'altitude
                self.parent().statusBar().showMessage(f"Altitude : {elevation:.2f} m")

    def mettre_a_jour_profil(self, x_coords, y_coords, elevations, longueur_segment):
        """Met à jour le graphique 3D du profil d'élévation."""
        self.ax.clear()

        # Ajuster le buffer en fonction de la longueur du segment dynamique
        buffer_factor = 0.1  # Par exemple, 10% de la longueur du segment
        buffer_min = 20  # Valeur minimale du buffer en mètres
        buffer = max(buffer_min, longueur_segment * buffer_factor)

        # Ajuster le nombre de points du maillage en fonction de la longueur
        # Plus le segment est court, plus la résolution est élevée
        if longueur_segment <= 100:
            num_points = 250  # Résolution élevée pour les segments courts
        elif longueur_segment <= 500:
            num_points = 200
        elif longueur_segment <= 1000:
            num_points = 150
        else:
            num_points = 100  # Résolution plus faible pour les segments longs

        # Calculer les limites du graphique pour inclure tout le segment dynamique
        xmin = min(x_coords) - buffer
        xmax = max(x_coords) + buffer
        ymin = min(y_coords) - buffer
        ymax = max(y_coords) + buffer

        # Créer la grille
        X = np.linspace(xmin, xmax, num_points)
        Y = np.linspace(ymin, ymax, num_points)
        X_grid, Y_grid = np.meshgrid(X, Y)

        # Obtenir les valeurs Z du MNT
        Z_grid = self.outil.obtenir_elevation_aux_points_multiples(X_grid, Y_grid)

        # Sauvegarder les grilles pour on_mouse_move
        self.X_grid = X_grid
        self.Y_grid = Y_grid
        self.Z_grid = Z_grid

        # Tracer la surface 3D
        self.ax.plot_surface(X_grid, Y_grid, Z_grid, edgecolor='gray', lw=0.2,
                             rstride=10, cstride=10, alpha=0.6, cmap='terrain',
                             zorder=1)

        # Ajouter les projections de contours
        zmin = np.nanmin(Z_grid)
        zmax = np.nanmax(Z_grid)

        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='z', offset=zmin, cmap='terrain',
                         zorder=2)
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='x', offset=xmin, cmap='terrain',
                         zorder=2)
        self.ax.contourf(X_grid, Y_grid, Z_grid, zdir='y', offset=ymax, cmap='terrain',
                         zorder=2)

        # Tracer le segment dynamique
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

        # Ajuster les limites
        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(ymin, ymax)
        self.ax.set_zlim(zmin, zmax)

        # Ajuster les labels et le titre
        self.ax.set_xlabel("X (Longitude)")
        self.ax.set_ylabel("Y (Latitude)")
        self.ax.set_zlabel("Élévation (m)")
        self.ax.set_title("Assistance topographique 3D")
        self.ax.legend()

        self.ax.dist = 7  # Vous pouvez ajuster cette valeur

        self.canvas.draw()