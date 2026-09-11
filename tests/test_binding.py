"""The optional Hyprland keybinding.

This edits a file the user owns, so the tests are about the two properties that
make that acceptable: it refuses a combination something else already holds,
and removing it puts the file back exactly as it was.

`existing_bindings` and `_validate` are patched throughout. The real ones shell
out to `omarchy` and `hyprctl`, which means a test would otherwise depend on a
live compositor and could reload it as a side effect.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from omarchy_mise import binding, paths

#: A stock-ish listing, in the spelling `omarchy menu keybindings --print` uses.
STOCK = [
    ("SUPER + K", "Keybindings"),
    ("SUPER SHIFT + M", "Music"),
    ("SUPER CTRL + V", "Clipboard manager"),
]

ORIGINAL = """\
-- Keep only your personal keybinding overrides here.

-- >>> other-tool: a block this plugin must not touch
o.bind("SUPER + F9", "Other", "true")
-- <<< other-tool: a block this plugin must not touch
"""


class BindingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.target = directory / "bindings.lua"
        self.target.write_text(ORIGINAL, encoding="utf-8")
        self.enterContext(mock.patch.dict(os.environ, {paths.BINDINGS_ENV: str(self.target)}))
        # Never touch a live compositor from a test.
        self.enterContext(mock.patch.object(binding, "_validate", return_value=None))
        self.bindings = list(STOCK)
        self.enterContext(
            mock.patch.object(binding, "existing_bindings", side_effect=lambda: self.bindings)
        )

    def read(self) -> str:
        return self.target.read_text(encoding="utf-8")


class NormaliseTests(unittest.TestCase):
    def test_the_spellings_a_user_might_type_all_canonicalise(self) -> None:
        for spelling in ("SUPER + M", "super+m", "Super M", "  super  +  M  "):
            with self.subTest(spelling):
                self.assertEqual("SUPER + M", binding.normalise(spelling))

    def test_modifier_order_is_stable_so_the_written_line_is_too(self) -> None:
        self.assertEqual(
            "SUPER + CTRL + ALT + SHIFT + M", binding.normalise("shift alt ctrl super m")
        )

    def test_modifiers_without_a_key_are_refused(self) -> None:
        with self.assertRaises(binding.BindingError):
            binding.normalise("SUPER + CTRL")

    def test_an_empty_combination_is_refused(self) -> None:
        with self.assertRaises(binding.BindingError):
            binding.normalise("   ")

    def test_an_unknown_modifier_is_refused(self) -> None:
        with self.assertRaises(binding.BindingError):
            binding.normalise("HYPER + M")

    def test_lua_cannot_be_smuggled_through_the_key(self) -> None:
        # The combination is written into a Lua string literal, so this is the
        # one place untrusted input reaches the user's config.
        for hostile in ('SUPER + "); os.execute("evil', "SUPER + M\no.bind(", 'SUPER + "'):
            with self.subTest(hostile), self.assertRaises(binding.BindingError):
                binding.normalise(hostile)


class AddTests(BindingTestCase):
    def test_binding_a_free_combination_writes_one_block(self) -> None:
        result = binding.add("SUPER + M")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["changed"])
        text = self.read()
        self.assertEqual(1, text.count(binding.BEGIN))
        self.assertIn('o.bind("SUPER + M", "Mise tasks", "omarchy-shell shell toggle', text)

    def test_another_tools_block_is_left_alone(self) -> None:
        binding.add("SUPER + M")
        self.assertIn("-- >>> other-tool: a block this plugin must not touch", self.read())
        self.assertIn('o.bind("SUPER + F9", "Other", "true")', self.read())

    def test_a_combination_something_else_owns_is_refused(self) -> None:
        result = binding.add("SUPER + SHIFT + M")
        self.assertFalse(result["ok"])
        self.assertEqual("Music", result["conflict"])
        self.assertIn("Music", result["detail"])
        # Refusing means refusing: the file is untouched.
        self.assertEqual(ORIGINAL, self.read())

    def test_force_overrides_a_conflict_with_an_unbind_first(self) -> None:
        result = binding.add("SUPER + SHIFT + M", force=True)
        self.assertTrue(result["ok"], result)
        text = self.read()
        # Omarchy requires the unbind before the bind, and in that order.
        self.assertIn('hl.unbind("SUPER + SHIFT + M")', text)
        self.assertLess(text.index("hl.unbind"), text.index('o.bind("SUPER + SHIFT + M"'))

    def test_binding_twice_changes_nothing_the_second_time(self) -> None:
        binding.add("SUPER + M")
        after_first = self.read()
        result = binding.add("SUPER + M")
        self.assertTrue(result["ok"])
        self.assertFalse(result["changed"])
        self.assertEqual(after_first, self.read())

    def test_rebinding_replaces_the_block_rather_than_adding_one(self) -> None:
        binding.add("SUPER + M")
        result = binding.add("SUPER + CTRL + M")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["replaced"])
        text = self.read()
        self.assertEqual(1, text.count(binding.BEGIN))
        self.assertIn('o.bind("SUPER + CTRL + M"', text)
        self.assertNotIn('o.bind("SUPER + M"', text)

    def test_our_own_binding_is_not_a_conflict_with_itself(self) -> None:
        binding.add("SUPER + M")
        # The listing now reports our binding too, as the real command would.
        self.bindings.append(("SUPER + M", binding.DESCRIPTION))
        result = binding.add("SUPER + M")
        self.assertTrue(result["ok"], result)
        self.assertIsNone(result["conflict"])

    def test_the_previous_file_is_backed_up(self) -> None:
        result = binding.add("SUPER + M")
        backup = Path(result["backup"])
        self.assertTrue(backup.is_file())
        self.assertEqual(ORIGINAL, backup.read_text(encoding="utf-8"))

    def test_a_conflict_check_that_cannot_run_does_not_block_the_bind(self) -> None:
        # Off an Omarchy desktop there is nothing to ask, and refusing every
        # bind would be worse than binding without the check.
        self.bindings = None  # type: ignore[assignment]
        with mock.patch.object(binding, "existing_bindings", return_value=None):
            result = binding.add("SUPER + SHIFT + M")
        self.assertTrue(result["ok"], result)

    def test_a_missing_bindings_file_is_an_error_not_a_new_file(self) -> None:
        self.target.unlink()
        with self.assertRaises(binding.BindingError):
            binding.add("SUPER + M")
        self.assertFalse(self.target.exists())


class RemoveTests(BindingTestCase):
    def test_removing_restores_the_file_byte_for_byte(self) -> None:
        binding.add("SUPER + M")
        self.assertNotEqual(ORIGINAL, self.read())
        result = binding.remove()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["changed"])
        self.assertEqual(ORIGINAL, self.read())

    def test_removing_when_nothing_is_bound_is_a_no_op(self) -> None:
        result = binding.remove()
        self.assertTrue(result["ok"])
        self.assertFalse(result["changed"])
        self.assertEqual(ORIGINAL, self.read())

    def test_a_truncated_block_is_still_removed(self) -> None:
        # A hand-edit that deleted the closing marker must not leave the
        # plugin unable to clean up after itself.
        self.target.write_text(
            ORIGINAL + f'\n{binding.BEGIN}\no.bind("SUPER + M", "Mise tasks", "x")\n',
            encoding="utf-8",
        )
        result = binding.remove()
        self.assertTrue(result["changed"])
        self.assertNotIn(binding.BEGIN, self.read())

    def test_repeated_add_and_remove_does_not_grow_the_file(self) -> None:
        for _ in range(3):
            binding.add("SUPER + M")
            binding.remove()
        self.assertEqual(ORIGINAL, self.read())


class StatusTests(BindingTestCase):
    def test_status_reports_the_bound_combination(self) -> None:
        binding.add("SUPER + M")
        report = binding.status()
        self.assertTrue(report["bound"])
        self.assertEqual("SUPER + M", report["key"])

    def test_status_on_an_unbound_file(self) -> None:
        report = binding.status()
        self.assertFalse(report["bound"])
        self.assertIsNone(report["key"])

    def test_status_when_the_file_does_not_exist(self) -> None:
        self.target.unlink()
        report = binding.status()
        self.assertTrue(report["ok"])
        self.assertFalse(report["bound"])
        self.assertFalse(report["exists"])


if __name__ == "__main__":
    unittest.main()
