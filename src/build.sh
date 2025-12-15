#!/usr/bin/env bash
set -euo pipefail

# =================================
# Configuration
# =================================
MODE="${MODE:-remote}"
AUTO_SAVE_STATE="${AUTO_SAVE_STATE:-false}"

# =================================
# Path Setup
# =================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
UTILS_DIR="$PROJECT_ROOT/utils"

# =================================
# Configuration via ENV vars
# =================================
VALKEY_VERSION="${VALKEY_VERSION:-8.1.0}"
VALKEY_DOWNLOAD_URL="${VALKEY_DOWNLOAD_URL:-https://github.com/valkey-io/valkey/archive/refs/tags/8.1.0.tar.gz}"
VALKEY_DOWNLOAD_SHA="${VALKEY_DOWNLOAD_SHA:-559274e81049326251fa5b1e1c64d46d3d4d605a691481e0819133ca1f1db44f}"

# =================================
# Output Paths
# =================================
OUT_DIR="$PROJECT_ROOT/$VALKEY_VERSION/fs"
OUT_ROOTFS_TAR="$OUT_DIR/alpine-rootfs.tar"
OUT_ROOTFS_FLAT="$OUT_DIR/alpine-rootfs-flat"
OUT_FSJSON="$OUT_DIR/alpine-fs.json"
STATES_DIR="$PROJECT_ROOT/$VALKEY_VERSION/states"
TEMPLATE_PATH="$UTILS_DIR/image_creator.template.html"
OUTPUT_HTML="$PROJECT_ROOT/$VALKEY_VERSION/image_creator.html"

CONTAINER_NAME="alpine-v86-$VALKEY_VERSION"
IMAGE_NAME="i386/alpine-v86-$VALKEY_VERSION"

# =================================
# Prepare Directories
# =================================
if [[ "$MODE" == "local" ]]; then
mkdir -p "$OUT_DIR"
fi 
mkdir -p "$STATES_DIR"

# =================================
# Docker Build & Export
# =================================
if [[ "$MODE" == "local" ]]; then
    echo "==> MODE=local: building Docker image and filesystem..."

    echo "==> Building Docker image..."
    docker build "$SCRIPT_DIR" --platform linux/386 --rm --tag "$IMAGE_NAME" \
        --build-arg VALKEY_VERSION="${VALKEY_VERSION}" \
        --build-arg VALKEY_DOWNLOAD_URL="${VALKEY_DOWNLOAD_URL}" \
        --build-arg VALKEY_DOWNLOAD_SHA="${VALKEY_DOWNLOAD_SHA}"

    echo "==> Creating and exporting container filesystem..."
    docker rm "$CONTAINER_NAME" || true
    docker create --platform linux/386 -t -i --name "$CONTAINER_NAME" "$IMAGE_NAME"
    docker export "$CONTAINER_NAME" -o "$OUT_ROOTFS_TAR"

    # Optional: remove .dockerenv if present
    tar --delete -f "$OUT_ROOTFS_TAR" ".dockerenv" || true

    # =================================
    # Convert TAR to v86 formats
    # =================================
    echo "==> Generating alpine-fs.json..."
    "$SCRIPT_DIR/fs2json.py" --out "$OUT_FSJSON" "$OUT_ROOTFS_TAR"

    echo "==> Flattening to alpine-rootfs-flat..."
    mkdir -p "$OUT_ROOTFS_FLAT"
    "$SCRIPT_DIR/copy-to-sha256.py" "$OUT_ROOTFS_TAR" "$OUT_ROOTFS_FLAT"

    # Remove tar file after use
    rm "$OUT_ROOTFS_TAR"
    echo " - Removed $OUT_ROOTFS_TAR"

    echo "✅ Filesystem build complete: $OUT_FSJSON and $OUT_ROOTFS_FLAT"
else
    echo "==> MODE=remote: skipping build, using CDN paths only"
fi

# =================================
# Generate versioned HTML
# =================================
if [[ -f "$TEMPLATE_PATH" ]]; then
    echo "==> Generating image_creator.html for MODE=$MODE..."

    if [[ "$MODE" == "local" ]]; then
        BASEURL="./fs/alpine-rootfs-flat"
        BASEFS="./fs/alpine-fs.json"
    elif [[ "$MODE" == "remote" ]]; then
        BASEURL="https://download.valkey.io/try-me-valkey/$VALKEY_VERSION/fs/alpine-rootfs-flat"
        BASEFS="https://download.valkey.io/try-me-valkey/$VALKEY_VERSION/fs/alpine-fs.json"
    else
        echo "❌ Invalid MODE: $MODE"
        exit 1
    fi

    sed -e "s|{{BASEURL}}|$BASEURL|g" \
        -e "s|{{BASEFS}}|$BASEFS|g" \
        "$TEMPLATE_PATH" > "$OUTPUT_HTML"

    echo " - Created $OUTPUT_HTML"
else
    echo "⚠️  Template $TEMPLATE_PATH not found, skipping HTML generation."
fi

# =================================
# Automated State Save
# =================================
if [[ "$AUTO_SAVE_STATE" == "true" ]]; then
    echo ""
    echo "==> Running automated state save..."
    
    AUTOMATE_SCRIPT="$SCRIPT_DIR/automate_save_state.py"
    
    if [[ ! -f "$AUTOMATE_SCRIPT" ]]; then
        echo "❌ Automation script not found: $AUTOMATE_SCRIPT"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
    python3 "$AUTOMATE_SCRIPT" "$VALKEY_VERSION"
    
    echo "✅ Automated state save complete!"
fi

echo ""
echo "========================================="
echo "✅ Build Complete!"
echo "========================================="