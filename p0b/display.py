"""Display-only complex cosine reconstruction; raw Field is never replaced."""
from dataclasses import dataclass
import time
import numpy as np
from viz_methods import fit, predict
from raster import centers, tensor_cosine, cell_indices

# A failed 3/72 final-cell sets; B passed 72/72 (audit SELECTION.json).
DEFAULT_CELL_WIDTH = 0.0078125


def regular_indices(actual, expected):
    actual=np.asarray(actual)
    if actual.ndim!=1 or not np.all(np.isfinite(actual)) or not np.all(np.diff(actual)>0):
        raise ValueError("Display input axis must be finite, one-dimensional and increasing")
    indices=np.searchsorted(actual,expected)
    if np.any(indices>=len(actual)) or not np.array_equal(actual[indices],expected):
        raise ValueError("Required regular 0.25 m training coordinates are missing")
    # Additional raw intersection coordinates are allowed, but never used as DCT nodes.
    return indices


@dataclass(frozen=True)
class DisplayField:
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    xy: np.ndarray
    xz: np.ndarray
    models: dict
    fit_seconds: float
    query_seconds: float
    training_indices: dict
    cell_width_m: float

    def extent(self, panel):
        if panel not in ("xy", "xz"):
            raise ValueError("Unknown display panel")
        return (0., 5., 0., 4. if panel == "xy" else 3.)

    def sample_cells(self, panel, coordinates):
        """Complex value of the actual constant display cell containing q."""
        extent = self.extent(panel)
        ix, iv = cell_indices(coordinates, (extent[1], extent[3]), self.cell_width_m)
        return getattr(self, panel)[ix, iv]

    def query(self,panel,coordinates):
        if panel not in ("xy","xz"):
            raise ValueError("Unknown display panel")
        q=np.asarray(coordinates,dtype=float)
        limits=np.array((5.,4. if panel=="xy" else 3.))
        if q.ndim!=2 or q.shape[1]!=2 or not np.all(np.isfinite(q)) or np.any(q<0) or np.any(q>limits):
            raise ValueError("Display queries must be finite points within the named plane")
        return predict(self.models[panel],q)[0]

    def saturation(self,upper):
        return {"xy_count":int(np.count_nonzero(abs(self.xy)>upper)),"xz_count":int(np.count_nonzero(abs(self.xz)>upper)),
                "xy_max_pa":float(np.max(abs(self.xy))),"xz_max_pa":float(np.max(abs(self.xz)))}


def reconstruct(field, cell_width_m=DEFAULT_CELL_WIDTH):
    x0=np.linspace(0,5,21);y0=np.linspace(0,4,17);z0=np.linspace(0,3,13)
    ix=regular_indices(field.x,x0);iy=regular_indices(field.y,y0);iz=regular_indices(field.z,z0)
    if not np.array_equal(field.x,x0) or field.xy.shape!=(len(field.x),len(field.y)) or field.xz.shape!=(len(field.x),len(field.z)):
        raise ValueError("Unexpected raw field axes or array shape")
    xy=field.xy[np.ix_(ix,iy)];xz=field.xz[np.ix_(ix,iz)]
    if not np.all(np.isfinite(xy)) or not np.all(np.isfinite(xz)):
        raise ValueError("Nonfinite raw complex training field")
    xy.setflags(write=False);xz.setflags(write=False)
    t=time.perf_counter()
    models={"xy":fit("cosine_complex",[x0,y0],xy),"xz":fit("cosine_complex",[x0,z0],xz)}
    fit_seconds=time.perf_counter()-t
    # Final cells tile the exact physical rectangle. Cuts are parameters of the
    # underlying sampled planes, never extra centers in the regular raster.
    x=centers(5.,cell_width_m)
    y=centers(4.,cell_width_m)
    z=centers(3.,cell_width_m)
    t=time.perf_counter()
    xy_display=tensor_cosine(models["xy"],x,y)
    xz_display=tensor_cosine(models["xz"],x,z)
    query_seconds=time.perf_counter()-t
    for array in (x,y,z,xy_display,xz_display):array.setflags(write=False)
    return DisplayField(x,y,z,xy_display,xz_display,models,fit_seconds,query_seconds,
                        {"x":ix,"y":iy,"z":iz},cell_width_m)
