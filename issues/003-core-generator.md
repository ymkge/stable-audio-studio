# Issue #003: [Phase 3] 推論コア層 (`core/generator.py`) の実装

## 1. 目的・概要
UI層と完全に分離された推論・音声生成・ファイル保存エンジンを実装する。FastAPI等のバックエンドからもそのまま呼出可能な設計とする。

## 2. タスクリスト
- [x] シングルトン / クラスベースのモデルマネージャクラス設計（初回ロード保持、再利用）
- [x] デバイス検出（`torch.backends.mps.is_available()` によるMPS自動選択、CPUフォールバック）
- [x] パラメータ統合処理
  - `bpm` と `prompt` の結合フォーマット（例: `"{bpm} BPM, {prompt}"`）
  - `negative_prompt` の処理
  - シード値制御（指定値、またはランダムシード生成）
- [x] 音声生成パイプライン呼び出し（`stable-audio-tools` またはモデル固有API）
- [x] 出力ファイル名フォーマット & 保存処理
  - 命名規則: `YYYYMMDD_HHMMSS_{bpm}bpm_{duration}s_{prompt_summary}_s{seed}.wav`（記号のサニタイズ処理）
  - WAV形式書き出し（`soundfile`）
- [x] Hugging Face 認証エラー時の分かりやすいハンドリング

## 3. 発生した課題・留意点
- `soundfile` などの重いCライブラリ依存は呼び出し時に遅延ロードする設計とし、設定ロードや単体テスト時の不要なインポートエラーを回避。
- Hugging Faceの規約未同意やトークン未設定（401/403/Gated repoエラー）をキャッチし、ユーザーに対処手順を親切に伝えるカスタム例外 `ModelLoadError` を実装。
- 記号サニタイズ処理でファイル名として安全な30文字以内のスラグ（英数字・ハイフン・アンダースコア）を自動生成。

## 4. 完了条件 (Definition of Done)
- [x] `AudioGenerator` クラスが独立して単体テスト・実行できること。
- [x] 指定通りの命名規則で `output/` 配下にWAVファイルが保存され、生成ファイルパスとシード値が返却されること。

## 5. 実装ウォークスルー・動作確認結果
- **実装内容**: `core/generator.py` に `AudioGenerator` シングルトンクラスを実装。
- **検証手順**:
  ```python
  from core.generator import AudioGenerator
  gen = AudioGenerator()
  assert gen.sanitize_text('120 BPM Lo-Fi Hip Hop!! Relaxing...') == '120_bpm_lo-fi_hip_hop_relaxing'
  assert gen.build_full_prompt('Lo-Fi beat', 100) == '100 BPM, Lo-Fi beat'
  assert gen.build_full_prompt('120 BPM chill vibe', 90) == '120 BPM chill vibe'
  ```
- **実行結果**:
  - `All helper functions verified successfully!`
  - BPMプレフィックスの自動結合と二重付与防止が確認できました。
  - 特殊記号やスペースを含むプロンプトがファイル名として安全なスラグ（最大30文字）にサニタイズされることを確認しました。
  - Hugging Faceの認証エラー（Gated model / 401 / 403）を捕捉し、日本語の手順案内を表示するハンドラを実装しました。
