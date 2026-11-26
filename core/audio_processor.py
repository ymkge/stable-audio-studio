"""Audio Post-Processor module for Stable Audio Studio.

Provides seamless looping and smooth fade-in/fade-out audio processing
using mathematically optimal equal-power crossfading and smooth S-curves.
"""

from pathlib import Path
from typing import Optional, Tuple
import json
import math
import numpy as np
import soundfile as sf

from core.history import save_metadata


def load_audio_numpy(file_path: str) -> Tuple[np.ndarray, int]:
    """Loads an audio file into numpy array (samples, channels) and sample_rate."""
    data, sr = sf.read(file_path)
    if data.ndim == 1:
        # Convert mono to stereo for consistent studio output
        data = np.column_stack([data, data])
    return data, sr


def create_seamless_loop(
    audio_path: str,
    crossfade_duration: float = 3.0,
    output_path: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Creates a perfectly seamless, click-free infinite loop audio file
    using equal-power crossfading.

    The algorithm blends the end of the track into the beginning,
    ensuring mathematical continuity across the loop boundary with
    no volume dips or phase cancellation.

    Args:
        audio_path: Path to the source WAV/audio file.
        crossfade_duration: Crossfade duration in seconds (default: 3.0s).
        output_path: Optional output path. If None, appends '_loop.wav' to source.

    Returns:
        Tuple[str, str]: (output_wav_path, status_message)
    """
    src_path = Path(audio_path)
    if not src_path.exists():
        raise FileNotFoundError(f"音声ファイルが見つかりません: {audio_path}")

    audio_data, sr = load_audio_numpy(str(src_path))
    total_samples = len(audio_data)
    total_duration = total_samples / sr

    # Validate crossfade duration
    max_allowed_crossfade = total_duration / 2.5
    actual_crossfade_sec = min(crossfade_duration, max_allowed_crossfade)
    fade_samples = int(actual_crossfade_sec * sr)

    if fade_samples <= 0 or total_samples <= 2 * fade_samples:
        raise ValueError(
            f"音源の長さ ({total_duration:.1f}秒) が短すぎるため、クロスフェード処理を行えません。"
        )

    # Split audio:
    # Head: [0 : fade_samples]
    # Body: [fade_samples : total_samples - fade_samples]
    # Tail: [total_samples - fade_samples : total_samples]
    body = audio_data[fade_samples : total_samples - fade_samples]
    tail = audio_data[total_samples - fade_samples :]
    head = audio_data[:fade_samples]

    # Equal-power crossfade weights: cos^2(t) + sin^2(t) = 1
    t = np.linspace(0.0, 1.0, fade_samples, endpoint=True)
    fade_out = np.cos(t * (math.pi / 2.0))[:, np.newaxis]  # Tail fades out (1 -> 0)
    fade_in = np.sin(t * (math.pi / 2.0))[:, np.newaxis]   # Head fades in (0 -> 1)

    blended_transition = (tail * fade_out) + (head * fade_in)

    # Final looped audio: [Body, Blended Transition]
    # At the loop boundary (from Blended Transition end to Body start),
    # the waveform naturally connects exactly at audio_data[fade_samples],
    # eliminating all clicks and frequency jumps.
    looped_audio = np.concatenate([body, blended_transition], axis=0)

    # Determine destination
    if output_path:
        out_wav = Path(output_path)
    else:
        out_wav = src_path.parent / f"{src_path.stem}_loop.wav"

    sf.write(str(out_wav), looped_audio, sr)

    # Copy and update sidecar JSON metadata if present
    src_json = src_path.with_suffix(".json")
    if src_json.exists():
        try:
            with open(src_json, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["file_path"] = str(out_wav)
            meta["filename"] = out_wav.name
            meta["duration"] = int(len(looped_audio) / sr)
            meta["is_seamless_loop"] = True
            meta["crossfade_seconds"] = round(actual_crossfade_sec, 2)
            out_json = out_wav.with_suffix(".json")
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Failed to copy metadata for looped audio: {e}")

    new_duration = len(looped_audio) / sr
    msg = f"🔁 シームレスループ音源を作成しました（{new_duration:.1f}秒, クロスフェード: {actual_crossfade_sec:.1f}秒）: {out_wav.name}"
    return str(out_wav), msg


def apply_fade(
    audio_path: str,
    fade_in_sec: float = 2.0,
    fade_out_sec: float = 3.0,
    output_path: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Applies smooth S-curve (raised cosine) fade-in and fade-out to an audio file.

    Args:
        audio_path: Path to the source WAV/audio file.
        fade_in_sec: Fade-in duration in seconds.
        fade_out_sec: Fade-out duration in seconds.
        output_path: Optional output path. If None, appends '_fade.wav' to source.

    Returns:
        Tuple[str, str]: (output_wav_path, status_message)
    """
    src_path = Path(audio_path)
    if not src_path.exists():
        raise FileNotFoundError(f"音声ファイルが見つかりません: {audio_path}")

    audio_data, sr = load_audio_numpy(str(src_path))
    total_samples = len(audio_data)
    total_duration = total_samples / sr

    # Copy audio buffer to avoid mutating
    faded_audio = audio_data.copy()

    # Calculate fade samples
    in_samples = int(fade_in_sec * sr)
    out_samples = int(fade_out_sec * sr)

    # Clamp if sum of fades exceeds duration
    if in_samples + out_samples > total_samples:
        scale = total_samples / (in_samples + out_samples)
        in_samples = int(in_samples * scale)
        out_samples = int(out_samples * scale)

    # Smooth S-curve (Hanning window curve: 0.5 * (1 - cos(pi * t)))
    if in_samples > 0:
        t_in = np.linspace(0.0, 1.0, in_samples, endpoint=True)
        curve_in = (0.5 * (1.0 - np.cos(math.pi * t_in)))[:, np.newaxis]
        faded_audio[:in_samples] *= curve_in

    if out_samples > 0:
        t_out = np.linspace(0.0, 1.0, out_samples, endpoint=True)
        curve_out = (0.5 * (1.0 + np.cos(math.pi * t_out)))[:, np.newaxis]
        faded_audio[total_samples - out_samples :] *= curve_out

    # Determine destination
    if output_path:
        out_wav = Path(output_path)
    else:
        out_wav = src_path.parent / f"{src_path.stem}_fade.wav"

    sf.write(str(out_wav), faded_audio, sr)

    # Copy and update sidecar JSON metadata if present
    src_json = src_path.with_suffix(".json")
    if src_json.exists():
        try:
            with open(src_json, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["file_path"] = str(out_wav)
            meta["filename"] = out_wav.name
            meta["fade_in_seconds"] = round(fade_in_sec, 2)
            meta["fade_out_seconds"] = round(fade_out_sec, 2)
            out_json = out_wav.with_suffix(".json")
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Failed to copy metadata for faded audio: {e}")

    msg = f"🌊 フェード加工音源を作成しました（Fade In: {fade_in_sec:.1f}秒, Fade Out: {fade_out_sec:.1f}秒）: {out_wav.name}"
    return str(out_wav), msg
