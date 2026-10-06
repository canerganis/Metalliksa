"""Source-bound P2 Elastic Constants helper; registry integration belongs to the parent.

This describes requests reachable from MaterialsProjectExplorer, not every legacy
DFTStructureInput field. No solver, schema, registry or evidence ceiling is changed.
"""
from module_contract import (
    Evidence, InputField, Lifecycle, ModuleContract, Operation, Oracle,
    OutputSchema, Authority, TestRefs, View, OWNER_UNASSIGNED, FORBIDDEN_CLAIM_KEYS,
)


# Real availability values are explicit transport, not emitted evidence statuses.
AVAILABILITY_OUTPUTS = {
    'status': ('available', 'unavailable'),
    'directionalYoungsModuliStatus': ('available', 'unavailable'),
}


def _selector(key, label, values, default, note):
    return InputField(key=key, label=label, unit=None, quantity_kind='selection',
                      min=None, max=None, default=default, value_type='enum',
                      enum=values, note=note)


def build_elasticity_contract(seed) -> ModuleContract:
    """Build the P2 form contract without registering it or inventing blank defaults."""
    if seed['id'] != 'materials-project':
        raise ValueError('Elastic Constants preserves the materials-project identity')
    operation = Operation(
        id='calculate-elasticity', method='POST', route='/api/python/dft-properties',
        authority=Authority(kind='python-ipc', script='python/dft_property_calculator.py',
                            timeout_ms=25000, warm=True),
        input=(
            _selector('input_mode', 'Elastic constants source', ('custom', 'isotropic'), 'custom',
                      'Initial UI selector only; always explicitly sent. Missing backend mode retains legacy '
                      'library behavior, outside this P2 form contract.'),
            _selector('crystal_system', 'Crystal symmetry',
                      ('cubic', 'hexagonal', 'trigonal', 'tetragonal', 'orthorhombic', 'isotropic'),
                      'cubic', 'Initial custom selector only; isotropic mode always sends isotropic. '
                      'Both selectors are explicit request keys, not filled from the specimen.'),
        ),
        undeclared_input=('custom_c_ij', 'formula', 'density', 'k_vrh', 'g_vrh',
                          'molar_mass', 'atoms_per_formula_unit'),
        # Union inventory, not required keys: unavailable results have no tensor/moduli.
        output=OutputSchema(status_key=None,
            fields=('success', 'status', 'engine', 'scientificModel', 'label', 'isDft', 'constantsOrigin',
                    'referenceStatus', 'sourceNotes', 'computeTimeMs', 'materialInfo',
                    'elasticStiffnessMatrix_Cij_GPa', 'elasticComplianceMatrix_Sij_1_over_GPa',
                    'bornStability', 'voigtReussHillModuli', 'mechanicalIntegrityIndices',
                    'acousticAndThermalProperties', 'directionalYoungsModuli', 'directionalYoungsModuliStatus',
                    'directionalYoungsModuliReason', 'unavailableCode', 'reason', 'isPythonEngine'),
            transport_values=tuple(AVAILABILITY_OUTPUTS.items()) +
                             (('referenceStatus', ('supplied-by-caller',)),)),
    )
    return ModuleContract(
        id=seed['id'], version='0.1.0', owner=OWNER_UNASSIGNED, workspace=seed['workspace'],
        label=seed['label'], description=seed['description'], next=seed['next'], maturity=seed['scope'],
        navigation='listed', view=View(component=seed['viewComponent'], export=seed['viewExport']),
        migration_state='contracted', operations=(operation,),
        lifecycle=Lifecycle(background_work='none', resources=('fetch',)),
        evidence=Evidence(emits=(), ceiling='screening-only', forbidden_claims=FORBIDDEN_CLAIM_KEYS,
            note='No evidence status is emitted. status and directionalYoungsModuliStatus are availability '
                 '(available/unavailable), not evidence; acousticAndThermalProperties.status, '
                 'voigtReussHillModuli.status and mechanicalIntegrityIndices.status are also availability. '
                 'Top-level availability keys are explicitly declared transport values with no evidence status key. '
                 'referenceStatus=supplied-by-caller is provenance, not '
                 'measurement. Contract oracle pending; existing algebraic/regression tests do not establish '
                 'experimental validation or an applicability domain.'),
        tests=TestRefs(oracle=Oracle(status='pending'), schema='python/test_module_contract_elasticity.py',
                       docs='docs/modules/materials-project.md'),
        legacy_notes=(
            'Scope is the explicit Calculate P2 form: blank initial numerical fields; no autoCalculate or '
            'shared specimen/process auto-fill. Backend library mode and absent-mode legacy behavior remain '
            'outside this operation; explicit custom/isotropic never use library constants or density.',
            'custom_c_ij is a dynamic nested map in GPa, recorded as undeclaredInput, not fake scalar fields. '
            'The form requires complete selected symmetry: cubic c11,c12,c44; hexagonal c11,c33,c12,c13,c44; '
            'trigonal also c14; tetragonal also c66; orthorhombic c11,c22,c33,c12,c13,c23,c44,c55,c66; '
            'custom isotropic c11,c12. Finite values are required; diagonals positive, off-diagonals may be negative.',
            'isotropic requires finite positive k_vrh and g_vrh in GPa, with no custom_c_ij. The SDK cannot '
            'encode conditional required fields or blank numeric defaults; these are undeclaredInput, with '
            'actual validation in buildElasticityInput and the Python authority. input_problems does not '
            'validate undeclared keys, tensor completeness, positivity or mode/symmetry combinations.',
            'formula is optional trimmed text. density is optional finite positive g/cm^3; blank is omitted, '
            'not replaced by 8.2 or library density. Optional molar_mass (g/mol) and atoms_per_formula_unit '
            '(formula-unit atom count) must be entered together and finite positive. No numerical defaults '
            'or unsupported min/max applicability limits are invented.',
            'Successful output inventories Cij (GPa), Sij (1/GPa), VRH K/G/E (GPa), dimensionless Poisson '
            'ratio and anisotropy indices, Born mechanical stability and optional acoustic/directional results. '
            'Born is elastic mechanical stability, not phase stability; VRH is homogenization, not DFT. '
            'isDft is false; materialInfo phase/electronic metadata is not calculated by this P2 form.',
            'status=available/unavailable and directionalYoungsModuliStatus=available/unavailable are '
            'explicit transport values, separate from evidence. The output '
            'fields are a conditional union, not mandatory non-null outputs. unavailableCode/reason accompanies '
            'solver unavailable results (HTTP 200), without fabricated tensor/moduli. Missing density leaves '
            'acoustic values null/unavailable while directional E may remain available. Missing composition '
            'or paired mass/atom inputs leaves Debye quantities null even when velocities are available.',
            'Service failures return unavailable with PYTHON_NOT_REQUESTED, PYTHON_BAD_RESPONSE, '
            'PYTHON_HTTP_ERROR or PYTHON_UNREACHABLE; no browser surrogate calculation. isPythonEngine and '
            'computeTimeMs are execution metadata, not evidence. Raw route failures/CLI errors are normalized '
            'by calculateDFTProperties before reaching this view.',
            'Request generation is held in useRef: begin on Calculate, invalidate on edits and unmount; '
            'old success/error including A-B-A is ignored. Fetch is not aborted by the generation gate; '
            'the Python IPC deadline is enforced separately. Pure gate tests do not prove mounted effects.',
            'No physical applicability domain is declared. Source tests cover numerical formulas and software '
            'regressions; they do not qualify a material or validate supplied constants experimentally.',
        ),
        source_refs=(
            'src/utils/elasticityInput.ts::buildElasticityInput',
            'src/utils/elasticityRequestGate.ts::createElasticityRequestGate',
            'src/components/MaterialsProjectExplorer.tsx::MaterialsProjectExplorer',
            'src/components/MaterialsProjectElasticityPanel.tsx',
            'src/services/pythonComputationService.ts',
            'routes/physics.ts:62-64#/api/python/dft-properties',
            'routes/physics.ts:11-17#25000',
            'python/persistent_ipc_service.py:95-100#dft_property_calculator',
            'python/dft_property_calculator.py::calculate_dft_properties',
            'python/dft_property_calculator.py::_calculate_elasticity',
            'python/dft_property_calculator.py::_unavailable_result',
            'python/dft_property_calculator.py::_acoustic_and_directional',
            'python/test_elasticity_input_mode.py', 'python/test_elasticity_oracle.py',
            'tests/elasticity-input.test.ts', 'tests/elasticity-request-gate.test.ts',
        ),
        seed_derived=('label', 'description', 'next', 'maturity'),
    )
