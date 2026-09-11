import QtQuick
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

    implicitWidth: vertical
        ? barSize
        : Math.min(caption.implicitWidth + Style.space(12), Style.space(180))
    implicitHeight: barSize

    Services.Config {
        id: config
    }

    // The catalog is owned by this plugin's service entry point, so there is
    // one of it for the whole shell rather than one per monitor. The widget
    // subscribes; it never starts a catalog process itself.
    readonly property var catalog: bar && bar.shell && typeof bar.shell.serviceFor === "function"
        ? bar.shell.serviceFor(moduleName)
        : null

    onCatalogChanged: {
        if (catalog)
            console.log("omarchy-mise", "widget: catalog service resolved")
        else if (bar && bar.shell)
            // Only a real absence is worth reporting. This binding evaluates
            // once before the host has injected `bar`, and warning then would
            // put a false alarm in the log on every startup.
            console.warn("omarchy-mise", "widget: catalog service is not available")
    }

    Text {
        id: caption

        anchors.centerIn: parent
        width: Math.max(0, root.width - Style.space(8))
        text: root.label
        textFormat: Text.PlainText
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter
        color: root.bar ? root.bar.barForeground : Color.foreground
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.body
    }
}
