"""Research fork of the enthalpy-FV reference transient with surface evaporative cooling.

Nothing in this package is part of the frozen implementation closure
(`lpbf_simulation.IMPLEMENTATION_SOURCE_FILES`); it imports the frozen helpers read-only.
Scope: evaporative heat sink (Hertz-Knudsen-Langmuir / Anisimov flux with Clausius-Clapeyron
saturation pressure), surface Gaussian flux source, ever-melted envelope operator.
Out of scope (stated): recoil-pressure-driven flow, surface recession, keyhole cavity.
"""
