#!/bin/bash

# ==============================================================================
# Stable Audio Studio - One-Click Launcher for macOS
# ==============================================================================

# Move to the project root directory where this script resides
cd "$(dirname "$0")" || exit 1

echo "========================================================"
echo " 🎵 Stable Audio Studio - Local Music Generation"
echo "========================================================"

# Enable PyTorch MPS fallback for Apple Silicon
export PYTORCH_ENABLE_MPS_FALLBACK=1

# Check for Python virtual environment
VENV_DIR=""
if [ -d "venv" ]; then
    VENV_DIR="venv"
elif [ -d ".venv" ]; then
    VENV_DIR=".venv"
fi

if [ -z "$VENV_DIR" ]; then
    echo "⚠️ 仮想環境が見つかりません。初回セットアップ（venv作成）を開始します..."
    python3 -m venv venv
    VENV_DIR="venv"
    source "$VENV_DIR/bin/activate"
    echo "📦 必要なライブラリをインストールしています（初回のみ数分かかります）..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source "$VENV_DIR/bin/activate"
fi

echo "🚀 アプリケーションを起動しています..."
python3 app.py

# ==============================================================================
# Cleanup & auto-close Terminal window on exit
# ==============================================================================
echo ""
echo "🛑 アプリケーションが停止しました。このウィンドウを閉じます..."

# Close the Terminal window automatically after 1 second
osascript -e 'delay 1' -e 'tell application "Terminal" to close (first window whose name contains "run_app.command")' &>/dev/null &
exit 0
