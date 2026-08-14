# MiniMax Music3

`opc music` uses the native MiniMax Music3 nodes in the configured ComfyUI server. It generates stereo music from a music description plus optional tagged lyrics.

## Commands

```bash
# Vocal music with inline lyrics
opc music \
  --caption "Warm Mandarin indie pop, intimate female vocal, acoustic guitar and piano" \
  --lyrics $'[Verse]\n清晨的光落在窗边\n[Chorus]\n把微光唱成盛夏' \
  --duration 30 -o song.mp3

# Read structured inputs from files
opc music --caption-file caption.txt --lyrics-file lyrics.txt --duration 120 -o song.flac

# Instrumental music
opc music --caption "Cinematic orchestral score, slow emotional build" --instrumental

# Enforce at least 30 seconds of valid output; retry with up to five seeds
opc music --caption-file caption.txt --instrumental --duration 32 --min-duration 30 --attempts 5

# Inspect the exact ComfyUI workflow without submitting it
opc music --caption-file caption.txt --lyrics-file lyrics.txt --dry-run
```

## Prompt Format

For best control, write the caption in English with these three sections:

```text
Global Metadata: genre, BPM, key, mood progression, use case, production profile.
Vocal Details: singer gender, timbre, delivery, harmonies, backing vocals, effects.
Arrangement: instruments, groove, section-by-section evolution, textures, spatial effects.
```

Lyrics may use `[Intro]`, `[Verse]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Instrumental]`, `[Solo]`, and `[Outro]`. Lyrics stay in their intended language; do not copy them into the caption.

## Defaults

- Duration: 120 seconds; the model may end earlier; accepted range is 0.04-360 seconds.
- Duration acceptance: defaults to at least 95% of `--duration`; failed outputs automatically retry with up to three consecutive seeds. Set `--min-duration 0` to disable this gate.
- Instrumental mode automatically supplies section tags so the AR model is less likely to end after a single short phrase.
- Sampling: 30 steps, CFG 1.7, Euler/simple, top-k 50.
- Output: MP3 V0; FLAC is available with `--format flac` or a `.flac` output path.
- Model files: `minimax_music3_dit_fp16.safetensors`, `minimax_music3_text_encoder_pruned_int8_convrot.safetensors`, and `minimax_music3_dav.safetensors`.
- Generation is non-streaming.

Every successful command returns a `qc` object with actual duration, sample rate, channel count, peak, RMS, clipping ratio, silence ratio, and warnings. Duration and basic audio integrity are automatic gates; musical taste and fit with the edit still require listening.
