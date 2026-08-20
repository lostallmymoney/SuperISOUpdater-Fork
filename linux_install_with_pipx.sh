#!/bin/sh
set -eu

PKG_NAME="sisou2"
APP_NAME="sisou2"

cleanup_build_artifacts() {
    rm -rf build dist
    find . -maxdepth 1 -type d -name "*.egg-info" -exec rm -rf {} \;
}

echo "Ensuring pipx exists..."

if ! command -v pipx >/dev/null 2>&1; then
    echo "pipx not found. Installing..."

    if command -v apt >/dev/null 2>&1; then
        sudo apt update
        sudo apt install -y pipx
    else
        python3 -m pip install --user pipx --break-system-packages
    fi

    # IMPORTANT: ensure PATH for current script run
    export PATH="$HOME/.local/bin:$PATH"

    pipx ensurepath || true
fi

if [ ! -f "setup.py" ] && [ ! -f "pyproject.toml" ]; then
    echo "No setup.py or pyproject.toml found. Run from project root."
    exit 1
fi

echo "Cleaning previous pipx install (if any)..."
pipx uninstall "$PKG_NAME" >/dev/null 2>&1 || true

# DO NOT manually delete pipx internal folders (breaks state)
rm -f "$HOME/.local/bin/$APP_NAME" 2>/dev/null || true

echo "Cleaning build artifacts..."
cleanup_build_artifacts

echo "Installing project with pipx..."
pipx install --force . || {
    echo "pipx install failed"
    cleanup_build_artifacts
    exit 1
}

if [ -f "requirements.txt" ]; then
    echo "Injecting requirements..."
    pipx inject --force "$PKG_NAME" -r requirements.txt || {
        echo "pipx inject failed"
        cleanup_build_artifacts
        exit 1
    }
fi

cleanup_build_artifacts

echo "Done. Run with: $APP_NAME"
pipx ensurepath || true
