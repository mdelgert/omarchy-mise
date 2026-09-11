.pragma library

// Where this plugin is installed. Derived from a QML file's own URL so the
// CLI is found whether the plugin was cloned into ~/.config/omarchy/plugins
// or symlinked there from a development checkout.
//
// `here` is Qt.resolvedUrl(".") from a file in services/.
function rootFrom(here) {
  var path = String(here || "")
  if (path.indexOf("file://") === 0)
    path = path.substring(7)
  return path.replace(/\/services\/?$/, "")
}

// Bar label used until the config service answers, and when a user blanks the
// setting. A glyph rather than a word: Omarchy pins fontconfig's `monospace`
// alias to a Nerd Font and its own bar widgets and menu draw their icons from
// that range, so this renders on every Omarchy install. Keep it in step with
// `DEFAULTS["ui"]["label"]` in scripts/python/omarchy_mise/config.py --
// tests/test_config.py fails if the two drift.
//
// U+F487, a rocket: one of the glyphs Omarchy's own menu draws. Any string
// works; see config.example.toml for how to change it.
var DEFAULT_LABEL = ""

// The plugin's CLI. Every process this plugin starts goes through it, so the
// argv array is built in one place and never from a shell string.
function cli(here, args) {
  return [rootFrom(here) + "/bin/omarchy-mise"].concat(args)
}
