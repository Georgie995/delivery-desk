"""Writing new files without ever replacing an existing one."""


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
