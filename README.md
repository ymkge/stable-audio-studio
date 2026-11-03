# 🎵 Stable Audio Studio

MacBook Pro (Apple Silicon / MPS) 上でローカル動作する、オープンソースの音楽生成AI Web UIアプリケーションです。
推論コア層（`core/`）とUI層（`ui/`）が疎結合に設計されており、将来のFastAPIやTypeScript (Next.js / Tauri) への移行にも対応しています。

---

## 💻 動作要件
- **OS**: macOS (Apple Silicon M1/M2/M3/M4)
- **Python**: 3.10+
- **利用モデル**: `stabilityai/stable-audio-open-1.0`

---

## 🚀 起動方法

### 1. 初回のみ: Hugging Face モデル利用規約の同意
本アプリが使用する `stabilityai/stable-audio-open-1.0` は利用規約への同意が必要です。
1. [Hugging Face: stable-audio-open-1.0](https://huggingface.co/stabilityai/stable-audio-open-1.0) をブラウザで開き、利用規約に同意（Accept）します。
2. ターミナルで `huggingface-cli login` を実行してログインするか、環境変数 `export HF_TOKEN="your_token"` を設定してください。

### 2. ワンクリック起動 (推奨)
Finderで **`run_app.command`** をダブルクリックするだけで起動できます。
- 自動的にPython仮想環境（venv）と依存ライブラリをセットアップし、ブラウザでUIが開きます。
- アプリを終了すると、ターミナルウィンドウも自動的に閉じます。

### 3. コマンドラインからの起動
```bash
# 仮想環境の作成とライブラリインストール
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 起動（MPSフォールバック有効）
export PYTORCH_ENABLE_MPS_FALLBACK=1
python3 app.py
```

---

## 📁 ディレクトリ構成

```text
stable-audio-studio/
├── core/
│   ├── __init__.py
│   ├── config.py           # モデルID、BPM/秒数/ステップ等の設定
│   └── generator.py        # モデル推論・WAV生成・サニタイズ命名・保存ロジック
├── ui/
│   ├── __init__.py
│   └── gradio_app.py       # Gradio Blocks UI、波形プレビュー、終了制御
├── output/                 # 生成されたWAVファイルの自動保存先
├── issues/                 # 開発Issue・進捗・課題トラッカー
├── app.py                  # アプリケーションのエントリーポイント
├── run_app.command         # ダブルクリック起動スクリプト (macOS)
├── requirements.txt        # 依存パッケージ定義
└── .gitignore
```

---

## 🎨 主な機能
- **BPM自動統合**: プロンプト先頭に自動で `{BPM} BPM, ` を付与
- **DAW連携**: 生成されたWAVは `output/` フォルダへ自動保存（UI上のボタンからFinderで一発オープン）
- **安全なアプリ終了**: 画面右上の「🛑 アプリを終了する」ボタンから確認ダイアログ付きで安全にプロセスをシャットダウン
