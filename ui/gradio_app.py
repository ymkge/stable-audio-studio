"""Gradio Web UI for Stable Audio Studio."""

import os
import signal
import subprocess
import threading
import time
from typing import Optional, Tuple
import gradio as gr

from core.config import config
from core.generator import generator, ModelLoadError
from core.presets import PRESETS, StylePreset
from core.history import load_history, HistoryItem


def get_history_choices() -> list:
    """Returns a list of (display_label, file_path) for Gradio Dropdown."""
    items = load_history(config.output_dir)
    return [(item.display_label, item.file_path) for item in items]


def open_output_folder() -> str:
    """Opens the output directory in macOS Finder."""
    try:
        subprocess.run(["open", str(config.output_dir)], check=True)
        return "📁 Finderで保存先フォルダを開きました"
    except Exception as e:
        return f"フォルダを開くのに失敗しました: {e}"


def handle_generate(
    prompt: str,
    negative_prompt: str,
    bpm: int,
    duration: int,
    steps: int,
    cfg_scale: float,
    random_seed: bool,
    seed_input: int,
    model_id: str,
) -> Tuple[Optional[str], Optional[int], str, gr.update]:
    """Generates audio, updates output and refreshes the history dropdown."""
    if not prompt or not prompt.strip():
        return None, None, "⚠️ プロンプトを入力してください。", gr.update()

    actual_seed = None if random_seed else int(seed_input)

    try:
        wav_path, used_seed = generator.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            bpm=int(bpm),
            duration=int(duration),
            steps=int(steps),
            cfg_scale=float(cfg_scale),
            seed=actual_seed,
            model_id=model_id,
        )
        new_choices = get_history_choices()
        return (
            wav_path,
            used_seed,
            f"✅ 生成完了: {os.path.basename(wav_path)}",
            gr.update(choices=new_choices, value=wav_path),
        )
    except ModelLoadError as e:
        return None, None, f"❌ モデルエラー:\n{str(e)}", gr.update()
    except Exception as e:
        return None, None, f"❌ 生成中に予期せぬエラーが発生しました: {str(e)}", gr.update()


def on_select_history(file_path: Optional[str]) -> Tuple[Optional[str], Optional[int], str]:
    """Loads selected historical audio into preview player."""
    if not file_path or not os.path.exists(file_path):
        return None, None, ""

    items = {item.file_path: item for item in load_history(config.output_dir)}
    item = items.get(file_path)
    if not item:
        return file_path, None, f"選択: {os.path.basename(file_path)}"

    return (
        file_path,
        item.seed,
        f"🎵 **履歴を読み込みました:** {item.created_at} | {item.bpm} BPM | seed: {item.seed}\n> *{item.prompt}*",
    )


def on_restore_settings(file_path: Optional[str]):
    """Restores parameters from selected history item back into input form."""
    if not file_path or not os.path.exists(file_path):
        return (
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            "⚠️ 復元する音源を生成履歴から選択してください。",
        )

    items = {item.file_path: item for item in load_history(config.output_dir)}
    item = items.get(file_path)
    if not item:
        return (
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            "⚠️ メタデータが見つかりませんでした。",
        )

    return (
        item.prompt,
        item.negative_prompt,
        item.bpm,
        item.duration,
        False,  # random_seed = False (enable manual seed input)
        gr.update(value=item.seed, interactive=True),  # seed_input
        item.model_id if item.model_id in config.available_models else config.model_id,
        f"📋 音源「{item.filename}」の設定を入力フォームに復元しました！（Seed: {item.seed} 固定）",
    )


def handle_shutdown(confirm_status: str) -> gr.update:
    """Safely shuts down the process if confirmed by the user."""
    if confirm_status != "CONFIRMED":
        return gr.update(visible=False)

    def delayed_kill():
        time.sleep(0.5)
        # Kill current process cleanly
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=delayed_kill, daemon=True).start()
    return gr.update(
        value="## 🛑 アプリを終了しました\nブラウザのタブを閉じてください。ターミナルも自動的に終了します。",
        visible=True,
    )


def create_ui() -> gr.Blocks:
    """Builds the Gradio Blocks UI."""
    custom_css = """
    #header-row {
        align-items: center;
        border-bottom: 1px solid #e0e0e0;
        padding-bottom: 8px;
        margin-bottom: 16px;
    }
    #shutdown-box {
        text-align: center;
        padding: 24px;
        background-color: #fff1f0;
        border: 1px solid #ffa39e;
        border-radius: 8px;
        margin-bottom: 16px;
    }
    .preset-box {
        background-color: #fafafa;
        border: 1px solid #ebebeb;
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 14px;
    }
    """

    with gr.Blocks(title="Stable Audio Studio", css=custom_css, theme=gr.themes.Soft()) as demo:
        # Shutdown confirmation hidden input
        confirm_state = gr.Textbox(visible=False, elem_id="confirm_state")

        # Header Row
        with gr.Row(elem_id="header-row"):
            with gr.Column(scale=8):
                gr.Markdown("# 🎵 Stable Audio Studio\n*Powered by Stable Audio 3 Medium (Apple Silicon / MPS)*")
            with gr.Column(scale=2, min_width=150):
                stop_btn = gr.Button("🛑 アプリを終了する", variant="stop", size="sm")

        # Shutdown notice container (initially hidden)
        shutdown_msg = gr.Markdown("", visible=False, elem_id="shutdown-box")

        with gr.Row():
            # Left Column: Inputs & Controls
            with gr.Column(scale=5):
                # Style Preset Buttons
                preset_buttons = {}
                with gr.Group(elem_classes=["preset-box"]):
                    gr.Markdown("⚡ **スタイルプリセット** *(クリックでジャンル設定を一括反映)*")
                    with gr.Row():
                        for p in PRESETS[:3]:
                            preset_buttons[p.id] = gr.Button(
                                p.display_label, size="sm", variant="secondary"
                            )
                    with gr.Row():
                        for p in PRESETS[3:]:
                            preset_buttons[p.id] = gr.Button(
                                p.display_label, size="sm", variant="secondary"
                            )

                prompt = gr.Textbox(
                    label="プロンプト (Prompt)",
                    placeholder="例: Chill Lo-Fi hip hop beat, mellow electric piano chords, soft warm bass, subtle vinyl crackle",
                    lines=3,
                )
                negative_prompt = gr.Textbox(
                    label="ネガティブプロンプト (Negative Prompt)",
                    placeholder="例: distortion, harsh noise, vocals, low quality, clipping",
                    lines=1,
                )

                with gr.Row():
                    bpm = gr.Slider(
                        minimum=config.min_bpm,
                        maximum=config.max_bpm,
                        value=config.default_bpm,
                        step=1,
                        label="BPM (テンポ)",
                    )
                    duration = gr.Slider(
                        minimum=config.min_duration,
                        maximum=config.max_duration,
                        value=config.default_duration,
                        step=5,
                        label="生成秒数 (秒)",
                    )

                with gr.Accordion("詳細設定 (Advanced Settings)", open=False):
                    model_select = gr.Dropdown(
                        choices=config.available_models,
                        value=config.model_id,
                        label="使用モデル (Model)",
                        info="デフォルト: Stable Audio 3 Medium",
                    )
                    steps = gr.Slider(
                        minimum=config.min_steps,
                        maximum=config.max_steps,
                        value=config.default_steps,
                        step=10,
                        label="サンプリングステップ数 (Steps)",
                    )
                    cfg_scale = gr.Slider(
                        minimum=config.min_cfg_scale,
                        maximum=config.max_cfg_scale,
                        value=config.default_cfg_scale,
                        step=0.5,
                        label="CFGスケール (忠実度)",
                    )
                    with gr.Row():
                        random_seed = gr.Checkbox(label="シード値をランダムにする", value=True)
                        seed_input = gr.Number(
                            label="シード値 (固定時)",
                            value=42,
                            interactive=False,
                            precision=0,
                        )

                generate_btn = gr.Button("🎼 音楽を生成する", variant="primary", size="lg")

            # Right Column: Outputs & DAW Integration
            with gr.Column(scale=5):
                audio_player = gr.Audio(label="生成された音楽 (Preview)", type="filepath")
                seed_output = gr.Number(label="使用されたシード値 (Used Seed)", precision=0, interactive=False)
                status_text = gr.Markdown("")

                with gr.Row():
                    open_finder_btn = gr.Button("📁 保存先フォルダを開く (Finder)", variant="secondary")

                # History Gallery Section
                with gr.Accordion("📜 生成履歴 (History Gallery)", open=True):
                    with gr.Row():
                        history_dropdown = gr.Dropdown(
                            label="過去の生成音源を選択 (クリックで試聴)",
                            choices=get_history_choices(),
                            value=None,
                            interactive=True,
                            scale=8,
                        )
                        refresh_history_btn = gr.Button("🔄 更新", size="sm", scale=2)

                    restore_btn = gr.Button(
                        "📋 選択した音源の設定を入力フォームに復元", variant="secondary"
                    )

        # Dynamic interactivity: Enable seed_input only when random_seed is False
        random_seed.change(
            fn=lambda is_random: gr.update(interactive=not is_random),
            inputs=[random_seed],
            outputs=[seed_input],
        )

        # Style preset button actions
        for p in PRESETS:
            preset_buttons[p.id].click(
                fn=lambda preset=p: (
                    preset.prompt,
                    preset.negative_prompt,
                    preset.bpm,
                    preset.duration,
                    f"🎨 プリセット「{preset.display_label}」を反映しました（BPM: {preset.bpm}, {preset.duration}秒）",
                ),
                inputs=[],
                outputs=[prompt, negative_prompt, bpm, duration, status_text],
            )

        # Generate action
        generate_btn.click(
            fn=handle_generate,
            inputs=[
                prompt,
                negative_prompt,
                bpm,
                duration,
                steps,
                cfg_scale,
                random_seed,
                seed_input,
                model_select,
            ],
            outputs=[audio_player, seed_output, status_text, history_dropdown],
        )

        # History Gallery Actions
        history_dropdown.change(
            fn=on_select_history,
            inputs=[history_dropdown],
            outputs=[audio_player, seed_output, status_text],
        )

        restore_btn.click(
            fn=on_restore_settings,
            inputs=[history_dropdown],
            outputs=[
                prompt,
                negative_prompt,
                bpm,
                duration,
                random_seed,
                seed_input,
                model_select,
                status_text,
            ],
        )

        refresh_history_btn.click(
            fn=lambda: gr.update(choices=get_history_choices()),
            inputs=[],
            outputs=[history_dropdown],
        )

        # Finder action
        open_finder_btn.click(
            fn=open_output_folder,
            inputs=[],
            outputs=[status_text],
        )

        # Shutdown Javascript Confirmation UX
        shutdown_js = """
        () => {
            const ok = confirm("アプリを終了してよろしいですか？\\n（サーバーとバックグラウンド処理が停止します）");
            return ok ? "CONFIRMED" : "CANCELLED";
        }
        """
        stop_btn.click(
            fn=handle_shutdown,
            inputs=[confirm_state],
            outputs=[shutdown_msg],
            _js=shutdown_js,
        )

    return demo
