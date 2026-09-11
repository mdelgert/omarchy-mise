from __future__ import annotations

import json
import unittest

from omarchy_mise import usage


def one(spec: str) -> dict:
    """Parse a spec expected to declare exactly one argument."""
    arguments = usage.parse(spec)
    if len(arguments) != 1:
        raise AssertionError(f"expected one argument from {spec!r}, got {arguments}")
    return arguments[0]


class EmptyInputTests(unittest.TestCase):
    def test_absent_or_blank_usage_yields_no_arguments(self) -> None:
        for spec in (None, "", "   ", "\n\t\n"):
            with self.subTest(spec=spec):
                self.assertEqual([], usage.parse(spec))

    def test_a_spec_of_only_comments_yields_no_arguments(self) -> None:
        self.assertEqual([], usage.parse("// nothing here\n/* nor here */\n"))


class PositionalTests(unittest.TestCase):
    def test_bracket_style_sets_required(self) -> None:
        cases = [
            ('arg "<name>"', True),
            ('arg "[name]"', False),
            # An unquoted name is accepted by mise and reads as required.
            ("arg <name>", True),
        ]
        for spec, required in cases:
            with self.subTest(spec=spec):
                argument = one(spec)
                self.assertEqual("name", argument["name"])
                self.assertEqual("positional", argument["kind"])
                self.assertIs(required, argument["required"])

    def test_required_property_overrides_the_brackets(self) -> None:
        self.assertIs(False, one('arg "<x>" required=#false')["required"])
        self.assertIs(True, one('arg "[x]" required=#true')["required"])

    def test_help_and_default_are_read(self) -> None:
        argument = one('arg "[name]" help="Name to greet" default="world"')
        self.assertEqual("Name to greet", argument["help"])
        self.assertEqual("world", argument["default"])

    def test_missing_help_and_default_are_none(self) -> None:
        argument = one('arg "<name>"')
        self.assertIsNone(argument["help"])
        self.assertIsNone(argument["default"])

    def test_variadic_is_set_by_the_suffix_or_the_var_property(self) -> None:
        for spec, required in [
            ('arg "<files>..."', True),
            ('arg "[files]..."', False),
            ('arg "<files>" var=#true', True),
        ]:
            with self.subTest(spec=spec):
                argument = one(spec)
                self.assertEqual("files", argument["name"])
                self.assertIs(True, argument["variadic"])
                self.assertIs(required, argument["required"])

    def test_a_plain_argument_is_not_variadic(self) -> None:
        self.assertIs(False, one('arg "<name>"')["variadic"])

    def test_double_dash_shorthand_keeps_only_the_name(self) -> None:
        # `<-- file>` declares a positional that follows a literal `--`.
        self.assertEqual("file", one('arg "<-- file>"')["name"])

    def test_flag_only_keys_are_present_and_empty(self) -> None:
        # The widget reads one shape for both kinds rather than branching.
        argument = one('arg "<name>"')
        self.assertIsNone(argument["long"])
        self.assertIsNone(argument["short"])
        self.assertIsNone(argument["negate"])
        self.assertEqual("name", argument["valueName"])


class FlagTests(unittest.TestCase):
    def test_a_flag_without_a_value_is_a_switch(self) -> None:
        argument = one('flag "-v --verbose" help="Verbose output"')
        self.assertEqual("verbose", argument["name"])
        self.assertEqual("flag", argument["kind"])
        self.assertEqual("--verbose", argument["long"])
        self.assertEqual("-v", argument["short"])
        self.assertIsNone(argument["valueName"])

    def test_a_flag_with_a_value_records_the_placeholder(self) -> None:
        argument = one('flag "-p --profile <profile>" help="Build profile" default="dev"')
        self.assertEqual("profile", argument["name"])
        self.assertEqual("profile", argument["valueName"])
        self.assertEqual("dev", argument["default"])
        self.assertEqual("Build profile", argument["help"])

    def test_a_value_declared_as_a_child_node_is_found(self) -> None:
        argument = one('flag "--user" {\n  arg "<user>"\n}\n')
        self.assertEqual("user", argument["valueName"])

    def test_a_short_only_flag_is_named_after_its_short_spelling(self) -> None:
        argument = one('flag "-f" help="Force"')
        self.assertEqual("f", argument["name"])
        self.assertIsNone(argument["long"])
        self.assertEqual("-f", argument["short"])

    def test_a_flag_is_optional_unless_it_says_otherwise(self) -> None:
        self.assertIs(False, one('flag "--config <file>"')["required"])
        self.assertIs(True, one('flag "--config <file>" required=#true')["required"])

    def test_negation_is_carried_through(self) -> None:
        argument = one('flag "--color" negate="--no-color" default=#true')
        self.assertEqual("--no-color", argument["negate"])
        self.assertIs(True, argument["default"])

    def test_a_repeatable_flag_is_variadic(self) -> None:
        self.assertIs(True, one('flag "--include <pattern>" var=#true')["variadic"])


class ChoiceTests(unittest.TestCase):
    def test_choices_are_read_from_the_child_node(self) -> None:
        for spec in (
            'arg "<shell>" {\n  choices "bash" "zsh" "fish"\n}\n',
            'flag "--shell <shell>" {\n  choices "bash" "zsh" "fish"\n}\n',
        ):
            with self.subTest(spec=spec):
                self.assertEqual(["bash", "zsh", "fish"], one(spec)["choices"])

    def test_nested_choice_nodes_contribute_their_values(self) -> None:
        # Aliases are alternate spellings of a value already listed, so they
        # are deliberately left out of the choice list.
        spec = (
            'arg "<color>" {\n'
            "  choices ignore_case=#true {\n"
            '    choice "always" help="Always use colour" {\n'
            '      alias "yes"\n'
            "    }\n"
            '    choice "never"\n'
            "  }\n"
            "}\n"
        )
        self.assertEqual(["always", "never"], one(spec)["choices"])

    def test_an_argument_without_choices_gets_an_empty_list(self) -> None:
        self.assertEqual([], one('arg "<name>"')["choices"])


class SyntaxTests(unittest.TestCase):
    """KDL details a real spec relies on, each confirmed against mise."""

    def test_several_declarations_parse_in_declaration_order(self) -> None:
        spec = (
            'arg "<name>" help="Name"\n'
            'flag "--count <count>" default="1"\n'
            'flag "--dry-run" help="Do nothing"\n'
        )
        arguments = usage.parse(spec)
        self.assertEqual(["name", "count", "dry-run"], [a["name"] for a in arguments])
        self.assertEqual(["positional", "flag", "flag"], [a["kind"] for a in arguments])

    def test_a_semicolon_separates_declarations_on_one_line(self) -> None:
        arguments = usage.parse('arg "<a>" help="A"; arg "<b>" help="B"')
        self.assertEqual(["a", "b"], [argument["name"] for argument in arguments])

    def test_comments_and_line_continuations_are_skipped(self) -> None:
        for spec in (
            '// leading comment\narg "<name>" help="N"\n',
            '/* block */ arg "<name>" help="N"\n',
            '/* outer /* inner */ still a comment */\narg "<name>" help="N"\n',
            'arg "<name>" \\\n  help="N"\n',
        ):
            with self.subTest(spec=spec):
                self.assertEqual("N", one(spec)["help"])

    def test_string_escapes_and_raw_strings_are_decoded(self) -> None:
        self.assertEqual('A "quoted" word', one('arg "<n>" help="A \\"quoted\\" word"')["help"])
        self.assertEqual("line\nbreak", one('arg "<n>" help="line\\nbreak"')["help"])
        # A raw string keeps its backslashes; nothing inside it is an escape.
        self.assertEqual("a raw \\n string", one('arg "<n>" help=#"a raw \\n string"#')["help"])

    def test_nodes_that_are_not_arg_or_flag_are_ignored(self) -> None:
        # A spec may describe the command itself; only parameters matter here.
        spec = 'about "A task"\narg "<name>"\ncomplete "name" run="ls"\n'
        self.assertEqual(["name"], [argument["name"] for argument in usage.parse(spec)])


class MalformedTests(unittest.TestCase):
    def test_unparseable_specs_raise_usage_error(self) -> None:
        cases = [
            'arg "<name',  # unterminated string
            "arg",  # no name
            'arg "<>"',  # brackets with nothing in them
            'arg "<n>" {',  # unterminated child block
            'arg [name] help="N"',  # unquoted brackets, which mise rejects too
            'arg "<n>" help="x" }',  # a closing brace with no block
            'arg "<n>" help=#"unterminated',  # unterminated raw string
            'arg "<n>" /* unterminated comment',
        ]
        for spec in cases:
            with self.subTest(spec=spec), self.assertRaises(usage.UsageError):
                usage.parse(spec)

    def test_the_error_says_where_it_gave_up(self) -> None:
        with self.assertRaises(usage.UsageError) as caught:
            usage.parse('arg "<name')
        self.assertIn("unterminated string", str(caught.exception))

    def test_a_usage_error_is_a_value_error(self) -> None:
        self.assertTrue(issubclass(usage.UsageError, ValueError))

    def test_prose_that_declares_nothing_yields_no_arguments(self) -> None:
        # mise rejects this at run time, but it is parseable KDL declaring no
        # parameters, so the catalog reports no arguments rather than an error.
        self.assertEqual([], usage.parse("this is not a usage spec at all"))

    def test_deep_nesting_is_refused_rather_than_recursing_away(self) -> None:
        spec = 'arg "<n>" ' + "{ choices " * 64 + "}" * 64
        with self.assertRaises(usage.UsageError):
            usage.parse(spec)


class PayloadTests(unittest.TestCase):
    def test_every_argument_survives_a_json_round_trip(self) -> None:
        # The widget reads this across a process boundary, so nothing in an
        # argument may be a type json cannot carry.
        spec = (
            'arg "<name>" help="Name" default="world"\n'
            'flag "-v --verbose"\n'
            'flag "--color" negate="--no-color" default=#true\n'
            'arg "<shell>" {\n  choices "bash" "zsh"\n}\n'
        )
        arguments = usage.parse(spec)
        self.assertEqual(arguments, json.loads(json.dumps(arguments)))

    def test_every_argument_carries_the_same_keys(self) -> None:
        expected = {
            "name",
            "kind",
            "required",
            "default",
            "help",
            "variadic",
            "choices",
            "long",
            "short",
            "valueName",
            "negate",
        }
        for spec in ('arg "<name>"', 'flag "--lines <lines>"'):
            with self.subTest(spec=spec):
                self.assertEqual(expected, set(one(spec)))


class CatalogAttachmentTests(unittest.TestCase):
    """`catalog.attach_arguments` is the seam between the parser and the payload."""

    def setUp(self) -> None:
        # Imported here so a parser-only test run does not need the catalog.
        from omarchy_mise import catalog

        self.catalog = catalog

    def test_a_parsed_usage_string_becomes_the_arguments_list(self) -> None:
        task = {"name": "example:param", "usage": 'arg "<name>" help="Name to greet"'}
        self.assertIsNone(self.catalog.attach_arguments(task))
        self.assertEqual(["name"], [argument["name"] for argument in task["arguments"]])
        self.assertNotIn("error", task)

    def test_a_task_without_a_usage_string_gets_an_empty_list(self) -> None:
        task = {"name": "example:hello", "usage": None}
        self.assertIsNone(self.catalog.attach_arguments(task))
        self.assertEqual([], task["arguments"])

    def test_a_broken_usage_string_is_reported_not_raised(self) -> None:
        task = {"name": "example:broken", "usage": 'arg "<name'}
        problem = self.catalog.attach_arguments(task)
        self.assertIsNotNone(problem)
        self.assertEqual([], task["arguments"])
        self.assertEqual(problem, task["error"])
        self.assertTrue(task["error"].startswith("usage:"))

    def test_the_raw_usage_string_is_left_alone(self) -> None:
        # Other lanes read `usage`; `arguments` is added beside it, not instead.
        spec = 'arg "<name>" help="Name to greet"'
        task = {"name": "example:param", "usage": spec}
        self.catalog.attach_arguments(task)
        self.assertEqual(spec, task["usage"])


if __name__ == "__main__":
    unittest.main()


class ArgvTests(unittest.TestCase):
    """Turning editor values into argv. This lives in Python rather than QML
    because it is the part with rules worth proving."""

    def positional(self, **overrides: object) -> dict:
        spec = {
            "name": "name",
            "kind": "positional",
            "required": False,
            "variadic": False,
            "long": None,
            "short": None,
            "valueName": "name",
        }
        spec.update(overrides)
        return spec

    def flag(self, **overrides: object) -> dict:
        spec = {
            "name": "lines",
            "kind": "flag",
            "required": False,
            "variadic": False,
            "long": "--lines",
            "short": None,
            "valueName": "lines",
        }
        spec.update(overrides)
        return spec

    def test_positional_passes_the_value_through(self) -> None:
        self.assertEqual(["Omarchy"], usage.to_argv([self.positional()], {"name": "Omarchy"}))

    def test_declaration_order_is_preserved(self) -> None:
        specs = [self.positional(name="first"), self.positional(name="second")]
        self.assertEqual(["a", "b"], usage.to_argv(specs, {"second": "b", "first": "a"}))

    def test_blank_value_is_omitted_so_the_task_default_applies(self) -> None:
        self.assertEqual([], usage.to_argv([self.positional()], {"name": "   "}))
        self.assertEqual([], usage.to_argv([self.positional()], {}))

    def test_flag_emits_its_spelling_and_value(self) -> None:
        self.assertEqual(["--lines", "50"], usage.to_argv([self.flag()], {"lines": "50"}))

    def test_short_only_flag_uses_the_short_spelling(self) -> None:
        spec = self.flag(long=None, short="-n")
        self.assertEqual(["-n", "50"], usage.to_argv([spec], {"lines": "50"}))

    def test_valueless_flag_is_a_switch(self) -> None:
        spec = self.flag(valueName=None)
        for truthy in ("1", "true", "TRUE", "yes", "on"):
            with self.subTest(truthy):
                self.assertEqual(["--lines"], usage.to_argv([spec], {"lines": truthy}))
        for falsy in ("", "0", "false", "no"):
            with self.subTest(falsy):
                self.assertEqual([], usage.to_argv([spec], {"lines": falsy}))

    def test_variadic_positional_splits_on_whitespace(self) -> None:
        spec = self.positional(variadic=True)
        self.assertEqual(["a", "b", "c"], usage.to_argv([spec], {"name": "a  b c"}))

    def test_a_blank_positional_before_a_filled_one_holds_its_place(self) -> None:
        # Dropping the gap would bind "x" to `first`, which is a different run.
        specs = [self.positional(name="first"), self.positional(name="second")]
        self.assertEqual(["", "x"], usage.to_argv(specs, {"first": "  ", "second": "x"}))

    def test_trailing_blank_positionals_are_still_omitted(self) -> None:
        specs = [self.positional(name="first"), self.positional(name="second")]
        self.assertEqual(["x"], usage.to_argv(specs, {"first": "x", "second": ""}))

    def test_a_flag_with_no_spelling_is_skipped(self) -> None:
        self.assertEqual([], usage.to_argv([self.flag(long=None, short=None)], {"lines": "50"}))

    def test_missing_required_reports_blank_and_absent(self) -> None:
        specs = [self.positional(required=True), self.flag(name="lines", required=True)]
        self.assertEqual(["name", "lines"], usage.missing_required(specs, {"name": "  "}))

    def test_missing_required_is_empty_when_satisfied(self) -> None:
        spec = self.positional(required=True)
        self.assertEqual([], usage.missing_required([spec], {"name": "x"}))
