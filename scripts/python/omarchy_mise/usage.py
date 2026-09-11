"""Parse a mise task's `usage` string into structured arguments.

A mise task declares its parameters in a `usage` string, which mise hands back
verbatim in `mise tasks ls --json` without validating it. Turning that string
into "required, optional, default, flag, choice" is pure string work, so it
lives here next to the tests that can prove it rather than in QML.

The string is a fragment of a `usage` spec (https://usage.jdx.dev), which is a
KDL v2 document: each line is a node, values follow the node name, `key=value`
properties add metadata, and braces contain child nodes. Only the `arg` and
`flag` nodes describe parameters; every other node describes the command
itself and is ignored, so a spec that grows a `complete` or `about` node still
parses.

Everything the parser accepts was checked against mise 2026.9.1 by declaring
the shape in a task and reading `mise run <task> --help`:

    arg "<name>"                 required positional
    arg "[name]"                 optional positional
    arg "<name>..."              variadic, one or more
    arg "[name]..."              variadic, zero or more
    arg "<name>" var=#true       variadic, same as the `...` suffix
    arg "<name>" required=#false optional despite the angle brackets
    arg "<-- name>"              positional after a literal `--`
    flag "-v --verbose"          boolean switch
    flag "--lines <lines>"       flag taking a value
    flag "--tag [tag]"           flag whose value is optional
    flag "--user" { arg "<u>" }  the value declared as a child node
    flag "-c" required=#true     a flag the task insists on
    flag "--color" negate="--no-color"
    help= default= env=          properties, on either node
    choices "a" "b"              a child node, optionally nesting `choice`

and the KDL syntax underneath it: quoted strings with `\\"` escapes, raw
strings (`#"..."#`), `#true`/`#false`/`#null`, bare identifiers, `//` and
`/* */` comments, `;` as a node terminator, and `\\` line continuations.

Deliberately not supported, because mise rejects it: an inline choice list
such as `choices="a,b,c"`, and unquoted brackets such as `arg [name]`. KDL's
slashdash (`/-`) comment and type annotations (`(type)name`) are not handled
either, and `var_min` / `var_max`, `count`, `env`, and the optionality of a
flag's own value (`flag "--tag [tag]"` reads the same as `<tag>` here) are
parsed but not carried through. A spec using one of those raises `UsageError`
or loses that detail rather than having behaviour guessed for it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["UsageError", "parse"]

POSITIONAL = "positional"
FLAG = "flag"

#: Guard against a pathological spec nesting braces without end.
MAX_DEPTH = 32

#: KDL's whitespace, minus the newlines that terminate a node.
_WHITESPACE = frozenset(
    "\t\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
    "\u2007\u2008\u2009\u200a\u202f\u205f\u3000\ufeff"
)
_NEWLINES = frozenset("\n\r\f\u0085\u2028\u2029")

#: Characters that end a bare identifier. KDL v2 reserves the brackets, which
#: is why `arg [name]` is rejected while `arg <name>` parses.
_BARE_STOP = _WHITESPACE | _NEWLINES | frozenset('\\/(){}[];"=')

_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "s": " ",
}


class UsageError(ValueError):
    """Raised when a `usage` string cannot be parsed.

    mise does not validate the string when it lists tasks, so an invalid spec
    reaches the catalog intact. Like an unreadable project, it is a state to
    report against the one task rather than a failure of the whole payload.
    """


@dataclass
class _Node:
    """One KDL node: `name value... key=value... { children }`."""

    name: str
    values: list[Any] = field(default_factory=list)
    props: dict[str, Any] = field(default_factory=dict)
    children: list[_Node] = field(default_factory=list)


class _Scanner:
    """A recursive-descent reader for the subset of KDL a usage spec uses."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    # -- primitives ------------------------------------------------------

    def _fail(self, message: str) -> UsageError:
        return UsageError(f"{message} at character {self.pos + 1}")

    def _peek(self, offset: int = 0) -> str:
        index = self.pos + offset
        return self.text[index] if index < len(self.text) else ""

    def _startswith(self, prefix: str) -> bool:
        return self.text.startswith(prefix, self.pos)

    def _skip_trivia(self, *, newlines: bool) -> None:
        """Consume whitespace, comments, and line continuations."""
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char in _WHITESPACE or (newlines and char in _NEWLINES):
                self.pos += 1
            elif self._startswith("//"):
                while self.pos < len(self.text) and self.text[self.pos] not in _NEWLINES:
                    self.pos += 1
            elif self._startswith("/*"):
                self._skip_block_comment()
            elif char == "\\":
                # A continuation escapes the newline that would end the node.
                self.pos += 1
                self._skip_trivia(newlines=False)
                if self._peek() in _NEWLINES:
                    self.pos += 1
                elif self._peek():
                    raise self._fail("stray backslash")
            else:
                return

    def _skip_block_comment(self) -> None:
        """Consume a `/* */` comment, which KDL allows to nest."""
        depth = 0
        while self.pos < len(self.text):
            if self._startswith("/*"):
                depth += 1
                self.pos += 2
            elif self._startswith("*/"):
                depth -= 1
                self.pos += 2
                if depth == 0:
                    return
            else:
                self.pos += 1
        raise self._fail("unterminated block comment")

    def _read_quoted(self) -> str:
        self.pos += 1  # the opening quote
        out: list[str] = []
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == '"':
                self.pos += 1
                return "".join(out)
            if char != "\\":
                out.append(char)
                self.pos += 1
                continue
            self.pos += 1
            escape = self._peek()
            if escape == "u" and self._peek(1) == "{":
                out.append(self._read_unicode_escape())
            elif escape in _ESCAPES:
                out.append(_ESCAPES[escape])
                self.pos += 1
            else:
                raise self._fail(f"unknown string escape '\\{escape}'")
        raise self._fail("unterminated string")

    def _read_unicode_escape(self) -> str:
        end = self.text.find("}", self.pos)
        if end == -1:
            raise self._fail("unterminated unicode escape")
        digits = self.text[self.pos + 2 : end]
        try:
            codepoint = chr(int(digits, 16))
        except ValueError as error:
            raise self._fail(f"invalid unicode escape '{digits}'") from error
        self.pos = end + 1
        return codepoint

    def _read_raw(self) -> str:
        """Read `#"..."#`, where the hash count sets the terminator."""
        start = self.pos
        while self._peek() == "#":
            self.pos += 1
        hashes = self.text[start : self.pos]
        if self._peek() != '"':
            raise self._fail("expected a raw string after '#'")
        self.pos += 1
        closing = '"' + hashes
        end = self.text.find(closing, self.pos)
        if end == -1:
            raise self._fail("unterminated raw string")
        value = self.text[self.pos : end]
        self.pos = end + len(closing)
        return value

    def _read_bare(self) -> str:
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in _BARE_STOP:
            self.pos += 1
        if self.pos == start:
            raise self._fail(f"unexpected character '{self._peek()}'")
        return self.text[start : self.pos]

    def _read_term(self) -> Any:
        """Read one string, keyword, number, or bare identifier."""
        char = self._peek()
        if char == '"':
            return self._read_quoted()
        if char == "#":
            for keyword, value in (("#true", True), ("#false", False), ("#null", None)):
                if self._startswith(keyword):
                    self.pos += len(keyword)
                    return value
            return self._read_raw()
        word = self._read_bare()
        return _as_number(word)

    # -- structure -------------------------------------------------------

    def parse_document(self) -> list[_Node]:
        nodes = self._parse_nodes(depth=0)
        if self.pos < len(self.text):
            raise self._fail(f"unexpected '{self._peek()}'")
        return nodes

    def _parse_nodes(self, *, depth: int) -> list[_Node]:
        if depth > MAX_DEPTH:
            raise self._fail("usage spec nests too deeply")
        nodes: list[_Node] = []
        while True:
            self._skip_trivia(newlines=True)
            while self._peek() == ";":
                self.pos += 1
                self._skip_trivia(newlines=True)
            if not self._peek() or self._peek() == "}":
                return nodes
            nodes.append(self._parse_node(depth=depth))

    def _parse_node(self, *, depth: int) -> _Node:
        name = self._read_term()
        if not isinstance(name, str):
            raise self._fail("node name must be a string")
        node = _Node(name)

        while True:
            self._skip_trivia(newlines=False)
            char = self._peek()
            if not char or char in _NEWLINES or char == ";" or char == "}":
                return node
            if char == "{":
                self.pos += 1
                node.children = self._parse_nodes(depth=depth + 1)
                if self._peek() != "}":
                    raise self._fail("unterminated child block")
                self.pos += 1
                return node
            term = self._read_term()
            if self._peek() == "=":
                self.pos += 1
                if not isinstance(term, str):
                    raise self._fail("property name must be a string")
                node.props[term] = self._read_term()
            else:
                node.values.append(term)


def _as_number(word: str) -> Any:
    try:
        return int(word, 10)
    except ValueError:
        pass
    try:
        return float(word)
    except ValueError:
        return word


def _text(value: Any) -> str | None:
    """Render a property as text, leaving a missing one as None."""
    if value is None or isinstance(value, bool):
        return None
    return value if isinstance(value, str) else str(value)


def _flagged(node: _Node, key: str, fallback: bool) -> bool:
    value = node.props.get(key, fallback)
    return bool(value) if isinstance(value, bool) else fallback


def _split_placeholder(raw: str) -> tuple[str, bool, bool]:
    """Split `<name>`, `[name]`, or either with a `...` suffix.

    Returns the bare name, whether the brackets make it required, and whether
    it is variadic.
    """
    token = raw.strip()
    variadic = token.endswith("...")
    if variadic:
        token = token[: -len("...")].rstrip()

    if token.startswith("<") and token.endswith(">") and len(token) > 1:
        required, token = True, token[1:-1]
    elif token.startswith("[") and token.endswith("]") and len(token) > 1:
        required, token = False, token[1:-1]
    else:
        # Unbracketed names are not a usage shape mise accepts for a
        # positional; treat one as required rather than rejecting the task.
        required = True

    token = token.strip()
    # `<-- name>` is shorthand for a positional that follows a literal `--`.
    if token.startswith("--"):
        token = token[2:].strip()
    if not token:
        raise UsageError(f"argument has no name: {raw!r}")
    return token, required, variadic


def _choices(node: _Node) -> list[str]:
    """Read a `choices` child node's values and any nested `choice` nodes.

    Aliases declared under a `choice` are omitted: mise accepts them, but they
    are alternate spellings of a value already listed, not separate options.
    """
    found: list[str] = []
    for child in node.children:
        if child.name != "choices":
            continue
        for value in child.values:
            if isinstance(value, str):
                found.append(value)
        for grandchild in child.children:
            if grandchild.name == "choice" and grandchild.values:
                value = grandchild.values[0]
                if isinstance(value, str):
                    found.append(value)
    return found


def _argument(
    *,
    name: str,
    kind: str,
    required: bool,
    default: Any,
    help_text: str | None,
    variadic: bool,
    choices: list[str],
    long: str | None = None,
    short: str | None = None,
    value_name: str | None = None,
    negate: str | None = None,
) -> dict[str, Any]:
    """Build one argument entry.

    Every key is present on every entry, flag-only ones included, so the
    widget can read the list without branching on `kind` first. `default`
    keeps the type the spec declared — a string, number, or boolean.
    """
    return {
        "name": name,
        "kind": kind,
        "required": required,
        "default": default,
        "help": help_text,
        "variadic": variadic,
        "choices": choices,
        "long": long,
        "short": short,
        "valueName": value_name,
        "negate": negate,
    }


def _parse_arg(node: _Node) -> dict[str, Any]:
    if not node.values or not isinstance(node.values[0], str):
        raise UsageError("arg is missing its name")
    name, required, variadic = _split_placeholder(node.values[0])
    return _argument(
        name=name,
        kind=POSITIONAL,
        required=_flagged(node, "required", required),
        default=node.props.get("default"),
        help_text=_text(node.props.get("help")),
        variadic=variadic or _flagged(node, "var", False),
        choices=_choices(node),
        value_name=name,
    )


def _parse_flag(node: _Node) -> dict[str, Any]:
    if not node.values or not isinstance(node.values[0], str):
        raise UsageError("flag is missing its name")

    short: str | None = None
    long: str | None = None
    value_name: str | None = None
    variadic = False

    # `flag "-p --profile <profile>"` packs the spellings and the value into
    # one string; a value may instead arrive as a child `arg` node.
    for token in node.values[0].split():
        if token.startswith("--"):
            long = token
        elif token.startswith("-") and len(token) > 1:
            short = token
        else:
            value_name, _, variadic = _split_placeholder(token)

    for child in node.children:
        if child.name == "arg" and child.values and isinstance(child.values[0], str):
            value_name, _, variadic = _split_placeholder(child.values[0])

    spelling = long or short
    if spelling is None:
        raise UsageError(f"flag has no name: {node.values[0]!r}")

    return _argument(
        name=spelling.lstrip("-"),
        kind=FLAG,
        # A flag is optional unless it says otherwise; the brackets around its
        # value say whether the value is optional, not the flag.
        required=_flagged(node, "required", False),
        default=node.props.get("default"),
        help_text=_text(node.props.get("help")),
        variadic=variadic or _flagged(node, "var", False),
        choices=_choices(node),
        long=long,
        short=short,
        value_name=value_name,
        negate=_text(node.props.get("negate")),
    )


def parse(spec: str | None) -> list[dict[str, Any]]:
    """Turn a task's `usage` string into a list of argument dicts.

    Arguments come back in declaration order, positionals and flags mixed,
    because a positional's order is part of its meaning. Raises `UsageError`
    if the string is not a usage spec; an absent or blank one is not an error
    and yields no arguments.
    """
    if not spec or not spec.strip():
        return []

    arguments: list[dict[str, Any]] = []
    for node in _Scanner(spec).parse_document():
        if node.name == "arg":
            arguments.append(_parse_arg(node))
        elif node.name == "flag":
            arguments.append(_parse_flag(node))
    return arguments


def missing_required(arguments: list[dict[str, Any]], values: dict[str, str]) -> list[str]:
    """Names of required arguments the caller has not supplied a value for."""
    missing = []
    for argument in arguments:
        if not argument.get("required"):
            continue
        if not str(values.get(str(argument.get("name")), "")).strip():
            missing.append(str(argument.get("name")))
    return missing


def to_argv(arguments: list[dict[str, Any]], values: dict[str, str]) -> list[str]:
    """Turn `{name: value}` into the argv a task expects.

    Declaration order is preserved because a positional's position is its
    meaning. A flag is emitted by the spelling it actually declared -- a
    short-only flag has no `--name` form -- and a flag with no value name is a
    switch, present or absent rather than carrying a value.

    Empty values are omitted entirely rather than passed as "", so an optional
    argument left blank falls through to the task's own default instead of
    overriding it with nothing.
    """
    argv: list[str] = []
    for argument in arguments:
        raw = str(values.get(str(argument.get("name")), "")).strip()
        spelling = argument.get("long") or argument.get("short")

        if argument.get("kind") == "flag":
            if not spelling:
                continue
            if argument.get("valueName") is None:
                # A switch: its presence is the value.
                if raw.lower() in {"1", "true", "yes", "on"}:
                    argv.append(str(spelling))
                continue
            if raw:
                argv.extend([str(spelling), raw])
            continue

        if not raw:
            continue
        # A variadic positional takes every whitespace-separated word; quoting
        # for a value containing spaces is deliberately not invented here.
        if argument.get("variadic"):
            argv.extend(raw.split())
        else:
            argv.append(raw)

    return argv
