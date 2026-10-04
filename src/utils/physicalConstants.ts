/**
 * Exact SI 2019 molar gas constant and Faraday constant for the client-side
 * duplicates of the migrated Python solvers (Tafel, Pourbaix, CALPHAD fallbacks).
 *
 * Mirrors python/physical_constants.py GAS_CONSTANT_R / FARADAY (Phase 6a design
 * step (b)); python/test_physical_constants.py checks that the two files agree.
 * Both are exact products of SI defining constants (CODATA 2018 / SI 2019):
 * R = N_A * k, F = N_A * e. The printed CODATA truncations 8.314462618 and
 * 96485.33212 they replace differ by 1.8e-11 and 3.4e-11 relative.
 */
// Literals are the shortest round-trip decimal of the IEEE double nearest to the exact
// products 8.31446261815324 and 96485.3321233100184 (same doubles as the Python floats).
export const GAS_CONSTANT_R = 8.31446261815324; // J / (mol K), exact N_A * k
export const FARADAY_CONSTANT = 96485.33212331001; // C / mol, exact N_A * e
