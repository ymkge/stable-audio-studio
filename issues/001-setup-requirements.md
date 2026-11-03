# Issue #001: [Phase 1] 依存ライブラリの定義と環境要件整理

## 1. 目的・概要
Apple Silicon (MPS) 環境で動作する `stable-audio-tools` および Gradio Web UI に必要な依存パッケージを `requirements.txt` に定義する。

## 2. タスクリスト
- [x] `requirements.txt` の作成
  - `torch`, `torchaudio`
  - `stable-audio-tools`
  - `gradio`
  - `soundfile`
  - `huggingface-hub`
- [x] Apple Silicon / macOS に特有のバージョン競合や注意点の洗い出し

## 3. 発生した課題・留意点
- macOS (Apple Silicon / MPS) では `torch>=2.1.0` を推奨。MPS上での特定操作のフォールバックのため、実行時に `PYTORCH_ENABLE_MPS_FALLBACK=1` を指定することが不可欠。
- `stable-audio-tools` は Hugging Face リポジトリ（`stabilityai/stable-audio-open-1.0`）から重み・設定を取得するため `huggingface-hub` の認証が必須。

## 4. 完了条件 (Definition of Done)
- [x] `requirements.txt` が生成され、必要なライブラリが過不足なく指定されていること。
