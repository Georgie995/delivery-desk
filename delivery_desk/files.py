"""Writing files safely: new files never replace old ones, and the note is updated in one step."""

import os
import tempfile


def write_new(folder, stem, suffix, text):
    """Write stem+suffix, or stem-2, stem-3 … if taken. Mode "x" refuses to open an existing
    file, so even two runs at the same moment can't overwrite each other's work."""
    n = 1
    while True:
        path = folder / (f"{stem}{suffix}" if n == 1 else f"{stem}-{n}{suffix}")
        try:
            with open(path, "x", encoding="utf-8") as f:
                f.write(text)
            return path
        except FileExistsError:
            n += 1


def replace_safely(path, text):
    """Replace a file's contents in one step: write a temporary file next to it, then swap it in.
    If anything goes wrong midway, the original is still there, whole."""
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.remove(temp)  # only ever our own temporary file
        raise
