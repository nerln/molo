"""Punto d'ingresso per PyInstaller.

Non si può puntare la build direttamente a `molo/__main__.py`: PyInstaller lo
eseguirebbe come script di primo livello, senza pacchetto genitore, e ogni
`from . import ...` fallirebbe con ImportError. Questo file lo importa invece
per nome, così il pacchetto `molo` esiste davvero a runtime.
"""

import multiprocessing
import sys

from molo.__main__ import main

if __name__ == "__main__":
    # Obbligatorio nelle app congelate: senza, un eventuale processo figlio
    # rilancerebbe l'intera app invece del worker.
    multiprocessing.freeze_support()
    sys.exit(main())
