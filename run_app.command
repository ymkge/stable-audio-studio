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
fi

source "$VENV_DIR/bin/activate"

# Verify essential dependencies are ready
python3 -c "import torch, gradio, stable_audio_3" &>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 必要なライブラリのセットアップを確認しています..."
    pip install --upgrade pip
    pip install torch torchaudio gradio soundfile huggingface-hub
    pip install "git+https://github.com/Stability-AI/stable-audio-3.git"
    pip uninstall -y torchvision 2>/dev/null || true
fi

echo "🚀 アプリケーションを起動しています..."
python3 app.py
APP_EXIT_CODE=$?

# ==============================================================================
# Cleanup & auto-close Terminal window on exit
# ==============================================================================
if [ $APP_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "🛑 アプリケーションが正常終了しました。このウィンドウを閉じます..."
    osascript -e 'delay 1' -e 'tell application "Terminal" to close (first window whose name contains "run_app.command")' &>/dev/null &
    exit 0
else
    echo ""
    echo "⚠️ エラーが発生したため停止しました（終了コード: $APP_EXIT_CODE）。"
    read -p "Enterキーを押すとこのウィンドウを閉じます..."
    exit $APP_EXIT_CODE
fi
