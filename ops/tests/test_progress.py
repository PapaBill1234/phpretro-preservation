"""Roadmap measurement cannot promote scaffolds, alter units or dispatch work."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from harness import tmpdir, REPO
import progress as p
import orchestrator as o


class ProgressTest(unittest.TestCase):
    def setUp(self):
        self.repo = tmpdir("progress-")
        (self.repo / "docs").mkdir()
        (self.repo / "docs/spec.md").write_text("Synthetic boundary only.\n")
        self.canonical = {"F1": {"id": "F1", "status": "todo", "title": "Boundary"}}
        self.runtime = {"F1": {"id": "F1", "status": "todo"}}
        self.deliveries = {"F1": [{"pr": 1, "head": "example", "merged_at": "fixture", "branch": "unit/F1"}]}
        self.catalog = {"assessment_date": "fixture", "units": [{"id": "F1", "area": "Redis", "classification": "scaffold", "reason": "Memory store only", "criteria": [{"path": "docs/spec.md", "line": 1, "quote": "Synthetic boundary only.", "kind": "written"}], "evidence": [{"path": "docs/spec.md", "line": 1, "fingerprint": p.fingerprint(self.repo / "docs/spec.md")}], "assessed_prs": [1], "tests": [], "production_wiring": "n/a", "gaps": []}], "platform": [], "gaps": [], "stand_ins": [], "test_doubles": [], "legacy_capture": {"reason": "skipped"}}

    def build(self):
        return p.build(self.repo, self.canonical, self.runtime, self.deliveries, self.catalog, timestamp="fixture")

    def test_git_merge_remains_scaffold_and_status_divergence_is_reported(self):
        before = copy.deepcopy((self.canonical, self.runtime, self.deliveries))
        result = self.build()
        self.assertEqual(result["units"][0]["classification"], "scaffold")
        self.assertEqual(result["merged_scaffold_units"], ["F1"])
        self.assertEqual(len(result["divergences"]), 1)
        self.assertEqual(before, (self.canonical, self.runtime, self.deliveries))

    def test_changed_sources_and_new_delivery_do_not_auto_promote(self):
        (self.repo / "docs/spec.md").write_text("Changed acceptance.\n")
        result = self.build()["units"][0]
        self.assertFalse(result["assessment_current"])
        self.assertEqual(result["classification"], "not started")
        self.deliveries["F1"].append({"pr": 2})
        self.assertFalse(self.build()["units"][0]["assessment_current"])

    def test_implemented_requires_delivery_wiring_and_tests(self):
        row = self.catalog["units"][0]
        row["classification"] = "implemented"
        row["production_wiring"] = "real adapter"
        with self.assertRaises(ValueError):
            self.build()
        row["tests"] = ["real behavior test"]
        self.assertEqual(self.build()["units"][0]["classification"], "implemented")
        row["classification"] = "verified"
        row["verification"] = "n/a: not compared"
        with self.assertRaises(ValueError):
            self.build()
        row["classification"] = "implemented"
        row["production_wiring"] = "n/a: incomplete"
        with self.assertRaises(ValueError):
            self.build()

    def test_support_units_do_not_inflate_canonical_denominator(self):
        self.runtime["RF1"] = {"id": "RF1", "status": "merged"}
        result = self.build()
        self.assertEqual(result["canonical_total"], 1)
        self.assertEqual(result["runtime_total"], 2)
        self.assertEqual(sum(sum(counts.values()) for counts in result["counts_by_area"].values()), 1)

    def test_invalid_catalog_fails_measurement_without_changing_runtime(self):
        (self.repo / "ops").mkdir()
        (self.repo / "ops/roadmap-assessment.json").write_text("invalid")
        result = p.publish(self.repo, self.canonical, self.runtime, self.deliveries,
                           self.repo / "progress.json", o.control.atomic_json)
        self.assertFalse(result["available"])
        self.assertEqual(self.runtime["F1"]["status"], "todo")

    def test_new_and_historical_pr_mappings_require_git_ancestry(self):
        inventory = [{"number": 1, "headRefName": "old/history", "mergeCommit": {"oid": "fixture-commit"}, "mergedAt": "fixture"}]
        with self.assertRaises(ValueError):
            p.delivery_map(self.repo, inventory, self.runtime, lambda commit: False, self.catalog)
        mapped = p.delivery_map(self.repo, inventory, self.runtime, lambda commit: True, self.catalog)
        self.assertEqual(mapped["F1"][0]["pr"], 1)

    def test_read_escape_is_rejected(self):
        self.catalog["units"][0]["evidence"][0]["path"] = "../outside.md"
        with self.assertRaises(ValueError):
            self.build()


class CatalogTest(unittest.TestCase):
    def test_every_reserved_card_is_assessed_and_product_claims_are_conservative(self):
        catalog = json.loads((REPO / "ops/roadmap-assessment.json").read_text())
        canonical = {u["id"] for u in o.parse_yaml((REPO / "units.yaml").read_text())["units"]}
        rows = {u["id"]: u for u in catalog["units"]}
        self.assertTrue(canonical <= rows.keys())
        self.assertEqual(len(canonical), 56)
        self.assertEqual(rows["F35"]["classification"], "scaffold")
        self.assertEqual(rows["F38-a"]["classification"], "scaffold")
        self.assertEqual(rows["F40"]["classification"], "designed")
        self.assertEqual(rows["F21"]["classification"], "scaffold")
        self.assertTrue(any(p["area"] == "themes: Atom CMS" for p in catalog["platform"]))
        for row in rows.values():
            for source in row["criteria"]:
                self.assertIn(source["quote"], (REPO / source["path"]).read_text())
            for e in row["evidence"]:
                self.assertEqual(e["fingerprint"], p.fingerprint(REPO / e["path"]))

    def test_publication_has_no_worker_or_provider_calls(self):
        state = tmpdir("publish-")
        with patch.object(o, "STATE_DIR", state), patch.object(o, "_progress_inventory", []), patch.object(o, "git", return_value=(0, "")), patch.object(o, "start_build", side_effect=AssertionError("must not dispatch")), patch.object(o, "hermes_run", side_effect=AssertionError("must not call provider")):
            result = o.publish_roadmap_progress({})
        self.assertTrue(result["available"], result)
        self.assertEqual(result["git_merged_units"], 0)
        self.assertTrue((state / "progress.json").is_file())


if __name__ == "__main__":
    unittest.main()
