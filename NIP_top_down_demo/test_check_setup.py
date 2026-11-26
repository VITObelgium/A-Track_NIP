# Author: Alexandra Evans <alexandra.evans@vito.be>
# Copyright © 2026 VITO
#
# SPDX-FileCopyrightText: 2026 VITO
# SPDX-License-Identifier: MIT
#
# Please acknowledge the author and copyright holder in outputs produced using these scripts.
#
# Licensed under the MIT License.
# See LICENCE-SCRIPTS.md in the repository root for the licence terms.

"""Standard-library tests for the preflight check; no geospatial dependencies needed."""
from contextlib import redirect_stdout
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import Check_setup


class SetupCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input_file = self.root / "input"
        self.input_file.write_bytes(b"data")
        self.settings = SimpleNamespace(**{
            name: self.input_file for name in (
                "site_polygon_path", "raster_opening_path", "raster_closing_path",
                "lut_path", "threat_csv", "legend_qml_path", "ref_polygon_path",
                "ref_raster_opening_path", "ref_raster_closing_path")
        })
        for name in ("extent_output_dir", "transformations_output_dir", "conversion_output_dir",
                     "connectivity_output_dir", "productivity_output_dir"):
            setattr(self.settings, name, self.root / "outputs" / name)
        self.settings.tprod_dir = self.root / "TPROD"
        self.settings.year_labels = ("2021", "2024")

    def test_dependency_import_errors_are_reported_and_check_continues(self):
        requirements = self.root / "requirements.txt"
        requirements.write_text("# packages\nnumpy\n\nscikit-image\n", encoding="utf-8")
        with patch.object(Check_setup.importlib, "import_module",
                          side_effect=[ImportError("missing numpy"), object()]) as importer:
            results = Check_setup.check_dependencies(requirements)
        self.assertEqual([status for status, _ in results], ["FAIL", "OK"])
        self.assertEqual(importer.call_args_list[-1].args, ("skimage",))
        self.assertIn("missing numpy", results[0][1])

    def test_default_paths_pass_without_productivity_tiles_or_creating_outputs(self):
        results = Check_setup.check_paths(self.settings)
        self.assertFalse(any(status == "FAIL" for status, _ in results))
        self.assertTrue(any(status == "WARN" for status, _ in results))
        self.assertEqual(list(self.root.iterdir()), [self.input_file])

    def test_missing_file_fails(self):
        self.settings.lut_path = self.root / "missing.csv"
        self.assertTrue(any(status == "FAIL" and "lut_path" in message
                            for status, message in Check_setup.check_paths(self.settings)))

    def test_disabled_optional_files_are_accepted(self):
        self.settings.legend_qml_path = None
        self.settings.ref_raster_opening_path = None
        self.settings.ref_raster_closing_path = None
        self.settings.raster_closing_path = None
        results = Check_setup.check_paths(self.settings)
        self.assertFalse(any(status == "FAIL" for status, _ in results))

    def test_incomplete_reference_pair_fails(self):
        self.settings.ref_raster_closing_path = None
        self.assertTrue(any(status == "FAIL" for status, _ in Check_setup.check_paths(self.settings)))

    def test_productivity_requires_tiles_for_every_year(self):
        self.settings.tprod_dir.mkdir()
        (self.settings.tprod_dir / "VPP_2021_S2_T30UWD_s1_TPROD.tif").write_bytes(b"tile")
        results = Check_setup.check_paths(self.settings, productivity=True)
        self.assertEqual(sum(status == "FAIL" for status, _ in results), 1)
        self.assertTrue(any(status == "FAIL" and "2024" in message for status, message in results))
        (self.settings.tprod_dir / "VPP_2024_S2_T30UWD_s1_TPROD.tif").write_bytes(b"tile")
        self.assertFalse(any(status == "FAIL" for status, _ in
                             Check_setup.check_paths(self.settings, productivity=True)))

    def test_productivity_requires_closing_raster(self):
        self.settings.raster_closing_path = None
        self.assertTrue(any(status == "FAIL" and "closing site raster" in message for status, message in
                            Check_setup.check_paths(self.settings, productivity=True)))

    def test_output_path_blocked_by_file_fails(self):
        self.assertEqual(Check_setup.check_output("output_dir", self.input_file / "outputs")[0], "FAIL")

    def test_output_permission_failure_is_reported(self):
        with patch.object(Check_setup, "TemporaryFile", side_effect=PermissionError("denied")):
            status, message = Check_setup.check_output("output_dir", self.root)
        self.assertEqual(status, "FAIL")
        self.assertIn("denied", message)

    def test_main_exit_status(self):
        for status, expected in (("OK", 0), ("WARN", 0), ("FAIL", 1)):
            with self.subTest(status=status), \
                    patch.object(Check_setup, "check_dependencies", return_value=[(status, "dependency")]), \
                    patch.object(Check_setup.importlib, "import_module", return_value=self.settings), \
                    patch.object(Check_setup, "check_paths", return_value=[]), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(Check_setup.main([]), expected)


if __name__ == "__main__":
    unittest.main()
