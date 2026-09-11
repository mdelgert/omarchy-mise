import QtQuick
import qs.Commons
import qs.Ui

// Collects values for the arguments a task declares.
//
// It gathers `{name: value}` and nothing more. Which spelling a flag uses,
// what order positionals go in, whether a blank means "omit" or "empty
// string" -- all of that belongs to `omarchy-mise run`, which resolves the
// values against the task's own usage spec. Duplicating that ordering logic
// here would be a second implementation with no tests behind it.
Item {
  id: root

  property var task: null
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family

  readonly property var arguments: task && Array.isArray(task.arguments) ? task.arguments : []
  // Qualified: a binding is a JS function, so a bare `arguments` resolves to
  // that function's own arguments object rather than to the property above.
  readonly property bool hasArguments: root.arguments.length > 0

  // name -> value, rebuilt whenever the task changes so one task's input can
  // never leak into another's run.
  property var values: ({})

  signal accepted
  signal cancelled

  visible: hasArguments
  implicitHeight: visible ? fields.implicitHeight : 0

  onTaskChanged: {
    // Read the spec off the task rather than the derived `arguments`
    // property: that binding has not necessarily re-evaluated yet at the
    // moment this handler runs, which left every field seeded from the
    // previous task -- or from nothing at all.
    const declared = task && Array.isArray(task.arguments) ? task.arguments : []
    const seeded = ({})
    for (let i = 0; i < declared.length; i++) {
      const argument = declared[i]
      // A declared default is the most likely answer, so offer it rather than
      // making the user retype it.
      seeded[argument.name] = argument.default === null || argument.default === undefined
        ? ""
        : String(argument.default)
    }
    values = seeded
  }

  function setValue(name, value) {
    const next = ({})
    for (const key in values)
      next[key] = values[key]
    next[name] = value
    values = next
  }

  function focusFirst() {
    if (repeater.count > 0 && repeater.itemAt(0))
      repeater.itemAt(0).focusField()
  }

  Column {
    id: fields

    width: parent.width
    spacing: Style.space(6)

    Repeater {
      id: repeater

      model: root.arguments

      delegate: Column {
        id: field

        required property int index
        required property var modelData

        function focusField() { input.forceActiveFocus() }

        width: parent.width
        spacing: Style.space(2)

        Text {
          width: parent.width
          // Argument names and help text come from a project's own config.
          text: {
            const label = field.modelData.kind === "flag" && field.modelData.long
              ? String(field.modelData.long)
              : String(field.modelData.name)
            const help = String(field.modelData.help || "")
            const required = field.modelData.required ? " (required)" : ""
            return help !== "" ? label + required + " — " + help : label + required
          }
          textFormat: Text.PlainText
          elide: Text.ElideRight
          color: Qt.darker(root.foreground, 1.4)
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }

        TextField {
          id: input

          width: parent.width
          text: root.values[field.modelData.name] || ""
          placeholderText: field.modelData.valueName === null
            ? "true / false"
            : String(field.modelData.valueName || field.modelData.name)
          foreground: root.foreground
          font.family: root.fontFamily
          onTextChanged: root.setValue(field.modelData.name, text)

          Keys.priority: Keys.BeforeItem
          Keys.onPressed: function (event) {
            switch (event.key) {
            case Qt.Key_Escape:
              root.cancelled()
              event.accepted = true
              break
            case Qt.Key_Return:
            case Qt.Key_Enter:
              root.accepted()
              event.accepted = true
              break
            case Qt.Key_Down:
              if (field.index + 1 < repeater.count && repeater.itemAt(field.index + 1))
                repeater.itemAt(field.index + 1).focusField()
              event.accepted = true
              break
            case Qt.Key_Up:
              if (field.index > 0 && repeater.itemAt(field.index - 1))
                repeater.itemAt(field.index - 1).focusField()
              event.accepted = true
              break
            }
          }
        }
      }
    }
  }
}
