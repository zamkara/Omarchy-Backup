# Backup & Restore

A native Omarchy Quattro overlay for selective user backups and restores. Choose sections, inspect a verified backup, restore selected sections, and review the live log before refreshing the desktop.

## Install

Requires Omarchy Quattro, Python 3.12 or newer, Bash, and `wl-copy` for copying logs. The plugin uses Omarchy's existing Quickshell, theme, fonts and controls. No pip packages, root access, custom sound plugin, Foot, or private scripts are needed. This requires the Quattro shell with the official `qs.Ui` and `qs.Commons` APIs; older Omarchy releases without the plugin system are not supported.

```sh
omarchy plugin add https://github.com/zamkara/Omarchy-Backup.git --enable
```

The enabled plugin automatically adds **Setup → Backup & Restore**. No installer script, manual configuration or extra command is required. This preserves existing menu entries and backs up the menu before its first change. Repeated loads leave it unchanged.

To open from a terminal:

```sh
omarchy-shell shell summon zam.backup
```

## Use

- Browse to the destination, choose sections and create a backup.
- Each backup is saved directly under the chosen destination as `omarchy-backup-YYYY-MM-DD_HH-MM-SS`.
- Open Backup verifies SHA-256 checksums before showing selectable restore sections.
- During backup or restore, other actions are disabled; Cancel rolls back a restore or removes an incomplete backup.
- Restore stays on its own page with live output. Once finished, its action becomes **Refresh System**.
- Active desktop configuration is staged until Refresh System is clicked. This applies pending files in a detached worker, reloads Hyprland configuration, then restarts the Omarchy shell. It does not reboot the computer or restart the compositor. The dialog closes during this explicit shell restart.
- Copy Log copies the full diagnostic log, including errors. Logs live in `~/.local/state/omarchy/backup/logs/`.

## Portable restoration

Each completed backup contains exactly one supporting executable script: `restore.sh`. It embeds the restore engine and optional package installer; there is no separate Python or installation script in the backup folder.

```sh
cd /path/to/omarchy-backup-YYYY-MM-DD_HH-MM-SS
bash restore.sh
```

Choose restore, package installation or verification interactively. Restoring lets you choose sections. Existing files are saved under `~/omarchy-restore-backups/`.

```sh
bash restore.sh --check
bash restore.sh --restore --sections desktop,terminals
bash restore.sh --extract /path/to/empty-folder --sections git
bash restore.sh --install-packages
```

Desktop changes restored into an active home are staged under `~/.local/state/omarchy/restore-pending/`. To apply from a terminal, use the pending path printed in the restore log:

```sh
bash restore.sh --backup /path/to/pending-backup --restore --apply-desktop
```

Optional package installation asks separately before invoking `sudo pacman` or an existing `yay`/`paru`. Foreign-package inventories may contain packages unavailable in AUR. Flatpak inventory is retained for manual installation. No package installation occurs from the GUI restore action.

## Backup scope and safety

The selectable sections include desktop, terminals, editors, fonts/themes, local tools, user services, preferences, package inventories, Git, SSH configuration and keys, credential stores, browser profiles, VPN/sync settings, documents, projects and media. Secrets and personal-file sections are off by default. **Select All includes these optional sections. Backups are unencrypted.** Close applications before backing up their profiles.

This is a user-data backup, not a disk image. System mount configuration is reference-only and is never installed. Services are not automatically enabled. Clipboard history, migration markers, `node_modules`, Python bytecode and known backup artifacts are excluded. Symlinks are stored without following external targets. Project Git history is included.

Removal hides the Setup entry automatically and never deletes backups, logs, restored files or rollback copies:

```sh
omarchy plugin remove zam.backup
```

## Compatibility checks

Backend tests include an otherwise empty home and a restricted command path containing only Python, Bash and coreutils. Missing Flatpak, AUR helpers, personal tools and optional session-refresh commands do not prevent file backup or restore. The native UI is tested on the installed Quattro shell; a fresh-OS VM has not been tested yet. Restoring application settings does not install the corresponding applications automatically.

## Development

```sh
omarchy plugin validate .
python3 -m unittest discover -s tests -v
```

Publishing checklist and submission instructions: https://plugins.omarchy.org/publish.html

License: Almatera Incubator License, see LICENSE. This plugin uses Omarchy's installed UI components rather than copying their source.
