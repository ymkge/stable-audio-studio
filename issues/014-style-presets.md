# Issue #014: [機能追加] ワンクリックでジャンル別設定を反映できるスタイルプリセット機能

## 1. 目的・概要
英語プロンプトを毎回ゼロから考える負担を軽減するため、UI上にワンクリックでジャンル（Lo-Fi, Ambient, Synthwave, Cinematic, Acoustic, Jazz）に応じた推奨プロンプト・ネガティブプロンプト・BPM・秒数を自動反映できるスタイルプリセットボタン群を実装する。

## 2. タスクリスト
- [x] 開発用ブランチ `feature/14-style-presets` の作成
- [x] `core/presets.py` の新規作成
  - `StylePreset` データクラスの定義
  - 6種類の厳選ジャンルプリセット定義（Lo-Fi, Ambient, Synthwave, Cinematic, Acoustic Folk, Lounge Jazz）
- [x] `ui/gradio_app.py` の更新
  - プロンプト入力欄上部にプリセットボタングループを配置
  - 各ボタン押下時に `prompt`, `negative_prompt`, `bpm`, `duration`, `status_text` を一括更新するイベント配線
  - スタイルプリセット用CSSスタイリング
- [x] 単体テスト・検証
- [x] ドキュメント（`README.md`, `issues/`）の更新
- [x] リモートへプッシュ & プルリクエスト作成

## 3. 実装ウォークスルー・動作確認結果
- `python3 -m py_compile ui/gradio_app.py core/presets.py` にて構文整合性を検証。
- 単体テストスクリプトにて、全6種のプリセットが正常にロードされ、BPM・秒数がアプリの許容範囲内に収まっていることを検証済み。
- プリセットクリック時、ユーザーがゼロから入力することなくプロンプト・ネガティブプロンプト・BPM・秒数が即時反映され、その後ユーザーが自由に編集可能なUIフローを確立。

## 4. 完了条件 (Definition of Done)
- [x] プリセットボタンをクリックすると、対応する設定値が入力欄に即時反映されること。
- [x] 疎結合アーキテクチャ（`core/` に定義、`ui/` で利用）が維持されていること。
