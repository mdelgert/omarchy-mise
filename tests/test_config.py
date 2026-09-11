from __future__ import annotations

from pathlib import Path
import re
import tempfile
import unittest

from omarchy_mise import catalog, config, paths


class ConfigTests(unittest.TestCase):
    def write(self, body: str) -> Path:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        target = directory / "config.toml"
        target.write_text(body, encoding="utf-8")
        return target

    def test_missing_file_yields_defaults(self) -> None:
        resolved = config.load(Path("/nonexistent/omarchy-mise.toml"))
        self.assertEqual(config.DEFAULTS["ui"]["label"], resolved["ui"]["label"])
        self.assertIsNone(resolved["_source"])
        self.assertEqual([], resolved["_warnings"])

    def test_values_override_defaults(self) -> None:
        resolved = config.load(
            self.write('[ui]\nlabel = "Tasks"\n\n[scan]\ndirectories = ["/tmp"]\nmax_depth = 4\n')
        )
        self.assertEqual("Tasks", resolved["ui"]["label"])
        self.assertEqual(["/tmp"], resolved["scan"]["directories"])
        self.assertEqual(4, resolved["scan"]["max_depth"])
        # Untouched sections keep their defaults.
        self.assertEqual(
            config.DEFAULTS["run"]["timeout_seconds"], resolved["run"]["timeout_seconds"]
        )

    def test_unknown_keys_warn_instead_of_failing(self) -> None:
        resolved = config.load(self.write('[ui]\nlabel = "x"\ncolour = "red"\n\n[future]\nx = 1\n'))
        self.assertEqual("x", resolved["ui"]["label"])
        self.assertIn("ignoring unknown key ui.colour", resolved["_warnings"])
        self.assertIn("ignoring unknown section [future]", resolved["_warnings"])

    def test_newer_schema_version_warns(self) -> None:
        resolved = config.load(self.write("schema_version = 99\n"))
        self.assertTrue(any("schema_version 99" in item for item in resolved["_warnings"]))

    def test_wrong_type_is_an_error(self) -> None:
        with self.assertRaises(config.ConfigError):
            config.load(self.write('[scan]\nmax_depth = "deep"\n'))

    def test_boolean_is_not_accepted_as_integer(self) -> None:
        with self.assertRaises(config.ConfigError):
            config.load(self.write("[scan]\nmax_depth = true\n"))

    def test_non_positive_integer_is_an_error(self) -> None:
        with self.assertRaises(config.ConfigError):
            config.load(self.write("[run]\ntimeout_seconds = 0\n"))

    def test_empty_string_in_list_is_an_error(self) -> None:
        with self.assertRaises(config.ConfigError):
            config.load(self.write('[scan]\ndirectories = ["~/code", "  "]\n'))

    def test_malformed_toml_is_an_error(self) -> None:
        with self.assertRaises(config.ConfigError):
            config.load(self.write("[ui\nlabel = 1\n"))

    def test_blank_label_falls_back_to_the_default(self) -> None:
        resolved = config.load(self.write('[ui]\nlabel = "   "\n'))
        self.assertEqual(config.DEFAULTS["ui"]["label"], resolved["ui"]["label"])

    def test_scan_roots_skips_missing_directories(self) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        resolved = config.defaults()
        resolved["scan"]["directories"] = [str(directory), str(directory / "absent")]
        self.assertEqual([directory.resolve()], config.scan_roots(resolved))

    def test_example_config_matches_the_schema(self) -> None:
        resolved = config.load(paths.repo_root() / "config.example.toml")
        self.assertEqual([], resolved["_warnings"])

    def test_the_qml_fallback_label_matches_the_python_default(self) -> None:
        # Main.qml shows its fallback until the config service answers, so a
        # drift here is a visible flicker from one label to another.
        source = (paths.repo_root() / "services" / "Plugin.js").read_text(encoding="utf-8")
        match = re.search(r'DEFAULT_LABEL\s*=\s*"([^"]*)"', source)
        assert match is not None, "DEFAULT_LABEL not found in services/Plugin.js"
        declared = re.sub(
            r"\\u\{([0-9a-fA-F]+)\}", lambda m: chr(int(m.group(1), 16)), match.group(1)
        )
        self.assertEqual(config.DEFAULTS["ui"]["label"], declared)

    def test_the_starter_config_label_matches_the_default(self) -> None:
        resolved = config.load(paths.repo_root() / "config.example.toml")
        self.assertEqual(config.DEFAULTS["ui"]["label"], resolved["ui"]["label"])

    def test_the_default_label_is_a_single_glyph(self) -> None:
        # The bar gives the label one icon slot; a word fits, but the shipped
        # default should not be the thing that overflows it.
        self.assertEqual(1, len(config.DEFAULTS["ui"]["label"]))

    def test_no_scan_directory_is_hard_coded_in_python(self) -> None:
        # Guessing at someone's layout means scanning directories they never
        # named. The starter config is where a suggestion belongs.
        self.assertEqual([], config.defaults()["scan"]["directories"])

    def test_the_starter_config_is_what_supplies_a_scan_directory(self) -> None:
        resolved = config.load(paths.repo_root() / "config.example.toml")
        self.assertNotEqual([], resolved["scan"]["directories"])

    def test_no_scan_directories_is_a_warning_not_an_error(self) -> None:
        payload = catalog.build(config.defaults())
        self.assertEqual([], payload["projects"])
        self.assertEqual(0, payload["taskCount"])
        self.assertTrue(
            any("scan.directories" in warning for warning in payload["warnings"]),
            payload["warnings"],
        )

    def test_defaults_are_not_shared_between_calls(self) -> None:
        first = config.defaults()
        first["scan"]["directories"].append("~/mutated")
        self.assertNotIn("~/mutated", config.defaults()["scan"]["directories"])


if __name__ == "__main__":
    unittest.main()


class PanelAppearanceTests(unittest.TestCase):
    """ui.position / width / height / font_scale, added so the panel is not
    stuck wherever the widget happens to sit."""

    def write(self, body: str) -> Path:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        target = directory / "config.toml"
        target.write_text(body, encoding="utf-8")
        return target

    def test_defaults_centre_the_panel(self) -> None:
        ui = config.defaults()["ui"]
        self.assertEqual("center", ui["position"])
        self.assertEqual(1.0, ui["font_scale"])

    def test_position_accepts_the_documented_values(self) -> None:
        for value in config.POSITIONS:
            with self.subTest(value):
                resolved = config.load(self.write(f'[ui]\nposition = "{value}"\n'))
                self.assertEqual(value, resolved["ui"]["position"])

    def test_position_is_case_and_space_insensitive(self) -> None:
        resolved = config.load(self.write('[ui]\nposition = "  Center "\n'))
        self.assertEqual("center", resolved["ui"]["position"])

    def test_an_unknown_position_names_the_valid_ones(self) -> None:
        with self.assertRaises(config.ConfigError) as caught:
            config.load(self.write('[ui]\nposition = "bottom-left"\n'))
        self.assertIn("center", str(caught.exception))

    def test_font_scale_accepts_an_integer(self) -> None:
        # `font_scale = 2` is what someone will actually type.
        resolved = config.load(self.write("[ui]\nfont_scale = 2\n"))
        self.assertEqual(2.0, resolved["ui"]["font_scale"])

    def test_font_scale_is_bounded(self) -> None:
        low, high = config.FONT_SCALE_RANGE
        for value in (low - 0.1, high + 0.1, 0):
            with self.subTest(value), self.assertRaises(config.ConfigError):
                config.load(self.write(f"[ui]\nfont_scale = {value}\n"))

    def test_font_scale_rejects_a_boolean(self) -> None:
        with self.assertRaises(config.ConfigError):
            config.load(self.write("[ui]\nfont_scale = true\n"))

    def test_size_must_be_positive(self) -> None:
        for key in ("width", "height"):
            with self.subTest(key), self.assertRaises(config.ConfigError):
                config.load(self.write(f"[ui]\n{key} = 0\n"))

    def test_size_overrides_apply(self) -> None:
        resolved = config.load(self.write("[ui]\nwidth = 600\nheight = 300\n"))
        self.assertEqual(600, resolved["ui"]["width"])
        self.assertEqual(300, resolved["ui"]["height"])
