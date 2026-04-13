"""Qwen3-TTS engine for opc tts.

Supports two backends:
  - cuda: Linux + NVIDIA GPU, uses qwen-tts + PyTorch
  - mlx:  macOS + Apple Silicon, uses mlx-audio
"""

import os
import sys
import subprocess

from scripts.shared.platform import get_backend
from scripts.shared.model_path import resolve_model_path

# Qwen3-TTS model mapping: mode -> size -> model_id
# CUDA models (from ModelScope)
QWEN_MODELS = {
    "custom_voice": {
        "1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "0.6B": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    },
    "voice_design": {
        "1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    },
    "voice_clone": {
        "1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "0.6B": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    },
}

# MLX models (from HuggingFace mlx-community)
QWEN_MLX_MODELS = {
    "custom_voice": {
        "1.7B": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
        "0.6B": "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit",
    },
    "voice_design": {
        "1.7B": "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit",
    },
    "voice_clone": {
        "1.7B": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit",
        "0.6B": "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit",
    },
}

QWEN_SPEAKERS = ["Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ryan", "Aiden", "Ono_Anna", "Sohee"]

# Speaker info: (chinese_name, description_en, description_cn, native_language)
QWEN_SPEAKER_INFO = {
    "Vivian":    ("薇薇安",   "Bright, slightly edgy young female voice",
                  "明亮、略带棱角感的年轻女性声音", "Chinese 中文"),
    "Serena":    ("塞蕾娜",   "Warm, gentle young female voice",
                  "温暖、温柔的年轻女性声音", "Chinese 中文"),
    "Uncle_Fu":  ("傅叔叔",   "Seasoned male voice with a low, mellow timbre",
                  "成熟男性声音，音色低沉柔和", "Chinese 中文"),
    "Dylan":     ("迪伦",     "Youthful Beijing male voice with a clear, natural timbre",
                  "年轻北京男性声音，音质清晰自然", "Chinese (Beijing Dialect) 北京方言"),
    "Eric":      (None,       "Lively Chengdu male voice with a slightly husky brightness",
                  "活泼成都男性声音，略带沙哑的明亮感", "Chinese (Sichuan Dialect) 四川方言"),
    "Ryan":      ("瑞安",     "Dynamic male voice with strong rhythmic drive",
                  "富有节奏感的动态男声", "English 英语"),
    "Aiden":     ("艾登",     "Sunny American male voice with a clear midrange",
                  "阳光美国男性声音，中频清晰", "English 英语"),
    "Ono_Anna":  ("小野安娜", "Playful Japanese female voice with a light, nimble timbre",
                  "活泼的日语女性声音，音色轻快灵活", "Japanese 日语"),
    "Sohee":     (None,       "Warm Korean female voice with rich emotion",
                  "温暖感人的韩语女性声音", "Korean 韩语"),
}

# Language mapping for MLX (lang_code parameter)
_MLX_LANG_MAP = {
    "Auto": "auto",
    "Chinese": "chinese",
    "English": "english",
    "Japanese": "japanese",
    "Korean": "korean",
    "German": "german",
    "French": "french",
    "Russian": "russian",
    "Portuguese": "portuguese",
    "Spanish": "spanish",
    "Italian": "italian",
}

# Model cache
_loaded_models = {}


# ── Model loading ───────────────────────────────────────────────

def _load_model_cuda(model_id):
    """Load a Qwen3-TTS model using CUDA/PyTorch."""
    import torch
    from qwen_tts import Qwen3TTSModel

    model_path = resolve_model_path(model_id)
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    print(f"Loading Qwen3-TTS ({model_id}) on {device}...")
    model = Qwen3TTSModel.from_pretrained(model_path, device_map=device, dtype=torch.bfloat16)
    return model


def _load_model_mlx(model_id):
    """Load a Qwen3-TTS model using MLX (Apple Silicon)."""
    from mlx_audio.tts.utils import load_model

    model_path = resolve_model_path(model_id)
    print(f"Loading Qwen3-TTS ({model_id}) via MLX...")
    model = load_model(model_path)
    return model


def get_qwen_model(model_id):
    """Load and cache a Qwen3-TTS model."""
    if model_id in _loaded_models:
        return _loaded_models[model_id]

    backend = get_backend()
    if backend == "mlx":
        model = _load_model_mlx(model_id)
    else:
        model = _load_model_cuda(model_id)

    _loaded_models[model_id] = model
    return model


# ── TTS generation ──────────────────────────────────────────────

def _get_models_table():
    """Get the model table for the current backend."""
    if get_backend() == "mlx":
        return QWEN_MLX_MODELS
    return QWEN_MODELS


def tts_qwen(text, output_file, mode, model_size="1.7B",
             speaker=None, instruct=None, language=None,
             ref_audio=None, ref_text=None, x_vector_only=False):
    """Generate speech using Qwen3-TTS (local model).

    Three modes:
      - custom_voice: Built-in speaker + optional instruct for emotion/style.
      - voice_design: Design a voice from natural language description.
      - voice_clone:  Clone a voice from reference audio.
    """
    backend = get_backend()
    models = _get_models_table()

    if mode not in models:
        print(f"Error: Unknown mode '{mode}'. Available: {', '.join(models.keys())}")
        sys.exit(1)
    if model_size not in models[mode]:
        print(f"Error: Mode '{mode}' does not support model size '{model_size}'. "
              f"Available: {', '.join(models[mode].keys())}")
        sys.exit(1)

    model_id = models[mode][model_size]
    model = get_qwen_model(model_id)

    if language is None:
        language = "Auto"

    wav_file = output_file.replace(".mp3", ".wav")

    if backend == "mlx":
        _tts_mlx(model, text, wav_file, mode, speaker, instruct, language,
                 ref_audio, ref_text)
    else:
        _tts_cuda(model, text, wav_file, mode, model_id, speaker, instruct, language,
                  ref_audio, ref_text, x_vector_only)

    # Convert to mp3 if requested
    if output_file.endswith(".mp3"):
        mp3_file = wav_file.replace(".wav", ".mp3")
        subprocess.run(["ffmpeg", "-y", "-i", wav_file, "-b:a", "192k", mp3_file],
                       check=True, capture_output=True)
        os.remove(wav_file)
        print(f"Converted to mp3: {mp3_file}")
        return mp3_file
    else:
        if wav_file != output_file:
            os.rename(wav_file, output_file)
        return output_file


def _tts_cuda(model, text, wav_file, mode, model_id, speaker, instruct, language,
              ref_audio, ref_text, x_vector_only):
    """TTS generation using CUDA/PyTorch backend."""
    import soundfile as sf

    gen_kwargs = dict(max_new_tokens=4096, do_sample=True, top_k=50, top_p=1.0,
                      temperature=0.9, repetition_penalty=1.05)

    if mode == "custom_voice":
        if not speaker:
            print("Error: --speaker is required for custom_voice mode.")
            print(f"  Available speakers: {', '.join(QWEN_SPEAKERS)}")
            sys.exit(1)
        print(f"Generating with CustomVoice: speaker={speaker}, instruct={instruct}")
        wavs, sr = model.generate_custom_voice(
            text=[text], speaker=[speaker], language=[language],
            instruct=[instruct] if instruct else None,
            **gen_kwargs,
        )
    elif mode == "voice_design":
        if not instruct:
            print("Error: --instruct is required for voice_design mode.")
            print("  Provide a voice description, e.g.: --instruct '温柔的女声，音调偏高'")
            sys.exit(1)
        print(f"Generating with VoiceDesign: instruct={instruct}")
        wavs, sr = model.generate_voice_design(
            text=[text], instruct=[instruct], language=[language],
            **gen_kwargs,
        )
    elif mode == "voice_clone":
        if not ref_audio:
            print("Error: --ref-audio is required for voice_clone mode.")
            sys.exit(1)
        if not x_vector_only and not ref_text:
            print("Warning: --ref-text is recommended for ICL mode (better quality).")
            print("  Use --x-vector-only to skip ref_text (lower quality).")
        print(f"Generating with VoiceClone: ref_audio={ref_audio}")
        prompt_items = model.create_voice_clone_prompt(
            ref_audio=ref_audio,
            ref_text=ref_text if ref_text else None,
            x_vector_only_mode=x_vector_only,
        )
        wavs, sr = model.generate_voice_clone(
            text=[text], language=[language],
            voice_clone_prompt=prompt_items,
            **gen_kwargs,
        )

    sf.write(wav_file, wavs[0], sr)
    print(f"Generated wav: {wav_file}")


def _tts_mlx(model, text, wav_file, mode, speaker, instruct, language,
             ref_audio, ref_text):
    """TTS generation using MLX backend (Apple Silicon)."""
    import numpy as np
    import mlx.core as mx
    from mlx_audio.audio_io import write as audio_write

    # Convert language to lang_code for MLX
    lang_code = _MLX_LANG_MAP.get(language, language.lower() if language else "auto")

    # Collect audio from generator
    audio_chunks = []
    sample_rate = None

    if mode == "custom_voice":
        if not speaker:
            print("Error: --speaker is required for custom_voice mode.")
            print(f"  Available speakers: {', '.join(QWEN_SPEAKERS)}")
            sys.exit(1)
        print(f"Generating with CustomVoice: speaker={speaker}, instruct={instruct}")
        for result in model.generate(
            text=text,
            voice=speaker,
            instruct=instruct,
            lang_code=lang_code,
            verbose=True,
        ):
            audio_chunks.append(np.array(result.audio))
            sample_rate = result.sample_rate

    elif mode == "voice_design":
        if not instruct:
            print("Error: --instruct is required for voice_design mode.")
            print("  Provide a voice description, e.g.: --instruct '温柔的女声，音调偏高'")
            sys.exit(1)
        print(f"Generating with VoiceDesign: instruct={instruct}")
        for result in model.generate(
            text=text,
            instruct=instruct,
            lang_code=lang_code,
            verbose=True,
        ):
            audio_chunks.append(np.array(result.audio))
            sample_rate = result.sample_rate

    elif mode == "voice_clone":
        if not ref_audio:
            print("Error: --ref-audio is required for voice_clone mode.")
            sys.exit(1)
        print(f"Generating with VoiceClone: ref_audio={ref_audio}")
        for result in model.generate(
            text=text,
            ref_audio=ref_audio,
            ref_text=ref_text,
            lang_code=lang_code,
            verbose=True,
        ):
            audio_chunks.append(np.array(result.audio))
            sample_rate = result.sample_rate

    if not audio_chunks:
        print("Error: No audio generated.")
        sys.exit(1)

    # Join audio chunks
    if len(audio_chunks) > 1:
        audio = mx.concatenate(audio_chunks, axis=0)
    else:
        audio = audio_chunks[0]

    # Write WAV file
    audio_write(wav_file, audio, sample_rate, format="wav")
    print(f"Generated wav: {wav_file}")
