#!/usr/bin/env python3
"""
Cutx Auto Server - Qwen3-ASR Edition for opc-cli

Usage:
    uv run python scripts/cut/server.py --video /path/to/video.mp4 [--json /path/to/result.json]
"""

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
from flask import Flask, jsonify, request, send_file, render_template
from flask_cors import CORS

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(os.path.dirname(SCRIPTS_DIR))  # Go up two levels to skill root
TEMPLATE_FOLDER = os.path.join(SKILL_DIR, 'web', 'templates')

# Add scripts dir to path for imports (shared module is in scripts/)
sys.path.insert(0, os.path.join(SKILL_DIR, 'scripts'))
from shared.config import load_config

# Get workspace from config or use default
cfg = load_config()
workspace_dir = os.path.expanduser(cfg.get('workspace_dir', str(Path.home() / ".opc_cli" / "workspace")))
WORKSPACE_DIR = Path(workspace_dir)
UPLOAD_FOLDER = WORKSPACE_DIR / 'uploads'
OUTPUT_FOLDER = WORKSPACE_DIR / 'outputs'

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder=str(TEMPLATE_FOLDER))
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

AUTO_FILE_ID = None
AUTO_VIDEO_PATH = None
AUTO_JSON_PATH = None


def run_asr_pipeline(audio_path: str, language: Optional[str] = None) -> dict:
    """Call opc asr command for ASR processing, output JSON format."""
    output_file = OUTPUT_FOLDER / f"temp_{uuid.uuid4().hex[:8]}.json"

    cmd = [
        sys.executable, '-m', 'opc',
        'asr', str(audio_path),
        '--format', 'json',
        '-o', str(output_file),
    ]
    if language:
        cmd.extend(['--language', language])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=SKILL_DIR)

    if result.returncode != 0:
        raise Exception(f"ASR failed: {result.stderr}")

    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {
            "language": data.get("language", "Chinese"),
            "text": data.get("text", ""),
            "duration": data.get("duration", 0),
            "words": data.get("words", []),
        }
    return {}


def init_auto_mode(video_path, json_path: Optional[str] = None, language: str = 'Chinese'):
    """Initialize auto-load mode."""
    global AUTO_FILE_ID, AUTO_VIDEO_PATH, AUTO_JSON_PATH

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    AUTO_FILE_ID = video_path.stem
    AUTO_VIDEO_PATH = str(video_path)

    if json_path and Path(json_path).exists():
        print(f"Loading existing JSON: {json_path}")
        AUTO_JSON_PATH = str(json_path)
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            asr_result = data.get('asr_result', data)
    else:
        print(f"Running ASR on: {video_path}")
        asr_result = run_asr_pipeline(str(video_path), language)
        AUTO_JSON_PATH = str(OUTPUT_FOLDER / f"{AUTO_FILE_ID}.json")

    # Wrap words for cutx frontend compatibility
    if 'words' in asr_result and 'segments' not in asr_result:
        asr_result_for_frontend = {
            "language": asr_result.get("language", "Chinese"),
            "text": asr_result.get("text", ""),
            "duration": asr_result.get("duration", 0),
            "segments": [{"words": asr_result["words"]}]
        }
    else:
        asr_result_for_frontend = asr_result

    metadata = {
        'file_id': AUTO_FILE_ID,
        'original_filename': video_path.name,
        'file_path': AUTO_VIDEO_PATH,
        'asr_result': asr_result_for_frontend,
        'auto_mode': True
    }

    with open(OUTPUT_FOLDER / f"{AUTO_FILE_ID}.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    words_count = len(asr_result_for_frontend.get('segments', [{}])[0].get('words', []))
    print(f"Auto mode initialized: File ID={AUTO_FILE_ID}, Video={AUTO_VIDEO_PATH}, Words={words_count}")
    return AUTO_FILE_ID


@app.route('/')
def index():
    return render_template('editor.html')


@app.route('/api/auto-file', methods=['GET'])
def get_auto_file():
    if not AUTO_FILE_ID:
        return jsonify({'auto_mode': False})
    json_path = OUTPUT_FOLDER / f"{AUTO_FILE_ID}.json"
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify({
        'auto_mode': True,
        'file_id': AUTO_FILE_ID,
        'filename': data['original_filename'],
        'asr_result': data['asr_result']
    })


@app.route('/api/upload', methods=['POST'])
def upload_video():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    file_id = str(uuid.uuid4())[:8]
    filename = file.filename
    file_path = UPLOAD_FOLDER / f"{file_id}{Path(filename).suffix}"
    file.save(file_path)

    try:
        asr_result = run_asr_pipeline(str(file_path), request.form.get('language'))
        json_path = OUTPUT_FOLDER / f"{file_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'file_id': file_id,
                'original_filename': filename,
                'file_path': str(file_path),
                'asr_result': asr_result,
            }, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True, 'file_id': file_id, 'filename': filename, 'asr_result': asr_result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/video/<file_id>', methods=['GET'])
def get_video(file_id):
    if file_id == AUTO_FILE_ID and AUTO_VIDEO_PATH:
        return send_file(AUTO_VIDEO_PATH)
    json_path = OUTPUT_FOLDER / f"{file_id}.json"
    if not json_path.exists():
        return jsonify({'error': 'File not found'}), 404
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    file_path = data.get('file_path')
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'Video file not found'}), 404
    return send_file(file_path)


@app.route('/api/export', methods=['POST'])
def export_video():
    data = request.json
    file_id = data.get('file_id')
    cuts = data.get('cuts', [])
    output_format = data.get('format', 'mp4')

    # Valley correction parameters (optional, default to safe values)
    apply_valley_correction = data.get('apply_valley_correction', True)
    energy_threshold = data.get('energy_threshold', 0.7)
    search_ms = data.get('search_ms', 100)

    if not file_id or not cuts:
        return jsonify({'error': 'Missing file_id or cuts'}), 400

    if file_id == AUTO_FILE_ID and AUTO_VIDEO_PATH:
        source_path = AUTO_VIDEO_PATH
    else:
        json_path = OUTPUT_FOLDER / f"{file_id}.json"
        if not json_path.exists():
            return jsonify({'error': 'Source file not found'}), 404
        with open(json_path, 'r', encoding='utf-8') as f:
            file_data = json.load(f)
        source_path = file_data.get('file_path')

    if not source_path or not os.path.exists(source_path):
        return jsonify({'error': 'Source video not found'}), 404

    # Apply valley correction if requested
    corrected_cuts = []
    if apply_valley_correction:
        try:
            import soundfile as sf
            # Extract audio from video for analysis
            temp_audio = OUTPUT_FOLDER / f"temp_{file_id}_audio.wav"
            cmd = ['ffmpeg', '-y', '-i', source_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', str(temp_audio)]
            subprocess.run(cmd, check=True, capture_output=True)

            wav, sr = sf.read(str(temp_audio))
            if wav.ndim > 1:
                wav = np.mean(wav, axis=1)

            for cut in cuts:
                from .valley_finder import find_valley_boundaries
                result = find_valley_boundaries(
                    wav, sr,
                    cut['start'], cut['end'],
                    search_ms, search_ms,
                    energy_threshold
                )
                corrected_cuts.append({
                    'start': result['cut_start'],
                    'end': result['cut_end']
                })

            # Clean up temp audio
            if temp_audio.exists():
                temp_audio.unlink()

        except Exception as e:
            # If correction fails, use original cuts
            print(f"Valley correction failed: {e}, using original cuts")
            corrected_cuts = cuts
    else:
        corrected_cuts = cuts

    try:
        output_id = str(uuid.uuid4())[:8]
        output_path = OUTPUT_FOLDER / f"{file_id}_exported_{output_id}.{output_format}"

        if len(corrected_cuts) == 1:
            cut = corrected_cuts[0]
            duration = cut['end'] - cut['start']
            cmd = ['ffmpeg', '-y', '-i', source_path, '-ss', str(cut['start']), '-t', str(duration), '-c', 'copy', str(output_path)]
            subprocess.run(cmd, check=True, capture_output=True)
        else:
            segment_files = []
            concat_list_path = None
            try:
                for i, cut in enumerate(corrected_cuts):
                    segment_path = OUTPUT_FOLDER / f"{file_id}_segment_{i}.mp4"
                    duration = cut['end'] - cut['start']
                    cmd = ['ffmpeg', '-y', '-i', source_path, '-ss', str(cut['start']), '-t', str(duration), '-c', 'copy', str(segment_path)]
                    subprocess.run(cmd, check=True, capture_output=True)
                    segment_files.append(segment_path)

                concat_list_path = OUTPUT_FOLDER / f"{file_id}_concat.txt"
                with open(concat_list_path, 'w') as f:
                    for seg_file in segment_files:
                        f.write(f"file '{seg_file}'\n")
                cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_list_path), '-c', 'copy', str(output_path)]
                subprocess.run(cmd, check=True, capture_output=True)
            finally:
                for seg_file in segment_files:
                    if seg_file.exists():
                        seg_file.unlink()
                if concat_list_path and concat_list_path.exists():
                    concat_list_path.unlink()

        return jsonify({'success': True, 'output_file': str(output_path), 'download_url': f'/api/download/{output_path.name}'})
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    file_path = OUTPUT_FOLDER / filename
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    return send_file(file_path, as_attachment=True)


@app.route('/api/find-valley', methods=['POST'])
def find_valley():
    """
    找到字词边界附近的能量谷底作为剪切点

    Request JSON:
    {
        "file_id": "xxx",  # 可选，如果有 file_id 则从缓存加载音频
        "audio_path": "/path/to/audio.mp3",  # 或者指定音频路径
        "word_start_time": 0.08,  # 第一个字的开始时间
        "word_end_time": 3.68,    # 最后一个字的结束时间
        "left_search_ms": 100,    # 可选，向左搜索范围 (ms)
        "right_search_ms": 100,   # 可选，向右搜索范围 (ms)
        "threshold": 0.7          # 可选，能量比阈值
    }

    Response JSON:
    {
        "cut_start": 0.075,       # 修正后的开始时间
        "cut_end": 3.695,         # 修正后的结束时间
        "left_ratio": 0.02,       # 左边界能量比
        "right_ratio": 0.05,      # 右边界能量比
        "quality": "good",        # good | fair | poor
        "warning": null           # 警告信息
    }
    """
    from .valley_finder import find_valley_boundaries, load_audio_for_valley

    data = request.json
    if not data:
        return jsonify({'error': '缺少请求数据'}), 400

    # 获取音频路径
    audio_path = data.get('audio_path')
    file_id = data.get('file_id')

    if not audio_path:
        # 尝试从 file_id 获取
        if file_id == AUTO_FILE_ID and AUTO_VIDEO_PATH:
            audio_path = AUTO_VIDEO_PATH
        elif file_id:
            json_path = OUTPUT_FOLDER / f"{file_id}.json"
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                audio_path = file_data.get('file_path')

    if not audio_path:
        return jsonify({'error': '未指定音频路径'}), 400

    if not os.path.exists(audio_path):
        return jsonify({'error': f'音频文件不存在：{audio_path}'}), 404

    # 获取参数
    word_start_time = data.get('word_start_time')
    word_end_time = data.get('word_end_time')

    if word_start_time is None or word_end_time is None:
        return jsonify({'error': '必须指定 word_start_time 和 word_end_time'}), 400

    left_search_ms = data.get('left_search_ms', 100)
    right_search_ms = data.get('right_search_ms', 100)
    threshold = data.get('threshold', 0.7)

    # 加载音频并查找谷底
    try:
        wav, sr = load_audio_for_valley(audio_path)
        result = find_valley_boundaries(
            wav, sr,
            word_start_time, word_end_time,
            left_search_ms, right_search_ms,
            threshold
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def main():
    # Get default port from config
    cfg = load_config()
    default_port = cfg.get('cut_server_port', 12082)

    parser = argparse.ArgumentParser(description='Cutx Auto Server')
    parser.add_argument('--video', '-v', required=True, help='Video file path')
    parser.add_argument('--json', '-j', help='Existing ASR result JSON path')
    parser.add_argument('--language', '-l', default='Chinese', help='Language')
    parser.add_argument('--port', '-p', type=int, default=default_port, help='Server port')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser')
    parser.add_argument('--host', '-H', default='0.0.0.0', help='Server host')

    args = parser.parse_args()
    file_id = init_auto_mode(args.video, args.json, args.language)
    url = f"http://localhost:{args.port}"

    print(f"\n{'='*60}\nCutx Auto Server started\n{'='*60}")
    print(f"URL: {url}\nFile ID: {file_id}\nVideo: {args.video}")
    print(f"{'='*60}\n")

    if not args.no_browser:
        import webbrowser
        webbrowser.open(url)

    app.run(host=args.host, port=args.port, debug=True)


if __name__ == '__main__':
    main()
