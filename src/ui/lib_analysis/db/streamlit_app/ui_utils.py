from __future__ import annotations

def human_bytes(n: int) -> str:
    if n is None:
        return "0 B"
    n = int(n)
    if n < 1024:
        return f"{n} B"
    units = ["KiB", "MiB", "GiB", "TiB"]
    x = float(n)
    for u in units:
        x /= 1024.0
        if x < 1024.0:
            return f"{x:.2f} {u}"
    return f"{x:.2f} PiB"
