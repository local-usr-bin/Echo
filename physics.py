"""Lossless 3-D Neumann box; exp(+i omega t), SI units, no damping.

(-Delta - k**2) P = i rho omega sum_j Q_j h_sigma(r, s_j).
h_sigma is the normalized Neumann heat kernel at heat-time sigma**2/2.
The constant mode is included in every basis and forced expansion.
"""
from dataclasses import dataclass
from itertools import product
import numpy as np


@dataclass(frozen=True)
class Room:
    lengths: tuple = (5.0, 4.0, 3.0)
    c: float = 343.0
    rho: float = 1.20

    def __post_init__(self):
        values = np.asarray((*self.lengths, self.c, self.rho), dtype=float)
        if len(self.lengths) != 3 or not np.all(np.isfinite(values)) or np.any(values <= 0):
            raise ValueError("Three positive lengths, c and rho are required")


class ResonanceError(ValueError):
    """No field is returned for either incompatible or nonunique resonance."""

    def __init__(self, details):
        self.details = details
        super().__init__(details["status"])


class Modes:
    def __init__(self, cutoff_hz, room=Room()):
        if not np.isfinite(cutoff_hz) or cutoff_hz <= 0:
            raise ValueError("Positive finite cutoff required")
        self.room = room
        self.cutoff_hz = float(cutoff_hz)
        lengths = np.asarray(room.lengths)
        upper = np.ceil(2 * cutoff_hz * lengths / room.c).astype(int)
        n = np.array(list(product(*(range(int(v) + 1) for v in upper))), dtype=int)
        k2 = np.pi**2 * np.sum((n / lengths)**2, axis=1)
        keep = k2 <= (2 * np.pi * cutoff_hz / room.c)**2 * (1 + 16 * np.finfo(float).eps)
        n, k2 = n[keep], k2[keep]
        order = np.lexsort((n[:, 2], n[:, 1], n[:, 0], k2))
        self.n, self.k2 = n[order], k2[order]
        self.f = room.c * np.sqrt(self.k2) / (2 * np.pi)
        self.norm = np.sqrt(np.prod(np.where(self.n == 0, 1.0, 2.0) / lengths, axis=1))
        self.alpha = self.n * np.pi / lengths

    def points(self, points):
        p = np.asarray(points, dtype=float)
        if p.ndim != 2 or p.shape[1] != 3 or not np.all(np.isfinite(p)):
            raise ValueError("Points must be a finite N by 3 array")
        if np.any(p < 0) or np.any(p > np.asarray(self.room.lengths)):
            raise ValueError("Point outside the closed room")
        return p

    def basis(self, points):
        p = self.points(points)
        values = np.broadcast_to(self.norm, (len(p), len(self.n))).copy()
        for axis in range(3):
            values *= np.cos(p[:, axis, None] * self.alpha[None, :, axis])
        return values

    def derivative(self, points, axis):
        if axis not in (0, 1, 2):
            raise ValueError("axis must be 0, 1 or 2")
        p = self.points(points)
        values = np.broadcast_to(self.norm, (len(p), len(self.n))).copy()
        for a in range(3):
            phase = p[:, a, None] * self.alpha[None, :, a]
            values *= (-self.alpha[None, :, a] * np.sin(phase)) if a == axis else np.cos(phase)
        return values

    def synthesize(self, points, coefficients, chunk_size=256):
        p = self.points(points)
        a = np.asarray(coefficients, dtype=complex)
        if a.shape != self.k2.shape or not np.all(np.isfinite(a)):
            raise ValueError("Finite coefficient vector of the basis size required")
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError("Positive integer chunk size required")
        out = np.empty(len(p), dtype=complex)
        for start in range(0, len(p), chunk_size):
            stop = start + chunk_size
            out[start:stop] = self.basis(p[start:stop]) @ a
        if not np.all(np.isfinite(out)):
            raise FloatingPointError("Nonfinite field; no replacement or clipping performed")
        return out

    def source_coefficients(self, position, sigma=0.25):
        if not np.isfinite(sigma) or sigma <= 0:
            raise ValueError("Positive finite sigma required")
        return self.basis(np.asarray(position, dtype=float).reshape(1, 3))[0] * np.exp(-sigma**2 * self.k2 / 2)

    def solve_rhs(self, frequency_hz, rhs_coefficients):
        """Solve (-Delta-k^2)P=b from L2-projected complex RHS.

        Resonance tolerances classify floating point proximity; they do not alter
        denominators. Numerically unexcited resonance is still rejected because
        the forced solution is not unique. No arbitrary nullspace choice is made.
        """
        f = float(frequency_hz)
        if not np.isfinite(f) or f <= 0 or f > self.cutoff_hz:
            raise ValueError("Require 0 < frequency <= modal cutoff")
        b = np.asarray(rhs_coefficients, dtype=complex)
        if b.shape != self.k2.shape or not np.all(np.isfinite(b)):
            raise ValueError("Finite RHS vector of the basis size required")
        tolerance = max(1e-10, 64 * np.finfo(float).eps * max(1.0, f))
        resonant = np.flatnonzero(np.abs(self.f - f) <= tolerance)
        if len(resonant):
            excitation_tolerance = 128 * np.finfo(float).eps * max(float(np.max(np.abs(b))), np.finfo(float).tiny)
            excited = bool(np.any(np.abs(b[resonant]) > excitation_tolerance))
            raise ResonanceError({
                "status": "EXCITED_RESONANCE_NO_FINITE_SOLUTION" if excited else "NUMERICALLY_UNEXCITED_RESONANCE_NONUNIQUE",
                "frequency_hz": f, "resonance_tolerance_hz": tolerance,
                "excitation_roundoff_threshold": excitation_tolerance,
                "modes": [{"n": self.n[i].tolist(), "frequency_hz": float(self.f[i]),
                           "rhs_abs": float(abs(b[i]))} for i in resonant],
                "field_returned": False,
            })
        k2 = (2 * np.pi * f / self.room.c)**2
        with np.errstate(divide="raise", invalid="raise", over="raise"):
            a = b / (self.k2 - k2)
        nearest = int(np.argmin(np.abs(self.f - f)))
        fn = float(self.f[nearest])
        detuning = abs(fn - f) / max(fn, f)
        diagnostics = {
            "frequency_hz": f, "cutoff_hz": self.cutoff_hz,
            "mode_count": len(self.n), "nearest_mode": self.n[nearest].tolist(),
            "nearest_mode_hz": fn, "distance_hz": abs(fn - f),
            "relative_detuning": detuning,
            "near_resonance": bool(detuning <= 1e-4),
            "nearest_denominator_relative_frequency_sensitivity": 2 * f**2 / abs(fn**2 - f**2),
            "interpretation": "harmonic particular solution; no claim of asymptotic steady state",
        }
        if not np.all(np.isfinite(a)):
            raise FloatingPointError("Nonfinite coefficients; no replacement performed")
        return a, diagnostics

    def solve_sources(self, frequency_hz, sources):
        """sources: iterable of (position_m, complex volume_velocity_m3_s, sigma_m)."""
        source = np.zeros(len(self.n), dtype=complex)
        for position, Q, sigma in sources:
            Q = complex(Q)
            if not np.isfinite(Q):
                raise ValueError("Finite complex volume velocity required")
            source += Q * self.source_coefficients(position, sigma)
        rhs = 1j * self.room.rho * (2 * np.pi * frequency_hz) * source
        return self.solve_rhs(frequency_hz, rhs)
