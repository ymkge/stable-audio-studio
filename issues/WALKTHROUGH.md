# 🎵 Stable Audio Studio - 実装・動作確認ウォークスルー (Walkthrough)

本ドキュメントは、Stable Audio Studioの全体アーキテクチャ、実装コンポーネント、およびエンドツーエンド（E2E）の動作確認手順をまとめたウォークスルーガイドです。

---

## 1. 全体アーキテクチャ & 疎結合設計

```text
[ ユーザー (デザイナー / ミュージシャン) ]
       │
       ▼ (ダブルクリック)
[ run_app.command ] ── (MPS_FALLBACK=1, venvアクティベート)
       │
       ▼ (起動)
[ app.py ] ── (inbrowser=True でブラウザ自動オープン)
       │
       ▼
┌───────────────────────────────────────────────┐
│ UI層 (ui/gradio_app.py)                       │
│  - プロンプト / BPM / 秒数 / 詳細設定入力     │
│  - 🛑 アプリ終了ボタン (JS confirm + SIGTERM) │
│  - 📁 Finderで開くボタン (open output)        │
└───────────────────────┬───────────────────────┘
                        │ (呼び出し: 完全疎結合)
┌───────────────────────▼───────────────────────┐
│ 推論コア層 (core/generator.py & config.py)    │
│  - デバイス自動判定: MPS (Apple Silicon) / CPU│
│  - シングルトン・モデルキャッシング           │
│  - BPM自動結合 & ファイル名サニタイズ         │
│  - WAV書き出し (output/*.wav)                 │
└───────────────────────────────────────────────┘
                        │
                        ▼ (将来移行)
           [ FastAPI / Next.js / Tauri ]
     ※ core/ は1行も変更せずそのまま利用可能
```

---

## 2. フェーズ別実装ウォークスルー

### Phase 1: 依存ライブラリ選定 (`requirements.txt`)
* **ポイント**: Apple Silicon (MPS) 環境での動作を前提に、`torch>=2.1.0` および `stable-audio-tools` を指定。
* **検証内容**: 依存関係のバージョン競合がないことを確認し、重いCライブラリは呼び出し時までインポートを遅延させる構成としました。

### Phase 2: 設定モジュール (`core/config.py`)
* **ポイント**: モデルID、デフォルトパラメータ（BPM: 120, 秒数: 30s, Steps: 100等）を一元管理。
* **動作検証結果**:
  ```python
  from core.config import config
  print('Device:', config.device, 'Output Dir:', config.output_dir, 'Exists:', config.output_dir.exists())
  # -> Device: mps Output Dir: /.../output Exists: True
  ```
  Apple Siliconの `mps` デバイスが正しく自動検出され、`output/` ディレクトリが自動作成されることを検証済み。

### Phase 3: 推論コア層 (`core/generator.py`)
* **ポイント**:
  1. **モデルシングルトン**: UI操作のたびに巨大なモデルを再ロードしないキャッシュ機構。
  2. **BPM自動結合**: プロンプト先頭に自動で `{bpm} BPM, ` を付与（既にBPMが含まれる場合は二重付与を防止）。
  3. **DAW用サニタイズファイル名**: `YYYYMMDD_HHMMSS_{bpm}bpm_{duration}s_{prompt_summary}_s{seed}.wav`
* **動作検証結果**:
  ```python
  gen = AudioGenerator()
  gen.sanitize_text('120 BPM Lo-Fi Hip Hop!! Relaxing...')
  # -> '120_bpm_lo-fi_hip_hop_relaxing' (記号除去・小文字化・30文字スラグ化)
  gen.build_full_prompt('Lo-Fi beat', 100)
  # -> '100 BPM, Lo-Fi beat'
  ```
  ユニットテストにて、サニタイズ処理とBPM結合処理が想定通り機能することを確認済み。

### Phase 4: UI層 (`ui/gradio_app.py`)
* **ポイント**:
  1. **安全な終了制御**:
     * 終了ボタン押下時にブラウザネイティブの `confirm("アプリを終了してよろしいですか？...")` が実行されます。
     * 「キャンセル」時は処理を中断。
     * 「OK」時のみ画面に「🛑 アプリを終了しました」と表示し、別スレッドから遅延して `os.kill(os.getpid(), signal.SIGTERM)` を発行してプロセスを安全終了。
  2. **Finder連携**: 「📁 保存先フォルダを開く」ボタンで macOS ネイティブの `open output` コマンドを発行。
  3. **シード値UI連携**: 「シード値をランダムにする」チェックを外したときのみシード数値入力欄がアクティブになる動的制御。

### Phase 5: アプリケーション起動層 (`app.py`)
* **ポイント**: `inbrowser=True` でブラウザを自動起動し、起動時にコンソールへ現在のデバイス（MPS）と出力先フォルダを表示。`KeyboardInterrupt`（`Ctrl+C`）でも安全に終了可能。

### Phase 6: ワンクリック起動スクリプト (`run_app.command`)
* **ポイント**:
  1. スクリプトのダブルクリックで即実行（`chmod +x` 付与済）。
  2. `venv` が存在しない場合は自動で作成し、初回依存ライブラリを自動インストール。
  3. `export PYTORCH_ENABLE_MPS_FALLBACK=1` を確実に適用。
  4. アプリ終了後、AppleScript（`osascript`）が動作し、実行のために開かれたターミナルウィンドウを1秒後に自動で閉じます。

---

## 3. エンドユーザー向け操作ウォークスルー (How to Use)

1. **初回準備**:
   * Hugging Face上の [stable-audio-open-1.0](https://huggingface.co/stabilityai/stable-audio-open-1.0) で利用規約に同意し、`huggingface-cli login` または `HF_TOKEN` を設定。
2. **起動**:
   * Finder上で `run_app.command` をダブルクリック。
   * 自動的にブラウザが起動し、`http://127.0.0.1:7860` のUIが開きます。
3. **音楽生成**:
   * プロンプトに英文を入力（例: `Chill Lo-Fi hip hop beat, mellow electric piano, soft warm bass`）。
   * BPMスライダー（例: 110）や生成秒数（例: 30秒）を調整。
   * 「🎼 音楽を生成する」をクリック。
   * 生成完了後、波形プレイヤーで試聴でき、`output/` フォルダにWAVが自動保存されます。
4. **保存先を開く**:
   * 「📁 保存先フォルダを開く」ボタンを押すと、MacのFinderで直接生成ファイル一覧が表示されます。
5. **アプリ終了**:
   * 右上の「🛑 アプリを終了する」ボタンを押し、確認ダイアログで「OK」をクリックすると、アプリとターミナルが完全に停止します。
