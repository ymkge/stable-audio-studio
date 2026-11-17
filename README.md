# 🎵 Stable Audio Studio

<img width="1893" height="845" alt="Stable Audio Studio UI" src="https://github.com/user-attachments/assets/b8f923fe-5f64-402a-874f-dac18c7f20c3" />

MacBook Pro (Apple Silicon / MPS) 上でローカル動作する、Stability AI の最新モデル **`Stable Audio 3 Medium`** を搭載したオープンソースの高音質AI音楽生成スタジオ（Web UI）です。

ワンクリックで起動し、短尺（30秒）から長尺（最大6分 / 360秒）のハイクオリティな楽曲を超高速に生成できます（30秒の楽曲ならわずか **3秒〜10秒程度** で完走）。

---

## ✨ 主な特徴

- ⚡ **超高速ローカル推論 (Apple Silicon / MPS 最適化)**: 最新の Rectified Flow アーキテクチャにより、わずか **8ステップ** で高品質な音楽を生成（30秒の楽曲なら約3〜10秒で完走）。
- ⏱️ **柔軟な生成尺（5秒〜最大6分）**: ワンフレーズのジングル（5秒〜15秒）から、作業用BGMやYouTube動画に最適なフル尺（最長360秒 / 6分）までスライダーで自在に指定可能。
- 🖱️ **ワンクリック起動 (`run_app.command`)**: ターミナル操作に不慣れなデザイナー・ミュージシャンでも、Finder上でファイルをダブルクリックするだけで自動セットアップ＆ブラウザ起動。
- 🎨 **6つのスタイルプリセット**: Lo-Fi Chill、Ambient / Meditation、80s Synthwave、Cinematic Orchestral、Acoustic Folk、Lounge Jazz をワンクリック適用。
- 🧹 **ワンクリック入力クリア**: 別の曲アイデアを試したい時、ボタン1つでプロンプトとネガティブプロンプトを瞬時にクリアしてゼロからスムーズに入力可能。
- 🌊 **リアルタイム波形プレビュー**: 生成された音源をその場で波形表示・再生・シーク。
- 🎲 **シード値（Seed）コントロール**: 気に入った曲のシード値を固定してBPMや音色を微調整（A/Bテスト）可能。
- 📜 **生成履歴ギャラリー & レシピ復元**: 過去に生成した楽曲を一覧化。ワンクリックで試聴、および当時のプロンプト・BPM・秒数・シード値を入力フォームへ完全復元。
- 💾 **サイドカー方式（`.wav` + `.json`）の保存**: 音声本体（WAV）と制作レシピ（JSON）を `output/` フォルダへ自動保存。UI上のボタンからFinderで一発オープン。
- 🛑 **安全なシャットダウン**: 画面右上の「🛑 アプリを終了する」ボタンから確認ダイアログ付きで安全にプロセスを終了。

---

## 💻 動作要件

- **対応OS**: macOS (Apple Silicon M1 / M2 / M3 / M4)
- **推奨環境**: メモリ 16GB 以上（推奨 24GB〜48GB）
- **Python**: 3.10 〜 3.12
- **使用モデル**: `stabilityai/stable-audio-3-medium`（標準）
- **ネットワーク**: 初回起動時のモデルダウンロード時のみ必要（完了後は完全オフライン動作可能）

---

## 🚀 はじめかた（初回セットアップ）

### ステップ 1: Hugging Face モデル利用規約への同意
本アプリで使用する `stabilityai/stable-audio-3-medium` は、Stability AI のコミュニティライセンスモデルです。初回のみ利用規約への同意が必要です。

1. [Hugging Face: stable-audio-3-medium](https://huggingface.co/stabilityai/stable-audio-3-medium) にアクセスし、ログインします。
2. 画面上の利用規約を確認し、**「Accept conditions」**（同意）ボタンをクリックします。

### ステップ 2: Hugging Face 認証（トークン設定）
ターミナルを開き、Hugging Face アカウントと連携します。

```bash
hf auth login
# （または huggingface-cli login）
```

1. **トークン入力**: [Hugging Face Access Tokens](https://huggingface.co/settings/tokens) で発行した `Read` 権限のトークンを貼り付けて Enter を押します（入力内容は画面に表示されません）。
2. **Git credential の質問**: `Add token as git credential? (Y/n)` と表示されたら、`n` と入力（または何も入力せずそのまま Enter）します。
3. `Login successful.` と表示されれば完了です。

---

## 🎵 アプリの起動

### 方法 A: ワンクリック起動（推奨）
プロジェクトフォルダ内の **`run_app.command`** をダブルクリックします。

- 初回実行時：仮想環境（`venv`）と依存ライブラリを自動構築します。
- ブラウザが自動的に開き、`http://127.0.0.1:7860` で Web UI が立ち上がります。
- アプリ右上の「🛑 アプリを終了する」ボタンを押すと、開いていたターミナルウィンドウも自動的に閉じます。

> **⚠️ 初回音楽生成時の注意（ダウンロード待ち）**:
> 初回に「✨ 音楽を生成する」ボタンをクリックした時のみ、Hugging Face からモデル重みファイル（約9.2GB）とテキストエンコーダー（約1.2GB）の自動ダウンロードが始まります。
> ご利用の回線速度によりますが、**初回のみ数分〜十数分** かかります（ターミナル画面上に進捗バーが表示されます）。
> ※ 2回目以降はローカルキャッシュから即座にロードされ、わずか数秒で生成されます。

### 方法 B: ターミナルからの手動起動
```bash
# 1. 仮想環境の作成と有効化
python3 -m venv venv
source venv/bin/activate

# 2. 依存パッケージのインストール
pip install --upgrade pip
pip install -r requirements.txt
pip uninstall -y torchvision 2>/dev/null || true

# 3. アプリ起動（Apple Silicon MPSフォールバック有効）
export PYTORCH_ENABLE_MPS_FALLBACK=1
python3 app.py
```

---

## 📁 生成ファイルの仕様と構造

音楽を生成すると、`output/` フォルダ内に **2つのファイルがセット** で自動保存されます。

- **`{タイムスタンプ}_{BPM}bpm_{秒数}s_{プロンプト概要}_s{シード値}.wav`**:
  - 非圧縮の高品質オーディオファイル（44.1kHz / ステレオ）。DAW（Logic Pro, Ableton 等）や動画編集ソフト（Premiere, DaVinci 等）にそのまま取り込んで使用可能。
- **`{同じ名前}.json`**:
  - その曲を生成した当時の「制作レシピ（プロンプト、BPM、生成秒数、シード値、モデル名、生成日時など）」を記録したメタデータ。
  - アプリ内の「📋 選択した音源の設定を入力フォームに復元」ボタンを押すと、このファイルを読み込んで当時の設定を一瞬で再現できます。

---

## 🛠️ トラブルシューティング

| 現象 | 原因と対策 |
| :--- | :--- |
| **`Hugging Face認証エラー (401/403/gated repo)`** | モデル規約への同意が未完了、またはトークン未認証です。<br>1. [Hugging Face モデルページ](https://huggingface.co/stabilityai/stable-audio-3-medium) で規約に同意してください。<br>2. ターミナルで `hf auth login` を実行してください。 |
| **`RuntimeError: operator torchvision::nms does not exist`** | 依存関係に `torchvision` が混入してテキストエンコーダーの読み込みを阻害しています。<br>ターミナルで `./venv/bin/pip uninstall -y torchvision` を実行してください。 |
| **「ダブルクリックしても起動しない」** | macOSのセキュリティ制限で実行権限がない場合があります。<br>ターミナルで `chmod +x run_app.command` を実行してください。 |

---

## 🏛️ アーキテクチャ設計（将来の拡張性）

本プロジェクトは **クリーンアーキテクチャ** に基づき、音楽生成コア（`core/`）と画面表示（`ui/`）が完全に分離されています。

```text
stable-audio-studio/
├── core/                  # ★ 純粋な音楽生成・設定・履歴ロジック（UI非依存）
│   ├── config.py          # モデルID・BPM・秒数・最適ステップ数（8）等の設定
│   ├── generator.py       # stable-audio-3推論、WAV/JSON保存ロジック
│   ├── history.py         # 履歴読み出し・サイドカーJSON管理
│   └── presets.py         # 音楽スタイルプリセット定義
├── ui/                    # ★ 画面表示層（将来的にNext.js/Tauri等へ差し替え可能）
│   └── gradio_app.py      # Gradio Blocks UI、波形プレビュー、終了制御
├── output/                # 生成されたWAV/JSONの自動保存先
├── issues/                 # 開発Issue・進捗・課題・ウォークスルー情報
├── app.py                 # エントリーポイント
├── run_app.command        # macOS用ダブルクリック起動スクリプト
└── requirements.txt       # 依存パッケージ定義
```

将来的には、`ui/gradio_app.py` を FastAPI（`api/server.py`）に差し替えることで、**TypeScript（React / Next.js）や Tauri を用いた本格的なDAW風デスクトップアプリ（.app）への発展** がスムーズに行える設計になっています。

---

## 📄 ライセンス

本プロジェクトのコードは MIT ライセンスです。
使用している `Stable Audio 3 Medium` モデルのウェイトおよび利用に関しては、[Stability AI Community License](https://huggingface.co/stabilityai/stable-audio-3-medium) に準拠します。
