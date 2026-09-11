import QtQuick
import qs.Commons
import qs.Ui

BarWidget {
    id: root

    moduleName: "io.github.mdelgert.omarchy-mise"

    // Keep the starter passive: it proves discovery, theming, settings, and
    // placement without introducing a global shortcut or subprocess lifecycle.
    readonly property string label: {
        const configured = setting("label", "Mise")
        return typeof configured === "string" && configured.trim().length > 0
            ? configured.slice(0, 80)
            : "Mise"
    }

    implicitWidth: vertical
        ? barSize
        : Math.min(caption.implicitWidth + Style.space(12), Style.space(180))
    implicitHeight: barSize

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
