"""History and metadata management for generated audio in Stable Audio Studio."""

from dataclasses import dataclass, asdict
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

    @property
    def display_label(self) -> str:
        """Formatted human-readable label for UI selection."""
        # e.g., "11/12 23:45 | 120 BPM (30s) | Chill Lo-Fi beat... [s:42]"
        short_prompt = self.prompt.strip()
        if len(short_prompt) > 35:
            short_prompt = short_prompt[:32] + "..."
        return f"{self.created_at} | {self.bpm} BPM ({self.duration}s) | {short_prompt} [seed: {self.seed}]"


def save_metadata(
    wav_path: Path,
    prompt: str,
    negative_prompt: str,
    bpm: int,
    duration: int,
    seed: int,
    model_id: str,
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
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return meta_path


def parse_from_filename(wav_path: Path) -> HistoryItem:
    """Fallback parser when sidecar JSON metadata is missing."""
    # Pattern: YYYYMMDD_HHMMSS_{bpm}bpm_{duration}s_{prompt_summary}_s{seed}.wav
    filename = wav_path.name
    pattern = r"^(\d{8})_(\d{4,6})_(\d+)bpm_(\d+)s_(.*)_s(\d+)\.wav$"
    match = re.match(pattern, filename)

    created_at = datetime.fromtimestamp(wav_path.stat().st_mtime).strftime("%Y/%m/%d %H:%M")
    if match:
        date_str, time_str, bpm_str, dur_str, prompt_slug, seed_str = match.groups()
        bpm = int(bpm_str)
        duration = int(dur_str)
        seed = int(seed_str)
        prompt = prompt_slug.replace("_", " ")
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
        negative_prompt="",
        seed=seed,
        model_id="stabilityai/stable-audio-3-medium",
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

    items: List[HistoryItem] = []
    for wav_path in wav_files:
        json_path = wav_path.with_suffix(".json")
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items.append(HistoryItem(**data))
                    continue
            except Exception:
                pass
        # Fallback to filename parsing
        items.append(parse_from_filename(wav_path))

    return items
