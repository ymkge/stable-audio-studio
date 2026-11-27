"""History and metadata management for generated audio in Stable Audio Studio."""

from dataclasses import dataclass, asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json
import re


@dataclass
class HistoryItem:
    file_path: str
    filename: str
    created_at: str
    bpm: int
    duration: int
    prompt: str
    negative_prompt: str
    seed: int
    model_id: str
    init_audio_filename: Optional[str] = None
    init_noise_level: Optional[float] = None
    is_seamless_loop: bool = False
    crossfade_seconds: Optional[float] = None
    fade_in_seconds: Optional[float] = None
    fade_out_seconds: Optional[float] = None
    take_index: Optional[int] = None
    total_takes: Optional[int] = None

    @property
    def display_label(self) -> str:
        """Formatted human-readable label for UI selection."""
        # e.g., "11/12 23:45 | 120 BPM (30s) | Chill Lo-Fi beat... [s:42]"
        # or    "11/12 23:45 | 🎲 T1/4 120 BPM (30s) | Chill Lo-Fi beat... [s:42]"
        # or    "11/12 23:45 | 🔁 Loop SFX (42s) | Gentle soothing rain... [s:42]"
        short_prompt = self.prompt.strip()
        if len(short_prompt) > 35:
            short_prompt = short_prompt[:32] + "..."
        
        tag_parts = []
        if self.is_seamless_loop or self.filename.endswith("_loop.wav"):
            tag_parts.append("🔁 Loop")
        elif self.fade_in_seconds or self.fade_out_seconds or self.filename.endswith("_fade.wav"):
            tag_parts.append("🌊 Fade")
        elif self.init_audio_filename:
            tag_parts.append("🔄 Remix")

        if self.total_takes and self.total_takes > 1 and self.take_index:
            tag_parts.append(f"🎲 T{self.take_index}/{self.total_takes}")

        prefix = f"{' '.join(tag_parts)} " if tag_parts else ""

        if self.bpm and self.bpm > 0 and "sfx" not in self.model_id.lower():
            return f"{self.created_at} | {prefix}{self.bpm} BPM ({self.duration}s) | {short_prompt} [seed: {self.seed}]"
        mode_str = f"{prefix}SFX" if prefix else "SFX"
        return f"{self.created_at} | {mode_str} ({self.duration}s) | {short_prompt} [seed: {self.seed}]"


def save_metadata(
    wav_path: Path,
    prompt: str,
    negative_prompt: str,
    bpm: int,
    duration: int,
    seed: int,
    model_id: str,
    init_audio_filename: Optional[str] = None,
    init_noise_level: Optional[float] = None,
    take_index: Optional[int] = None,
    total_takes: Optional[int] = None,
) -> Path:
    """Saves sidecar JSON metadata alongside the generated WAV file."""
    meta_path = wav_path.with_suffix(".json")
    created_at = datetime.fromtimestamp(wav_path.stat().st_mtime).strftime("%Y/%m/%d %H:%M")
    
    data = {
        "file_path": str(wav_path),
        "filename": wav_path.name,
        "created_at": created_at,
        "bpm": bpm,
        "duration": duration,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "seed": seed,
        "model_id": model_id,
        "init_audio_filename": init_audio_filename,
        "init_noise_level": init_noise_level,
        "take_index": take_index,
        "total_takes": total_takes,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return meta_path


def parse_from_filename(wav_path: Path) -> HistoryItem:
    """Fallback parser when sidecar JSON metadata is missing."""
    # Music: YYYYMMDD_HHMMSS_{bpm}bpm_{duration}s_{prompt_summary}_s{seed}(_t{take}).wav
    # SFX:   YYYYMMDD_HHMMSS_sfx_{duration}s_{prompt_summary}_s{seed}(_t{take}).wav
    filename = wav_path.name
    clean_stem = filename.removesuffix(".wav")
    is_loop = clean_stem.endswith("_loop")
    is_fade = clean_stem.endswith("_fade")
    normalized_name = re.sub(r"_(loop|fade)$", "", clean_stem)

    # Check for optional take suffix: _t1, _t2, etc.
    take_index = None
    take_match = re.search(r"_t(\d+)$", normalized_name)
    if take_match:
        take_index = int(take_match.group(1))
        normalized_name = normalized_name[:take_match.start()]

    normalized_name += ".wav"

    pattern_music = r"^(\d{8})_(\d{4,6})_(\d+)bpm_(\d+)s_(.*)_s(\d+)\.wav$"
    pattern_sfx = r"^(\d{8})_(\d{4,6})_sfx_(\d+)s_(.*)_s(\d+)\.wav$"

    match_music = re.match(pattern_music, normalized_name)
    match_sfx = re.match(pattern_sfx, normalized_name)

    try:
        created_at = datetime.fromtimestamp(wav_path.stat().st_mtime).strftime("%Y/%m/%d %H:%M")
    except (OSError, FileNotFoundError):
        created_at = datetime.now().strftime("%Y/%m/%d %H:%M")

    model_id = "stabilityai/stable-audio-3-medium"
    negative_prompt = ""

    if match_music:
        date_str, time_str, bpm_str, dur_str, prompt_slug, seed_str = match_music.groups()
        bpm = int(bpm_str)
        duration = int(dur_str)
        seed = int(seed_str)
        prompt = prompt_slug.replace("_", " ")
    elif match_sfx:
        date_str, time_str, dur_str, prompt_slug, seed_str = match_sfx.groups()
        bpm = 0
        duration = int(dur_str)
        seed = int(seed_str)
        prompt = prompt_slug.replace("_", " ")
        model_id = "stabilityai/stable-audio-3-small-sfx"
    else:
        bpm = 120
        duration = 30
        seed = 0
        prompt = filename

    return HistoryItem(
        file_path=str(wav_path),
        filename=filename,
        created_at=created_at,
        bpm=bpm,
        duration=duration,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        model_id=model_id,
        is_seamless_loop=is_loop,
        fade_in_seconds=2.0 if is_fade else None,
        fade_out_seconds=3.0 if is_fade else None,
        take_index=take_index,
        total_takes=4 if take_index else None,
    )


def load_history(output_dir: Path) -> List[HistoryItem]:
    """Loads all generated audio records from output directory, sorted newest first."""
    if not output_dir.exists():
        return []

    wav_files = sorted(
        output_dir.glob("*.wav"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    valid_keys = {f.name for f in fields(HistoryItem)}
    items: List[HistoryItem] = []
    for wav_path in wav_files:
        json_path = wav_path.with_suffix(".json")
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                    items.append(HistoryItem(**filtered_data))
                    continue
            except Exception:
                pass
        # Fallback to filename parsing
        items.append(parse_from_filename(wav_path))

    return items
