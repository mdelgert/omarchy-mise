import QtQuick
import Quickshell.Io
import qs.Commons
import qs.Ui
import "services" as Services

BarWidget {
    id: root

    moduleName: "io.github.mdelgert.omarchy-mise"

    // Label precedence: the host's inline setting wins, because a user who set
    // it in shell.json meant this bar instance specifically; then the config
    // file, which applies everywhere; then the built-in default.
    readonly property string label: {
        const inline = setting("label", "")
        const configured = typeof inline === "string" && inline.trim().length > 0
            ? inline
            : config.value("ui", "label", "Mise")
        return typeof configured === "string" && configured.trim().length > 0
            ? configured.trim().slice(0, 80)
            : "Mise"
    }

    // The catalog is owned by this plugin's service entry point, so there is
    // one of it for the whole shell rather than one per monitor. The widget
    // subscribes; it never starts a catalog process itself.
    readonly property var catalog: bar && bar.shell && typeof bar.shell.serviceFor === "function"
        ? bar.shell.serviceFor(moduleName)
        : null

    onCatalogChanged: {
        injectPanel()
        if (!catalog && bar && bar.shell)
            // This binding evaluates once before the host has injected `bar`,
            // so only a real absence is worth reporting.
            console.warn("omarchy-mise", "widget: catalog service is not available")
    }
    onBarChanged: injectPanel()
    onSettingsChanged: injectPanel()

    function injectPanel() {
        const target = panelLoader.item
        if (!target)
            return
        if ("bar" in target) target.bar = root.bar
        if ("settings" in target) target.settings = root.settings
        if ("moduleName" in target) target.moduleName = root.moduleName
        if ("anchorItem" in target) target.anchorItem = button
        if ("hostWidget" in target) target.hostWidget = root
        if ("catalog" in target) target.catalog = root.catalog
    }

    function panelAction(method) {
        const target = panelLoader.item
        if (target && typeof target[method] === "function")
            target[method]()
    }

    function togglePanel() { panelAction("toggle") }
    function openPanel() { panelAction("open") }
    function closePanel() { panelAction("close") }

    implicitWidth: vertical ? barSize : button.implicitWidth
    implicitHeight: vertical ? button.implicitHeight : barSize

    WidgetButton {
        id: button

        anchors.centerIn: parent
        bar: root.bar
        text: root.label
        textRotation: root.vertical ? -90 : 0
        active: panelLoader.item ? panelLoader.item.opened : false
        onPressed: function (button) { root.togglePanel() }
    }

    Services.Config {
        id: config
    }

    // One handler for the whole plugin, relayed to every monitor's panel.
    // R6 turns this into a documented, user-chosen binding.
    IpcHandler {
        target: root.moduleName

        function toggle(): void { root.broadcast("togglePanel") }
        function open(): void { root.broadcast("openPanel") }
        function close(): void { root.broadcast("closePanel") }
    }

    Loader {
        id: panelLoader

        active: true
        visible: false
        source: Qt.resolvedUrl("components/TaskListPanel.qml")
        onLoaded: {
            root.injectPanel()
            // The host finishes injecting `bar` after the Loader completes, so
            // a second pass on the next tick catches what the first one missed.
            Qt.callLater(root.injectPanel)
        }
    }
}
