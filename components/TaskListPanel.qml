import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui
import "../services" as Services

// Read-only browser for the tasks the catalog service found.
//
// Owns presentation only: every task, project and state it renders comes from
// the injected catalog service, and nothing here starts a process. Running a
// task is R4 — this surface deliberately has no way to do it, so there is no
// path from "browsing" to "ran something" by accident.
Panel {
    id: root

    // The bar widget hosting this panel, injected by Main.qml.
    property Item anchorItem: null
    property var hostWidget: null
    // The one TaskCatalog instance, injected rather than created: a panel per
    // monitor must not mean a catalog per monitor.
    property var catalog: null

    // The host routes an IPC target to exactly one handler, but a bar surface
    // exists per monitor. Letting each panel register the target would mean a
    // toggle reaches whichever one happened to win the race and leaves the
    // other screens stale, so Main.qml owns the handler and broadcasts to all
    // of them instead.
    manageIpc: false

    property string filter: ""

    // The row the user would act on, or null when the list is empty or the
    // selection sits on a project that cannot be read.
    readonly property var selectedRow: list.currentIndex >= 0 && list.currentIndex < rows.length
        ? rows[list.currentIndex]
        : null

    // The task whose arguments are being filled in, or null when none is.
    property var editing: null

    function runSelected() {
        const row = selectedRow
        // An unusable project has no task to run, and a run already in flight
        // owns the runner until it finishes.
        if (!row || !row.task || runner.running)
            return
        // A task that declares arguments gets the editor first; one that does
        // not runs straight away rather than showing an empty form.
        const declared = row.task.arguments
        if (Array.isArray(declared) && declared.length > 0 && editing !== row.task) {
            editing = row.task
            Qt.callLater(editor.focusFirst)
            return
        }
        runEditing(row)
    }

    function runEditing(row) {
        const values = editing === row.task ? editor.values : ({})
        editing = null
        // The editor's field is about to be hidden; hand focus back or the
        // next keystroke lands on an invisible item and appears to do nothing.
        filterField.forceActiveFocus()
        runner.run(row.project.path, row.task.name, values, false)
    }

    function commitEditor() {
        const row = selectedRow
        if (row && row.task)
            runEditing(row)
    }

    function cancelEditor() {
        editing = null
        filterField.forceActiveFocus()
    }

    readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
    readonly property color foreground: bar ? bar.barForeground : Color.foreground

    // Flattened rows matching the filter, so the view binds to one list
    // instead of nesting repeaters over projects. `projectName` is duplicated
    // onto each row because ListView groups by a plain property name, and two
    // projects can define the same task name — without the grouping those
    // rows are indistinguishable.
    readonly property var rows: {
        const needle = filter.trim().toLowerCase()
        const out = []
        const projects = catalog && catalog.projects ? catalog.projects : []
        for (let p = 0; p < projects.length; p++) {
            const project = projects[p]
            const tasks = project.tasks || []
            // A project that cannot be read has no tasks to match, but the
            // user still needs to see that it exists and why it is unusable.
            if (tasks.length === 0 && project.error) {
                if (needle === "" || String(project.name || "").toLowerCase().indexOf(needle) !== -1)
                    out.push({ project: project, task: null, projectName: project.name })
                continue
            }
            for (let t = 0; t < tasks.length; t++) {
                const task = tasks[t]
                if (needle !== "") {
                    const haystack = (String(task.name || "") + " "
                        + String(task.description || "") + " "
                        + String(project.name || "")).toLowerCase()
                    if (haystack.indexOf(needle) === -1)
                        continue
                }
                out.push({ project: project, task: task, projectName: project.name })
            }
        }
        return out
    }

    // What to say when there is nothing to list. Empty, filtered-to-nothing,
    // broken and cancelled are four different situations and each one tells
    // the user to do something different.
    readonly property string emptyMessage: {
        if (!catalog)
            return "The task catalog is not available."
        if (catalog.loading && rows.length === 0)
            return "Looking for mise projects…"
        if (catalog.status === catalog.statusError)
            return catalog.error !== "" ? catalog.error : "The task catalog could not be read."
        if (catalog.status === catalog.statusCancelled)
            return "The refresh was cancelled."
        if (filter.trim() !== "")
            return "No task matches “" + filter.trim() + "”."
        return "No mise projects found. Set scan.directories in ~/.config/omarchy-mise/config.toml."
    }

    function selectDelta(delta) {
        if (rows.length === 0)
            return
        let next = list.currentIndex + delta
        next = Math.max(0, Math.min(rows.length - 1, next))
        list.currentIndex = next
        list.positionViewAtIndex(next, ListView.Contain)
    }

    // Re-filtering changes what row 0 means, so anchor the selection rather
    // than leaving it pointing past the end of a shorter list.
    onRowsChanged: list.currentIndex = rows.length > 0 ? 0 : -1

    // Moving off a task abandons its half-filled form rather than carrying
    // the values onto whatever is selected next.
    onSelectedRowChanged: {
        if (editing && (!selectedRow || selectedRow.task !== editing))
            editing = null
    }

    onOpenedChanged: {
        if (!opened)
            return
        // Opening is an explicit user action, so it is the right moment to
        // refresh — and the only automatic one besides the slow heartbeat.
        if (catalog && typeof catalog.refresh === "function" && !catalog.loading)
            catalog.refresh()
    }

    Services.TaskRunner {
        id: runner

        onConfirmationRequired: function (request) {
            // The CLI refused and spawned nothing. Ask, and only retry if the
            // answer is yes.
            // Name the level the task actually carries. Hardcoding "high"
            // was wrong for anyone whose run.confirm_risk lists another level.
            const level = runner.result && runner.result.risk
                ? String(runner.result.risk)
                : "risky"
            confirmDialog.message = "Run " + request.task + "?\n"
                + "It is marked " + level + " risk in this project's task metadata."
            confirmDialog.selectedIndex = 0
            confirmDialog.opened = true
        }
        onFinished: function (result) {
            if (result && result.ok !== true)
                console.warn("omarchy-mise", "run failed:", result.error || result.status)
        }
    }

    KeyboardPanel {
        id: panel

        anchorItem: root.anchorItem
        // The bar tracks the widget mounted in its slot, not this nested
        // panel, and resolves popout identity by slot.activeItem === owner.
        // Naming the panel here breaks the open-panel indicator and Tab.
        owner: root.hostWidget || root
        bar: root.bar
        open: root.opened
        // The filter field, not the key catcher: typing to narrow the list is
        // the primary interaction, and KeyboardPanel focuses its focusTarget
        // on a callLater that would otherwise overwrite anything set here.
        // Keys the field does not consume still bubble up to the catcher.
        focusTarget: filterField
        contentWidth: panel.fittedContentWidth(Style.space(420))
        contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(520))

        PanelKeyCatcher {
            id: keyCatcher

            anchors.fill: parent

            onMoveRequested: function (dx, dy) {
                if (dy !== 0)
                    root.selectDelta(dy)
            }
            onCloseRequested: root.close()
            onTabRequested: function (direction) { root.switchPanel(direction) }
            onActivateRequested: root.runSelected()

            // While the dialog is up it owns the keyboard, so a stray Enter
            // cannot reach the list and start a second run behind it.
            blocked: confirmDialog.opened

            ConfirmDialog {
                id: confirmDialog

                anchors.fill: parent
                z: 10
                confirmText: "Run"
                foreground: root.foreground
                fontFamily: root.fontFamily

                onCanceled: {
                    opened = false
                    runner.declineConfirmation()
                }
                onConfirmed: {
                    opened = false
                    runner.confirm()
                }
            }

            Column {
                id: column

                anchors.fill: parent
                spacing: Style.space(8)

                PanelSectionHeader {
                    width: parent.width
                    text: root.catalog && root.catalog.taskCount > 0
                        ? root.catalog.taskCount + " TASKS"
                        : "MISE TASKS"
                    foreground: root.foreground
                    fontFamily: root.fontFamily
                }

                TextField {
                    id: filterField

                    width: parent.width
                    placeholderText: "Filter tasks"
                    foreground: root.foreground
                    font.family: root.fontFamily
                    onTextChanged: root.filter = text
                    // Arrow keys belong to the list even while typing, so the
                    // user never has to leave the filter to pick a result.
                    // One handler, ahead of the field's own editing, because
                    // the specific Keys.onEscapePressed / onReturnPressed
                    // signals fire even when Keys.onPressed has accepted the
                    // event -- which let Escape dismiss the whole panel out
                    // from under a modal dialog. Only the keys handled here
                    // are accepted; everything else still reaches the field.
                    Keys.priority: Keys.BeforeItem
                    Keys.onPressed: function (event) {
                        if (confirmDialog.opened) {
                            // The dialog is modal: it answers what it knows,
                            // and swallows the rest so nothing reaches the
                            // list or the filter behind it.
                            confirmDialog.handleKey(event)
                            event.accepted = true
                            return
                        }

                        switch (event.key) {
                        case Qt.Key_Escape:
                            root.close()
                            event.accepted = true
                            break
                        case Qt.Key_Return:
                        case Qt.Key_Enter:
                            root.runSelected()
                            event.accepted = true
                            break
                        case Qt.Key_Down:
                            root.selectDelta(1)
                            event.accepted = true
                            break
                        case Qt.Key_Up:
                            root.selectDelta(-1)
                            event.accepted = true
                            break
                        }
                    }
                }

                PanelSeparator { width: parent.width }

                Text {
                    width: parent.width
                    visible: root.rows.length === 0
                    text: root.emptyMessage
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    color: Qt.darker(root.foreground, 1.4)
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.body
                }

                ParameterEditor {
                    id: editor

                    width: parent.width
                    visible: root.editing !== null
                    task: root.editing
                    foreground: root.foreground
                    fontFamily: root.fontFamily

                    onAccepted: root.commitEditor()
                    onCancelled: root.cancelEditor()
                }

                TaskStatus {
                    width: parent.width
                    runner: runner
                    foreground: root.foreground
                    fontFamily: root.fontFamily
                }

                ListView {
                    id: list

                    width: parent.width
                    height: Math.min(contentHeight, Style.space(380))
                    visible: root.rows.length > 0
                    model: root.rows
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    currentIndex: 0
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    section.property: "projectName"
                    section.criteria: ViewSection.FullString
                    section.delegate: PanelSectionHeader {
                        required property string section

                        width: ListView.view.width
                        topPadding: Style.space(6)
                        text: section
                        foreground: ListView.view.rowForeground
                        fontFamily: ListView.view.rowFontFamily
                    }

                    // The delegate reaches these through ListView.view rather
                    // than closing over ids in this file, which it cannot
                    // resolve statically.
                    property color rowForeground: root.foreground
                    property string rowFontFamily: root.fontFamily
                    property color rowSelection: Style.selectionFillFor(root.foreground, Color.accent)

                    delegate: Item {
                        id: row

                        required property int index
                        required property var modelData

                        readonly property var task: modelData.task
                        readonly property var project: modelData.project
                        readonly property bool selected: ListView.isCurrentItem
                        // A project mise refused to read, or one the user has
                        // not trusted. Shown, never silently dropped.
                        readonly property bool unusable: !task

                        width: row.ListView.view.width
                        implicitHeight: label.implicitHeight + Style.space(10)

                        Rectangle {
                            anchors.fill: parent
                            radius: Style.space(4)
                            color: row.selected ? row.ListView.view.rowSelection : "transparent"
                        }

                        Column {
                            id: label

                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: Style.space(6)
                            anchors.rightMargin: Style.space(6)
                            spacing: Style.space(2)

                            Text {
                                width: parent.width
                                // Everything here comes from files this plugin
                                // does not control, so none of it is markup.
                                text: row.unusable
                                    ? row.project.name
                                    : row.task.name
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: row.unusable ? Color.urgent : row.ListView.view.rowForeground
                                font.family: row.ListView.view.rowFontFamily
                                font.pixelSize: Style.font.body
                            }

                            Text {
                                width: parent.width
                                text: row.unusable
                                    ? String(row.project.error || "unavailable")
                                    : String(row.task.description || "")
                                visible: text !== ""
                                textFormat: Text.PlainText
                                elide: Text.ElideRight
                                color: Qt.darker(row.ListView.view.rowForeground, 1.5)
                                font.family: row.ListView.view.rowFontFamily
                                font.pixelSize: Style.font.caption
                            }
                        }
                    }
                }
            }
        }
    }
}
