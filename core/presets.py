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
    category: str = "music"

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
        category="music",
    ),
    StylePreset(
        id="ambient",
        name="Ambient / Meditation",
        icon="🌌",
        prompt="Calm ambient soundscape, lush evolving synth pads, ethereal atmospheric texture, delicate shimmering chimes, peaceful meditation music",
        negative_prompt="drums, percussion, fast beat, distortion, vocals, loud",
        bpm=60,
        duration=45,
        category="music",
    ),
    StylePreset(
        id="synthwave",
        name="80s Synthwave",
        icon="🌆",
        prompt="80s retro synthwave, driving analog synth bassline, vintage gated reverb drums, neon cyberpunk melody, nostalgic arpeggio leads",
        negative_prompt="acoustic instruments, folk, vocal singing, low quality, noise",
        bpm=120,
        duration=30,
        category="music",
    ),
    StylePreset(
        id="cinematic",
        name="Cinematic Orchestral",
        icon="🎬",
        prompt="Epic cinematic film score, powerful soaring orchestral strings, deep brass swells, dramatic timpani and percussion, inspiring atmosphere",
        negative_prompt="electronic synthesizer, lo-fi, vocals, distortion, clipping",
        bpm=110,
        duration=45,
        category="music",
    ),
    StylePreset(
        id="acoustic",
        name="Acoustic Folk",
        icon="🌿",
        prompt="Warm acoustic guitar fingerpicking, gentle wooden percussion, uplifting organic folk melody, sunny morning relaxed atmosphere",
        negative_prompt="electronic synths, heavy drums, distortion, electric guitar, vocals",
        bpm=95,
        duration=30,
        category="music",
    ),
    StylePreset(
        id="jazz",
        name="Lounge Jazz",
        icon="🎷",
        prompt="Smooth lounge jazz, warm upright acoustic bass, soft brush snare rhythm, cozy electric piano chords, sophisticated cafe background music",
        negative_prompt="heavy metal, rock, EDM, aggressive, loud, vocals",
        bpm=100,
        duration=30,
        category="music",
    ),
]

SFX_PRESETS: List[StylePreset] = [
    StylePreset(
        id="sfx_rain",
        name="優しい雨音",
        icon="🌧️",
        prompt="Gentle soothing rainfall, soft rain falling continuously, calm ambient rain sounds, peaceful white noise",
        negative_prompt="thunder, lightning, loud wind, storm, music, voices, distortion",
        bpm=0,
        duration=45,
        category="sfx",
    ),
    StylePreset(
        id="sfx_stream",
        name="川のせせらぎ",
        icon="🏞️",
        prompt="Gentle flowing stream in nature, crystal clear babbling brook, soothing running river water, relaxing natural ambient sound",
        negative_prompt="loud splash, waterfall roaring, music, talking, distortion, machine noise",
        bpm=0,
        duration=45,
        category="sfx",
    ),
    StylePreset(
        id="sfx_fire",
        name="暖炉・焚き火",
        icon="🔥",
        prompt="Cozy crackling fireplace, warm gentle campfire flames, soft wood popping embers, peaceful warmth ambience",
        negative_prompt="loud explosion, roaring inferno, music, speaking, noise",
        bpm=0,
        duration=45,
        category="sfx",
    ),
    StylePreset(
        id="sfx_waves",
        name="穏やかな波音",
        icon="🌊",
        prompt="Calm gentle ocean waves, soft rhythmic water lapping on a quiet sandy beach, soothing nature white noise",
        negative_prompt="storm, rough seas, loud screech, harsh wind, music, voices",
        bpm=0,
        duration=45,
        category="sfx",
    ),
    StylePreset(
        id="sfx_forest",
        name="静かな森の自然音",
        icon="🌲",
        prompt="Peaceful quiet forest nature sounds, subtle gentle breeze through green leaves, distant soft bird singing, tranquil atmosphere",
        negative_prompt="loud screech, chainsaw, footsteps, music, heavy rain",
        bpm=0,
        duration=45,
        category="sfx",
    ),
    StylePreset(
        id="sfx_keyboard",
        name="作業用タイピング音",
        icon="⌨️",
        prompt="Subtle mechanical keyboard typing sounds, rhythmic soft key clicks, quiet study room ASMR ambience",
        negative_prompt="loud slamming, mouse clicking, speech, music, distortion",
        bpm=0,
        duration=30,
        category="sfx",
    ),
]

ALL_PRESETS: List[StylePreset] = PRESETS + SFX_PRESETS
PRESET_MAP: Dict[str, StylePreset] = {p.id: p for p in ALL_PRESETS}
