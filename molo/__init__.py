"""Molo: a local queue for yt-dlp.

This file is almost empty on purpose, and the one thing it does has to happen
here. `engine` and `watch` both `import yt_dlp` when they load, so if Molo is
going to prefer a newer engine downloaded into its data folder, the path has to
be arranged before either of them is touched. Importing the package is the only
moment early enough.
"""

from . import upgrade as _upgrade

#: Version of the downloaded engine in use, or None when Molo is running the one
#: it ships with. Read it rather than guessing: `engine.current_version()` says
#: which yt-dlp is loaded, this says where it came from.
ENGINE_FROM_DATA_DIR: str | None = _upgrade.activate()

__all__ = ["ENGINE_FROM_DATA_DIR"]
