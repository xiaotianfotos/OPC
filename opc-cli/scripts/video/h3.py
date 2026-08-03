"""Native ComfyUI workflow builders for the local MiniMax H3 models."""

import random


H3_FL2VA_MODEL = "minimax_h3_fl2va_int8_convrot.safetensors"
H3_REF2VA_MODEL = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
H3_TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
H3_VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
H3_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
SEEDVR2_MODEL = "seedvr2_3b_int8_convrot.safetensors"
SEEDVR2_VAE = "seedvr2_ema_vae_fp16.safetensors"

WORKFLOWS = {
    "h3-t2v": {
        "description": "MiniMax H3 text-to-video with native stereo audio",
        "inputs": "prompt; optional --upscale and --upscale-factor",
    },
    "h3-i2v": {
        "description": "MiniMax H3 first/last-frame image-to-video with native audio",
        "inputs": "prompt plus --first-frame and optional --last-frame; optional --upscale",
    },
    "h3-r2v": {
        "description": "MiniMax H3 reference-image-to-video with native audio",
        "inputs": "prompt plus image/video/audio references; optional --upscale",
    },
    "h3-t2v-upscale": {
        "description": "Legacy alias for h3-t2v --upscale",
        "inputs": "prompt; --upscale-factor defaults to 2",
    },
}


def duration_to_frames(duration):
    """Convert seconds to H3's 17k+5 frame grid at 24 fps."""
    frame_count = max(5, int(float(duration) * 24 + 0.5))
    return frame_count + (5 - frame_count % 17) % 17


def _validate(alias, prompt, width, height, duration, steps, upscale, upscale_factor):
    if alias not in WORKFLOWS:
        raise ValueError(f"Unknown H3 workflow: {alias}")
    if not prompt or not prompt.strip():
        raise ValueError("Prompt must not be empty")
    if width < 32 or height < 32 or width % 32 or height % 32:
        raise ValueError("Width and height must be positive multiples of 32")
    if not 5 <= float(duration) <= 15:
        raise ValueError("H3 duration must be between 5 and 15 seconds")
    if not 1 <= int(steps) <= 100:
        raise ValueError("Steps must be between 1 and 100")
    if upscale and not 1 < float(upscale_factor) <= 4:
        raise ValueError("Upscale factor must be greater than 1 and at most 4")


def _base_workflow(model_name, conditioning_node, steps, seed, output_node="14"):
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": model_name, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": H3_TEXT_ENCODER,
                "type": "minimax",
                "device": "default",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": H3_VIDEO_VAE},
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": H3_AUDIO_VAE},
        },
        "6": {
            "class_type": "BasicGuider",
            "inputs": {"model": ["1", 0], "conditioning": [conditioning_node, 0]},
        },
        "7": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["1", 0],
                "scheduler": "simple",
                "steps": int(steps),
                "denoise": 1.0,
            },
        },
        "8": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "res_multistep"},
        },
        "9": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": seed},
        },
        "10": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["9", 0],
                "guider": ["6", 0],
                "sampler": ["8", 0],
                "sigmas": ["7", 0],
                "latent_image": [conditioning_node, 1],
            },
        },
        "11": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["10", 0], "vae": ["3", 0]},
        },
        "12": {
            "class_type": "VAEDecodeAudio",
            "inputs": {"samples": ["10", 0], "vae": ["4", 0]},
        },
        "13": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["11", 0],
                "audio": ["12", 0],
                "fps": 24.0,
                "bit_depth": 8,
            },
        },
        output_node: {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["13", 0],
                "filename_prefix": "video/OPC_MiniMax_H3",
                "format": "mp4",
                "codec": "auto",
            },
        },
    }


def _add_seedvr2(workflow, factor, seed):
    workflow.pop("14", None)
    workflow.update({
        "15": {
            "class_type": "ResizeImageMaskNode",
            "inputs": {
                "input": ["11", 0],
                "resize_type": "scale by multiplier",
                "resize_type.multiplier": float(factor),
                "scale_method": "lanczos",
            },
        },
        "16": {
            "class_type": "SeedVR2Preprocess",
            "inputs": {"resized_images": ["15", 0]},
        },
        "17": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": SEEDVR2_VAE},
        },
        "18": {
            "class_type": "VAEEncodeTiled",
            "inputs": {
                "pixels": ["16", 0],
                "vae": ["17", 0],
                "tile_size": 512,
                "overlap": 128,
                "temporal_size": 64,
                "temporal_overlap": 8,
            },
        },
        "19": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": SEEDVR2_MODEL, "weight_dtype": "default"},
        },
        "20": {
            "class_type": "SeedVR2Conditioning",
            "inputs": {"model": ["19", 0], "vae_conditioning": ["21", 0]},
        },
        "21": {
            "class_type": "SeedVR2TemporalChunk",
            "inputs": {
                "latent": ["18", 0],
                "temporal_overlap": 0,
                "chunking_mode": "auto",
            },
        },
        "22": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["19", 0],
                "seed": seed,
                "steps": 1,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "positive": ["20", 0],
                "negative": ["20", 1],
                "latent_image": ["21", 0],
                "denoise": 1.0,
            },
        },
        "23": {
            "class_type": "SeedVR2TemporalMerge",
            "inputs": {"latents": ["22", 0], "temporal_overlap": ["21", 1]},
        },
        "24": {
            "class_type": "VAEDecodeTiled",
            "inputs": {
                "samples": ["23", 0],
                "vae": ["17", 0],
                "tile_size": 512,
                "overlap": 128,
                "temporal_size": 64,
                "temporal_overlap": 8,
            },
        },
        "25": {
            "class_type": "SeedVR2PostProcessing",
            "inputs": {
                "images": ["24", 0],
                "original_resized_images": ["15", 0],
                "color_correction_method": "none",
            },
        },
        "26": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["25", 0],
                "audio": ["12", 0],
                "fps": 24.0,
                "bit_depth": 8,
            },
        },
        "27": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["26", 0],
                "filename_prefix": "video/OPC_MiniMax_H3_SeedVR2",
                "format": "mp4",
                "codec": "auto",
            },
        },
    })


def build_h3_workflow(
    alias,
    prompt,
    width=864,
    height=480,
    duration=5,
    steps=20,
    seed=-1,
    first_frame=None,
    last_frame=None,
    reference_images=None,
    reference_videos=None,
    reference_audios=None,
    include_reference_video_audio=True,
    ref_image_size="match",
    upscale=False,
    upscale_factor=2.0,
):
    """Build a ComfyUI API workflow for a MiniMax H3 CLI alias."""
    legacy_upscale_alias = alias == "h3-t2v-upscale"
    base_alias = "h3-t2v" if legacy_upscale_alias else alias
    upscale = bool(upscale or legacy_upscale_alias)
    _validate(alias, prompt, width, height, duration, steps, upscale, upscale_factor)
    reference_images = list(reference_images or [])
    reference_videos = list(reference_videos or [])
    reference_audios = list(reference_audios or [])
    if base_alias != "h3-i2v" and (first_frame or last_frame):
        raise ValueError("First/last frames are only valid for h3-i2v")
    if base_alias != "h3-r2v" and (reference_images or reference_videos or reference_audios):
        raise ValueError("Reference media are only valid for h3-r2v")
    if base_alias == "h3-i2v" and not (first_frame or last_frame):
        raise ValueError("h3-i2v requires --first-frame or --last-frame")
    if base_alias == "h3-r2v" and not (reference_images or reference_videos or reference_audios):
        raise ValueError("h3-r2v requires at least one image, video, or audio reference")
    if len(reference_images) > 9:
        raise ValueError("h3-r2v accepts at most nine reference images")
    if len(reference_videos) > 3:
        raise ValueError("h3-r2v accepts at most three reference videos")
    if len(reference_audios) > 3:
        raise ValueError("h3-r2v accepts at most three standalone reference audios")
    if ref_image_size not in ("match", "max"):
        raise ValueError("Reference image size must be 'match' or 'max'")

    seed = int(seed)
    if seed < 0:
        seed = random.SystemRandom().randrange(0, 2**63)
    frames = duration_to_frames(duration)
    model_name = H3_REF2VA_MODEL if base_alias == "h3-r2v" else H3_FL2VA_MODEL
    workflow = _base_workflow(model_name, "5", steps, seed)

    if base_alias == "h3-r2v":
        inputs = {
            "clip": ["2", 0],
            "vae": ["3", 0],
            "audio_vae": ["4", 0],
            "prompt": prompt.strip(),
            "width": int(width),
            "height": int(height),
            "length": frames,
            "ref_image_size": ref_image_size,
        }
        for index, filename in enumerate(reference_images):
            node_id = str(30 + index)
            workflow[node_id] = {
                "class_type": "LoadImage",
                "inputs": {"image": filename},
            }
            inputs[f"ref_images.ref_image_{index}"] = [node_id, 0]
        for index, filename in enumerate(reference_videos):
            load_node_id = str(50 + index * 2)
            components_node_id = str(51 + index * 2)
            workflow[load_node_id] = {
                "class_type": "LoadVideo",
                "inputs": {"file": filename},
            }
            workflow[components_node_id] = {
                "class_type": "GetVideoComponents",
                "inputs": {"video": [load_node_id, 0]},
            }
            inputs[f"ref_videos.ref_video_{index}"] = [components_node_id, 0]
            if include_reference_video_audio:
                inputs[f"ref_video_audios.ref_video_audio_{index}"] = [components_node_id, 1]
        for index, filename in enumerate(reference_audios):
            node_id = str(70 + index)
            workflow[node_id] = {
                "class_type": "LoadAudio",
                "inputs": {"audio": filename},
            }
            inputs[f"ref_audios.ref_audio_{index}"] = [node_id, 0]
        workflow["5"] = {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": inputs,
        }
    else:
        inputs = {
            "clip": ["2", 0],
            "vae": ["3", 0],
            "prompt": prompt.strip(),
            "width": int(width),
            "height": int(height),
            "length": frames,
        }
        for node_id, field, filename in (
            ("30", "first_frame", first_frame),
            ("31", "last_frame", last_frame),
        ):
            if filename:
                workflow[node_id] = {
                    "class_type": "LoadImage",
                    "inputs": {"image": filename},
                }
                inputs[field] = [node_id, 0]
        workflow["5"] = {
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": inputs,
        }

    if upscale:
        _add_seedvr2(workflow, upscale_factor, seed)

    return workflow
