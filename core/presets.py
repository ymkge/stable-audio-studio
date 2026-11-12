"""Style presets configuration for Stable Audio Studio."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class StylePreset:
    id: str
    name: str
    icon: str
    prompt: str
    negative_prompt: str
    bpm: int
    duration: int

    @property
    def display_label(self) -> str:
        return f"{self.icon} {self.name}"


PRESETS: List[StylePreset] = [
    StylePreset(
        id="lofi",
        name="Lo-Fi Chill",
        icon="☕",
        prompt="Chill Lo-Fi hip hop beat, mellow electric piano chords, warm vintage bassline, subtle vinyl crackle, relaxed downtempo drums",
        negative_prompt="distortion, harsh noise, vocals, aggressive, clipping, fast tempo",
        bpm=85,
        duration=30,
    ),
    StylePreset(
        id="ambient",
        name="Ambient / Meditation",
        icon="🌌",
        prompt="Calm ambient soundscape, lush evolving synth pads, ethereal atmospheric texture, delicate shimmering chimes, peaceful meditation music",
        negative_prompt="drums, percussion, fast beat, distortion, vocals, loud",
        bpm=60,
        duration=45,
    ),
    StylePreset(
        id="synthwave",
        name="80s Synthwave",
        icon="🌆",
        prompt="80s retro synthwave, driving analog synth bassline, vintage gated reverb drums, neon cyberpunk melody, nostalgic arpeggio leads",
        negative_prompt="acoustic instruments, folk, vocal singing, low quality, noise",
        bpm=120,
        duration=30,
    ),
    StylePreset(
        id="cinematic",
        name="Cinematic Orchestral",
        icon="🎬",
        prompt="Epic cinematic film score, powerful soaring orchestral strings, deep brass swells, dramatic timpani and percussion, inspiring atmosphere",
        negative_prompt="electronic synthesizer, lo-fi, vocals, distortion, clipping",
        bpm=110,
        duration=45,
    ),
    StylePreset(
        id="acoustic",
        name="Acoustic Folk",
        icon="🌿",
        prompt="Warm acoustic guitar fingerpicking, gentle wooden percussion, uplifting organic folk melody, sunny morning relaxed atmosphere",
        negative_prompt="electronic synths, heavy drums, distortion, electric guitar, vocals",
        bpm=95,
        duration=30,
    ),
    StylePreset(
        id="jazz",
        name="Lounge Jazz",
        icon="🎷",
        prompt="Smooth lounge jazz, warm upright acoustic bass, soft brush snare rhythm, cozy electric piano chords, sophisticated cafe background music",
        negative_prompt="heavy metal, rock, EDM, aggressive, loud, vocals",
        bpm=100,
        duration=30,
    ),
]

PRESET_MAP: Dict[str, StylePreset] = {p.id: p for p in PRESETS}
