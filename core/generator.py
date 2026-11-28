"""Audio Generator core module for Stable Audio Studio."""

from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple
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


def is_sfx_model(model_id: str) -> bool:
    """Checks whether the specified model is dedicated to sound effects / ambience."""
    if not model_id:
        return False
    alias = MODEL_ALIASES.get(model_id, model_id).lower()
    return "sfx" in alias or "sfx" in model_id.lower()


def load_audio_for_conditioning(file_path: str) -> Tuple[int, torch.Tensor]:
    """Loads an audio file and converts it to (sample_rate, tensor_channels_first)."""
    import soundfile as sf
    try:
        audio_data, sr = sf.read(file_path)
    except Exception as e:
        try:
            import torchaudio
            tensor, sr = torchaudio.load(file_path)
            return sr, tensor.float()
        except Exception as e2:
            raise RuntimeError(f"参考音源ファイルの読み込みに失敗しました: {e} (torchaudio: {e2})")

    if audio_data.ndim == 1:
        tensor = torch.from_numpy(audio_data).unsqueeze(0).float()
    else:
        tensor = torch.from_numpy(audio_data.T).float()
    return sr, tensor


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

        # Release previous model if switching models to prevent memory leaks
        if self.model is not None:
            del self.model
            self.model = None
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()

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

    def build_full_prompt(self, prompt: str, bpm: int, model_id: Optional[str] = None) -> str:
        """Prepends BPM to prompt if applicable for music models."""
        clean_prompt = prompt.strip()
        # For SFX / ambience models or non-positive BPM, do not prepend BPM
        if (model_id and is_sfx_model(model_id)) or bpm <= 0:
            return clean_prompt
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
        init_audio_path: Optional[str] = None,
        init_noise_level: float = 0.6,
        take_index: Optional[int] = None,
        total_takes: Optional[int] = None,
    ) -> Tuple[str, int]:
        """
        Generates audio from prompt and saves to the output directory.

        Supports text-to-audio and audio-to-audio (conditioning from reference audio).

        Returns:
            Tuple[str, int]: (output_wav_filepath, seed_used)
        """
        target_model_id = model_id or self.config.model_id
        self.load_model(model_id=target_model_id)

        # Determine seed
        if seed is None or seed < 0:
            seed = random.randint(0, 2**32 - 1)

        # Build prompt (skip BPM prefix for SFX / Ambience models)
        full_prompt = self.build_full_prompt(prompt, bpm, model_id=target_model_id)
        neg_prompt = negative_prompt.strip()

        # Clamp duration to model's maximum supported duration
        max_allowed_duration = self.config.get_max_duration(target_model_id)
        effective_duration = int(duration)
        if effective_duration > max_allowed_duration:
            print(
                f"Notice: Requested duration {effective_duration}s exceeds model maximum {max_allowed_duration}s for '{target_model_id}'. Clamping to {max_allowed_duration}s."
            )
            effective_duration = max_allowed_duration

        is_sfx = is_sfx_model(target_model_id) or (bpm <= 0)
        mode_label = "SFX/Ambience" if is_sfx else f"Music (BPM={bpm})"

        # Prepare init_audio if provided (Audio-to-Audio / Remix)
        init_audio_input = None
        init_audio_filename = None
        if init_audio_path and os.path.exists(init_audio_path):
            try:
                sr, audio_tensor = load_audio_for_conditioning(init_audio_path)
                init_audio_input = (sr, audio_tensor)
                init_audio_filename = Path(init_audio_path).name
                print(
                    f"Generating audio [{mode_label} / Audio-to-Audio]: Ref='{init_audio_filename}', NoiseLevel={init_noise_level}, Prompt='{full_prompt}', Duration={effective_duration}s, Seed={seed}"
                )
            except Exception as e:
                print(f"Warning: Failed to load reference audio '{init_audio_path}': {e}. Falling back to Text-to-Audio.")
        else:
            print(f"Generating audio [{mode_label}]: Prompt='{full_prompt}', Neg='{neg_prompt}', Duration={effective_duration}s, Seed={seed}")

        # Set seeds for reproducibility
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        # Use model's configured sample_size (defaults to 16777216 for SA3 Medium = ~380s)
        # to ensure generation beyond 120s is not clamped by default sample_size.
        model_sample_size = self.model_config.get("sample_size", 16777216)

        with torch.no_grad():
            gen_kwargs = {
                "prompt": full_prompt,
                "negative_prompt": neg_prompt if neg_prompt else None,
                "duration": float(effective_duration),
                "steps": steps,
                "cfg_scale": cfg_scale,
                "seed": seed,
                "sample_size": model_sample_size,
            }
            if init_audio_input is not None:
                gen_kwargs["init_audio"] = init_audio_input
                gen_kwargs["init_noise_level"] = float(init_noise_level)

            output_tensor = self.model.generate(**gen_kwargs)

        # Format tensor to audio (channels, samples)
        output_tensor = output_tensor.to(torch.float32).cpu()
        if output_tensor.dim() == 3:
            # Shape is (batch, channels, samples) -> select batch 0
            output_tensor = output_tensor[0]

        # Clamp between -1.0 and 1.0 to prevent clipping
        output_tensor = torch.clamp(output_tensor, -1.0, 1.0)

        # File naming:
        # Music: YYYYMMDD_HHMMSS_{bpm}bpm_{duration}s_{prompt_summary}_s{seed}(_t{take}).wav
        # SFX:   YYYYMMDD_HHMMSS_sfx_{duration}s_{prompt_summary}_s{seed}(_t{take}).wav
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        prompt_summary = self.sanitize_text(prompt)
        take_suffix = f"_t{take_index}" if (total_takes and total_takes > 1 and take_index) else ""
        if is_sfx:
            filename = f"{now_str}_sfx_{effective_duration}s_{prompt_summary}_s{seed}{take_suffix}.wav"
        else:
            filename = f"{now_str}_{bpm}bpm_{effective_duration}s_{prompt_summary}_s{seed}{take_suffix}.wav"
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
        effective_bpm = 0 if is_sfx else bpm
        save_metadata(
            wav_path=output_path,
            prompt=prompt,
            negative_prompt=neg_prompt,
            bpm=effective_bpm,
            duration=effective_duration,
            seed=seed,
            model_id=target_model_id,
            init_audio_filename=init_audio_filename,
            init_noise_level=float(init_noise_level) if init_audio_input else None,
            take_index=take_index,
            total_takes=total_takes,
        )

        return str(output_path), seed

    def generate_takes(
        self,
        prompt: str,
        negative_prompt: str = "",
        bpm: int = 120,
        duration: int = 30,
        steps: int = 8,
        cfg_scale: float = 1.0,
        seed: Optional[int] = None,
        model_id: Optional[str] = None,
        init_audio_path: Optional[str] = None,
        init_noise_level: float = 0.6,
        num_takes: int = 1,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Tuple[str, int]]:
        """
        Generates multiple takes for comparison/audition.

        Args:
            num_takes: Number of takes to generate (1 to 4).
            progress_callback: Optional callback(current_take, total_takes, message) for reporting progress.

        Returns:
            List[Tuple[str, int]]: List of (wav_path, seed_used) for each take.
        """
        target_takes = max(1, min(int(num_takes), self.config.max_takes))
        if target_takes == 1:
            if progress_callback:
                progress_callback(1, 1, "音声を生成中...")
            wav_path, used_seed = self.generate(
                prompt=prompt,
                negative_prompt=negative_prompt,
                bpm=bpm,
                duration=duration,
                steps=steps,
                cfg_scale=cfg_scale,
                seed=seed,
                model_id=model_id,
                init_audio_path=init_audio_path,
                init_noise_level=init_noise_level,
                take_index=None,
                total_takes=None,
            )
            return [(wav_path, used_seed)]

        # Pre-load model once before loop
        target_model_id = model_id or self.config.model_id
        self.load_model(model_id=target_model_id)

        results: List[Tuple[str, int]] = []
        base_seed = seed if (seed is not None and seed >= 0) else None
        used_seeds = set()

        for idx in range(1, target_takes + 1):
            if base_seed is not None:
                # Use large prime offset so each take explores distinctly different latent trajectories
                take_seed = (base_seed + (idx - 1) * 10007) % (2**32)
            else:
                # Ensure each take in the batch receives a genuinely unique random seed
                take_seed = random.randint(0, 2**32 - 1)
                while take_seed in used_seeds:
                    take_seed = random.randint(0, 2**32 - 1)
            used_seeds.add(take_seed)

            if progress_callback:
                progress_callback(idx, target_takes, f"テイク {idx}/{target_takes} を生成中 (seed: {take_seed})...")

            wav_path, used_seed = self.generate(
                prompt=prompt,
                negative_prompt=negative_prompt,
                bpm=bpm,
                duration=duration,
                steps=steps,
                cfg_scale=cfg_scale,
                seed=take_seed,
                model_id=target_model_id,
                init_audio_path=init_audio_path,
                init_noise_level=init_noise_level,
                take_index=idx,
                total_takes=target_takes,
            )
            results.append((wav_path, used_seed))

        return results


# Module-level singleton instance for convenience
generator = AudioGenerator.get_instance()
