import QtQuick
import qs.Commons

// One line about the last run, plus the tail of its output when there is
// something worth reading. Output is a diagnostic here, not a terminal: the
// CLI already caps what it captures, and anyone who needs the full thing runs
// the task in a shell.
Item {
  id: root

  property var runner: null
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family

  readonly property bool failed: runner
    && (runner.status === runner.statusFailed || runner.error !== "")

  // The most useful few lines: stderr when something went wrong, stdout when
  // it did not.
  readonly property string output: {
    if (!runner || !runner.result)
      return ""
    const stream = failed
      ? String(runner.result.stderr || "") || String(runner.result.stdout || "")
      : String(runner.result.stdout || "")
    const lines = stream.split("\n").filter(line => line.trim() !== "")
    return lines.slice(-3).join("\n")
  }

  visible: runner && (runner.status !== runner.statusIdle)
  implicitHeight: visible ? column.implicitHeight : 0

  Column {
    id: column

    width: parent.width
    spacing: Style.space(2)

    Text {
      width: parent.width
      text: root.runner ? root.runner.summary() : ""
      textFormat: Text.PlainText
      wrapMode: Text.WordWrap
      color: root.failed ? Color.urgent : root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }

    Text {
      width: parent.width
      visible: root.output !== ""
      // Task output is text this plugin does not control.
      text: root.output
      textFormat: Text.PlainText
      wrapMode: Text.WrapAnywhere
      maximumLineCount: 3
      elide: Text.ElideRight
      color: Qt.darker(root.foreground, 1.5)
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }
  }
}
