"""Final regular cells, evaluated from the frozen complex cosine polynomial."""
import numpy as np

ALLOWED_WIDTHS = (0.015625, 0.0078125)


def centers(length, width):
    if width not in ALLOWED_WIDTHS:
        raise ValueError("Only the two predeclared display resolutions are permitted")
    count = int(length / width)
    if count * width != length:
        raise ValueError("Display cells must tile the full physical extent")
    return (np.arange(count, dtype=float) + 0.5) * width


def tensor_cosine(model, x, vertical):
    """Same polynomial as frozen predict(), evaluated on a Cartesian product.

    Bx @ C @ Bv.T changes only contraction order, with no refitting, coefficient
    truncation, pressure scaling or per-point giant basis temporary.
    """
    if model["method"] != "cosine_complex" or len(model["axes"]) != 2:
        raise ValueError("A frozen two-dimensional complex cosine model is required")
    coordinates = (np.asarray(x, dtype=float), np.asarray(vertical, dtype=float))
    bases = []
    for q, axis in zip(coordinates, model["axes"]):
        if q.ndim != 1 or not np.all(np.isfinite(q)) or np.any(q < 0) or np.any(q > axis[-1]):
            raise ValueError("Raster query axis outside the physical rectangle")
        bases.append(np.cos(np.outer(q / axis[-1], np.arange(len(axis))) * np.pi))
    return (bases[0] @ model["coefficients"]) @ bases[1].T


def cell_indices(coordinates, lengths, width):
    q = np.asarray(coordinates, dtype=float)
    limits = np.asarray(lengths, dtype=float)
    if q.ndim != 2 or q.shape[1] != 2 or not np.all(np.isfinite(q)) or np.any(q < 0) or np.any(q > limits):
        raise ValueError("Final-cell queries must be finite and within the physical extent")
    indices = np.floor(q / width).astype(np.int64)
    # The right/top exterior boundary belongs to the last closed cell.
    # No out-of-domain coordinates or pressure values are clipped.
    for axis in range(2):
        indices[q[:, axis] == limits[axis], axis] = int(limits[axis] / width) - 1
    return indices[:, 0], indices[:, 1]
