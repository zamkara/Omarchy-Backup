import QtQuick
import QtQuick.Layouts
import Qt.labs.folderlistmodel
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import "controls" as SoundUi
Item {
 id: root
 function toolPath(name) { return decodeURIComponent(Qt.resolvedUrl("scripts/" + name).toString().replace(/^file:\/\//, "")) }
 property bool refreshRequested: false
 function refreshSystem() { if (busy || phase !== "restored" || refreshRequested) return; refreshRequested = true; Quickshell.execDetached(["python3", root.toolPath("refresh.py"), "--pending", pendingDesktop, "--log-file", logPath]); }
 property bool opened: false
 property string destination: Quickshell.env("HOME") + "/Downloads"
 property string resultPath: ""
 property string message: "Ready. Choose where to save your backup."
 property string output: ""
 property string logText: ""
 property string pendingLog: ""
 property string pendingDesktop: ""
 property string jobId: ""
 property real progress: 0
 property string logPath: ""
 property string errorOutput: ""
 readonly property bool restoring: phase === "restore"
 function beginLog(name) { jobId = name + "-" + Date.now() + "-" + Math.random().toString(16).slice(2); logPath = Quickshell.env("HOME") + "/.local/state/omarchy/backup/logs/" + jobId + ".log"; logText = ""; pendingLog = ""; output = ""; errorOutput = "" }
 function receiveLine(line,isError) {
  if (line.indexOf("Desktop configuration staged without triggering live reload: ") === 0) pendingDesktop = line.substring("Desktop configuration staged without triggering live reload: ".length)
  var match = line.match(/^\[progress\] (\d+)\/(\d+)$/)
  if (match) { progress = Math.max(progress,Number(match[1])/Number(match[2])*(restoring ? 1 : 0.9)); return }
  pendingLog = (pendingLog + line + "\n").slice(-131072)
  if (isError) errorOutput = (errorOutput + line + "\n").slice(-131072); else if (phase === "inspect" || line.indexOf("Backup complete: ") === 0) output += line + "\n"
 }

 property var restoreSections: []
 readonly property bool restoreAllSelected: restoreSections.length > 0 && restoreSections.every(function(s) { return s.selected })
 readonly property bool restoreHasSelection: restoreSections.some(function(s) { return s.selected })
 function toggleRestore(index) { if (busy) return; var copy = restoreSections.slice(); copy[index] = Object.assign({},copy[index],{selected: !copy[index].selected}); restoreSections = copy; root.soundBus.interaction("click") }
 function toggleRestoreAll() { if (busy) return; var selected = !restoreAllSelected; restoreSections = restoreSections.map(function(s) { return Object.assign({},s,{selected: selected}) }); }
 property bool cancelRequested: false
 readonly property bool canCancel: phase === "backup" || phase === "verify" || phase === "restore"
 function cancelBackup() {
  if (!canCancel || cancelRequested) return
  cancelRequested = true; message = "Cancelling and removing unfinished backup…"
  if (worker.running) worker.signal(15); else finishCancel()
 }
 function finishCancel() {
  if (restoring) { phase = "cancelled"; cancelRequested = false; message = "Restore cancelled · previous files restored · Save to"; return }
  if (resultPath) { cleanup.command = ["python3", root.toolPath("omarchy-backup.py"), "--discard", resultPath, "--job-id", jobId, "--log-file", logPath]; cleanup.running = true }
  else { phase = "cancelled"; cancelRequested = false; output = ""; logText += "Cancelled. Incomplete backup cleared.\n"; message = "Backup cancelled · Save to" }
 }
 function copyLog() { Quickshell.execDetached(["bash", "-c", "wl-copy < \"$1\"", "copy-backup-log", logPath]); root.soundBus.interaction("click") }

 property string phase: ""
 property bool restoreConfirmed: false
 property bool pickerOpen: false
 property bool pickerRestore: false
 property string pickerPath: Quickshell.env("HOME")
 readonly property var soundBus: sounds
 readonly property bool allSelected: sections.every(function(s) { return s.selected })
 function toggleAll() { var select = !allSelected; sections = sections.map(function(s) { return Object.assign({},s,{selected:select}) }); root.soundBus.interaction("click") }
 function browseFolder(restore) { if (busy) return; pickerRestore = restore; pickerPath = restore && selectedBackup ? selectedBackup : destination; pickerOpen = true }
 property bool previewOpen: false
 property var previewData: ({})
 property string selectedBackup: ""
 property var sections: [
 {id:"desktop",label:"Desktop & plugins",selected:true}, {id:"terminals",label:"Terminals & shells",selected:true},
 {id:"editors",label:"Editor settings",selected:true}, {id:"fonts",label:"Fonts, icons & themes",selected:true},
 {id:"tools",label:"Local tools",selected:true}, {id:"services",label:"User services",selected:true},
 {id:"preferences",label:"Desktop preferences",selected:true}, {id:"packages",label:"Package inventories",selected:true},
 {id:"git",label:"Git configuration",selected:true}, {id:"ssh",label:"SSH config & known hosts",selected:false},
 {id:"ssh-keys",label:"SSH including private keys",selected:false}, {id:"credentials",label:"GPG & credential stores",selected:false},
 {id:"browsers",label:"Browser profiles & sessions",selected:false}, {id:"network",label:"VPN & sync configuration",selected:false},
 {id:"documents",label:"Documents",selected:false}, {id:"projects",label:"Projects",selected:false}, {id:"media",label:"Pictures, music & videos",selected:false}
 ]
 readonly property bool hasSelection: sections.some(function(s) { return s.selected })
 function toggleSection(index) { if (busy) return; var copy = sections.slice(); copy[index] = Object.assign({},copy[index],{selected:!copy[index].selected}); sections = copy }
 function checkBackup(path) { if (busy) return;
  beginLog("preview"); selectedBackup = path; restoreConfirmed = false; output = ""; phase = "inspect"; message = "Checking selected backup…"
  worker.command = ["python3", root.toolPath("omarchy-restore.py"), "--backup", path, "--preview", "--log-file", logPath]; worker.running = true
 }
 function restoreBackup() { if (busy) return;
  if (!restoreConfirmed) { restoreConfirmed = true; message = "Restore selected backup? Existing files will be backed up. Click Confirm Restore to continue."; root.soundBus.play("warning"); return }
  beginLog("restore"); pendingDesktop = ""; progress = 0; cancelRequested = false; resultPath = ""; phase = "restore"; message = "Restoring selected backup…"
  worker.command = ["python3", root.toolPath("omarchy-restore.py"), "--backup", selectedBackup, "--restore", "--yes", "--defer-desktop", "--sections", restoreSections.filter(function(s) { return s.selected }).map(function(s) { return s.id }).join(","), "--log-file", logPath]; worker.running = true
 }
 readonly property bool busy: refreshRequested || worker.running || cleanup.running || ["backup","verify","inspect","restore"].indexOf(phase) >= 0
 QtObject { id: sounds; function play(name) {} function surface(opened) {} function interaction(name) {} }
 Timer { interval: 150; repeat: true; running: !!root.pendingLog; onTriggered: { root.logText = (root.logText + root.pendingLog).slice(-131072); root.pendingLog = "" } }
 function open(payload) { opened = true }
 function close() { if (!busy) { if (pickerOpen) pickerOpen = false; else if (previewOpen) previewOpen = false; else opened = false } }
 onOpenedChanged: root.soundBus.surface(opened)
 function start() {
  if (!hasSelection || busy || destination.charAt(0) !== "/") return
  beginLog("backup"); resultPath = ""; progress = 0.015; cancelRequested = false; phase = "backup"
  message = "Creating archives and standalone restore tools…"
  var folder = destination.replace(/\/$/, "")
  worker.command = ["python3", root.toolPath("omarchy-backup.py"), "--destination", folder, "--job-id", jobId, "--log-file", logPath, "--sections", sections.filter(function(s) { return s.selected }).map(function(s) { return s.id }).join(",")]
  worker.running = true
 }
 IpcHandler { target: "backup"; function browse(restore: bool): string { root.opened = true; root.browseFolder(restore); return "ok" } function preview(path: string): string { root.opened = true; root.checkBackup(path); return "ok" } function status(): string { return JSON.stringify({busy: root.busy, phase: root.phase, picker: root.pickerOpen, folders: folders.count, message: root.message, result: root.resultPath}) } }
 // Setup integration is idempotent and runs only while this enabled plugin is loaded.
 Process {
  id: menuIntegration
  command: ["python3", root.toolPath("menu.py"), "--install"]
  running: true
  stderr: StdioCollector { onStreamFinished: { if (text) root.pendingLog += text } }
 }
 FolderListModel { id: folders; folder: "file://" + root.pickerPath; showFiles: false; showDotAndDotDot: false; showHidden: false; sortField: FolderListModel.Name }
 Process {
  id: worker
  stdout: SplitParser { onRead: function(data) { root.receiveLine(data,false) } }
  stderr: SplitParser { onRead: function(data) { root.receiveLine(data,true) } }
  onExited: function(code, exitStatus) {
   if (root.cancelRequested) { if (root.restoring && code !== 130) { root.cancelRequested = false; root.phase = "error"; root.message = "Restore stopped · inspect log for rollback status" } else root.finishCancel(); return }
   if (code !== 0) { root.phase = "error"; root.message = "Operation failed · see log"; root.soundBus.play("error"); return }
   if (root.phase === "inspect") { try { root.previewData = JSON.parse(root.output); root.restoreSections = root.previewData.archives.map(function(a) { return {id: a.name.replace(/\.tar\.gz$/, ""), selected: true} }); root.previewOpen = true; root.phase = "restore-ready"; root.message = "Selected backup verified." } catch (e) { root.phase = "error"; root.message = "Could not read backup preview: " + e } return }
   if (root.phase === "restore") { root.phase = "restored"; root.restoreConfirmed = false; root.message = "Restore complete · Refresh System when ready"; root.soundBus.play("success"); return }
   if (root.phase === "backup") {
    var match = root.output.match(/Backup complete: ([^\n]+)/)
    if (!match) { root.phase = "error"; root.message = "Backup did not report its destination."; return }
    root.resultPath = match[1]; root.phase = "verify"; root.message = "Verifying SHA-256 checksums…"
    Qt.callLater(function() { if (root.cancelRequested) return; worker.command = ["python3", root.toolPath("omarchy-restore.py"), "--backup", root.resultPath, "--check", "--log-file", root.logPath]; worker.running = true })
   } else { root.phase = "complete"; root.progress = 1; root.message = "Backup complete · checksums verified · Save to"; root.soundBus.play("success") }
  }
 }
 Process {
  id: cleanup
  stdout: StdioCollector { waitForEnd: true; onStreamFinished: root.logText += text }
  stderr: StdioCollector { waitForEnd: true; onStreamFinished: root.logText += text }
  onExited: function(code, status) { root.cancelRequested = false; root.phase = code === 0 ? "cancelled" : "error"; root.message = code === 0 ? "Backup cancelled · Save to" : "Cleanup failed · see log"; root.resultPath = ""; root.output = "" }
 }
 PanelWindow {
  visible: root.opened
  anchors { top: true; bottom: true; left: true; right: true }
  color: "transparent"
  exclusionMode: ExclusionMode.Ignore
  WlrLayershell.namespace: "omarchy-menu"
  WlrLayershell.layer: WlrLayer.Overlay
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
  MouseArea { anchors.fill: parent; onClicked: root.close() }
  Rectangle {
   visible: !root.previewOpen && !root.pickerOpen
   width: Math.min(820, parent.width - 60)
   height: content.implicitHeight + 44
   anchors.centerIn: parent
   color: Color.menu.background; border.color: Color.menu.border; radius: Style.cornerRadius
   MouseArea { anchors.fill: parent }
   ColumnLayout {
    id: content
    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 22 }
    spacing: 12
    Keys.onEscapePressed: root.close()
    RowLayout {
     Layout.fillWidth: true
     Text { text: "Backup & Restore"; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.display; Layout.fillWidth: true }
     SoundUi.Button { soundBus: root.soundBus; fontFamily: Style.font.menuFamily; fontSize: Style.font.heading + 1; iconText: "󰅖"; enabled: !root.busy; tooltipText: "Close"; onClicked: root.close() }
    }
    Text { text: "Choose what to back up, or select a saved backup to restore."; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    Text { text: root.phase === "" ? "Save to" : root.message; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading }
    RowLayout {
     Layout.fillWidth: true
     Rectangle {
      Layout.fillWidth: true; implicitHeight: 40; color: "transparent"; border.color: Color.menu.border; radius: 6
      TextInput { anchors { fill: parent; margins: 10 } text: root.destination; enabled: !root.busy; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading; clip: true; selectByMouse: true; onTextEdited: root.destination = text }
     }
     SoundUi.Button { soundBus: root.soundBus; fontFamily: Style.font.menuFamily; fontSize: Style.font.heading + 1; iconText: "󰉋"; text: "Browse"; focusable: true; enabled: !root.busy; onClicked: root.browseFolder(false) }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.menu.border }
    RowLayout {
     Layout.fillWidth: true
     Text { text: "Included"; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading; Layout.fillWidth: true }
     SoundUi.Button { soundBus: root.soundBus; iconText: root.allSelected ? "󰄲" : "󰄱"; text: root.allSelected ? "Deselect All" : "Select All"; fontFamily: Style.font.menuFamily; fontSize: Style.font.heading; iconSize: 24; tooltipText: root.allSelected ? "Deselect all" : "Select all"; focusable: true; enabled: !root.busy; onClicked: root.toggleAll() }
    }
    GridLayout {
     columns: 2
     columnSpacing: 20
     rowSpacing: 4
     Layout.fillWidth: true
     Repeater {
      model: root.sections
      delegate: Rectangle {
       required property var modelData
       required property int index
       Layout.fillWidth: true
       implicitHeight: 42
       activeFocusOnTab: !root.busy
       Keys.onSpacePressed: { if (!root.busy) { root.toggleSection(index); root.soundBus.interaction("click") } }
       opacity: root.busy ? 0.45 : 1
       color: hover.containsMouse ? Color.menu.border : "transparent"
       radius: 6
       MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; enabled: !root.busy; onClicked: { root.toggleSection(index); root.soundBus.interaction("click") } }
       Item {
        anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
        FontMetrics { id: labelMetrics; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading }
        FontMetrics { id: checkMetrics; font.family: Style.font.family; font.pixelSize: 24 }
        Text {
         id: checkLabel
         text: modelData.selected ? "󰄲" : "󰄱"
         color: Color.menu.text; font: checkMetrics.font
         width: 24; horizontalAlignment: Text.AlignHCenter
         y: Math.round((parent.height - checkMetrics.tightBoundingRect(text).height) / 2 - baselineOffset - checkMetrics.tightBoundingRect(text).y)
        }
        Text {
         text: modelData.label; color: Color.menu.text; font: labelMetrics.font
         x: 34; width: parent.width - x; elide: Text.ElideRight
         y: Math.round((parent.height - labelMetrics.tightBoundingRect(text).height) / 2 - baselineOffset - labelMetrics.tightBoundingRect(text).y)
        }
       }
      }
     }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.menu.border }
    RowLayout {
     Layout.fillWidth: true
     Rectangle {
      Layout.fillWidth: true; implicitHeight: root.logText ? 90 : 64; color: "transparent"
      Flickable {
       id: logScroll
       anchors { fill: parent; margins: 8 }
       clip: true; contentWidth: width; contentHeight: logLabel.implicitHeight
       TextEdit { id: logLabel; width: logScroll.width; text: root.logText || "Optional private keys, credentials and profiles are unencrypted. Use a trusted backup drive. Close browsers before backing up profiles."; readOnly: true; selectByMouse: true; color: Color.menu.text; font.family: Style.font.family; font.pixelSize: Style.font.body + 2; wrapMode: TextEdit.WrapAnywhere; onTextChanged: Qt.callLater(function() { logScroll.contentY = Math.max(0,logScroll.contentHeight - logScroll.height) }) }
      }
     }
     SoundUi.Button { soundBus: root.soundBus; iconText: "󰆏"; iconSize: 22; tooltipText: "Copy log"; visible: !!root.logText; enabled: !!root.logText; onClicked: root.copyLog() }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.menu.border }
    RowLayout {
     id: footerActions
     Layout.fillWidth: true
     spacing: 12
     Item {
      Layout.fillWidth: true
      Layout.preferredWidth: (footerActions.width - footerActions.spacing) / 2
      implicitWidth: backupAction.implicitWidth
      implicitHeight: backupAction.implicitHeight
      Gradient {
       id: destructiveProgress
       orientation: Gradient.Horizontal
       GradientStop { position: 0; color: "#925258" }
       GradientStop { position: root.progress; color: "#925258" }
       GradientStop { position: Math.min(1,root.progress + 0.0001); color: "transparent" }
       GradientStop { position: 1; color: "transparent" }
      }
      SoundUi.Button { id: backupAction; opacity: enabled ? 1 : 0.45; gradient: root.busy && root.canCancel && !root.restoring ? destructiveProgress : null; anchors.fill: parent; soundBus: root.soundBus; fontFamily: Style.font.menuFamily; fontSize: Style.font.heading + 1; iconText: root.busy && root.canCancel && !root.restoring ? "󰅖" : "󰁯"; text: root.cancelRequested && !root.restoring ? "Cancelling…" : (root.busy ? (!root.restoring && root.canCancel ? "Cancel · " + Math.round(root.progress*100) + "%" : "Create Backup") : ("Create Backup")); foreground: Color.menu.text; bordered: true; focusable: true; enabled: root.busy ? (!root.restoring && root.canCancel && !root.cancelRequested) : root.hasSelection; onClicked: { if (root.busy) root.cancelBackup(); else root.start() } }
     }
     SoundUi.Button {
      Layout.fillWidth: true
      Layout.preferredWidth: (footerActions.width - footerActions.spacing) / 2
      opacity: enabled ? 1 : 0.45
      gradient: root.restoring ? destructiveProgress : null
      soundBus: root.soundBus; fontFamily: Style.font.menuFamily; fontSize: Style.font.heading + 1
      iconText: root.restoring ? "󰅖" : "󰉋"
      text: root.restoring ? (root.cancelRequested ? "Cancelling…" : "Cancel Restore · " + Math.round(root.progress*100) + "%") : "Open Backup"
      foreground: Color.menu.text; bordered: true; focusable: true
      enabled: root.restoring ? !root.cancelRequested : !root.busy
      onClicked: { if (root.restoring) root.cancelBackup(); else root.browseFolder(true) }
     }
    }
   }
  }
  Rectangle {
   visible: root.previewOpen
   width: Math.min(820, parent.width - 60)
   height: previewContent.implicitHeight + 44
   anchors.centerIn: parent
   color: Color.menu.background; border.color: Color.menu.border; radius: Style.cornerRadius
   MouseArea { anchors.fill: parent }
   ColumnLayout {
    id: previewContent
    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 22 }
    spacing: 12
    Text { text: root.phase === "restored" ? "Restore Complete" : (root.restoring ? "Restoring Backup" : "Restore Preview"); color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.display }
    Text { text: root.phase === "restored" ? "Restore finished. Review the log before refreshing." : "✓ Checksums verified"; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading }
    Text { text: root.selectedBackup; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
    Text { text: "Created: " + (root.previewData.created || "") + "  ·  User: " + (root.previewData.user || ""); color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.menu.border }
    RowLayout {
     visible: root.phase === "restore-ready"
     Layout.fillWidth: true
     Text { visible: root.phase === "restore-ready"; text: "Restore sections"; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading; Layout.fillWidth: true }
     SoundUi.Button { soundBus: root.soundBus; iconText: root.restoreAllSelected ? "󰄲" : "󰄱"; text: root.restoreAllSelected ? "Deselect All" : "Select All"; enabled: !root.busy; fontFamily: Style.font.menuFamily; fontSize: Style.font.heading; iconSize: 24; onClicked: root.toggleRestoreAll() }
    }
    GridLayout {
     columns: 2; columnSpacing: 20; rowSpacing: 4; Layout.fillWidth: true
     Repeater {
      model: root.phase === "restore-ready" ? root.restoreSections : []
      delegate: Rectangle {
       required property var modelData
       required property int index
       Layout.fillWidth: true; implicitHeight: 42
       color: restoreHover.containsMouse ? Color.menu.border : "transparent"; radius: 6
       activeFocusOnTab: true
       Keys.onSpacePressed: root.toggleRestore(index)
       MouseArea { id: restoreHover; anchors.fill: parent; hoverEnabled: true; enabled: !root.busy; onClicked: root.toggleRestore(index) }
       Item {
        anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
        FontMetrics { id: restoreLabelMetrics; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading }
        FontMetrics { id: restoreCheckMetrics; font.family: Style.font.family; font.pixelSize: 24 }
        Text {
         text: modelData.selected ? "󰄲" : "󰄱"; color: Color.menu.text; font: restoreCheckMetrics.font; width: 24; horizontalAlignment: Text.AlignHCenter
         y: Math.round((parent.height - restoreCheckMetrics.tightBoundingRect(text).height) / 2 - baselineOffset - restoreCheckMetrics.tightBoundingRect(text).y)
        }
        Text {
         text: { var entry = root.sections.find(function(s) { return s.id === modelData.id }); return entry ? entry.label : modelData.id }
         x: 34; width: parent.width - x; elide: Text.ElideRight; color: Color.menu.text; font: restoreLabelMetrics.font
         y: Math.round((parent.height - restoreLabelMetrics.tightBoundingRect(text).height) / 2 - baselineOffset - restoreLabelMetrics.tightBoundingRect(text).y)
        }
       }
      }
     }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.menu.border }
    RowLayout {
     visible: root.phase !== "restore-ready"; Layout.fillWidth: true
     Flickable {
      id: restoreLogScroll; Layout.fillWidth: true; Layout.preferredHeight: 220; clip: true
      contentWidth: width; contentHeight: restoreLogLabel.implicitHeight
      TextEdit { id: restoreLogLabel; width: restoreLogScroll.width; text: root.logText; readOnly: true; selectByMouse: true; color: Color.menu.text; font.family: Style.font.family; font.pixelSize: Style.font.body + 2; wrapMode: TextEdit.WrapAnywhere; onTextChanged: Qt.callLater(function() { restoreLogScroll.contentY = Math.max(0,restoreLogScroll.contentHeight-restoreLogScroll.height) }) }
     }
     SoundUi.Button { soundBus: root.soundBus; iconText: "󰆏"; tooltipText: "Copy log"; onClicked: root.copyLog() }
    }
    Text { text: "Existing files are saved before replacement. Package installation is available from restore.sh. System mount files remain reference-only."; color: Color.menu.text; font.family: Style.font.family; font.pixelSize: Style.font.body + 2; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.menu.border }
    RowLayout {
     Layout.fillWidth: true; spacing: 12
     SoundUi.Button { Layout.fillWidth: true; Layout.preferredWidth: 1; bordered: true; soundBus: root.soundBus; fontFamily: Style.font.menuFamily; fontSize: Style.font.heading + 1; iconText: "󰁯"; text: root.phase === "restored" ? (root.refreshRequested ? "Refreshing…" : "Refresh System") : (root.restoring ? (root.cancelRequested ? "Cancelling…" : "Cancel Restore · " + Math.round(root.progress*100) + "%") : "Confirm Restore"); gradient: root.restoring ? destructiveProgress : null; enabled: !root.refreshRequested && (root.restoring ? !root.cancelRequested : (root.phase === "restored" || (!root.busy && root.restoreHasSelection && root.phase === "restore-ready"))); focusable: true; onClicked: { if (root.restoring) root.cancelBackup(); else if (root.phase === "restored") root.refreshSystem(); else { root.restoreConfirmed = true; root.restoreBackup() } } }
     SoundUi.Button { Layout.fillWidth: true; Layout.preferredWidth: 1; bordered: true; soundBus: root.soundBus; fontFamily: Style.font.menuFamily; fontSize: Style.font.heading + 1; iconText: "󰅖"; text: root.phase === "restore-ready" ? "Cancel" : "Close"; focusable: true; enabled: !root.busy; onClicked: root.previewOpen = false }
    }
   }
  }

  Rectangle {
   visible: root.pickerOpen
   width: Math.min(820, parent.width - 60)
   height: folderContent.implicitHeight + 44
   anchors.centerIn: parent
   color: Color.menu.background; border.color: Color.menu.border; radius: Style.cornerRadius
   MouseArea { anchors.fill: parent }
   ColumnLayout {
    id: folderContent
    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 22 }
    spacing: 12
    Text { text: root.pickerRestore ? "Open Backup" : "Save Backup To"; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.display }
    RowLayout {
     Layout.fillWidth: true
     SoundUi.Button { soundBus: root.soundBus; iconText: "󰁝"; tooltipText: "Parent folder"; enabled: !root.busy; onClicked: { var path = root.pickerPath.replace(/\/$/, ""); root.pickerPath = path.substring(0,path.lastIndexOf("/")) || "/" } }
     SoundUi.Button { soundBus: root.soundBus; iconText: "󰋜"; tooltipText: "Home"; enabled: !root.busy; onClicked: root.pickerPath = Quickshell.env("HOME") }
     SoundUi.Button { soundBus: root.soundBus; iconText: "󰋊"; tooltipText: "Mounted drives"; enabled: !root.busy; onClicked: root.pickerPath = "/run/media/" + Quickshell.env("USER") }
     Rectangle { Layout.fillWidth: true; implicitHeight: 40; color: "transparent"; border.color: Color.menu.border; radius: 6
      TextInput { anchors { fill: parent; margins: 10 } text: root.pickerPath; enabled: !root.busy; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.heading; selectByMouse: true; clip: true; onAccepted: { if (text.charAt(0) === "/") root.pickerPath = text } }
     }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.menu.border }
    ListView {
     id: folderList
     Layout.fillWidth: true
     Layout.preferredHeight: 320
     model: folders
     clip: true
     reuseItems: true
     delegate: SoundUi.Button {
      required property string fileName
      width: folderList.width
      soundBus: root.soundBus; text: fileName; enabled: !root.busy; iconText: "󰉋"; leftAlign: true
      fontFamily: Style.font.menuFamily; fontSize: Style.font.heading + 1
      focusable: true
      onClicked: root.pickerPath = root.pickerPath.replace(/\/$/, "") + "/" + fileName
     }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Color.menu.border }
    Text { visible: folders.count === 0; text: "No subfolders. Select this folder or enter a path above."; color: Color.menu.text; font.family: Style.font.menuFamily; font.pixelSize: Style.font.body }
    RowLayout {
     Layout.fillWidth: true; spacing: 12
     SoundUi.Button { Layout.fillWidth: true; Layout.preferredWidth: 1; bordered: true; soundBus: root.soundBus; text: "Select This Folder"; enabled: !root.busy; iconText: "󰄬"; fontFamily: Style.font.menuFamily; fontSize: Style.font.heading + 1; onClicked: { root.pickerOpen = false; if (root.pickerRestore) root.checkBackup(root.pickerPath); else root.destination = root.pickerPath } }
     SoundUi.Button { Layout.fillWidth: true; Layout.preferredWidth: 1; bordered: true; soundBus: root.soundBus; text: "Cancel"; iconText: "󰅖"; fontFamily: Style.font.menuFamily; fontSize: Style.font.heading + 1; enabled: !root.busy; onClicked: root.pickerOpen = false }
    }
   }
  }

 }
}
