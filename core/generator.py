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


class AudioGenerator:
    """Core audio generation engine wrapping stable-audio-tools."""

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
            from stable_audio_tools import get_pretrained_model

            # Note: stable-audio models require accepting terms on Hugging Face
            model, model_config = get_pretrained_model(target_model_id)
            model = model.to(self.device)
            # Ensure evaluation mode
            model.eval()

            self.model = model
            self.model_config = model_config
            self.current_model_id = target_model_id
            print(f"Model '{target_model_id}' loaded successfully.")
        except ImportError as e:
            raise ModelLoadError(
                "stable-audio-tools is not installed. Please run: pip install -r requirements.txt"
            ) from e
        except Exception as e:
            err_msg = str(e)
            if "gated repo" in err_msg.lower() or "401" in err_msg or "403" in err_msg:
                raise ModelLoadError(
                    f"Hugging Face認証エラー: モデル '{target_model_id}' へのアクセス権がありません。\n"
                    f"1. Hugging Face (https://huggingface.co/{target_model_id}) で利用規約に同意してください。\n"
                    "2. ターミナルで `huggingface-cli login` を実行するか、環境変数 `HF_TOKEN` を設定してください。"
                ) from e
            raise ModelLoadError(f"モデルのロードに失敗しました: {err_msg}") from e

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
        steps: int = 100,
        cfg_scale: float = 7.0,
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

        from stable_audio_tools.inference.generation import generate_diffusion_cond

        # Prepare conditioning
        conditioning = [{"prompt": full_prompt, "seconds_start": 0, "seconds_total": duration}]
        negative_conditioning = (
            [{"prompt": neg_prompt, "seconds_start": 0, "seconds_total": duration}]
            if neg_prompt
            else None
        )

        with torch.no_grad():
            output_tensor = generate_diffusion_cond(
                self.model,
                steps=steps,
                cfg_scale=cfg_scale,
                conditioning=conditioning,
                negative_conditioning=negative_conditioning,
                sample_size=self.model_config["sample_size"],
                sample_rate=self.model_config.get("sample_rate", self.config.sample_rate),
                seed=seed,
                device=self.device,
            )

        # Format tensor to audio (channels, samples)
        # Rearrange and squeeze if necessary
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

        sf.write(str(output_path), audio_np, samplerate=sample_rate)
        print(f"Audio saved to: {output_path}")

        # Save sidecar metadata JSON
        target_model_id = model_id or getattr(self, "current_model_id", self.config.model_id)
        try:
            save_metadata(
                wav_path=output_path,
                prompt=prompt,
                negative_prompt=negative_prompt,
                bpm=bpm,
                duration=duration,
                seed=seed,
                model_id=target_model_id,
            )
        except Exception as e:
            print(f"Warning: Failed to save metadata JSON: {e}")

        return str(output_path), seed


# Global helper instance
generator = AudioGenerator.get_instance()
