"""Qwen3-ASR engine for opc asr.

Supports two backends:
  - cuda: Linux + NVIDIA GPU, uses qwen-asr + PyTorch
  - mlx:  macOS + Apple Silicon, uses mlx-audio

Output data structures (WordTimestamp, ASRResult, result_to_dict) are identical
regardless of backend, so the pipeline and CLI are unaffected.
"""

import os
import sys
from dataclasses import dataclass

from scripts.shared.platform import get_backend
from scripts.shared.model_path import resolve_model_path

# ASR model mapping: size -> model_id
ASR_MODELS = {
    "cuda": {
        "1.7B": "Qwen/Qwen3-ASR-1.7B",
        "0.6B": "Qwen/Qwen3-ASR-0.6B",
    },
    "mlx": {
        "1.7B": "mlx-community/Qwen3-ASR-1.7B-8bit",
        "0.6B": "mlx-community/Qwen3-ASR-0.6B-8bit",
    },
}

ALIGNER_MODELS = {
    "cuda": "Qwen/Qwen3-ForcedAligner-0.6B",
    "mlx": "mlx-community/Qwen3-ForcedAligner-0.6B-8bit",
}

# Model cache
_loaded_models = {}


@dataclass
class WordTimestamp:
    """Word-level timestamp information."""
    text: str
    start_time: float  # seconds
    end_time: float    # seconds


@dataclass
class ASRResult:
    """Complete ASR result with alignment.

    Returns a flat list of words with punctuation attached.
    No segment grouping — segmentation is handled by the pipeline.
    """
    language: str
    text: str
    duration: float
    words: list[WordTimestamp]


# ── CUDA backend ────────────────────────────────────────────────

def _load_asr_cuda(model_id, with_aligner=True):
    """Load ASR model using CUDA/PyTorch."""
    import torch
    from qwen_asr import Qwen3ASRModel

    asr_path = resolve_model_path(model_id)
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    if with_aligner:
        aligner_path = resolve_model_path(ALIGNER_MODELS["cuda"])
        print(f"Loading Qwen3-ASR ({model_id}) + ForcedAligner on {device}...")
        model = Qwen3ASRModel.from_pretrained(
            asr_path,
            dtype=torch.bfloat16,
            device_map=device,
            forced_aligner=aligner_path,
            forced_aligner_kwargs=dict(
                dtype=torch.bfloat16,
                device_map=device,
            ),
            max_inference_batch_size=8,
            max_new_tokens=4096,
        )
    else:
        print(f"Loading Qwen3-ASR ({model_id}) on {device}...")
        model = Qwen3ASRModel.from_pretrained(
            asr_path,
            dtype=torch.bfloat16,
            device_map=device,
            max_inference_batch_size=8,
            max_new_tokens=4096,
        )

    return model


# ── MLX backend ─────────────────────────────────────────────────

def _load_asr_mlx(model_id):
    """Load ASR model using MLX (Apple Silicon)."""
    from mlx_audio.stt.utils import load_model

    model_path = resolve_model_path(model_id)
    print(f"Loading Qwen3-ASR ({model_id}) via MLX...")
    model = load_model(model_path)
    return model


def _load_aligner_mlx():
    """Load ForcedAligner model using MLX."""
    from mlx_audio.stt.utils import load_model

    model_id = ALIGNER_MODELS["mlx"]
    model_path = resolve_model_path(model_id)
    print(f"Loading Qwen3-ForcedAligner ({model_id}) via MLX...")
    model = load_model(model_path)
    return model


# ── Unified model loading ───────────────────────────────────────

def get_asr_model(model_id, with_aligner=True):
    """Load and cache a Qwen3-ASR model with optional aligner."""
    backend = get_backend()
    cache_key = f"{backend}_{model_id}_aligner_{with_aligner}"

    if cache_key in _loaded_models:
        return _loaded_models[cache_key]

    if backend == "mlx":
        model = _load_asr_mlx(model_id)
        result = {"asr": model}
        if with_aligner:
            result["aligner"] = _load_aligner_mlx()
        _loaded_models[cache_key] = result
        return result
    else:
        model = _load_asr_cuda(model_id, with_aligner=with_aligner)
        _loaded_models[cache_key] = model
        return model


# ── Audio loading ───────────────────────────────────────────────

def load_audio(audio_path):
    """Load audio file and return waveform and sample rate."""
    import soundfile as sf
    import numpy as np

    print(f"Loading audio: {audio_path}")
    wav, sr = sf.read(audio_path, dtype="float32", always_2d=False)

    # Convert to mono if stereo
    if wav.ndim > 1:
        wav = np.mean(wav, axis=1)

    return np.asarray(wav, dtype=np.float32), int(sr)


# ── Punctuation restoration ─────────────────────────────────────

_PUNCT = set('，。、！？；：""''《》【】（）,.!?;:\'"()[]{}·…—~ ')


def _restore_punctuation(words, full_text):
    """Restore punctuation from full text into word timestamps.

    Uses substring matching to handle multi-char timestamp entries (e.g. "OpenCL").
    Finds each timestamp text in the full text sequentially, and attaches
    any intervening punctuation/spaces to the preceding word.
    """
    if not words or not full_text:
        return words

    result = [WordTimestamp(w.text, w.start_time, w.end_time) for w in words]
    pos = 0  # current position in full_text

    for wi in range(len(result)):
        expected = result[wi].text
        remaining = full_text[pos:]

        # Find this timestamp's text in the remaining full text
        idx = remaining.find(expected)
        if idx < 0:
            # Can't find it - skip this timestamp
            continue

        # Attach any chars before the match (punctuation only) to previous word
        if wi > 0:
            for ch in remaining[:idx]:
                if ch in _PUNCT:
                    result[wi - 1] = WordTimestamp(
                        result[wi - 1].text + ch,
                        result[wi - 1].start_time,
                        result[wi - 1].end_time,
                    )

        # Advance position past the matched text
        pos += idx + len(expected)

        # Attach trailing punctuation/spaces to this word
        while pos < len(full_text) and full_text[pos] in _PUNCT:
            result[wi] = WordTimestamp(
                result[wi].text + full_text[pos],
                result[wi].start_time,
                result[wi].end_time,
            )
            pos += 1

    return result


# ── Transcription (text only) ───────────────────────────────────

def asr_transcribe(audio_path, language=None, model_size="1.7B"):
    """Simple transcription, returns text string.

    Args:
        audio_path: Path to audio file
        language: Language hint (e.g., "Chinese", "English"). If None, auto-detect.
        model_size: Model size ("1.7B" or "0.6B")

    Returns:
        Transcribed text string
    """
    backend = get_backend()
    models = ASR_MODELS[backend]

    if model_size not in models:
        print(f"Error: Unknown model size '{model_size}'. Available: {', '.join(models.keys())}")
        sys.exit(1)

    model_id = models[model_size]
    model = get_asr_model(model_id, with_aligner=False)

    if backend == "mlx":
        return _asr_transcribe_mlx(model["asr"], audio_path, language)
    else:
        results = model.transcribe(audio=audio_path, language=language, return_time_stamps=False)
        return results[0].text


def _asr_transcribe_mlx(model, audio_path, language):
    """Transcribe using MLX backend."""
    # Map language name to code for MLX
    lang_code = _language_to_code(language)

    result = model.generate(
        audio_path,
        language=lang_code,
        verbose=True,
    )
    return result.text


# ── ASR with forced alignment ───────────────────────────────────

def asr_align(audio_path, language=None, model_size="1.7B"):
    """Full ASR with forced alignment, returns ASRResult with flat word list.

    Args:
        audio_path: Path to audio file
        language: Language hint (e.g., "Chinese", "English"). If None, auto-detect.
        model_size: Model size ("1.7B" or "0.6B")

    Returns:
        ASRResult with flat word-level timestamps (no segment grouping)
    """
    backend = get_backend()
    models = ASR_MODELS[backend]

    if model_size not in models:
        print(f"Error: Unknown model size '{model_size}'. Available: {', '.join(models.keys())}")
        sys.exit(1)

    model_id = models[model_size]
    models_dict = get_asr_model(model_id, with_aligner=True)

    # Load audio to get duration
    wav, sr = load_audio(audio_path)
    duration = len(wav) / sr
    print(f"Audio duration: {duration:.2f}s")

    if backend == "mlx":
        return _asr_align_mlx(models_dict["asr"], models_dict["aligner"],
                              audio_path, wav, sr, duration, language)
    else:
        return _asr_align_cuda(models_dict, audio_path, wav, sr, duration, language)


def _asr_align_cuda(model, audio_path, wav, sr, duration, language):
    """ASR + alignment using CUDA/PyTorch backend."""
    # For long audio (> 5 min), split into 30s chunks
    if duration > 300:
        print("Splitting audio into 30s chunks...")
        chunk_duration = 30.0
        segment_samples = int(chunk_duration * sr)

        all_words = []
        detected_language = None

        for i, start in enumerate(range(0, len(wav), segment_samples)):
            end = min(start + segment_samples, len(wav))
            offset = start / sr

            print(f"Processing chunk {i+1}...")
            results = model.transcribe(
                audio=(wav[start:end], sr),
                language=language,
                return_time_stamps=True,
            )

            if detected_language is None:
                detected_language = results[0].language

            chunk_text = results[0].text
            chunk_words = []
            if results[0].time_stamps:
                for ts in results[0].time_stamps:
                    chunk_words.append(WordTimestamp(
                        text=ts.text,
                        start_time=ts.start_time + offset,
                        end_time=ts.end_time + offset,
                    ))

            chunk_words = _restore_punctuation(chunk_words, chunk_text)
            all_words.extend(chunk_words)

        full_text = "".join(w.text for w in all_words)

        return ASRResult(
            language=detected_language or "unknown",
            text=full_text,
            duration=duration,
            words=all_words,
        )
    else:
        # Short audio, process directly
        print("Processing audio directly...")
        results = model.transcribe(
            audio=audio_path,
            language=language,
            return_time_stamps=True,
        )

        result = results[0]

        # Convert timestamps to WordTimestamp list
        words = []
        if result.time_stamps:
            for ts in result.time_stamps:
                words.append(WordTimestamp(
                    text=ts.text,
                    start_time=ts.start_time,
                    end_time=ts.end_time,
                ))

        # Restore punctuation from full text
        words = _restore_punctuation(words, result.text)

        return ASRResult(
            language=result.language,
            text=result.text,
            duration=duration,
            words=words,
        )


def _asr_align_mlx(asr_model, aligner_model, audio_path, wav, sr, duration, language):
    """ASR + alignment using MLX backend (Apple Silicon).

    MLX separates ASR and ForcedAligner into two models:
    1. Use ASR model to get transcription text
    2. Use ForcedAligner to get word-level timestamps
    """
    import numpy as np

    lang_code = _language_to_code(language) or "chinese"

    # Step 1: Transcribe to get full text
    print("Step 1/2: Transcribing...")
    asr_result = asr_model.generate(
        audio_path,
        language=lang_code,
        verbose=True,
    )
    full_text = asr_result.text
    detected_language = lang_code

    if not full_text:
        return ASRResult(
            language=detected_language,
            text="",
            duration=duration,
            words=[],
        )

    print(f"Transcribed text ({len(full_text)} chars): {full_text[:100]}...")

    # Step 2: Forced alignment to get word-level timestamps
    print("Step 2/2: Forced alignment...")
    align_result = aligner_model.generate(
        audio=audio_path,
        text=full_text,
        language=detected_language,
    )

    # Convert ForcedAlignResult items to WordTimestamp
    words = []
    for item in align_result:
        words.append(WordTimestamp(
            text=item.text,
            start_time=item.start_time,
            end_time=item.end_time,
        ))

    # Restore punctuation from full text
    words = _restore_punctuation(words, full_text)

    return ASRResult(
        language=detected_language,
        text=full_text,
        duration=duration,
        words=words,
    )


# ── Language helpers ────────────────────────────────────────────

def _language_to_code(language):
    """Convert language name to code for MLX models.

    MLX Qwen3-ASR expects language names like 'chinese', 'english', etc.
    CUDA qwen-asr uses similar names.
    """
    if not language:
        return None
    mapping = {
        "chinese": "Chinese",
        "english": "English",
        "japanese": "Japanese",
        "korean": "Korean",
        "german": "German",
        "french": "French",
        "russian": "Russian",
    }
    lower = language.lower().strip()
    # If already a code, return as-is
    if lower in mapping:
        return mapping[lower]
    # If it's a full name, find the code
    for code, name in mapping.items():
        if name.lower() == lower:
            return name
    # Return as-is (capitalized first letter)
    return language


# ── Serialization ───────────────────────────────────────────────

def result_to_dict(result: ASRResult) -> dict:
    """Convert ASRResult to JSON-serializable dict.

    Returns a flat structure with words list (no segments).
    """
    return {
        "language": result.language,
        "text": result.text,
        "duration": result.duration,
        "words": [
            {
                "text": w.text,
                "start_time": w.start_time,
                "end_time": w.end_time,
            }
            for w in result.words
        ],
    }
