"""Audio Generator core module for Stable Audio Studio."""

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import os
import random
import re
import torch

from core.config import config, AppConfig
from core.history import save_metadata


class ModelLoadError(Exception):
    """Raised when loading the Stable Audio model fails."""
    pass


# Map Hugging Face model IDs or short names to stable-audio-3 model identifiers
MODEL_ALIASES = {
    "stabilityai/stable-audio-3-medium": "medium",
    "medium": "medium",
    "stabilityai/stable-audio-3-medium-base": "medium-base",
    "stabilityai/stable-audio-3-small-music": "small-music",
    "small-music": "small-music",
    "stabilityai/stable-audio-3-small-sfx": "small-sfx",
    "small-sfx": "small-sfx",
}


class AudioGenerator:
    """Core audio generation engine wrapping stable-audio-3."""

    _instance: Optional["AudioGenerator"] = None

    def __init__(self, app_config: Optional[AppConfig] = None):
        self.config = app_config or config
        self.device = self.config.device
        self.model = None
        self.model_config = None

    @classmethod
    def get_instance(cls, app_config: Optional[AppConfig] = None) -> "AudioGenerator":
        """Singleton accessor for AudioGenerator."""
        if cls._instance is None:
            cls._instance = cls(app_config=app_config)
        return cls._instance

    def load_model(self, model_id: Optional[str] = None) -> None:
        """Loads and caches the model onto the selected device (MPS/CPU)."""
        target_model_id = model_id or self.config.model_id
        if self.model is not None and getattr(self, "current_model_id", None) == target_model_id:
            return

        print(f"Loading Stable Audio model '{target_model_id}' onto {self.device}...")
        try:
            from stable_audio_3 import StableAudioModel
        except ImportError as e:
            raise ModelLoadError(
                "stable-audio-3 がインストールされていません。\n"
                "ターミナルで `pip install git+https://github.com/Stability-AI/stable-audio-3.git` を実行してください。"
            ) from e

        try:
            alias = MODEL_ALIASES.get(target_model_id, target_model_id)
            self.model = StableAudioModel.from_pretrained(alias, device=self.device)
            self.model_config = getattr(self.model, "model_config", {})
            self.current_model_id = target_model_id
            print(f"Model '{target_model_id}' loaded successfully on {self.device}.")
        except Exception as e:
            err_msg = str(e)
            if "gated repo" in err_msg.lower() or "401" in err_msg or "403" in err_msg:
                raise ModelLoadError(
                    f"Hugging Face認証エラー: モデル '{target_model_id}' へのアクセス権がありません。\n"
                    f"1. Hugging Face (https://huggingface.co/{target_model_id}) で利用規約に同意してください。\n"
                    "2. ターミナルで `huggingface-cli login` を実行するか、環境変数 `HF_TOKEN` を設定してください。"
                ) from e
            raise ModelLoadError(f"モデルのロードに失敗しました ({type(e).__name__}): {err_msg}") from e

    @staticmethod
    def sanitize_text(text: str, max_length: int = 30) -> str:
        """Sanitizes text for safe filename inclusion."""
        # Replace non-alphanumeric characters with underscores
        cleaned = re.sub(r"[^\w\-_]+", "_", text.strip().lower())
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        if not cleaned:
            cleaned = "audio"
        return cleaned[:max_length]

    def build_full_prompt(self, prompt: str, bpm: int) -> str:
        """Prepends BPM to prompt if not already present."""
        clean_prompt = prompt.strip()
        # Avoid duplicate BPM prefix if user already typed it
        if re.search(r"^\d+\s*bpm", clean_prompt, flags=re.IGNORECASE):
            return clean_prompt
        return f"{bpm} BPM, {clean_prompt}"

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        bpm: int = 120,
        duration: int = 30,
        steps: int = 8,
        cfg_scale: float = 1.0,
        seed: Optional[int] = None,
        model_id: Optional[str] = None,
    ) -> Tuple[str, int]:
        """
        Generates audio from prompt and saves to the output directory.

        Returns:
            Tuple[str, int]: (output_wav_filepath, seed_used)
        """
        self.load_model(model_id=model_id)

        # Determine seed
        if seed is None or seed < 0:
            seed = random.randint(0, 2**32 - 1)

        # Build prompt
        full_prompt = self.build_full_prompt(prompt, bpm)
        neg_prompt = negative_prompt.strip()

        print(f"Generating audio: Prompt='{full_prompt}', Neg='{neg_prompt}', BPM={bpm}, Duration={duration}s, Seed={seed}")

        # Set seeds for reproducibility
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        # Use model's configured sample_size (defaults to 16777216 for SA3 Medium = ~380s)
        # to ensure generation beyond 120s is not clamped by default sample_size.
        model_sample_size = self.model_config.get("sample_size", 16777216)

        with torch.no_grad():
            output_tensor = self.model.generate(
                prompt=full_prompt,
                negative_prompt=neg_prompt if neg_prompt else None,
                duration=float(duration),
                steps=steps,
                cfg_scale=cfg_scale,
                seed=seed,
                sample_size=model_sample_size,
            )

        # Format tensor to audio (channels, samples)
        output_tensor = output_tensor.to(torch.float32).cpu()
        if output_tensor.dim() == 3:
            # Shape is (batch, channels, samples) -> select batch 0
            output_tensor = output_tensor[0]

        # Clamp between -1.0 and 1.0 to prevent clipping
        output_tensor = torch.clamp(output_tensor, -1.0, 1.0)

        # File naming: YYYYMMDD_HHMMSS_{bpm}bpm_{duration}s_{prompt_summary}_s{seed}.wav
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        prompt_summary = self.sanitize_text(prompt)
        filename = f"{now_str}_{bpm}bpm_{duration}s_{prompt_summary}_s{seed}.wav"
        output_path = self.config.output_dir / filename

        sample_rate = self.model_config.get("sample_rate", self.config.sample_rate)

        # Save audio using soundfile (converting tensor shape to samples, channels)
        try:
            import soundfile as sf
        except ImportError as e:
            raise RuntimeError("soundfile is not installed. Please run: pip install soundfile") from e

        audio_np = output_tensor.numpy()
        if audio_np.ndim == 2:
            audio_np = audio_np.T

        sf.write(str(output_path), audio_np, sample_rate)
        print(f"Saved audio to: {output_path}")

        # Save metadata sidecar JSON
        target_model_id = model_id or self.config.model_id
        save_metadata(
            wav_path=output_path,
            prompt=prompt,
            negative_prompt=neg_prompt,
            bpm=bpm,
            duration=duration,
            seed=seed,
            model_id=target_model_id,
        )

        return str(output_path), seed


# Module-level singleton instance for convenience
generator = AudioGenerator.get_instance()
