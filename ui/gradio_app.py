"""Gradio Web UI for Stable Audio Studio."""

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Tuple
import gradio as gr

from core.config import config
from core.generator import generator, ModelLoadError, is_sfx_model
from core.presets import PRESETS, SFX_PRESETS, StylePreset
from core.history import load_history, HistoryItem
from core.prompt_enhancer import enhance_prompt
from core.audio_processor import create_seamless_loop, apply_fade


def resolve_output_path(file_path: Optional[str]) -> Optional[str]:
    """Resolves potential temporary Gradio cache paths back to the canonical output directory path."""
    if not file_path:
        return None
    p = Path(file_path)
    # Check if a file with the same filename exists in the canonical output directory
    canonical = config.output_dir / p.name
    if canonical.exists():
        return str(canonical)
    if p.exists():
        return str(p.resolve())
    return file_path


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


def handle_enhance_prompt(current_prompt: str, model_id: str, current_bpm: int):
    """Enhances the prompt and negative prompt using the prompt_enhancer core engine."""
    res = enhance_prompt(user_input=current_prompt, model_id=model_id, current_bpm=current_bpm)
    tag_str = ", ".join(res.applied_tags) if res.applied_tags else "自動最適化"
    is_sfx = is_sfx_model(model_id)
    if not is_sfx and res.suggested_bpm:
        bpm_update = gr.update(value=res.suggested_bpm)
        bpm_msg = f", 推奨BPM: {res.suggested_bpm}"
    else:
        bpm_update = gr.update()
        bpm_msg = ""
    status_msg = f"🪄 プロンプトを自動強化しました！【適用: {tag_str}{bpm_msg}】"
    return res.prompt, res.negative_prompt, bpm_update, status_msg


def handle_create_loop(active_path: Optional[str], history_path: Optional[str], crossfade_sec: float):
    """Creates a seamless infinite loop audio from active take or history audio."""
    target_path = resolve_output_path(active_path) or resolve_output_path(history_path)
    if not target_path or not os.path.exists(target_path):
        return (
            gr.update(), gr.update(), gr.update(),
            "⚠️ ループ加工する音源がありません。先に音源を生成するか履歴から選択してください。",
            gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(),
        )

    try:
        out_wav, msg = create_seamless_loop(target_path, crossfade_duration=float(crossfade_sec))
        new_choices = get_history_choices()
        display_msg = f"🔁 **現在の加工対象:** ループ加工音源 (`{os.path.basename(out_wav)}`)"
        meta_str = f"🔁 **ループ加工済み** | `{os.path.basename(out_wav)}`"
        return (
            out_wav,      # active_audio_target
            display_msg,  # active_target_display
            out_wav,      # take_player_1
            f"✅ {msg}",  # status_text
            gr.update(choices=new_choices, value=out_wav),  # history_dropdown
            "#### 🔁 シームレス・ループ加工音源",           # take_title_1
            meta_str,     # take_meta_1
            gr.update(visible=True),   # take_card_1
            gr.update(visible=False),  # take_card_2
            gr.update(visible=False),  # take_card_3
            gr.update(visible=False),  # take_card_4
        )
    except Exception as e:
        return (
            gr.update(), gr.update(), gr.update(),
            f"❌ ループ作成エラー: {str(e)}",
            gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(),
        )


def handle_apply_fade(active_path: Optional[str], history_path: Optional[str], fade_in: float, fade_out: float):
    """Applies smooth S-curve fade-in and fade-out to audio."""
    target_path = resolve_output_path(active_path) or resolve_output_path(history_path)
    if not target_path or not os.path.exists(target_path):
        return (
            gr.update(), gr.update(), gr.update(),
            "⚠️ フェード加工する音源がありません。先に音源を生成するか履歴から選択してください。",
            gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(),
        )

    try:
        out_wav, msg = apply_fade(target_path, fade_in_sec=float(fade_in), fade_out_sec=float(fade_out))
        new_choices = get_history_choices()
        display_msg = f"🌊 **現在の加工対象:** フェード加工音源 (`{os.path.basename(out_wav)}`)"
        meta_str = f"🌊 **フェード加工済み** | `{os.path.basename(out_wav)}`"
        return (
            out_wav,      # active_audio_target
            display_msg,  # active_target_display
            out_wav,      # take_player_1
            f"✅ {msg}",  # status_text
            gr.update(choices=new_choices, value=out_wav),  # history_dropdown
            "#### 🌊 フェード加工音源",                     # take_title_1
            meta_str,     # take_meta_1
            gr.update(visible=True),   # take_card_1
            gr.update(visible=False),  # take_card_2
            gr.update(visible=False),  # take_card_3
            gr.update(visible=False),  # take_card_4
        )
    except Exception as e:
        return (
            gr.update(), gr.update(), gr.update(),
            f"❌ フェード加工エラー: {str(e)}",
            gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(),
        )


def get_duration_slider_update(model_id: str, current_duration: int) -> gr.update:
    """Returns dynamic update for the duration slider based on model limits."""
    max_sec = config.get_max_duration(model_id)
    is_sfx = is_sfx_model(model_id)
    if is_sfx:
        info = f"5秒〜{max_sec}秒（効果音モデル上限: 最大{max_sec // 60}分）"
    else:
        info = f"5秒〜{max_sec}秒（最大{max_sec // 60}分）"
    safe_duration = min(int(current_duration or config.default_duration), max_sec)
    return gr.update(maximum=max_sec, value=safe_duration, info=info)


def get_generate_btn_label(takes: int, model_id: str) -> str:
    """Returns dynamic label for the generate button based on mode and take count."""
    is_sfx = is_sfx_model(model_id)
    prefix = "🍃 効果音" if is_sfx else "🎼 音楽"
    model_tag = "Small SFXモデル" if is_sfx else "Mediumモデル"
    takes_int = int(takes)
    if takes_int > 1:
        return f"{prefix}を一括生成 ({takes_int}テイク / {model_tag})"
    return f"{prefix}を生成する ({model_tag})"


def get_mode_sync_updates(target_model_id: str, current_duration: int, takes: int = 1):
    """Generates unified updates across UI components when model/mode changes."""
    is_sfx = is_sfx_model(target_model_id)
    dur_update = get_duration_slider_update(target_model_id, current_duration)
    btn_label = get_generate_btn_label(takes, target_model_id)
    btn_update = gr.update(value=btn_label)
    if is_sfx:
        bpm_update = gr.update(value=config.default_bpm, visible=False)
        msg = "🍃 効果音・環境音モードに切り替えました（モデル: Small SFX 自動選択, BPMオフ）"
    else:
        bpm_update = gr.update(visible=True)
        msg = "🎵 音楽モードに切り替えました（モデル: Medium 自動選択）"
    return (
        target_model_id,  # for mode_radio
        target_model_id,  # for model_select
        bpm_update,
        dur_update,
        btn_update,
        msg,
    )


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
    init_audio: Optional[str] = None,
    init_noise_level: float = 0.6,
    num_takes: int = 1,
    progress=gr.Progress(track_tqdm=True),
):
    """Generates audio (single or multiple takes) and displays them in a vertical feed."""
    empty_feed = (
        gr.update(),  # history_dropdown
        None,         # active_audio_target
        "",           # active_target_display
        gr.update(visible=False), "", None, "",  # card 1
        gr.update(visible=False), "", None, "",  # card 2
        gr.update(visible=False), "", None, "",  # card 3
        gr.update(visible=False), "", None, "",  # card 4
    )
    if not prompt or not prompt.strip():
        return ("⚠️ プロンプトを入力してください。", *empty_feed)

    actual_seed = None if random_seed else int(seed_input)
    safe_bpm = int(bpm) if bpm is not None else 0
    safe_takes = max(1, min(int(num_takes), config.max_takes))

    try:
        def prog_callback(cur_take: int, total: int, msg: str):
            ratio = (cur_take - 1) / max(total, 1)
            progress(ratio, desc=msg)

        results = generator.generate_takes(
            prompt=prompt,
            negative_prompt=negative_prompt,
            bpm=safe_bpm,
            duration=int(duration),
            steps=int(steps),
            cfg_scale=float(cfg_scale),
            seed=actual_seed,
            model_id=model_id,
            init_audio_path=init_audio,
            init_noise_level=float(init_noise_level) if init_noise_level else 0.6,
            num_takes=safe_takes,
            progress_callback=prog_callback,
        )

        progress(1.0, desc="生成完了！")
        new_choices = get_history_choices()
        mode_tag = " (Audio-to-Audio)" if init_audio else ""
        total_gen = len(results)

        main_wav, main_seed = results[0]
        status_msg = (
            f"✅ 生成完了{mode_tag}: {os.path.basename(main_wav)}"
            if total_gen == 1
            else f"✅ 一括生成完了 ({total_gen}テイク){mode_tag}: 下のリストで各テイクを試聴・比較できます。"
        )
        display_msg = f"🎵 **現在の加工対象:** Take 1 (`{os.path.basename(main_wav)}` / Seed: {main_seed})"

        take_cards = []
        for i in range(4):
            if i < total_gen:
                w_path, s_val = results[i]
                title = "#### 🎵 生成音源 (Preview)" if total_gen == 1 else f"#### 🎧 Take {i+1}"
                meta = f"**Take {i+1}** | Seed: `{s_val}` | `{os.path.basename(w_path)}`"
                take_cards.append((gr.update(visible=True), title, w_path, meta))
            else:
                take_cards.append((gr.update(visible=False), "", None, ""))

        return (
            status_msg,
            gr.update(choices=new_choices),
            main_wav,
            display_msg,
            take_cards[0][0], take_cards[0][1], take_cards[0][2], take_cards[0][3],
            take_cards[1][0], take_cards[1][1], take_cards[1][2], take_cards[1][3],
            take_cards[2][0], take_cards[2][1], take_cards[2][2], take_cards[2][3],
            take_cards[3][0], take_cards[3][1], take_cards[3][2], take_cards[3][3],
        )
    except ModelLoadError as e:
        return (f"❌ モデルエラー:\n{str(e)}", *empty_feed)
    except Exception as e:
        return (f"❌ 生成中に予期せぬエラーが発生しました: {str(e)}", *empty_feed)


def on_adopt_take(take_idx: int, take_audio: Optional[str]):
    """Selects the designated take as the active target for post-processing and history."""
    real_path = resolve_output_path(take_audio)
    if not real_path or not os.path.exists(real_path):
        return gr.update(), gr.update(), "⚠️ 有効なテイク音源がありません。", gr.update()

    items = {item.file_path: item for item in load_history(config.output_dir)}
    item = items.get(real_path)
    seed_val = item.seed if item else None

    status_msg = f"⭐ **Take {take_idx} を採用しました:** `{os.path.basename(real_path)}` (Seed: {seed_val})"
    display_msg = f"🎵 **現在の加工対象:** Take {take_idx} (`{os.path.basename(real_path)}` / Seed: {seed_val})"

    return (
        real_path,
        display_msg,
        status_msg,
        gr.update(),
    )


def on_select_history(file_path: Optional[str]):
    """Loads selected historical audio into preview feed."""
    real_path = resolve_output_path(file_path)
    if not real_path or not os.path.exists(real_path):
        return (
            "", gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(),
        )

    items = {item.file_path: item for item in load_history(config.output_dir)}
    item = items.get(real_path)
    if not item:
        return (
            f"選択: {os.path.basename(real_path)}", real_path,
            f"🎵 **現在の加工対象:** 履歴音源 (`{os.path.basename(real_path)}`)",
            gr.update(visible=True), "#### 📜 選択された履歴音源", real_path, f"`{os.path.basename(real_path)}`",
            gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
        )

    is_sfx = (item.bpm <= 0) or is_sfx_model(item.model_id)
    bpm_info = "SFX (BPMなし)" if is_sfx else f"{item.bpm} BPM"
    icon = "🍃" if is_sfx else "🎵"

    ref_info = ""
    if getattr(item, "init_audio_filename", None):
        ref_info = f"\n> 🔄 *参考音源: {item.init_audio_filename} (アレンジ強度: {item.init_noise_level})*"

    meta_str = f"{icon} **履歴音源** | {item.created_at} | {bpm_info} | Seed: `{item.seed}`\n> *{item.prompt}*{ref_info}"
    status_msg = f"{icon} **履歴を読み込みました:** {item.created_at} | {bpm_info} | seed: {item.seed}"
    display_msg = f"🎵 **現在の加工対象:** 履歴音源 (`{os.path.basename(real_path)}`)"

    return (
        status_msg,
        real_path,
        display_msg,
        gr.update(visible=True),
        "#### 📜 選択された履歴音源",
        real_path,
        meta_str,
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
    )


def on_restore_settings(file_path: Optional[str]):
    """Restores parameters from selected history item back into input form."""
    real_path = resolve_output_path(file_path)
    if not real_path or not os.path.exists(real_path):
        return (
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
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
    item = items.get(real_path)
    if not item:
        return (
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(),
            "⚠️ メタデータが見つかりませんでした。",
        )

    is_sfx = (item.bpm <= 0) or is_sfx_model(item.model_id)
    if is_sfx:
        bpm_update = gr.update(value=config.default_bpm, visible=False)
        btn_update = gr.update(value="🍃 効果音を生成する (Small SFXモデル)")
        model_val = item.model_id if item.model_id in config.available_models else config.sfx_model_id
        dur_update = gr.update(
            maximum=config.sfx_max_duration,
            value=min(item.duration, config.sfx_max_duration),
            info="5秒〜120秒（効果音モデル上限: 最大2分）",
        )
        msg = f"📋 効果音「{item.filename}」の設定を入力フォームに復元しました！（Seed: {item.seed} 固定）"
    else:
        bpm_val = item.bpm if item.bpm >= config.min_bpm else config.default_bpm
        bpm_update = gr.update(value=bpm_val, visible=True)
        btn_update = gr.update(value="🎼 音楽を生成する (Mediumモデル)")
        model_val = item.model_id if item.model_id in config.available_models else config.model_id
        dur_update = gr.update(
            maximum=config.max_duration,
            value=min(item.duration, config.max_duration),
            info="5秒〜360秒（最大6分）",
        )
        msg = f"📋 音楽「{item.filename}」の設定を入力フォームに復元しました！（Seed: {item.seed} 固定）"

    # Audio-to-Audio settings restore
    init_audio_val = None
    if getattr(item, "init_audio_filename", None):
        possible_path = config.output_dir / item.init_audio_filename
        if possible_path.exists():
            init_audio_val = str(possible_path)
    noise_level_val = getattr(item, "init_noise_level", None) or config.default_init_noise_level

    return (
        item.prompt,
        item.negative_prompt,
        bpm_update,
        dur_update,
        False,  # random_seed = False (enable manual seed input)
        gr.update(value=item.seed, interactive=True),  # seed_input
        model_val,  # mode_radio
        model_val,  # model_select
        btn_update,
        init_audio_val,
        noise_level_val,
        msg,
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


CUSTOM_CSS = """
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
.mode-box {
    background: linear-gradient(135deg, #f0f5ff 0%, #f6ffed 100%);
    border: 1px solid #d9d9d9;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 14px;
}
.mode-box label {
    font-weight: 600;
}
.prompt-header-row {
    align-items: center;
    justify-content: space-between;
    margin-top: 8px;
    margin-bottom: -4px;
}
.take-card {
    border: 1px solid rgba(128, 128, 128, 0.2);
    background: rgba(128, 128, 128, 0.05);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 14px;
}
"""


def create_ui() -> gr.Blocks:
    """Builds the Gradio Blocks UI."""
    with gr.Blocks(title="Stable Audio Studio") as demo:
        # Shutdown confirmation hidden input
        confirm_state = gr.Textbox(visible=False, elem_id="confirm_state")

        # Header Row
        with gr.Row(elem_id="header-row"):
            with gr.Column(scale=8):
                gr.Markdown("# 🎵 Stable Audio Studio\n*高品質AI音楽 & 環境音・効果音生成スタジオ (Apple Silicon / MPS)*")
            with gr.Column(scale=2, min_width=150):
                stop_btn = gr.Button("🛑 アプリを終了する", variant="stop", size="sm")

        # Shutdown notice container (initially hidden)
        shutdown_msg = gr.Markdown("", visible=False, elem_id="shutdown-box")

        with gr.Row():
            # Left Column: Inputs & Controls
            with gr.Column(scale=5):
                # Style Preset Buttons (Music & SFX/Ambience)
                preset_buttons = {}
                with gr.Group(elem_classes=["preset-box"]):
                    gr.Markdown("⚡ **スタイルプリセット** *(クリックでジャンル・モデル設定を一括反映)*")
                    with gr.Tabs() as preset_tabs:
                        with gr.Tab("🎵 音楽 (Music)") as music_tab:
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
                        with gr.Tab("🍃 環境音・効果音 (Sound Effects)") as sfx_tab:
                            with gr.Row():
                                for p in SFX_PRESETS[:3]:
                                    preset_buttons[p.id] = gr.Button(
                                        p.display_label, size="sm", variant="secondary"
                                    )
                            with gr.Row():
                                for p in SFX_PRESETS[3:]:
                                    preset_buttons[p.id] = gr.Button(
                                        p.display_label, size="sm", variant="secondary"
                                    )

                # Production Mode & Model Selector (Always visible)
                with gr.Group(elem_classes=["mode-box"]):
                    mode_radio = gr.Radio(
                        choices=[
                            ("🎵 音楽モード (Stable Audio 3 Medium - 最大6分)", config.model_id),
                            ("🍃 効果音・環境音モード (Stable Audio 3 Small SFX - 最大2分)", config.sfx_model_id),
                        ],
                        value=config.model_id,
                        label="📻 制作モード / 使用モデル (Mode & Model)",
                        info="プリセットタブと自動連動します。手動で切り替えることも可能です。",
                    )

                with gr.Row(elem_classes=["prompt-header-row"]):
                    gr.Markdown("📝 **プロンプト入力** *(日本語・英語対応)*")
                    with gr.Row():
                        enhance_prompt_btn = gr.Button(
                            "🪄 プロンプトを自動強化",
                            size="sm",
                            variant="primary",
                            scale=0,
                            min_width=160,
                        )
                        clear_prompt_btn = gr.Button(
                            "🧹 クリア",
                            size="sm",
                            variant="secondary",
                            scale=0,
                            min_width=70,
                        )

                prompt = gr.Textbox(
                    label="プロンプト (Prompt)",
                    placeholder="日本語または英語で入力してください（例: 深夜のチルなローファイ / 喫茶店のジャズ / 秋の夜の森とフクロウ）\n※入力後に右上の「🪄 プロンプトを自動強化」を押すと高音質な英語プロンプトへ自動展開されます",
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
                        info="5秒〜360秒（最大6分）",
                    )

                with gr.Row():
                    num_takes = gr.Radio(
                        choices=[1, 2, 3, 4],
                        value=config.default_takes,
                        label="🎲 生成テイク数 (一括オーディション)",
                        info="異なるシード値で指定テイク数を一括生成し、右列で聴き比べ（オーディション）できます。",
                    )

                # Audio-to-Audio (Reference Audio Conditioning) Accordion
                with gr.Accordion("🔄 参考音源からアレンジ生成 (Audio-to-Audio) [任意]", open=False) as init_audio_accordion:
                    init_audio = gr.Audio(
                        label="参考音源 (ドラッグ＆ドロップまたはクリックで音源ファイルをセット)",
                        type="filepath",
                        sources=["upload"],
                    )
                    with gr.Row():
                        init_noise_level = gr.Slider(
                            minimum=config.min_init_noise_level,
                            maximum=config.max_init_noise_level,
                            value=config.default_init_noise_level,
                            step=0.05,
                            label="アレンジ強度 (Noise Level)",
                            info="0.2〜0.4: 原曲のメロディや構成を強く維持 / 0.6〜0.8: リズムや構成を活かして別ジャンルへ大胆にリメイク（※複数テイクで差を出したい場合は0.6以上推奨）",
                            scale=8,
                        )
                        clear_init_audio_btn = gr.Button("🗑️ 参考音源をクリア", size="sm", variant="secondary", scale=2)

                with gr.Accordion("詳細設定 (Advanced Settings)", open=False):
                    model_select = gr.Dropdown(
                        choices=config.available_models,
                        value=config.model_id,
                        label="使用モデル (Model)",
                        info="SA3 Medium (音楽向け) / Small SFX (効果音・環境音向け)",
                    )
                    steps = gr.Slider(
                        minimum=config.min_steps,
                        maximum=config.max_steps,
                        value=config.default_steps,
                        step=1,
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

                generate_btn = gr.Button("🎼 音楽を生成する (Mediumモデル)", variant="primary", size="lg")

            # Right Column: Outputs & Audition Feed (Suno-style vertical list)
            with gr.Column(scale=5):
                status_text = gr.Markdown("")
                with gr.Row():
                    open_finder_btn = gr.Button("📁 保存先フォルダを開く (Finder)", variant="secondary")

                # Hidden state holding active target audio for processing
                active_audio_target = gr.Textbox(visible=False)

                gr.Markdown("### 🎲 生成テイク一覧 (Audition Feed)")
                gr.Markdown("💡 *各テイクの波形プレイヤーで直接試聴・比較できます。「⭐ このテイクを採用」を押すと直下のオーディオ加工（ループ＆フェード）の対象にセットされます。*")

                # Take 1 Card
                with gr.Group(visible=True, elem_classes=["take-card"]) as take_card_1:
                    with gr.Row():
                        take_title_1 = gr.Markdown("#### 🎧 Take 1")
                        select_take_1_btn = gr.Button("⭐ このテイクを採用（加工対象にセット）", variant="primary", size="sm")
                    take_player_1 = gr.Audio(label="", type="filepath")
                    take_meta_1 = gr.Markdown("（音源を生成するとここに表示されます）")

                # Take 2 Card
                with gr.Group(visible=False, elem_classes=["take-card"]) as take_card_2:
                    with gr.Row():
                        take_title_2 = gr.Markdown("#### 🎧 Take 2")
                        select_take_2_btn = gr.Button("⭐ このテイクを採用（加工対象にセット）", variant="primary", size="sm")
                    take_player_2 = gr.Audio(label="", type="filepath")
                    take_meta_2 = gr.Markdown("")

                # Take 3 Card
                with gr.Group(visible=False, elem_classes=["take-card"]) as take_card_3:
                    with gr.Row():
                        take_title_3 = gr.Markdown("#### 🎧 Take 3")
                        select_take_3_btn = gr.Button("⭐ このテイクを採用（加工対象にセット）", variant="primary", size="sm")
                    take_player_3 = gr.Audio(label="", type="filepath")
                    take_meta_3 = gr.Markdown("")

                # Take 4 Card
                with gr.Group(visible=False, elem_classes=["take-card"]) as take_card_4:
                    with gr.Row():
                        take_title_4 = gr.Markdown("#### 🎧 Take 4")
                        select_take_4_btn = gr.Button("⭐ このテイクを採用（加工対象にセット）", variant="primary", size="sm")
                    take_player_4 = gr.Audio(label="", type="filepath")
                    take_meta_4 = gr.Markdown("")

                # Audio Post-Processing (Seamless Loop & Fade)
                with gr.Accordion("🔁 オーディオ加工・ループ＆フェード (Post-Processing)", open=False) as processor_accordion:
                    active_target_display = gr.Markdown("💡 *現在選択中の音源（デフォルト: Take 1）に対して、シームレスループ化やフェード処理を適用して別名保存します。*")
                    with gr.Tabs():
                        with gr.Tab("🔁 シームレス・ループ作成"):
                            gr.Markdown("末尾と先頭を等電力クロスフェードで滑らかに繋ぎ、何度リピート再生しても継ぎ目のない永久ループWAVを作成します。")
                            crossfade_slider = gr.Slider(
                                minimum=1.0,
                                maximum=10.0,
                                value=3.0,
                                step=0.5,
                                label="クロスフェード時間 (秒)",
                                info="環境音・アンビエントは 3〜5秒、短いフレーズは 1〜2秒がおすすめ",
                            )
                            create_loop_btn = gr.Button("🔁 シームレスループWAVを作成・保存", variant="primary")

                        with gr.Tab("🌊 フェードイン / フェードアウト"):
                            gr.Markdown("曲の始まりや終わりに自然なS字カーブ（Raised Cosine）フェードを付与して保存します。")
                            with gr.Row():
                                fade_in_slider = gr.Slider(
                                    minimum=0.0,
                                    maximum=10.0,
                                    value=2.0,
                                    step=0.5,
                                    label="フェードイン (秒)",
                                )
                                fade_out_slider = gr.Slider(
                                    minimum=0.0,
                                    maximum=10.0,
                                    value=3.0,
                                    step=0.5,
                                    label="フェードアウト (秒)",
                                )
                            apply_fade_btn = gr.Button("🌊 フェード加工WAVを作成・保存", variant="primary")

                # History Gallery Section
                with gr.Accordion("📜 生成履歴 (History Gallery)", open=True):
                    with gr.Row():
                        history_dropdown = gr.Dropdown(
                            label="過去の生成音源を選択 (クリックで試聴)",
                            choices=get_history_choices(),
                            value=None,
                            interactive=True,
                            allow_custom_value=True,
                            scale=8,
                        )
                        refresh_history_btn = gr.Button("🔄 更新", size="sm", scale=2)

                    with gr.Row():
                        restore_btn = gr.Button(
                            "📋 選択した音源の設定を入力フォームに復元", variant="secondary"
                        )
                        set_as_init_audio_btn = gr.Button(
                            "🔄 選択した音源を「参考音源」にセット", variant="secondary"
                        )

        # Dynamic interactivity: Enable seed_input only when random_seed is False
        random_seed.change(
            fn=lambda is_random: gr.update(interactive=not is_random),
            inputs=[random_seed],
            outputs=[seed_input],
        )

        # Tab Selection Events: Auto-switch mode & model when preset tabs are clicked
        music_tab.select(
            fn=lambda cur_dur, takes: get_mode_sync_updates(config.model_id, cur_dur, takes),
            inputs=[duration, num_takes],
            outputs=[mode_radio, model_select, bpm, duration, generate_btn, status_text],
        )
        sfx_tab.select(
            fn=lambda cur_dur, takes: get_mode_sync_updates(config.sfx_model_id, cur_dur, takes),
            inputs=[duration, num_takes],
            outputs=[mode_radio, model_select, bpm, duration, generate_btn, status_text],
        )

        # Mode Radio Selection Event (Always-visible toggle on main UI)
        mode_radio.change(
            fn=lambda m, cur_dur, takes: get_mode_sync_updates(m, cur_dur, takes),
            inputs=[mode_radio, duration, num_takes],
            outputs=[mode_radio, model_select, bpm, duration, generate_btn, status_text],
        )

        # Model selection dynamic update from Advanced Settings dropdown
        model_select.change(
            fn=lambda m, cur_dur, takes: get_mode_sync_updates(m, cur_dur, takes),
            inputs=[model_select, duration, num_takes],
            outputs=[mode_radio, model_select, bpm, duration, generate_btn, status_text],
        )

        # Dynamic update on take count change
        num_takes.change(
            fn=lambda takes, m: gr.update(value=get_generate_btn_label(takes, m)),
            inputs=[num_takes, model_select],
            outputs=[generate_btn],
        )

        # Style preset button actions (Music)
        for p in PRESETS:
            preset_buttons[p.id].click(
                fn=lambda preset=p: (
                    preset.prompt,
                    preset.negative_prompt,
                    gr.update(value=preset.bpm, visible=True),
                    gr.update(maximum=config.max_duration, value=preset.duration, info="5秒〜360秒（最大6分）"),
                    config.model_id,
                    config.model_id,
                    gr.update(value="🎼 音楽を生成する (Mediumモデル)"),
                    f"🎨 音楽プリセット「{preset.display_label}」を反映しました（BPM: {preset.bpm}, {preset.duration}秒）",
                ),
                inputs=[],
                outputs=[prompt, negative_prompt, bpm, duration, mode_radio, model_select, generate_btn, status_text],
            )

        # Style preset button actions (SFX / Ambience)
        for p in SFX_PRESETS:
            preset_buttons[p.id].click(
                fn=lambda preset=p: (
                    preset.prompt,
                    preset.negative_prompt,
                    gr.update(value=config.default_bpm, visible=False),
                    gr.update(
                        maximum=config.sfx_max_duration,
                        value=min(preset.duration, config.sfx_max_duration),
                        info="5秒〜120秒（効果音モデル上限: 最大2分）",
                    ),
                    config.sfx_model_id,
                    config.sfx_model_id,
                    gr.update(value="🍃 効果音を生成する (Small SFXモデル)"),
                    f"🍃 効果音プリセット「{preset.display_label}」を反映しました（モデル: Small SFX 自動選択, BPMオフ）",
                ),
                inputs=[],
                outputs=[prompt, negative_prompt, bpm, duration, mode_radio, model_select, generate_btn, status_text],
            )

        # Prompt Enhance & Clear actions
        enhance_prompt_btn.click(
            fn=handle_enhance_prompt,
            inputs=[prompt, model_select, bpm],
            outputs=[prompt, negative_prompt, bpm, status_text],
        )

        clear_prompt_btn.click(
            fn=lambda: ("", "", "🧹 プロンプトとネガティブプロンプトをクリアしました。"),
            inputs=[],
            outputs=[prompt, negative_prompt, status_text],
        )

        # Clear init_audio action
        clear_init_audio_btn.click(
            fn=lambda: (None, "🧹 参考音源をクリアしました（Text-to-Audioモード）"),
            inputs=[],
            outputs=[init_audio, status_text],
        )

        # Generate action (Single or Multi-Take Audition Feed)
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
                init_audio,
                init_noise_level,
                num_takes,
            ],
            outputs=[
                status_text,
                history_dropdown,
                active_audio_target,
                active_target_display,
                take_card_1,
                take_title_1,
                take_player_1,
                take_meta_1,
                take_card_2,
                take_title_2,
                take_player_2,
                take_meta_2,
                take_card_3,
                take_title_3,
                take_player_3,
                take_meta_3,
                take_card_4,
                take_title_4,
                take_player_4,
                take_meta_4,
            ],
        )

        # Adopt Take button actions
        select_take_1_btn.click(
            fn=lambda a: on_adopt_take(1, a),
            inputs=[take_player_1],
            outputs=[active_audio_target, active_target_display, status_text, history_dropdown],
        )
        select_take_2_btn.click(
            fn=lambda a: on_adopt_take(2, a),
            inputs=[take_player_2],
            outputs=[active_audio_target, active_target_display, status_text, history_dropdown],
        )
        select_take_3_btn.click(
            fn=lambda a: on_adopt_take(3, a),
            inputs=[take_player_3],
            outputs=[active_audio_target, active_target_display, status_text, history_dropdown],
        )
        select_take_4_btn.click(
            fn=lambda a: on_adopt_take(4, a),
            inputs=[take_player_4],
            outputs=[active_audio_target, active_target_display, status_text, history_dropdown],
        )

        # History Gallery Actions
        history_dropdown.input(
            fn=on_select_history,
            inputs=[history_dropdown],
            outputs=[
                status_text,
                active_audio_target,
                active_target_display,
                take_card_1,
                take_title_1,
                take_player_1,
                take_meta_1,
                take_card_2,
                take_card_3,
                take_card_4,
            ],
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
                mode_radio,
                model_select,
                generate_btn,
                init_audio,
                init_noise_level,
                status_text,
            ],
        )

        set_as_init_audio_btn.click(
            fn=lambda file_path: (
                file_path,
                gr.update(open=True),
                f"🔄 履歴音源「{os.path.basename(file_path)}」を参考音源にセットしました！（プロンプトやアレンジ強度を設定して生成できます）",
            ) if file_path and os.path.exists(file_path) else (
                gr.update(),
                gr.update(),
                "⚠️ 履歴から音源を選択してください。",
            ),
            inputs=[history_dropdown],
            outputs=[init_audio, init_audio_accordion, status_text],
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

        # Post-Processing actions (Seamless Loop & Fade)
        create_loop_btn.click(
            fn=handle_create_loop,
            inputs=[active_audio_target, history_dropdown, crossfade_slider],
            outputs=[
                active_audio_target,
                active_target_display,
                take_player_1,
                status_text,
                history_dropdown,
                take_title_1,
                take_meta_1,
                take_card_1,
                take_card_2,
                take_card_3,
                take_card_4,
            ],
        )

        apply_fade_btn.click(
            fn=handle_apply_fade,
            inputs=[active_audio_target, history_dropdown, fade_in_slider, fade_out_slider],
            outputs=[
                active_audio_target,
                active_target_display,
                take_player_1,
                status_text,
                history_dropdown,
                take_title_1,
                take_meta_1,
                take_card_1,
                take_card_2,
                take_card_3,
                take_card_4,
            ],
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
            js=shutdown_js,
        )

    return demo
