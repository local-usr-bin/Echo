"""P0-B state and sampling only. All physics is delegated to frozen physics.py."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import importlib.util
import math
import cmath
import sys
import time

import numpy as np
from phase_readout import classify_phase

PROJECT = Path(__file__).resolve().parent.parent
CORE_SHA256 = "abace7466c7437bd03473218b17eda455dcea14f712a8f74e7c6f7ee1ea00ec6"
CORE_PATH = PROJECT / "physics.py"
if not CORE_PATH.is_file() or hashlib.sha256(CORE_PATH.read_bytes()).hexdigest() != CORE_SHA256:
    raise RuntimeError("Frozen P0-A physics.py is missing or has a different SHA-256; stopped")
# Load only the verified file, without changing persistent Python configuration.
spec = importlib.util.spec_from_file_location("echo_p0a_frozen", CORE_PATH)
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

LENGTHS = (5.0, 4.0, 3.0)
DEFAULTS = {
    "source_x": "1.15", "source_y": "1.37", "source_z": "1.11",
    "source2_x": "3.73", "source2_y": "2.61", "source2_z": "1.93",
    "gain2": "0", "phase2_deg": "0",
    "observer_x": "2.50", "observer_y": "2.00", "observer_z": "1.50",
    "frequency_hz": "83", "xy_z": "1.50", "xz_y": "2.00", "vmax_pa": "0.003",
}
LABELS = {
    **{f"{who}_{axis}": f"{who} {axis} (m)" for who in ("source", "source2", "observer") for axis in "xyz"},
    "gain2": "Source 2 volume-velocity ratio g", "phase2_deg": "Source 2 relative phase (deg)",
    "frequency_hz": "Frequency (Hz)", "xy_z": "XY z (m)", "xz_y": "XZ y (m)", "vmax_pa": "Color upper limit (Pa)",
}


class InputError(ValueError):
    pass


def finite_number(raw, key):
    try:
        value = float(raw[key])
    except (ValueError, TypeError, KeyError, OverflowError):
        raise InputError(f"{LABELS[key]}: enter a finite number") from None
    if not math.isfinite(value):
        raise InputError(f"{LABELS[key]}: NaN and Infinity are not allowed")
    return value


def color_limit(raw):
    value = finite_number(raw, "vmax_pa")
    if value <= 0:
        raise InputError("Color upper limit (Pa) must be greater than zero")
    return value


@dataclass(frozen=True)
class Parameters:
    source: tuple
    observer: tuple
    frequency_hz: float
    xy_z: float
    xz_y: float
    source2: tuple = (3.73, 2.61, 1.93)
    gain2: float = 0.0
    phase2_deg: float = 0.0

    @property
    def volume_velocities(self):
        return (complex(1e-5), self.gain2 * 1e-5 * cmath.exp(1j * math.radians(self.phase2_deg)))


def parse(raw):
    positions = []
    for who in ("source", "observer", "source2"):
        point = tuple(finite_number(raw, f"{who}_{axis}") for axis in "xyz")
        for axis, value, length in zip("xyz", point, LENGTHS):
            if not 0 <= value <= length:
                raise InputError(f"{LABELS[who+'_'+axis]} must be within [0, {length:g}]")
        positions.append(point)
    frequency = finite_number(raw, "frequency_hz")
    if not 25 <= frequency <= 120:
        raise InputError("Frequency must be within [25, 120] Hz")
    z, y = finite_number(raw, "xy_z"), finite_number(raw, "xz_y")
    if not 0 <= z <= 3:
        raise InputError("XY z must be within [0, 3] m")
    if not 0 <= y <= 4:
        raise InputError("XZ y must be within [0, 4] m")
    gain = finite_number(raw, "gain2")
    phase = finite_number(raw, "phase2_deg")
    if not 0 <= gain <= 1:
        raise InputError("Source 2 relative amplitude g must be within [0, 1]")
    if not -180 <= phase <= 180:
        raise InputError("Source 2 relative phase must be within [-180, 180] deg")
    return Parameters(positions[0], positions[1], frequency, z, y, positions[2], gain, phase), color_limit(raw)


@dataclass(frozen=True)
class Field:
    parameters: Parameters
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    xy: np.ndarray
    xz: np.ndarray
    observer_pressure: complex
    coefficients: np.ndarray
    diagnostics: dict
    elapsed_seconds: float

    def saturation(self, upper):
        return {"xy_count": int(np.count_nonzero(np.abs(self.xy) > upper)),
                "xz_count": int(np.count_nonzero(np.abs(self.xz) > upper)),
                "xy_max_pa": float(np.max(np.abs(self.xy))),
                "xz_max_pa": float(np.max(np.abs(self.xz)))}


class Engine:
    """One fixed 3-D modal basis. No alternate physics or automatic cutoff."""
    def __init__(self):
        start = time.perf_counter()
        self.modes = core.Modes(1200.0, core.Room(LENGTHS, 343.0, 1.20))
        self.initialization_seconds = time.perf_counter() - start
        self.call_count = 0

    def compute(self, p):
        start = time.perf_counter()
        self.call_count += 1
        q1, q2 = p.volume_velocities
        coefficients, diagnostics = self.modes.solve_sources(
            p.frequency_hz, [(p.source, q1, 0.25), (p.source2, q2, 0.25)])
        x = np.linspace(0, 5, 21)
        # Insert each cut's intersection coordinate so both panels share an
        # actual, explicitly testable 3-D line even for non-grid slice positions.
        y = np.unique(np.r_[np.linspace(0, 4, 17), p.xz_y])
        z = np.unique(np.r_[np.linspace(0, 3, 13), p.xy_z])
        xx, yy = np.meshgrid(x, y, indexing="ij")
        xy_points = np.column_stack((xx.ravel(), yy.ravel(), np.full(xx.size, p.xy_z)))
        xx, zz = np.meshgrid(x, z, indexing="ij")
        xz_points = np.column_stack((xx.ravel(), np.full(xx.size, p.xz_y), zz.ravel()))
        combined = np.vstack((xy_points, xz_points, np.asarray(p.observer).reshape(1, 3)))
        unique, inverse = np.unique(combined, axis=0, return_inverse=True)
        values = self.modes.synthesize(unique, coefficients)[inverse]
        # Readout-only conditioning scale, before source or modal cancellation.
        # This never replaces pressure, modal coefficients or display samples.
        source_scale = (abs(q1) * abs(self.modes.source_coefficients(p.source, .25))
                        + abs(q2) * abs(self.modes.source_coefficients(p.source2, .25)))
        denominator = abs(self.modes.k2 - (2 * np.pi * p.frequency_hz / self.modes.room.c)**2)
        observer_basis = abs(self.modes.basis([p.observer])[0])
        phase_scale = float(np.sum(observer_basis * self.modes.room.rho
                                  * (2 * np.pi * p.frequency_hz) * source_scale / denominator))
        diagnostics = {**diagnostics, "observer_phase": classify_phase(
            complex(values[-1]), phase_scale, len(coefficients))}
        nxy, nxz = len(xy_points), len(xz_points)
        xy = values[:nxy].reshape(len(x), len(y))
        xz = values[nxy:nxy+nxz].reshape(len(x), len(z))
        # Prevent accidental in-place clipping or normalization by presentation.
        for a in (x, y, z, xy, xz, coefficients):
            a.setflags(write=False)
        return Field(p, x, y, z, xy, xz, complex(values[-1]), coefficients,
                     diagnostics, time.perf_counter() - start)


class Controller:
    """Explicit calculation and color application; safe invalid/stale states."""
    def __init__(self, engine=None):
        self.engine = engine if engine is not None else Engine()
        self.raw = DEFAULTS.copy()
        self.result = None
        self.applied_upper_pa = .003
        self.status = "NEEDS_UPDATE"
        self.message = "待更新 / Press Update calculation. No current field."
        self.error_details = None

    def edit(self, key, text):
        if key not in DEFAULTS:
            raise KeyError(key)
        if self.raw[key] == text:
            return
        self.raw[key] = text
        if key == "vmax_pa" and self.result is not None:
            self.describe_result()
            previous = self.message
            self.status = "COLOR_PENDING"
            self.message = f"色标待应用 / Color pending. Current displayed range remains 0–{self.applied_upper_pa:g} Pa.\n{previous}"
        else:
            self.result = None
            self.error_details = None
            self.status = "NEEDS_UPDATE"
            self.message = "待更新 / Inputs changed. Previous field cleared; press Update calculation."

    def clear_error(self, status, message, details=None):
        self.result = None
        self.status = status
        self.message = message
        self.error_details = details

    def describe_result(self):
        f = self.result
        d = f.diagnostics
        sat = f.saturation(self.applied_upper_pa)
        self.status = "NEAR_RESONANCE" if d["near_resonance"] else "READY"
        self.message = f"当前结果 / Current: {f.parameters.frequency_hz!r} Hz; color 0–{self.applied_upper_pa:g} Pa."
        if d["near_resonance"]:
            self.message += (f"\n近共振 / Near resonance: mode {d['nearest_mode']}, frequency gap {d['distance_hz']:.9g} Hz; "
                             f"relative frequency sensitivity {d['nearest_denominator_relative_frequency_sensitivity']:.7g}. "
                             "Small frequency changes can strongly change pressure. No damping or amplitude limiting.")
        if sat["xy_count"] or sat["xz_count"]:
            self.message += (f"\n超出色标 / Color saturation: XY {sat['xy_count']} samples, XZ {sat['xz_count']} samples. "
                             f"Actual maxima {sat['xy_max_pa']:.9g}, {sat['xz_max_pa']:.9g} Pa. Raw pressure is unchanged.")
        self.message += "\nLossless harmonic particular solution; no claim of convergence from arbitrary initial conditions."

    def update(self):
        self.result = None
        self.error_details = None
        try:
            parameters, upper = parse(self.raw)
            result = self.engine.compute(parameters)
        except InputError as exc:
            self.clear_error("INPUT_ERROR", f"输入无效 / {exc}. No current field.")
        except core.ResonanceError as exc:
            if exc.details["status"] == "EXCITED_RESONANCE_NO_FINITE_SOLUTION":
                reason = "Exact/numerical resonance excites an eigenmode: no finite single-frequency solution."
            else:
                reason = "Resonance is numerically unexcited: the solution is nonunique."
            self.clear_error("RESONANCE", f"共振拒绝求值 / {reason}\nNo field is shown; no damping is added.", exc.details)
        except Exception as exc:
            self.clear_error("COMPUTE_ERROR", f"计算失败 / {type(exc).__name__}: {exc}. No current field.")
        else:
            self.result = result
            self.applied_upper_pa = upper
            self.describe_result()
        return self.result

    def apply_color(self):
        try:
            upper = color_limit(self.raw)
        except InputError as exc:
            self.clear_error("INPUT_ERROR", f"色标无效 / {exc}. No current field.")
            return False
        self.applied_upper_pa = upper
        if self.result is None:
            self.status = "NEEDS_UPDATE"
            self.message = f"色标已设为 / Color set to 0–{upper:g} Pa. 待更新 / Press Update calculation."
        else:
            self.describe_result()
        return True
