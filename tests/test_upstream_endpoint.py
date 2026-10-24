import copy
import unittest
from check_upstream_endpoint import source_spec, direct, produce, consume, negative_controls
from bounded_decision import validate
import checker


class UpstreamEndpointTests(unittest.TestCase):
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
