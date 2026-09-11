import QtQuick
import Quickshell.Io
import "Plugin.js" as Plugin

// The one owner of the task catalog.
//
// Declared as this plugin's `service` entry point, so the host loads exactly
// one of these for the whole shell no matter how many monitors there are. Bar
// widgets reach it through `bar.shell.serviceFor(moduleName)` and subscribe;
// they never start a catalog process of their own. That is the difference
// between one refresh and one refresh per screen.
//
// It holds no UI. Rendering, including how the states below are worded, is
// the widget's job.
Item {
  id: root

  visible: false

  // ------------------------------------------------------------------ state
  //
  // Named `status`, not `state`: QQuickItem already owns `state`.
  // Empty, error, and cancelled are deliberately distinct. They look identical
  // if collapsed into "no tasks", and each one asks the user to do something
  // different about it.
  readonly property int statusIdle: 0
  readonly property int statusLoading: 1
  readonly property int statusReady: 2
  readonly property int statusEmpty: 3
  readonly property int statusError: 4
  readonly property int statusCancelled: 5

  property int status: statusIdle
  readonly property bool loading: status === statusLoading

  // Projects exactly as the CLI reported them, including any that carry an
  // `error` or `trusted: false`. A project the user cannot run tasks from is
  // still a project they need to see.
  property var projects: []
  property int taskCount: 0
  property var warnings: []
  property string error: ""
  property double lastRefresh: 0

  // A refresh that has not answered by now is not going to.
  property int timeoutMs: 20000
  // Bounded background refresh. Long enough that the catalog is never a
  // polling loop; a user who wants it sooner calls refresh().
  property int refreshIntervalMs: 300000

  signal refreshed

  // ---------------------------------------------------------------- controls

  function refresh() {
    // A newer request wins: cancel the one in flight rather than queueing
    // behind it, so the freshest answer is the one that lands.
    if (readProcess.running) {
      cancelling = true
      readProcess.running = false
    }
    root.error = ""
    root.status = statusLoading
    readProcess.running = true
    deadline.restart()
    heartbeat.restart()
  }

  function cancel() {
    if (!readProcess.running)
      return
    cancelling = true
    readProcess.running = false
  }

  // Tasks for one project path, or every task when no path is given.
  function tasksFor(projectPath) {
    var out = []
    for (var i = 0; i < root.projects.length; i++) {
      var project = root.projects[i]
      if (projectPath !== undefined && project.path !== projectPath)
        continue
      var tasks = project.tasks || []
      for (var t = 0; t < tasks.length; t++)
        out.push({ project: project, task: tasks[t] })
    }
    return out
  }

  // ----------------------------------------------------------------- private

  property bool cancelling: false

  function apply(payload) {
    var raw = String(payload || "").trim()
    // A failed read reports itself on stderr and writes nothing here; let
    // onExited surface that reason instead of blaming the parser.
    if (raw === "")
      return

    var parsed = null
    try {
      parsed = JSON.parse(raw)
    } catch (e) {
      root.error = "could not parse the task catalog: " + e
      return
    }
    if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.projects)) {
      root.error = "the task catalog was not in the expected shape"
      return
    }

    root.projects = parsed.projects
    root.taskCount = Number(parsed.taskCount || 0)
    root.warnings = Array.isArray(parsed.warnings) ? parsed.warnings : []
    root.lastRefresh = Date.now()
    for (var i = 0; i < root.warnings.length; i++)
      console.warn("omarchy-mise", "catalog:", root.warnings[i])
  }

  Process {
    id: readProcess

    command: Plugin.cli(Qt.resolvedUrl("."), ["--json", "catalog"])

    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.apply(text)
    }

    stderr: StdioCollector {
      waitForEnd: true
    }

    onExited: function (exitCode, exitStatus) {
      deadline.stop()

      if (root.cancelling) {
        root.cancelling = false
        // A cancelled refresh leaves the previous catalog in place; it is
        // stale, not wrong, and blanking the list would be worse.
        root.status = root.projects.length > 0 ? root.statusReady : root.statusCancelled
        return
      }

      if (root.error === "" && exitCode !== 0) {
        var detail = String(readProcess.stderr.text || "").trim()
        root.error = detail !== "" ? detail : "omarchy-mise catalog exited " + exitCode
      }

      if (root.error !== "") {
        console.warn("omarchy-mise", root.error)
        root.status = root.statusError
      } else if (root.taskCount === 0) {
        root.status = root.statusEmpty
      } else {
        root.status = root.statusReady
      }

      console.log("omarchy-mise", "catalog:", root.taskCount, "tasks in",
                  root.projects.length, "projects, status", root.status)
      root.refreshed()
    }
  }

  Timer {
    id: deadline

    interval: root.timeoutMs
    repeat: false
    onTriggered: {
      if (!readProcess.running)
        return
      root.error = "the task catalog timed out after " + root.timeoutMs + "ms"
      readProcess.running = false
    }
  }

  Timer {
    id: heartbeat

    interval: root.refreshIntervalMs
    repeat: true
    running: true
    onTriggered: root.refresh()
  }

  Component.onCompleted: root.refresh()

  Component.onDestruction: {
    deadline.stop()
    heartbeat.stop()
    if (readProcess.running)
      readProcess.running = false
  }
}
