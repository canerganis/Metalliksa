"""Versioned result identity binding; consistency is not scientific validation.

Hashes use Python sorted compact ASCII-escaped JSON (v1), not a universal
cross-language canonical JSON format. Existing result snapshots hold the data.
"""
import hashlib
import json
import math


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def _verify_material_revision(material):
    if 'materialRevisionSha256' not in material:
        return  # Legacy snapshots predate the additive material identity.
    if (type(material.get('materialIdentitySchemaVersion')) is not int
            or material['materialIdentitySchemaVersion'] != 1
            or not isinstance(material.get('materialId'), str)
            or not material['materialId'].strip()
            or material.get('provenanceClass') not in (
                'estimated-legacy', 'user-supplied-unverified')
            or not isinstance(material.get('materialRevisionSha256'), str)):
        raise ValueError('LPBF material revision identity is invalid')
    snapshot = {key: value for key, value in material.items()
                if key != 'materialRevisionSha256'}
    try:
        expected = hashlib.sha256(_encoded(snapshot)).hexdigest()
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('LPBF material revision snapshot is not finite JSON') from error
    if expected != material['materialRevisionSha256']:
        raise ValueError('LPBF material revision identity mismatch')


def build_core_contract(settings, material, solver_id, effective_mode):
    """Bind resolved inputs and material to an allowlisted executed model."""
    if not isinstance(settings, dict) or not isinstance(material, dict):
        raise ValueError('LPBF core contract requires resolved settings and material')
    _verify_material_revision(material)
    if settings.get('thermalModelId') is not None and solver_id != 'layered-enthalpy-fv-1':
        raise ValueError('Versioned thermal model does not match the executed solver')
    requested = settings.get('backend')
    if requested not in ('auto', 'reference', 'openfoam-thermal'):
        raise ValueError('LPBF core contract has unknown requested backend')
    support_material = None
    if effective_mode == 'screening' and solver_id == 'rosenthal+goldak':
        model, backend, transient = 'analytical-conduction-screening-v1', 'analytical', False
    elif effective_mode == 'standard' and solver_id == 'layered-enthalpy-fv-1':
        if (requested != 'reference'
                or settings.get('thermalModelId') != 'layered-plate-enthalpy-v1'
                or settings.get('surfaceMode') != 'bare-plate'
                or settings.get('scanAngle_deg') != 0
                or settings.get('layers') != 1 or settings.get('tracks') != 1
                or settings.get('study') != 'none'
                or settings.get('mode') != 'standard'
                or material.get('materialId') != 'in718'):
            raise ValueError('Layered-plate solver/model selection is inconsistent')
        required = ('plateThickness_um', 'supportThickness_um', 'contactResistance_m2K_W',
                    'supportBottomBoundary', 'incidenceAngle_deg', 'incidenceAzimuth_deg',
                    'beamProfileModelId', 'sourcePenetration_um')
        if any(key not in settings for key in required):
            raise ValueError('Layered-plate settings are incomplete')
        for key in ('plateThickness_um', 'supportThickness_um', 'contactResistance_m2K_W',
                    'incidenceAngle_deg', 'incidenceAzimuth_deg', 'sourcePenetration_um'):
            value = settings[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Layered-plate settings contain an invalid numeric value')
        if (settings['plateThickness_um'] <= 0 or settings['supportThickness_um'] <= 0
                or settings['contactResistance_m2K_W'] < 0
                or not 0 <= settings['incidenceAngle_deg'] < 90
                or not 0 <= settings['incidenceAzimuth_deg'] < 360
                or not 5 <= settings['sourcePenetration_um'] <= 150
                or settings['beamProfileModelId'] != 'assumed-oblique-gaussian-normal-plane-v1'
                or settings['supportBottomBoundary'] not in ('adiabatic', 'isothermal-at-preheat')):
            raise ValueError('Layered-plate solver/model selection is inconsistent')
        from lpbf_ss304_support_material import ss304_support_thermal_snapshot
        model, backend, transient = 'layered-plate-enthalpy-v1', 'numpy-reference', True
        support_material = ss304_support_thermal_snapshot()
    elif effective_mode in ('standard', 'calibration') and solver_id in (
            'enthalpy-fv-6', 'metalliksaThermal-OpenFOAM14-6'):
        backend = 'numpy-reference' if solver_id == 'enthalpy-fv-6' else 'openfoam-thermal'
        expected = 'reference' if backend == 'numpy-reference' else 'openfoam-thermal'
        if requested not in ('auto', expected):
            raise ValueError('LPBF core contract requested/executed backend mismatch')
        if settings.get('powderGridPolicy') == 'layer-conforming':
            if (settings.get('surfaceMode') != 'powder-layer'
                    or settings.get('mode') != 'standard'
                    or requested != expected):
                raise ValueError('Layer-conforming powder grid requires a matching standard powder backend')
            model = 'stationary-enthalpy-conduction-layer-conforming-v1'
        else:
            model = 'stationary-enthalpy-conduction-v1'
        transient = True
    else:
        raise ValueError('LPBF core contract has unknown solver/mode combination')
    if solver_id == 'layered-enthalpy-fv-1' and support_material is None:
        raise ValueError('Layered-plate material stack is incomplete')

    if support_material is None:
        material_sha256 = hashlib.sha256(_encoded(material)).hexdigest()
        units = dict(power='W', speed='mm/s', length='um', preheat='degC',
                     temperature='K', internalLength='m', time='s', energy='J',
                     beamDiameter='1/e2-intensity')
        resolved_physics = dict(conduction=True, transient=transient, latentHeat=transient,
                                momentum=False, freeSurface=False, evaporation=False)
        schema_version = 1
    else:
        ordered_materials = [material, support_material]
        material_sha256 = hashlib.sha256(_encoded(ordered_materials)).hexdigest()
        units = dict(power='W', speed='mm/s', length='um', preheat='degC',
                     temperature='K', internalLength='m', time='s', energy='J',
                     beamDiameter='1/e2-intensity', incidenceAngle='deg',
                     incidenceAzimuth='deg', contactResistance='m2-K/W')
        resolved_physics = dict(
            conduction=True, transient=True, latentHeat=True,
            momentum=False, freeSurface=False, evaporation=False,
            layeredMaterials=True,
            interfaceModelId='planar-series-resistance-v1',
            contactResistanceModelId='explicit-area-specific-resistance',
            supportMaterialRevisionSha256=support_material['materialRevisionSha256'],
            beamSourceModelId='assumed-oblique-gaussian-normal-plane-v1',
            supportBottomBoundaryId=settings['supportBottomBoundary'],
        )
        schema_version = 2
    return dict(schemaVersion=schema_version, modelId=model, actualBackend=backend,
        requestedBackend=requested, effectiveMode=effective_mode, solverId=solver_id,
        inputSha256=hashlib.sha256(_encoded(settings)).hexdigest(),
        materialSha256=material_sha256,
        units=units,
        resolvedPhysics=resolved_physics,
        evidenceClass='unvalidated-model')


def enforce_core_contract(result):
    """Validate present bindings, leaving true legacy absence unmodified."""
    if 'coreContract' not in result:
        return
    try:
        expected = build_core_contract(result['settings'], result['material'],
                                       result['solver']['id'], result['effectiveMode'])
        # JSON comparison also rejects booleans/numbers that Python equates.
        if _encoded(result['coreContract']) != _encoded(expected):
            raise ValueError('LPBF core contract identity mismatch')
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError(f'LPBF core contract invalid: {error}') from error
