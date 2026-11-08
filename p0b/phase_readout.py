"""Phase-readout conditioning only; no pressure correction or physical damping."""
import math
import sys


def classify_phase(value, uncancelled_modal_scale_pa, mode_count):
    """Use a gamma_m roundoff scale to avoid reporting cancellation-noise phase.

    S = sum_n |phi_n(o)| rho omega sum_j |Q_j h_n(s_j)| / |lambda_n-k^2|.
    gamma_m = m*eps/(1-m*eps), m=2*N+16 (two real dot products plus
    scalar/source operations). This is a conservative conditioning diagnostic,
    not a certified error enclosure for libm, eigenvalues, or the physical model.
    Raw complex pressure is retained even when its phase is withheld.
    """
    if not (math.isfinite(value.real) and math.isfinite(value.imag)
            and math.isfinite(uncancelled_modal_scale_pa) and uncancelled_modal_scale_pa >= 0):
        raise ValueError("Finite pressure and nonnegative phase scale required")
    if not isinstance(mode_count, int) or mode_count <= 0:
        raise ValueError("Positive modal count required")
    m = 2 * mode_count + 16
    product = m * sys.float_info.epsilon
    if product >= 1:
        raise ValueError("Roundoff diagnostic outside its domain")
    gamma = product / (1 - product)
    threshold = gamma * uncancelled_modal_scale_pa
    amplitude = abs(value)
    if amplitude == 0:
        status, degrees = "ZERO_UNDEFINED", None
    elif amplitude <= threshold:
        status, degrees = "NEAR_ZERO_UNRESOLVED", None
    else:
        status, degrees = "RESOLVED_NUMERICAL", math.degrees(math.atan2(value.imag, value.real))
    return {"status": status, "degrees": degrees, "uncancelled_modal_scale_pa": uncancelled_modal_scale_pa,
            "roundoff_threshold_pa": threshold, "gamma": gamma, "operation_count": m,
            "rule": "gamma_(2N+16) times uncancelled absolute modal sum; readout only"}
