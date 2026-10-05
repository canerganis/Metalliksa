"""Frozen solver-test fixture: the material values that used to be solve_toolpath defaults.

solve_toolpath now requires every alloy value (no defaults, no implicit alloy). The
Phase 22 solver tests were written, frozen and recorded against these exact numbers,
so they pass them explicitly to keep their numerics unchanged. This is a numerical
test fixture, NOT an alloy record: it is not Ti-6Al-4V from the material authority
(see four_alloy_materials) and must never be used by production code or the RPC.
"""

LEGACY_SOLVER_TEST_MATERIAL = {
    "rho": 4420.0,
    "L_f": 2.9e5,
    "T_solidus": 1878.0,
    "T_liquidus": 1928.0,
    "Lv": 9.7e6,
    "Rs": 173.93,
    "Tv": 3533.0,
    "cp_solid": 670.0,
    "cp_liquid": 730.0,
    "k_solid": 15.0,
    "k_liquid": 25.0,
}
