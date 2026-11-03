# Issue #002: [Phase 2] 設定モジュール (`core/config.py`) の実装

## 1. 目的・概要
モデル識別子、デフォルト生成パラメータ、オーディオ仕様（サンプリングレート等）、出力フォルダ設定などを一元管理する設定クラス/モジュールを定義する。

## 2. タスクリスト
- [x] `core/` ディレクトリおよび `core/__init__.py` の作成
- [x] `core/config.py` の実装
  - モデル名（デフォルト: `stabilityai/stable-audio-open-1.0`）
  - デフォルトパラメータ（サンプリングレート: 44100Hz、秒数: 30s、BPM: 120、steps: 100、cfg_scale: 7.0 等）
  - 出力ディレクトリパス（`output/`）の設定と自動生成処理
  - デバイス設定（MPS優先、CPUフォールバック）

## 3. 発生した課題・留意点
- `torch.backends.mps.is_available()` を用いてApple Silicon (MPS) が正常に認識されることを確認。
- 初期化時に `output/` フォルダが安全に自動生成されることを検証済み。

## 4. 完了条件 (Definition of Done)
- [x] 設定がクラスや定数として安全に取り出せること。
- [x] `output/` フォルダが存在しない場合に自動生成されること。

## 5. 実装ウォークスルー・動作確認結果
- **実装内容**: `core/config.py` に `AppConfig` クラスおよびシングルトン `config` を定義。
- **検証手順**:
  ```python
  from core.config import config
  print('Device:', config.device, 'Output Dir:', config.output_dir, 'Exists:', config.output_dir.exists())
  ```
- **実行結果**:
  - `Device: mps`（Apple Silicon MPSデバイスを自動検出）
  - `Output Dir: /.../output Exists: True`（`output/` ディレクトリの自動生成を確認）
