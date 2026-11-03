# Issue #006: [Phase 6] 起動スクリプト (`run_app.command`) の実装

## 1. 目的・概要
非エンジニア（デザイナー・ミュージシャン）がFinder上でダブルクリックするだけでアプリを起動・終了できるMac用シェルスクリプト `run_app.command` を作成する。

## 2. タスクリスト
- [x] `run_app.command` の作成
  - スクリプト自身のディレクトリへの安全な `cd`
  - Python venv環境の検出（存在しない場合は自動作成 / requirementsインストール案内）
  - 環境変数 `export PYTORCH_ENABLE_MPS_FALLBACK=1` の設定
  - `python3 app.py` の実行
  - アプリ終了後、ターミナルウィンドウを閉じるAppleScript実行
- [x] 実行権限 (`chmod +x run_app.command`) の付与

## 3. 発生した課題・留意点
- 仮想環境（`venv` または `.venv`）が存在しない場合、初回ダブルクリック時に自動で仮想環境の作成と `pip install -r requirements.txt` を実行するセーフティネットを組み込み。
- アプリ終了時にAppleScript（`osascript`）を用いて、起動スクリプトが動作していたターミナルウィンドウを1秒後に自動で閉じるUXを実装。

## 4. 完了条件 (Definition of Done)
- [x] 実行権限が付与され、ダブルクリックまたは `./run_app.command` で自動起動・終了できること。
