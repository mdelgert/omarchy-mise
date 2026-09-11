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

    onCatalogChanged: injectPanel()

    // The service resolves a moment after the widget is built, so `catalog` is
    // legitimately null at first and warning on every change put three false
    // alarms in the log on every startup. Report only a genuine absence.
    Timer {
        interval: 5000
        running: true
        repeat: false
        onTriggered: {
            if (!root.catalog)
                console.warn("omarchy-mise",
                             "widget: catalog service unavailable; is the plugin enabled?")
        }
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

    // Shape contract for shell.summon/hide/toggle routing: Bar.findPanelWidget
    // skips any bar widget that does not expose open(), close() and `opened`,
    // and that router is what picks the focused monitor's copy.
    readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false

    function panelAction(method) {
        const target = panelLoader.item
        if (target && typeof target[method] === "function")
            target[method]()
    }

    function open() { panelAction("open") }
    function close() { panelAction("close") }
    function togglePanel() { panelAction("toggle") }

    // Popout identity: Bar.requestPopout prefers closeForPopoutSwitch over
    // close, and KeyboardPanel reads popoutSwitchClosing back off its owner.
    readonly property bool popoutSwitchClosing: panelLoader.item
        ? panelLoader.item.popoutSwitchClosing === true
        : false

    function closeForPopoutSwitch() { panelAction("closeForPopoutSwitch") }

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

    // This target routes to whichever per-monitor instance registered first,
    // so it acts on that one instance. Opening every copy is not an option:
    // the bar keeps a single shell-wide activePopout, so three simultaneous
    // opens cancel each other and can leave a panel wedged open-but-unmapped.
    // `broadcast` is for refresh-style methods only. A summon that should land
    // on the focused monitor goes through the host instead:
    //   omarchy-shell shell toggle io.github.mdelgert.omarchy-mise
    // which resolves the right copy via Bar.findPanelWidget. R6 documents that
    // as the binding.
    IpcHandler {
        target: root.moduleName

        function toggle(): void { root.togglePanel() }
        function open(): void { root.open() }
        function close(): void { root.close() }
        function refresh(): void { root.broadcast("refreshCatalog") }
    }

    // Unlike open/close, a refresh must reach every screen or the others go
    // stale -- the case broadcast exists for.
    function refreshCatalog() {
        if (catalog && typeof catalog.refresh === "function")
            catalog.refresh()
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
