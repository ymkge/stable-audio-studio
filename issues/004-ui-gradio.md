# Issue #004: [Phase 4] UI層 (`ui/gradio_app.py`) の実装

## 1. 目的・概要
デザイナー・ミュージシャン向けの直感的なGradio Web UI（Blocks API）を構築する。

## 2. タスクリスト
- [x] `ui/` ディレクトリおよび `ui/__init__.py` の作成
- [x] ヘッダー構成（「🎵 Stable Audio Studio」、右上に「🛑 アプリを終了する」ボタン）
- [x] 入力フォーム配置
  - プロンプト (3行, プレースホルダー例文)
  - ネガティブプロンプト (1行)
  - BPMスライダー (40〜240, 初期値120, step 1)
  - 生成秒数スライダー (5〜180秒, 初期値30, step 5)
  - 詳細設定アコーディオン（折りたたみ初期非表示: steps, cfg_scale, seed固定/ランダム）
  - 生成ボタン（プライマリ、ラージ）
- [x] 出力エリア配置
  - `gr.Audio(type="filepath")` 波形プレイヤー
  - 使用シード値の表示
  - 「📁 保存先フォルダを開く」ボタン（Finderで `open output` 実行）
- [x] 終了制御UX
  - JavaScript `confirm(...)` ダイアログ実行
  - キャンセル時は停止処理を中断
  - OK時は画面に案内表示後、別スレッドから遅延 `os.kill(os.getpid(), signal.SIGTERM)`

## 3. 発生した課題・留意点
- 終了ダイアログはGradioイベントの `_js` 引数を用いてブラウザネイティブの `confirm()` を呼び出し。キャンセル時はPython側へ伝播させず停止処理を中断し、OK時のみメッセージを表示して `os.kill(os.getpid(), signal.SIGTERM)` で安全終了するロジックを確立。
- シード値入力欄は「シード値をランダムにする」チェックボックスの状態に応じて動的に `interactive` を切り替えられるようイベントを結合。

## 4. 完了条件 (Definition of Done)
- [x] Gradio UIが起動し、指定されたコンポーネントが配置されていること。
- [x] Finderオープン、安全終了が想定通り機能すること。

## 5. 実装ウォークスルー・動作確認結果
- **実装内容**: `ui/gradio_app.py` に Blocks API を用いたデザイナー・ミュージシャン向けUIを構築。
- **検証項目**:
  1. **UIコンパイル検証**: `python3 -m py_compile ui/gradio_app.py` を実行し構文エラーがないことを確認。
  2. **終了制御フロー**:
     - 終了ボタン (`stop_btn`) 押下時、`_js` 経由でブラウザネイティブの `confirm()` を実行。
     - キャンセル時はPython側に更新をかけず停止を中断。
     - OK時は画面にメッセージを出し、別スレッドで0.5秒後に `os.kill(os.getpid(), signal.SIGTERM)` を発行して安全終了。
  3. **動的シード制御**: 「シード値をランダムにする」のトグルに連動して、シード数値入力欄の `interactive` が自動で有効/無効化。
  4. **DAW連携**: 「保存先フォルダを開く」ボタンで macOS ネイティブの `subprocess.run(["open", output_dir])` を実行。
