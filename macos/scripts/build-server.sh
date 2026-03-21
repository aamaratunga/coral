#!/usr/bin/env bash
#
# Build the Coral Python server into a standalone macOS binary using PyInstaller,
# then copy the output into the Xcode project's Resources directory.
#
# Usage:
#   ./macos/scripts/build-server.sh
#
# Prerequisites:
#   pip install pyinstaller
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MACOS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$MACOS_DIR/.." && pwd)"
XCODE_RESOURCES="$MACOS_DIR/CoralApp/CoralApp/Resources"

echo "==> Building Coral server with PyInstaller..."
echo "    Repo root: $REPO_ROOT"
echo "    Output:    $XCODE_RESOURCES/coral-server/"

# Ensure pyinstaller is available
if ! command -v pyinstaller &>/dev/null; then
    echo "Error: pyinstaller not found. Install it with:"
    echo "  pip install pyinstaller"
    exit 1
fi

# Run PyInstaller from repo root so paths resolve correctly
cd "$REPO_ROOT"
pyinstaller \
    --distpath "$MACOS_DIR/dist" \
    --workpath "$MACOS_DIR/build" \
    --noconfirm \
    "$MACOS_DIR/coral-server.spec"

# Copy the built bundle into the Xcode Resources directory
echo "==> Copying to Xcode resources..."
rm -rf "$XCODE_RESOURCES/coral-server"
mkdir -p "$XCODE_RESOURCES"
cp -R "$MACOS_DIR/dist/coral-server" "$XCODE_RESOURCES/coral-server"

echo "==> Done! Server binary is at: $XCODE_RESOURCES/coral-server/coral-server"
echo ""
echo "Next steps:"
echo "  1. In Xcode, right-click the CoralApp group → Add Files to \"CoralApp\""
echo "     → select the coral-server folder → ensure 'Create folder references' is selected"
echo "  2. Build and run the app (Cmd+R)"
