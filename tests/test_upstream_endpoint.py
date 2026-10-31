import copy
import unittest
from check_upstream_endpoint import source_spec, direct, produce, consume, negative_controls
from check_upstream_endpoint import source_document, source_packet, consume_source_packet, translate_pair
from bounded_decision import validate
import checker


class UpstreamEndpointTests(unittest.TestCase):
    def test_helper_valid_record_does_not_establish_wrong_source_map(self):
        expected = source_document()
        record = produce(expected['spec'])
        expected['spec']['before'] = expected['spec']['after'] = 'def patch(d, n):\n    return 0\n'
        spec = expected['spec']
        record['case'] = translate_pair(spec['id'], spec['width'], spec['domain'],
                                        spec['before'], spec['after'])
        for row in record['rows']:
            row['before'] = row['after'] = ['u', 0]
        record['counts'] = {'repair': 0, 'new-fault': 0, 'defined-equal': 256,
                            'defined-changed': 0, 'both-fault': 0}
        record['bounded_refinement'] = False
        self.assertFalse(consume(spec, record)['bounded_refinement'])
        with self.assertRaisesRegex(checker.Invalid, 'source-map-arithmetic'):
            consume_source_packet(expected, source_packet(expected, record))

    def test_source_packet_binds_identity_and_premises_not_only_helpers(self):
        expected = source_document()
        packet = source_packet(expected, produce(expected["spec"]))
        self.assertTrue(consume_source_packet(expected, packet)["bounded_refinement"])
        for key in ("commit", "parent", "common_context", "mapping", "before_source_excerpt"):
            changed = copy.deepcopy(packet)
            changed["source"][key] += " stale"
            with self.assertRaisesRegex(checker.Invalid, "upstream-correspondence-binding"):
                consume_source_packet(expected, changed)
        for value in (False, 1):
            changed = copy.deepcopy(packet)
            changed["premises"]["overflow_checks"] = value
            with self.assertRaisesRegex(checker.Invalid, "endpoint-premises"):
                consume_source_packet(expected, changed)

    def test_complete_domain_and_direct_baseline(self):
        spec = source_spec()
        record = produce(spec)
        got = consume(spec, record)
        self.assertEqual(got["inputs_checked"], 256)
        self.assertEqual(got["counts"], {"repair": 120, "new-fault": 0,
            "defined-equal": 136, "defined-changed": 0, "both-fault": 0})
        self.assertTrue(got["bounded_refinement"])
        self.assertEqual(direct(0, 1), (["fault", "add-overflow"], ["u", 0]))
        self.assertEqual(direct(15, 0), (["u", 15], ["u", 15]))

    def test_transfer_rejections(self):
        spec = source_spec()
        self.assertEqual(set(negative_controls(spec, produce(spec))),
                         {"missing-input", "false-outcome", "false-verdict", "stale-source"})

    def test_single_witness_does_not_replace_complete_record(self):
        spec = source_spec()
        record = produce(spec)
        record["rows"] = [record["rows"][1]]
        with self.assertRaisesRegex(checker.Invalid, "complete-domain"):
            validate(spec, record)

    def test_shared_context_is_not_silently_a_larger_domain(self):
        spec = source_spec()
        record = produce(spec)
        larger = copy.deepcopy(spec)
        larger["domain"][0] = [0, 16]
        with self.assertRaisesRegex(checker.Invalid, "source-binding"):
            validate(larger, record)


if __name__ == "__main__":
    unittest.main()
