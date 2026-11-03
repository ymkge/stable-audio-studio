# Issue #010: [改善] 初期利用可能なモデルを「Stable Audio 3 Medium」に変更する

## 1. 目的・概要
初期設定モデルを `stabilityai/stable-audio-open-1.0` から、最新の `stabilityai/stable-audio-3-medium` に変更し、UIからもモデルを選択・確認できるようにする。

## 2. タスクリスト
- [x] 開発用ブランチ `feature/10-stable-audio-3-medium` の作成
- [x] `core/config.py` の更新
  - デフォルト `model_id` を `stabilityai/stable-audio-3-medium` に変更
  - `available_models` リストを追加（3-medium と open-1.0）
- [x] `core/generator.py` の更新
  - モデル動的ロード（`load_model(model_id)`）に対応
  - Hugging Face認証エラー時のリンク先を対象モデルURLに動的追従
- [x] `ui/gradio_app.py` の更新
  - ヘッダー表示を「Powered by Stable Audio 3 Medium」に更新
  - 詳細設定内に「使用モデル (Model)」ドロップダウンを追加
- [x] `README.md` の更新
- [x] 動作確認・コンパイルチェック
- [x] ブランチをGitHubへプッシュし、プルリクエスト作成用リンクを発行

## 3. 実装ウォークスルー・動作確認結果
- `python3 -m py_compile ui/gradio_app.py core/config.py core/generator.py` にて構文整合性を検証。
- `core/config.py` のデフォルト値が `stabilityai/stable-audio-3-medium` となり、UI上でも選択肢として提供されていることを確認。

## 4. 完了条件 (Definition of Done)
- [x] アプリ起動時にデフォルトで `stabilityai/stable-audio-3-medium` がロード対象となること。
- [x] プルリクエストを作成して main に安全にマージ可能な状態にすること。
