# Publication notes

Repository: https://github.com/zamkara/Omarchy-Backup
Plugin ID: `zam.backup`
Category: System / Utilities
Suggested tags: backup, restore, system, productivity

## Maintainer notes

Backup & Restore is a native Omarchy Quattro overlay. It installs through `omarchy plugin add https://github.com/zamkara/Omarchy-Backup.git --enable` and uses the installed Omarchy UI and theme APIs. All backend scripts are included; no private plugins, external GUI, pip dependencies or custom user scripts are required.

Setup-menu integration is opt-in: the first-run dialog requests explicit consent, preserves unrelated entries and backs up the existing menu file. Installation does not run backup or restore. File restoration requires selecting a verified backup, choosing sections and clicking Confirm Restore. Desktop changes are staged until the user clicks Refresh System. The plugin never automatically installs system mount files or enables services. Optional package installation is only available in the portable restore script and asks separately before using sudo pacman or an existing AUR helper.

Backups contain a single self-contained restore.sh, including interactive section selection, checksum verification and optional package installation. Private keys, credentials and browser profiles are optional and unencrypted; the UI and README explain this. The repository contains no preview assets. License, dependencies, installation and removal are documented in README.md and LICENSE.

Requirements: Omarchy Quattro, Python 3.12+, Bash/coreutils and wl-copy for Copy Log. Backend safety and compatibility tests run in GitHub Actions, including an empty home, restricted command path, interactive restore, cancellation rollback, archive traversal and cross-archive symlinks. The native UI has been checked on an installed Quattro desktop. A clean Omarchy VM has not yet been tested.

I understand that marketplace approval is for listing and does not constitute a security review.

## Submitter confirmation

The repository uses the existing Almatera Incubator License. Before checking the ownership/permission item, the submitting owner must confirm that they have the necessary rights to the code and any preview assets they attach. Listing approval is separate from plugin security review.
