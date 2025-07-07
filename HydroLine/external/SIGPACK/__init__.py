# SIGPACK/__init__.py

__all__ = []

import_error_occurred = False

# importer Ep depuis Epoint.py
try:
    from .Epoint import Ep
    __all__.append('Ep')
except ImportError as e:
    import_error_occurred = True
    Ep = None


# importer pT depuis profil_tool.py
try:
    from .profil_tool import pT
    __all__.append('pT')
except ImportError as e:
    import_error_occurred = True
    try:
        from .profil_tool_Stand import pT
        __all__.append('pT')
    except ImportError as e:
        pT = None

#  importer Ep depuis EpointArcgis.py si erreur
if import_error_occurred:
    try:
        from .EpointArcgis import EpArc
        __all__.append('EpArc')
    except ImportError as e:
        EpArc = None
