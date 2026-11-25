"""Prompt Enhancer engine for Stable Audio Studio.

Expands Japanese keywords, short phrases, and English concepts into rich,
production-ready prompts and negative prompts tailored for Stable Audio 3.
Runs completely offline without external APIs or dependencies.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import re

from core.generator import is_sfx_model


@dataclass
class EnhancedPromptResult:
    prompt: str
    negative_prompt: str
    suggested_bpm: Optional[int] = None
    applied_tags: List[str] = None


# Music category keywords (Japanese regex / English terms -> descriptor dict)
MUSIC_GENRES = [
    {
        "id": "lofi",
        "patterns": [r"lo-?fi", r"ローファイ", r"チル", r"chill", r"勉強", r"作業用", r"作業"],
        "prompt": "chill lo-fi hip hop beat, mellow electric piano chords, warm vintage bassline, subtle vinyl crackle, relaxed downtempo drums",
        "negative": "distortion, harsh noise, vocals, aggressive, clipping, fast tempo, heavy metal",
        "bpm": 85,
        "tag": "Lo-Fi Chill",
    },
    {
        "id": "jazz",
        "patterns": [r"ジャズ", r"jazz", r"カフェ", r"cafe", r"喫茶店", r"ラウンジ", r"lounge", r"バー"],
        "prompt": "sophisticated cozy cafe lounge jazz, warm upright acoustic bass, soft brush snare rhythm, sweet electric piano melody, coffee shop ambience",
        "negative": "heavy metal, aggressive EDM, loud synth, distortion, clipping, singing, harsh noise",
        "bpm": 100,
        "tag": "Lounge Jazz",
    },
    {
        "id": "ambient",
        "patterns": [r"アンビエント", r"ambient", r"瞑想", r"meditation", r"睡眠", r"癒やし", r"癒し", r"ヒーリング", r"リラックス"],
        "prompt": "deep atmospheric ambient soundscape, lush evolving synth pads, ethereal texture, delicate shimmering chimes, peaceful meditation music",
        "negative": "drums, heavy percussion, fast beat, distortion, vocals, loud, aggressive",
        "bpm": 60,
        "tag": "Ambient / Meditation",
    },
    {
        "id": "synthwave",
        "patterns": [r"シンセウェーブ", r"synthwave", r"80年代", r"80s", r"サイバーパンク", r"cyberpunk", r"レトロ", r"ドライブ"],
        "prompt": "80s retro synthwave, driving analog synth bassline, vintage gated reverb drums, neon cyberpunk melody, nostalgic arpeggio leads",
        "negative": "acoustic instruments, folk, vocal singing, low quality, noise, distortion",
        "bpm": 120,
        "tag": "80s Synthwave",
    },
    {
        "id": "cinematic",
        "patterns": [r"シネマティック", r"cinematic", r"オーケストラ", r"orchestral", r"映画", r"壮大", r"epic", r"劇伴", r"ファンタジー"],
        "prompt": "epic cinematic film score, powerful soaring orchestral strings, deep brass swells, dramatic timpani and percussion, inspiring atmosphere",
        "negative": "electronic synthesizer, lo-fi, vocals, distortion, clipping, harsh synth",
        "bpm": 110,
        "tag": "Cinematic Orchestral",
    },
    {
        "id": "acoustic",
        "patterns": [r"アコースティック", r"acoustic", r"フォーク", r"folk", r"ギター", r"弾き語り", r"爽やか", r"朝"],
        "prompt": "warm acoustic guitar fingerpicking, gentle wooden percussion, uplifting organic folk melody, sunny morning relaxed atmosphere",
        "negative": "electronic synths, heavy drums, distortion, electric guitar, vocals, clipping",
        "bpm": 95,
        "tag": "Acoustic Folk",
    },
    {
        "id": "piano",
        "patterns": [r"ピアノ", r"piano", r"クラシック", r"classical", r"エモい", r"切ない", r"感動"],
        "prompt": "emotional neoclassical solo piano, gentle felt acoustic piano melody, subtle room reverb, expressive dynamics, introspective peaceful atmosphere",
        "negative": "fast drums, loud electronic synths, distortion, vocals, harsh sounds",
        "bpm": 75,
        "tag": "Neoclassical Piano",
    },
    {
        "id": "edm",
        "patterns": [r"edm", r"ダンス", r"dance", r"クラブ", r"club", r"ハウス", r"house", r"テクノ", r"techno", r"フェス"],
        "prompt": "high-energy modern electronic dance music, driving four-on-the-floor kick, euphoric synth leads, energetic bassline, crisp percussion",
        "negative": "acoustic, quiet, low fidelity, distortion, muddy bass, clipping",
        "bpm": 128,
        "tag": "Energetic EDM",
    },
    {
        "id": "rock",
        "patterns": [r"ロック", r"rock", r"バンド", r"band", r"激しい", r"エネルギッシュ"],
        "prompt": "dynamic modern indie rock, driving energetic electric guitar riffs, punchy acoustic drums, melodic bassline, vibrant power chords",
        "negative": "electronic EDM synth, hip hop beat, lo-fi, distortion, clipping, vocals",
        "bpm": 130,
        "tag": "Indie Rock",
    },
    {
        "id": "japanese",
        "patterns": [r"和風", r"和", r"日本", r"japan", r"琴", r"尺八", r"祭り"],
        "prompt": "traditional Japanese neo-classical fusion, elegant koto melody, gentle shakuhachi flute, subtle ambient wooden percussion, meditative peaceful calm",
        "negative": "heavy metal, aggressive EDM, loud synth, distortion, clipping, singing",
        "bpm": 80,
        "tag": "Traditional Japanese",
    },
]

# SFX / Ambience category keywords
SFX_GENRES = [
    {
        "id": "owl_forest",
        "patterns": [r"フクロウ", r"ふくろう", r"owl", r"みみずく"],
        "prompt": "Autumn nocturnal forest ambience, crisp cool evening breeze gently rustling dry leaves and bare branches, solitary soft deep owl hooting, calm rhythmic 'hoo hoo' owl call echoing in the distance, peaceful nocturnal woods, quiet atmospheric ASMR",
        "negative": "birds, birdsong, chirping, daytime birds, bird tweet, screech, screech owl, shrieking, music, melody, drums, talking, footsteps, distortion",
        "tag": "Night Forest & Owl",
    },
    {
        "id": "rain",
        "patterns": [r"雨", r"雨音", r"rain", r"梅雨", r"しとしと", r"雫"],
        "prompt": "Gentle soothing rainfall, soft rain falling continuously on leaves and ground, calm ambient rain sounds, peaceful relaxing nature white noise",
        "negative": "thunder, lightning, loud wind, storm, music, melody, voices, distortion, harsh noise",
        "tag": "Gentle Rain",
    },
    {
        "id": "stream",
        "patterns": [r"川", r"せせらぎ", r"水", r"stream", r"river", r"brook", r"清流", r"小川"],
        "prompt": "Gentle flowing stream in nature, crystal clear babbling brook, soothing running river water, relaxing natural ambient sound, fresh nature atmosphere",
        "negative": "loud splash, waterfall roaring, music, melody, talking, distortion, machine noise",
        "tag": "Gentle Stream",
    },
    {
        "id": "fire",
        "patterns": [r"焚き火", r"たき火", r"焚火", r"暖炉", r"火", r"fire", r"campfire", r"fireplace", r"パチパチ"],
        "prompt": "Cozy crackling fireplace, warm gentle campfire flames, soft wood popping embers, peaceful warmth ambience, relaxing evening atmosphere",
        "negative": "loud explosion, roaring inferno, music, melody, speaking, screams, distortion",
        "tag": "Cozy Fireplace",
    },
    {
        "id": "waves",
        "patterns": [r"波", r"海", r"波音", r"beach", r"waves", r"ocean", r"海岸", r"砂浜"],
        "prompt": "Calm gentle ocean waves, soft rhythmic water lapping on a quiet sandy beach, soothing nature white noise, distant ocean breeze",
        "negative": "storm, rough seas, loud screech, harsh wind, seagulls screeching, music, voices, distortion",
        "tag": "Calm Ocean Waves",
    },
    {
        "id": "forest",
        "patterns": [r"森", r"森林", r"forest", r"wood", r"木々", r"自然", r"nature", r"風"],
        "prompt": "Peaceful quiet forest nature sounds, subtle gentle breeze swaying green leaves and tree branches, distant soft ambient rustling, tranquil atmosphere",
        "negative": "loud screech, chainsaw, footsteps, music, melody, heavy rain, loud bird screaming",
        "tag": "Quiet Forest",
    },
    {
        "id": "typing",
        "patterns": [r"タイピング", r"キーボード", r"typing", r"keyboard", r"パソコン", r"打鍵", r"カタカタ"],
        "prompt": "Satisfying mechanical keyboard typing sounds, crisp rhythmic keystrokes, tactile switches, quiet room desk study ambience, soothing ASMR trigger",
        "negative": "loud banging, mouse slamming, music, talking, background TV, distortion",
        "tag": "Keyboard ASMR",
    },
    {
        "id": "thunder",
        "patterns": [r"雷", r"thunder", r"嵐", r"storm", r"稲妻"],
        "prompt": "Atmospheric distant rolling thunderstorm, deep low rumble of thunder echoing across the sky, ambient rain showers, cinematic weather soundscape",
        "negative": "music, beats, melody, human voices, screaming, ear-splitting screech, distortion",
        "tag": "Distant Thunder",
    },
    {
        "id": "space",
        "patterns": [r"宇宙", r"space", r"ドローン", r"drone", r"sf", r"星", r"コズミック"],
        "prompt": "Deep cosmic space drone ambience, mysterious ethereal sub-bass rumble, sci-fi stellar void soundscape, expansive dark universe resonance",
        "negative": "music melody, acoustic drums, bright pop synths, voices, distortion",
        "tag": "Cosmic Space Drone",
    },
]

# Modifier descriptors to augment user terms
MOOD_MODIFIERS = [
    (r"夜|night|midnight|深夜", "nocturnal evening quiet atmosphere"),
    (r"朝|morning|夜明け", "fresh crisp morning atmosphere, gentle sunrise feel"),
    (r"夕方|sunset|黄昏|夕焼け", "warm golden hour dusk ambience, nostalgic feeling"),
    (r"神秘|mysterious|幻想", "mysterious mystical ethereal atmosphere"),
    (r"暗い|dark|重い", "dark moody dramatic undertones"),
    (r"明るい|bright|楽しい", "uplifting bright cheerful vibe"),
]


def enhance_prompt(
    user_input: str,
    model_id: str,
    current_bpm: int = 120,
) -> EnhancedPromptResult:
    """
    Enhances a user-provided keyword or sentence into a high-fidelity prompt
    and negative prompt customized for the active model (Music vs SFX).

    Args:
        user_input: The raw input from user (Japanese or English, words or sentences).
        model_id: The target model identifier (e.g. Medium vs Small SFX).
        current_bpm: Current BPM value from slider.

    Returns:
        EnhancedPromptResult containing improved prompt, negative prompt, suggested BPM and tags.
    """
    raw_text = user_input.strip()
    is_sfx = is_sfx_model(model_id)
    applied_tags: List[str] = []

    # If completely empty, provide an archetype default based on active mode
    if not raw_text:
        if is_sfx:
            return EnhancedPromptResult(
                prompt="Gentle ambient rain falling steadily, soft soothing raindrops on leaves and ground, cozy relaxing nature white noise, binaural ASMR, clean 4k audio",
                negative_prompt="music, melody, drums, heavy wind, human voice, talking, loud screech, distortion, noise",
                suggested_bpm=0,
                applied_tags=["雨音 (デフォルト)"],
            )
        else:
            return EnhancedPromptResult(
                prompt="Chill lo-fi hip hop beat, mellow electric piano chords, warm vintage bassline, subtle vinyl crackle, relaxed downtempo drums, high fidelity studio recording",
                negative_prompt="distortion, harsh noise, vocals, aggressive, clipping, fast tempo, heavy metal",
                suggested_bpm=85,
                applied_tags=["Lo-Fi (デフォルト)"],
            )

    matched_descriptors: List[str] = []
    matched_negatives: List[str] = []
    suggested_bpm = None

    categories = SFX_GENRES if is_sfx else MUSIC_GENRES

    # Check for category matches
    for cat in categories:
        for pat in cat["patterns"]:
            if re.search(pat, raw_text, re.IGNORECASE):
                matched_descriptors.append(cat["prompt"])
                matched_negatives.append(cat["negative"])
                if "bpm" in cat and suggested_bpm is None:
                    suggested_bpm = cat["bpm"]
                applied_tags.append(cat["tag"])
                break

    # Check mood modifiers
    extra_moods = []
    for pat, desc in MOOD_MODIFIERS:
        if re.search(pat, raw_text, re.IGNORECASE):
            extra_moods.append(desc)

    # Build enhanced prompt
    final_prompt_parts = []
    final_negative_parts = []

    if matched_descriptors:
        # We found recognized archetypes
        final_prompt_parts.append(matched_descriptors[0])
        if len(matched_descriptors) > 1:
            # Combine elements from second match
            final_prompt_parts.append(matched_descriptors[1])
        final_negative_parts.extend(matched_negatives)
    else:
        # No direct archetype match: Preserve original user text and enrich it
        # If user typed Japanese or unknown text, wrap with rich descriptors
        final_prompt_parts.append(raw_text)
        if is_sfx:
            final_prompt_parts.append(
                "highly detailed field recording, pure immersive environmental sound, binaural ASMR, realistic nature acoustics, clean 4k audio"
            )
            final_negative_parts.append(
                "music, melody, drums, bass, human speech, talking, loud distortion, clipping, background hum, low quality"
            )
            applied_tags.append("高音質効果音ブースト")
        else:
            final_prompt_parts.append(
                "rich harmonic texture, dynamic arrangement, pristine studio sound quality, well balanced mix, high fidelity audio"
            )
            final_negative_parts.append(
                "distortion, clipping, harsh frequencies, muffled, muddy mix, low bitrate, out of tune"
            )
            applied_tags.append("高音質音楽ブースト")

    if extra_moods:
        final_prompt_parts.extend(extra_moods)

    # Standard quality boosters
    if is_sfx:
        quality_boosters = "binaural field recording, high fidelity, 4k audio, clean ASMR"
        base_neg = "music, melody, vocals, distortion, low quality, noise"
    else:
        quality_boosters = "high fidelity, professional studio production, master quality"
        base_neg = "distortion, harsh noise, clipping, low bitrate"

    # Assemble and deduplicate
    full_prompt = ", ".join(final_prompt_parts)
    if quality_boosters not in full_prompt:
        full_prompt = f"{full_prompt}, {quality_boosters}"

    all_negatives = matched_negatives + [base_neg]
    neg_tokens = []
    seen = set()
    for neg_str in all_negatives:
        for t in neg_str.split(","):
            cleaned = t.strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                neg_tokens.append(cleaned)
    full_negative = ", ".join(neg_tokens)

    return EnhancedPromptResult(
        prompt=full_prompt,
        negative_prompt=full_negative,
        suggested_bpm=suggested_bpm or (0 if is_sfx else current_bpm),
        applied_tags=applied_tags,
    )
