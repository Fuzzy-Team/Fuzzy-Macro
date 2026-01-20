#!/bin/zsh
set -euo pipefail

# repair_macro.command
# Downloads the latest main.zip from the repository, extracts it, and
# replaces project files while excluding the `settings/` directory and
# this script itself. Overwritten files are moved to a timestamped
# backup folder `backups/repair-YYYYMMDD-HHMMSS`.

REPO_ZIP_URL="https://github.com/Fuzzy-Team/Fuzzy-Macro/archive/refs/heads/main.zip"

usage() {
  cat <<EOF
Usage: repair_macro.command [-y]
  -y    auto-confirm (no prompt)
This will download and replace project files from the repository,
excluding the 'settings/' directory and 'repair_macro.command'.
Overwritten files are backed up under 'backups/'.
EOF
}

AUTO_CONFIRM=0
while getopts ":y" opt; do
  case $opt in
    y) AUTO_CONFIRM=1 ;;
    *) usage; exit 1 ;;
  esac
done

TMPDIR=$(mktemp -d)
ZIP="$TMPDIR/main.zip"

echo "Downloading repository archive..."
curl -L --fail --progress-bar "$REPO_ZIP_URL" -o "$ZIP"

echo "Extracting..."
unzip -q "$ZIP" -d "$TMPDIR"

# find extracted top-level dir (Fuzzy-Macro-*)
# Use shell globbing for macOS compatibility instead of GNU find flags
TOPDIR=""
for d in "$TMPDIR"/Fuzzy-Macro-*; do
  if [ -d "$d" ]; then
    TOPDIR="$d"
    break
  fi
done
if [ -z "${TOPDIR:-}" ]; then
  echo "Failed to find extracted archive directory." >&2
  rm -rf "$TMPDIR"
  exit 1
fi

BACKUPDIR="backups/repair-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUPDIR"

EXCLUDES=(--exclude 'settings' --exclude 'repair_macro.command' --exclude '.git')

echo "Scanning changes (dry-run)..."
rsync -avn "${EXCLUDES[@]}" --delete "$TOPDIR/" ./ || true

if [ "$AUTO_CONFIRM" -eq 0 ]; then
  echo
  printf "%s" "Proceed to replace files listed above? (y/N) "
  read -r RESP
  case "$RESP" in
    [yY]|[yY][eE][sS]) true ;;
    *) echo "Aborted by user."; rm -rf "$TMPDIR"; exit 0 ;;
  esac
fi

echo "Applying updates and creating backups in $BACKUPDIR..."
rsync -av --delete "${EXCLUDES[@]}" --backup --backup-dir="$BACKUPDIR" "$TOPDIR/" ./

echo "Repair complete. Backups (if any) are in: $BACKUPDIR"
rm -rf "$TMPDIR"

exit 0
