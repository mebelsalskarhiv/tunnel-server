#!/bin/bash

# TunnelFlow Client Launcher for Linux/macOS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"

echo "===================================="
echo "   TunnelFlow - Secure Tunneling"
echo "===================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    echo "Please install Python 3 first"
    exit 1
fi

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[ERROR] config.json not found!"
    echo "Please configure your tunnel settings first."
    exit 1
fi

show_menu() {
    echo ""
    echo "Select mode:"
    echo "  1. Run once (no auto-reconnect)"
    echo "  2. Run with auto-reconnect (recommended)"
    echo "  3. Configure settings"
    echo "  4. Exit"
    echo ""
    read -p "Enter choice (1-4): " choice
}

run_once() {
    echo ""
    echo "Starting TunnelFlow in single-connect mode..."
    python3 "$SCRIPT_DIR/client.py" --once
}

run_auto() {
    echo ""
    echo "Starting TunnelFlow with auto-reconnect..."
    echo "Press Ctrl+C to stop"
    echo ""
    python3 "$SCRIPT_DIR/client.py"
}

configure() {
    echo ""
    echo "Current configuration:"
    if [ -f "$CONFIG_FILE" ]; then
        cat "$CONFIG_FILE"
    fi
    echo ""
    echo "Edit config.json to change settings."
    read -p "Press Enter to continue..."
}

# Main loop
while true; do
    show_menu
    
    case $choice in
        1)
            run_once
            ;;
        2)
            run_auto
            ;;
        3)
            configure
            ;;
        4)
            exit 0
            ;;
        *)
            echo "Invalid choice, please try again."
            ;;
    esac
done
