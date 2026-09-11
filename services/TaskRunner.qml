import QtQuick
import Quickshell.Io
import "Plugin.js" as Plugin

// Runs one mise task and reports what happened.
//
// Every decision that matters -- whether the task exists, whether its project
// is trusted, whether its risk level needs confirming, how long it may run,
// how much output to keep -- belongs to `omarchy-mise run`, which owns the
// user's config. This file starts that process, parses one JSON object, and
// exposes the outcome. It deliberately re-implements none of that logic: a
// second opinion in QML about what is safe to run is exactly the bug worth
// avoiding.
//
// Confirmation works by asking and being refused. A first attempt runs without
// --confirm; if the CLI comes back `confirmation-required` it spawned nothing,
// and the caller may retry with confirmed=true once a human has agreed.
Item {
  id: root

  visible: false

  readonly property int statusIdle: 0
  readonly property int statusRunning: 1
  readonly property int statusSucceeded: 2
  readonly property int statusFailed: 3
  readonly property int statusNeedsConfirmation: 4
  readonly property int statusCancelled: 5

  property int status: statusIdle
  readonly property bool running: status === statusRunning

  // The parsed result object from the CLI, or null before the first run.
  property var result: null
  property string error: ""

  // What was asked for, kept so a confirmed retry repeats it exactly.
  property var request: null

  signal finished(var result)
  // The task will not run until someone confirms. `request` describes what.
  signal confirmationRequired(var request)

  function run(projectPath, taskName, args, confirmed) {
    if (running)
      return
    root.request = {
      project: String(projectPath || ""),
      task: String(taskName || ""),
      args: args || [],
      confirmed: confirmed === true
    }
    root.result = null
    root.error = ""
    root.status = statusRunning
    runProcess.command = buildCommand(root.request)
    runProcess.running = true
  }

  // Retry the last request with the user's agreement.
  function confirm() {
    if (!root.request)
      return
    run(root.request.project, root.request.task, root.request.args, true)
  }

  // The user declined the confirmation. The CLI's refusal text explains a
  // --confirm flag they never typed, which is the wrong thing to leave on
  // screen after they pressed Cancel.
  function declineConfirmation() {
    if (root.status === statusNeedsConfirmation)
      root.status = statusCancelled
  }

  function cancel() {
    if (!running)
      return
    cancelling = true
    runProcess.running = false
  }

  function buildCommand(spec) {
    // An argv array throughout: a task name or argument is never spliced into
    // a shell string, here or in the CLI.
    var args = ["--json", "run"]
    if (spec.confirmed)
      args.push("--confirm")
    args.push(spec.project, spec.task)
    if (spec.args.length > 0) {
      // Anything that looks like a flag belongs to the task, not to us.
      args.push("--")
      for (var i = 0; i < spec.args.length; i++)
        args.push(String(spec.args[i]))
    }
    return Plugin.cli(Qt.resolvedUrl("."), args)
  }

  // A short line describing the outcome, for the status strip.
  function summary() {
    if (root.status === statusRunning)
      return "Running " + (root.request ? root.request.task : "") + "…"
    if (root.status === statusCancelled)
      return "Cancelled."
    if (root.error !== "")
      return root.error
    if (!root.result)
      return ""

    var name = String(root.result.task || "")
    switch (String(root.result.status || "")) {
    case "succeeded":
      return name + " succeeded in " + Number(root.result.durationSeconds || 0).toFixed(1) + "s"
    case "timedOut":
      return name + " timed out after " + root.result.timeoutSeconds + "s"
    case "refused":
      return String(root.result.error || "refused")
    default:
      return name + " failed (exit " + root.result.exitCode + ")"
    }
  }

  property bool cancelling: false

  Process {
    id: runProcess

    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.apply(text)
    }

    stderr: StdioCollector {
      waitForEnd: true
    }

    onExited: function (exitCode, exitStatus) {
      if (root.cancelling) {
        root.cancelling = false
        root.status = root.statusCancelled
        return
      }

      if (!root.result && root.error === "") {
        var detail = String(runProcess.stderr.text || "").trim()
        root.error = detail !== "" ? detail : "omarchy-mise run exited " + exitCode
      }

      if (root.error !== "") {
        console.warn("omarchy-mise", "run:", root.error)
        root.status = root.statusFailed
      } else if (String(root.result.reason || "") === "confirmation-required") {
        // Nothing was spawned; the CLI refused and told us why.
        root.status = root.statusNeedsConfirmation
        root.confirmationRequired(root.request)
        return
      } else {
        root.status = root.result.ok === true ? root.statusSucceeded : root.statusFailed
      }

      root.finished(root.result)
    }
  }

  function apply(payload) {
    var raw = String(payload || "").trim()
    // A run that could not start reports on stderr and writes nothing here.
    if (raw === "")
      return
    try {
      root.result = JSON.parse(raw)
    } catch (e) {
      root.error = "could not parse the run result: " + e
    }
  }

  Component.onDestruction: {
    if (runProcess.running)
      runProcess.running = false
  }
}
