"""Unit tests for MiniMax H3 ComfyUI workflow construction."""

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from video.h3 import build_h3_workflow, duration_to_frames  # noqa: E402
from video.comfyui import _extract_timing  # noqa: E402


class H3WorkflowTests(unittest.TestCase):
    def test_duration_uses_h3_frame_grid(self):
        self.assertEqual(duration_to_frames(5), 124)
        self.assertEqual(duration_to_frames(15), 362)

    def test_text_to_video_has_native_audio(self):
        workflow = build_h3_workflow("h3-t2v", "test", seed=42)
        self.assertEqual(workflow["5"]["class_type"], "MiniMaxH3ImageToVideo")
        self.assertEqual(workflow["5"]["inputs"]["length"], 124)
        self.assertEqual(workflow["12"]["class_type"], "VAEDecodeAudio")
        self.assertEqual(workflow["13"]["inputs"]["audio"], ["12", 0])
        self.assertEqual(workflow["14"]["inputs"]["format"], "mp4")

    def test_first_last_frame_nodes_are_connected(self):
        workflow = build_h3_workflow(
            "h3-i2v",
            "test",
            first_frame="first.png",
            last_frame="last.png",
            seed=42,
        )
        self.assertEqual(workflow["30"]["inputs"]["image"], "first.png")
        self.assertEqual(workflow["31"]["inputs"]["image"], "last.png")
        self.assertEqual(workflow["5"]["inputs"]["first_frame"], ["30", 0])
        self.assertEqual(workflow["5"]["inputs"]["last_frame"], ["31", 0])

    def test_reference_images_use_autogrow_input_names(self):
        workflow = build_h3_workflow(
            "h3-r2v",
            "test",
            reference_images=["one.png", "two.png"],
            seed=42,
        )
        inputs = workflow["5"]["inputs"]
        self.assertEqual(workflow["5"]["class_type"], "MiniMaxH3ReferenceToVideo")
        self.assertEqual(inputs["ref_images.ref_image_0"], ["30", 0])
        self.assertEqual(inputs["ref_images.ref_image_1"], ["31", 0])
        self.assertEqual(inputs["audio_vae"], ["4", 0])

    def test_reference_videos_and_audio_are_connected(self):
        workflow = build_h3_workflow(
            "h3-r2v",
            "Use <Video 1> motion and <Audio 2> voice",
            reference_videos=["clip.mp4"],
            reference_audios=["voice.wav"],
            seed=42,
        )
        inputs = workflow["5"]["inputs"]
        self.assertEqual(workflow["50"]["class_type"], "LoadVideo")
        self.assertEqual(workflow["51"]["class_type"], "GetVideoComponents")
        self.assertEqual(inputs["ref_videos.ref_video_0"], ["51", 0])
        self.assertEqual(inputs["ref_video_audios.ref_video_audio_0"], ["51", 1])
        self.assertEqual(workflow["70"]["class_type"], "LoadAudio")
        self.assertEqual(inputs["ref_audios.ref_audio_0"], ["70", 0])

        silent = build_h3_workflow(
            "h3-r2v",
            "Use <Video 1> motion",
            reference_videos=["clip.mp4"],
            include_reference_video_audio=False,
            seed=42,
        )
        self.assertNotIn("ref_video_audios.ref_video_audio_0", silent["5"]["inputs"])

    def test_seedvr2_upscale_preserves_audio_for_every_mode(self):
        workflow = build_h3_workflow(
            "h3-t2v", "test", upscale=True, upscale_factor=2, seed=42
        )
        resize = workflow["15"]["inputs"]
        self.assertEqual(resize["resize_type"], "scale by multiplier")
        self.assertEqual(resize["resize_type.multiplier"], 2.0)
        self.assertEqual(
            workflow["21"]["inputs"]["chunking_mode"],
            "auto",
        )
        self.assertEqual(workflow["20"]["inputs"]["vae_conditioning"], ["21", 0])
        self.assertEqual(workflow["26"]["inputs"]["audio"], ["12", 0])
        self.assertNotIn("14", workflow)
        self.assertEqual(workflow["27"]["class_type"], "SaveVideo")

        image_workflow = build_h3_workflow(
            "h3-i2v",
            "test",
            first_frame="first.png",
            upscale=True,
            upscale_factor=1.5,
            seed=42,
        )
        self.assertEqual(image_workflow["15"]["inputs"]["resize_type.multiplier"], 1.5)

        reference_workflow = build_h3_workflow(
            "h3-r2v",
            "test",
            reference_images=["reference.png"],
            upscale=True,
            upscale_factor=3,
            seed=42,
        )
        self.assertEqual(reference_workflow["15"]["inputs"]["resize_type.multiplier"], 3.0)

    def test_upscale_is_disabled_by_default_and_legacy_alias_still_works(self):
        workflow = build_h3_workflow("h3-t2v", "test", seed=42)
        self.assertIn("14", workflow)
        self.assertNotIn("15", workflow)

        legacy = build_h3_workflow("h3-t2v-upscale", "test", seed=42)
        self.assertNotIn("14", legacy)
        self.assertIn("27", legacy)

    def test_invalid_inputs_fail_early(self):
        with self.assertRaisesRegex(ValueError, "multiples of 32"):
            build_h3_workflow("h3-t2v", "test", width=853)
        with self.assertRaisesRegex(ValueError, "requires"):
            build_h3_workflow("h3-r2v", "test")
        with self.assertRaisesRegex(ValueError, "between 5 and 15"):
            build_h3_workflow("h3-t2v", "test", duration=4)
        with self.assertRaisesRegex(ValueError, "only valid for h3-i2v"):
            build_h3_workflow("h3-t2v", "test", first_frame="first.png")
        with self.assertRaisesRegex(ValueError, "greater than 1"):
            build_h3_workflow("h3-t2v", "test", upscale=True, upscale_factor=1)

    def test_queue_and_execution_timing_are_separate(self):
        history = {
            "status": {
                "messages": [
                    ["execution_start", {"timestamp": 1500}],
                    ["execution_success", {"timestamp": 3750}],
                ]
            }
        }
        self.assertEqual(
            _extract_timing(history, submitted_at_ms=1000),
            {"queue_seconds": 0.5, "execution_seconds": 2.25},
        )


if __name__ == "__main__":
    unittest.main()
