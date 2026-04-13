"""edge-tts engine for xt tts."""

import subprocess


def tts_edge(text, voice, output_file, rate="+0%", pitch="+0Hz", volume="+0%"):
    """Generate speech using edge-tts (Microsoft online TTS).

    Args:
        text: Text to synthesize.
        voice: Voice name, e.g. 'zh-CN-XiaoxiaoNeural'. Use 'xt voices -e edge-tts' to list all.
        output_file: Output file path. Extension determines format (.mp3).
        rate: Speed adjustment, e.g. '+20%', '-10%'. Default '+0%'.
        pitch: Pitch adjustment, e.g. '+10Hz', '-5Hz'. Default '+0Hz'.
        volume: Volume adjustment, e.g. '+50%'. Default '+0%'.
    """
    cmd = ["edge-tts", "--voice", voice, "--text", text,
           "--rate", rate, "--pitch", pitch, "--volume", volume,
           "--write-media", output_file]
    subprocess.run(cmd, check=True)
    return output_file
