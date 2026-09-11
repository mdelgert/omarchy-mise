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

// The plugin's CLI. Every process this plugin starts goes through it, so the
// argv array is built in one place and never from a shell string.
function cli(here, args) {
  return [rootFrom(here) + "/bin/omarchy-mise"].concat(args)
}
