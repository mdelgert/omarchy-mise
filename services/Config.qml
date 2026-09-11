import QtQuick
import Quickshell.Io

// Reads the plugin's configuration by asking its own CLI, which is the only
// thing that knows the schema. QML never parses TOML and never touches the
// filesystem directly: `omarchy-mise config --json` is the whole contract.
//
// This is a one-shot read at load, not a long-lived subscription, so one short
// process per bar instance is acceptable. Shared, refreshing state belongs to a
// single owner instead — see R2 in docs/ROADMAP.md.
Item {
  id: root

  visible: false

  // Resolved configuration, or null until the first read finishes. Consumers
  // must treat null as "not known yet" and fall back, never as "empty".
  property var settings: null
  property bool loaded: false
  // Human-readable reason the last read failed; empty when it succeeded.
  property string error: ""

  // A config read that has not answered by now is not going to. The bar must
  // never wait on it.
  property int timeoutMs: 5000

  signal reloaded

  // The plugin's own directory, so the CLI is found wherever the plugin is
  // installed — a git clone under ~/.config/omarchy/plugins or a development
  // symlink pointing anywhere else.
  readonly property string pluginRoot: {
    var here = String(Qt.resolvedUrl("."))
    if (here.indexOf("file://") === 0)
      here = here.substring(7)
    return here.replace(/\/services\/?$/, "")
  }

  function reload() {
    if (readProcess.running)
      return
    root.error = ""
    readProcess.running = true
    deadline.restart()
  }

  function apply(payload) {
    var raw = String(payload || "").trim()
    // A failed read writes its reason to stderr and leaves stdout empty.
    // Returning here lets onExited report that reason; parsing the empty
    // string instead would blame JSON for a configuration error and hide
    // the one line the user actually needs to read.
    if (raw === "")
      return

    var parsed = null
    try {
      parsed = JSON.parse(raw)
    } catch (e) {
      root.error = "could not parse configuration: " + e
      console.warn("omarchy-mise", root.error)
      return
    }
    if (!parsed || typeof parsed !== "object") {
      root.error = "configuration was not an object"
      console.warn("omarchy-mise", root.error)
      return
    }
    root.settings = parsed
    // Surface the CLI's own warnings once, so a typo in config.toml is
    // discoverable from the shell log instead of silently ignored.
    var warnings = parsed["_warnings"] || []
    for (var i = 0; i < warnings.length; i++)
      console.warn("omarchy-mise", "config:", warnings[i])
  }

  // Read one value, falling back while the config is unknown or absent.
  function value(section, key, fallback) {
    if (!root.settings)
      return fallback
    var table = root.settings[section]
    if (!table || typeof table !== "object")
      return fallback
    var found = table[key]
    return found === undefined || found === null ? fallback : found
  }

  Process {
    id: readProcess

    command: [root.pluginRoot + "/bin/omarchy-mise", "--json", "config"]

    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.apply(text)
    }

    stderr: StdioCollector {
      waitForEnd: true
    }

    onExited: function (exitCode) {
      deadline.stop()
      if (exitCode !== 0 && root.error === "") {
        var detail = String(readProcess.stderr.text || "").trim()
        root.error = detail !== "" ? detail : "omarchy-mise config exited " + exitCode
        console.warn("omarchy-mise", root.error)
      }
      root.loaded = true
      root.reloaded()
    }
  }

  Timer {
    id: deadline

    interval: root.timeoutMs
    repeat: false
    onTriggered: {
      if (!readProcess.running)
        return
      root.error = "configuration read timed out"
      console.warn("omarchy-mise", root.error)
      // Owning the process means ending it, not waiting on it.
      readProcess.signal(15)
      readProcess.running = false
    }
  }

  Component.onCompleted: root.reload()

  // Nothing may outlive the widget that started it.
  Component.onDestruction: {
    deadline.stop()
    if (readProcess.running)
      readProcess.running = false
  }
}
