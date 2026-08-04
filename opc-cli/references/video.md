# Video - MiniMax H3

`opc video` uses the local ComfyUI server. Every H3 workflow generates 24 fps
video with H3's native stereo audio.

## Workflows

```bash
opc video list
opc video info h3-t2v
```

| Alias | Input | Output |
|---|---|---|
| `h3-t2v` | text | H3 video + native audio |
| `h3-i2v` | first frame, optional last frame, text | H3 video + native audio |
| `h3-r2v` | up to 9 images, 3 videos, and 3 audio clips, plus text | H3 video + native audio |
| `h3-t2v-upscale` | text | Legacy alias for `h3-t2v --upscale` |

`h3-r2v` uses the full `minimax_h3_ref2va_int8_convrot.safetensors`
reference model by default. The smaller pruned Ref2VA checkpoint is not used
by the standard workflow.

The safe test preset is `864x480`, 5 seconds, 20 steps. H3 converts five
seconds to 124 frames on its required `17k+5` frame grid.

The CLI accepts 5-20 seconds. Durations above 15 seconds are experimental:
the ComfyUI nodes accept the resulting frame count, but H3 documents roughly
124-362 frames as its trained range. A 20-second request becomes 481 frames.
Expect substantially higher VRAM use and verify temporal consistency before
shipping the result.

EasyCache is enabled by default for every H3 workflow. The conservative
default uses a `0.05` reuse threshold between 20% and 90% of the sampling
schedule. Disable it for exact baseline comparisons with `--no-easy-cache`.

```bash
opc config --set-comfyui-host 192.168.100.10
opc config --set-comfyui-port 8188
opc config --set-video-output-dir /vol2/1000/temp/opc-video

opc video -w h3-t2v \
  -p "A five-second continuous cinematic shot of a violinist in a rainy neon alley." \
  --width 864 --height 480 --duration 5 --steps 20

# Experimental native 20-second generation (481 frames; not post-stitched)
opc video -w h3-t2v \
  -p "A continuous twenty-second cinematic shot." \
  --width 864 --height 480 --duration 20 --steps 20

opc video -w h3-t2v -p "The same shot without model-step caching." \
  --no-easy-cache

opc video -w h3-i2v -p "A smooth continuous camera push-in." \
  --first-frame first.png --last-frame last.png

opc video -w h3-r2v -p "Preserve the subject and clothing." \
  --reference-image subject.png

opc video -w h3-r2v -p "Use the motion and sound from <Video 1>." \
  --reference-video motion.mp4

opc video -w h3-t2v -p "A rainy neon street at night." \
  --width 864 --height 480 --duration 5 --upscale --upscale-factor 2
```

All three primary workflows (`h3-t2v`, `h3-i2v`, and `h3-r2v`) leave
upscaling disabled by default. Add `--upscale` to run SeedVR2 after H3, set
the multiplier with `--upscale-factor` (`>1` through `4`), or explicitly use
`--no-upscale` in reusable scripts.

EasyCache replaces selected full H3 model evaluations with cached video and
audio transformation vectors. Increase `--easy-cache-threshold` for more
aggressive reuse or reduce it for higher fidelity. The available controls are:

```text
--easy-cache / --no-easy-cache
--easy-cache-threshold 0.05
--easy-cache-start-percent 0.20
--easy-cache-end-percent 0.90
--easy-cache-verbose
```

Use `--easy-cache-verbose` while benchmarking. ComfyUI then reports the number
of skipped model evaluations and the model-step speedup in its server log.

`--ref-image-size match` is the practical default. `max` keeps more reference
detail but can be several times slower. The upscale workflow uses temporal
chunking in automatic mode to avoid retaining the full restored video in the
sampler at once.

Reference videos should be 2-15 seconds at 24 fps. Their soundtracks are used
by default; pass `--no-reference-video-audio` to use only their pictures.
Prompts identify media as `<Picture 1>`, `<Video 1>`, and `<Audio 1>` in the
same order that each type appears on the command line. Standalone audio uses
the next audio ordinal after soundtracks attached to reference videos.

## Verified Results

Measured before EasyCache was enabled by default on the local RTX PRO 6000
with ComfyUI 0.30.0. Server execution time excludes queue wait. Every test
used 20 H3 steps, 864x480 input, five seconds (124 frames), and the same
adapted open-repository prompt. Reproduce these baselines with
`--no-easy-cache`.

| Workflow | Server time | Verified output |
|---|---:|---|
| `h3-t2v` | 73.86 s | 864x480 H.264 + stereo AAC |
| `h3-i2v` | 73.88 s | 864x480 H.264 + stereo AAC |
| `h3-r2v` | 72.06 s | 864x480 H.264 + stereo AAC |
| `h3-r2v`, one 5 s video + audio reference | 218.16 s | 864x480 H.264 + stereo AAC |
| SeedVR2 2x stage | 69.30 s | 1728x960 H.264 + original stereo AAC |

The upscale test reused a cached H3 base generation. A practical cold estimate
for `h3-t2v-upscale` is therefore about 143 seconds (74 seconds H3 + 69 seconds
SeedVR2). H3's frame grid makes a requested five-second clip 5.167 seconds at
24 fps.

## Test Prompt Source

The smoke-test prompt adapts **Rainy Neon Tokyo Violinist** from
[YouMind OpenLab's awesome-seedance-2-prompts](https://github.com/YouMind-OpenLab/awesome-seedance-2-prompts),
licensed under CC BY 4.0. It was shortened from 15 seconds to one five-second
shot and retains the rainy alley, violin performance, camera move, and native
ambient/violin audio cues. The adapted prompt is stored at
`references/prompts/h3-rainy-neon-5s.txt`.
