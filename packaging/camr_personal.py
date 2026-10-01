"""Entry point of the standalone CAMR Personal download (PyInstaller)."""

import multiprocessing

from camr.app.server import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
