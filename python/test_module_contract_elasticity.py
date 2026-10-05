"""P2 contract checks against real payloads and the unchanged Python authority."""
import unittest

from module_contract import contract_from_dict
from module_contracts_elasticity import build_elasticity_contract, AVAILABILITY_OUTPUTS
from module_registry import load_seed, contract_ref_problems
from dft_property_calculator import calculate_dft_properties


class ElasticityContractTests(unittest.TestCase):
    def setUp(self):
        self.seed = next(row for row in load_seed() if row['id'] == 'materials-project')
        self.contract = build_elasticity_contract(self.seed)
        self.operation = self.contract.operations[0]

    def test_identity_roundtrip_and_resolvable_refs(self):
        self.assertEqual(self.contract.id, 'materials-project')
        self.assertEqual(self.contract.view.component, self.seed['viewComponent'])
        self.assertEqual(self.contract.next, self.seed['next'])
        self.assertEqual(contract_from_dict(self.contract.to_dict()), self.contract)
        # The parent emits this documentation when registering the helper.
        self.assertEqual(contract_ref_problems(self.contract, generated=frozenset({self.contract.tests.docs})), [])

    def test_does_not_mutate_seed_or_accept_another_module(self):
        original = dict(self.seed)
        build_elasticity_contract(self.seed)
        self.assertEqual(self.seed, original)
        with self.assertRaises(ValueError):
            build_elasticity_contract({**self.seed, 'id': 'composition'})

    def test_actual_route_authority_and_lifecycle(self):
        self.assertEqual((self.operation.method, self.operation.route), ('POST', '/api/python/dft-properties'))
        authority = self.operation.authority
        self.assertEqual((authority.kind, authority.script, authority.timeout_ms, authority.warm),
                         ('python-ipc', 'python/dft_property_calculator.py', 25000, True))
        self.assertEqual(self.contract.lifecycle.resources, ('fetch',))
        self.assertEqual(self.contract.lifecycle.background_work, 'none')
        notes = ' '.join(self.contract.legacy_notes)
        for boundary in ('explicit Calculate', 'A-B-A', 'unmount', 'not aborted', 'shared specimen'):
            self.assertIn(boundary, notes)

    def test_ui_modes_do_not_advertise_legacy_library_fallback(self):
        for mode in ('custom', 'isotropic'):
            self.assertEqual(self.operation.input_problems({'input_mode': mode, 'crystal_system': 'cubic'}), [])
        self.assertTrue(self.operation.input_problems({'input_mode': 'library', 'crystal_system': 'cubic'}))
        self.assertTrue(self.operation.input_problems({'crystal_system': 'cubic'}))
        self.assertTrue(self.operation.input_problems({'input_mode': 'custom', 'crystal_system': 'monoclinic'}))

    def test_optional_blank_values_and_nested_tensor_have_no_invented_defaults(self):
        undeclared = set(self.operation.undeclared_input)
        self.assertEqual(undeclared, {'custom_c_ij', 'formula', 'density', 'k_vrh', 'g_vrh',
                                     'molar_mass', 'atoms_per_formula_unit'})
        self.assertEqual({field.key for field in self.operation.input}, {'input_mode', 'crystal_system'})
        self.assertEqual(self.operation.input_problems({
            'input_mode': 'custom', 'crystal_system': 'cubic',
            'custom_c_ij': {'c11': 205, 'c12': 105, 'c44': 50}}), [])
        # This schema check deliberately cannot validate the nested/conditional keys.
        self.assertEqual(self.operation.input_problems({
            'input_mode': 'custom', 'crystal_system': 'cubic', 'custom_c_ij': {}}), [])
        out = calculate_dft_properties({'input_mode': 'custom', 'crystal_system': 'cubic', 'custom_c_ij': {}})
        self.assertEqual(out['status'], 'unavailable')

    def assert_output_inventory(self, output):
        self.assertFalse(set(output) - set(self.operation.output.fields) - set(AVAILABILITY_OUTPUTS))
        for key, values in AVAILABILITY_OUTPUTS.items():
            if key in output:
                self.assertIn(output[key], values)

    def test_real_custom_result_has_no_library_density_or_evidence_status(self):
        out = calculate_dft_properties({'input_mode': 'custom', 'formula': 'Ni', 'crystal_system': 'cubic',
                                       'custom_c_ij': {'c11': 205, 'c12': 105, 'c44': 50}})
        self.assert_output_inventory(out)
        self.assertEqual(out['constantsOrigin'], 'custom-user-supplied')
        self.assertIsNone(out['materialInfo']['density'])
        self.assertEqual(out['acousticAndThermalProperties']['status'], 'unavailable')
        self.assertEqual(out['status'], 'available')
        self.assertIsNone(self.operation.output.status_key)
        self.assertEqual(self.contract.evidence.emits, ())
        self.assertEqual(self.contract.tests.oracle.status, 'pending')
        self.assertEqual(self.contract.evidence.ceiling, 'screening-only')

    def test_missing_isotropic_input_is_unavailable_not_a_library_result(self):
        out = calculate_dft_properties({'input_mode': 'isotropic', 'formula': 'Ni', 'k_vrh': 100})
        self.assert_output_inventory(out)
        self.assertEqual(out['status'], 'unavailable')
        self.assertFalse(out['success'])
        self.assertNotIn('voigtReussHillModuli', out)

    def test_isotropic_density_does_not_invent_debye_composition(self):
        out = calculate_dft_properties({'input_mode': 'isotropic', 'crystal_system': 'isotropic',
                                       'k_vrh': 100, 'g_vrh': 40, 'density': 8})
        self.assert_output_inventory(out)
        self.assertEqual(out['constantsOrigin'], 'isotropic-from-supplied-K-G')
        self.assertIsNone(out['acousticAndThermalProperties']['debyeTemperature_K'])
        self.assertIsNotNone(out['acousticAndThermalProperties']['longitudinalSoundVelocity_m_s'])

    def test_unstable_tensor_is_an_available_result_with_unavailable_acoustics(self):
        out = calculate_dft_properties({'input_mode': 'custom', 'crystal_system': 'cubic',
                                       'custom_c_ij': {'c11': 100, 'c12': 150, 'c44': 50}, 'density': 8})
        self.assert_output_inventory(out)
        self.assertEqual(out['status'], 'available')
        self.assertEqual(out['directionalYoungsModuliStatus'], 'unavailable')
        self.assertIsNone(out['directionalYoungsModuli'])
        self.assertEqual(out['acousticAndThermalProperties']['status'], 'unavailable')
        self.assertIsNone(out['acousticAndThermalProperties']['debyeTemperature_K'])


if __name__ == '__main__':
    unittest.main()
