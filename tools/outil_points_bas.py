# tools/outil_points_bas.py


def select_next_pixel(courant, candidats_voisins, elevation_courante, arrivee_px, resoudre_egalite):
    """
    Sélectionne le prochain pixel en suivant les points bas.

    Args:
        courant (tuple): Coordonnées (cx, cy) du pixel courant.
        candidats_voisins (list): Liste des voisins candidats avec leurs informations.
        elevation_courante (float): Élévation du pixel courant.
        arrivee_px (tuple): Coordonnées (cx, cy) du pixel d'arrivée.
        resoudre_egalite (function): Fonction pour départager les candidats en cas d'égalité.

    Returns:
        tuple: Coordonnées (cx, cy) du prochain pixel.
    """
    # Rechercher les voisins avec une élévation inférieure
    voisins_plus_bas = [n for n in candidats_voisins if n['elevation'] < elevation_courante]

    if voisins_plus_bas:
        # Sélectionner le voisin avec l'élévation la plus basse
        elevation_min = min(n['elevation'] for n in voisins_plus_bas)
        voisins_minimums = [n for n in voisins_plus_bas if n['elevation'] == elevation_min]
        prochain_px = resoudre_egalite(voisins_minimums, arrivee_px)
    else:
        # Si aucun voisin plus bas, chercher les voisins à élévation égale
        voisins_egaux = [n for n in candidats_voisins if n['elevation'] == elevation_courante]
        if voisins_egaux:
            prochain_px = resoudre_egalite(voisins_egaux, arrivee_px)
        else:
            # Sinon, descendre vers le voisin le plus bas possible
            elevation_min = min(n['elevation'] for n in candidats_voisins)
            voisins_minimums = [n for n in candidats_voisins if n['elevation'] == elevation_min]
            prochain_px = resoudre_egalite(voisins_minimums, arrivee_px)

    return prochain_px
