#!/usr/bin/env python3
"""
Cutx Auto Server - Qwen3-ASR Edition
支持自动加载指定文件的Web服务

Usage:
    python auto_app.py --video /path/to/video.mp4 [--json /path/to/result.json]

如果不提供 --json，会自动运行 ASR 处理
"""

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, send_file, render_template
from flask_cors import CORS

from scripts.shared.config import load_config

cfg = load_config()
_workspace = Path(cfg.get('workspace_dir', str(Path.home() / ".opc_cli" / "workspace"))).expanduser()

# 模板和静态资源相对于项目根目录
_project_dir = Path(__file__).resolve().parent.parent
app = Flask(__name__,
    template_folder=str(_project_dir / 'cut' / 'web' / 'templates'),
    static_folder=str(_project_dir / 'cut' / 'web' / 'static')
)
CORS(app)

# 配置
UPLOAD_FOLDER = _workspace / 'uploads'
OUTPUT_FOLDER = _workspace / 'outputs'
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# 全局状态 - 自动加载的文件
AUTO_FILE_ID = None
AUTO_VIDEO_PATH = None
AUTO_JSON_PATH = None


def run_asr_pipeline(audio_path: str, language: Optional[str] = None) -> dict:
    """调用 asr_align_pipeline.py 进行 ASR 处理"""
    python_exe = sys.executable
    pipeline_script = Path(__file__).parent.parent / 'asr' / 'asr_align_pipeline.py'
    output_file = OUTPUT_FOLDER / f"temp_{uuid.uuid4().hex[:8]}.json"

    cmd = [
        python_exe, pipeline_script,
        audio_path,
        '--language', language or 'Chinese',
        '--output', str(output_file)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"ASR failed: {result.stderr}")

    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        os.unlink(output_file)
        return data.get('asr_result', {})

    return {}


def init_auto_mode(video_path: str, json_path: Optional[str] = None, language: str = 'Chinese'):
    """初始化自动加载模式"""
    global AUTO_FILE_ID, AUTO_VIDEO_PATH, AUTO_JSON_PATH

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # 生成文件ID
    AUTO_FILE_ID = video_path.stem  # 使用文件名作为ID
    AUTO_VIDEO_PATH = str(video_path)

    # 检查是否已有JSON文件
    if json_path and Path(json_path).exists():
        print(f"Loading existing JSON: {json_path}")
        AUTO_JSON_PATH = str(json_path)
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            asr_result = data.get('asr_result', data)
    else:
        # 运行ASR处理
        print(f"Running ASR on: {video_path}")
        asr_result = run_asr_pipeline(str(video_path), language)

        # 保存JSON
        AUTO_JSON_PATH = str(OUTPUT_FOLDER / f"{AUTO_FILE_ID}.json")

    # 保存或更新元数据
    metadata = {
        'file_id': AUTO_FILE_ID,
        'original_filename': video_path.name,
        'file_path': AUTO_VIDEO_PATH,
        'asr_result': asr_result,
        'auto_mode': True
    }

    with open(OUTPUT_FOLDER / f"{AUTO_FILE_ID}.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"Auto mode initialized:")
    print(f"  File ID: {AUTO_FILE_ID}")
    print(f"  Video: {AUTO_VIDEO_PATH}")
    print(f"  Duration: {asr_result.get('duration', 'N/A')}s")
    print(f"  Words: {len(asr_result.get('segments', [{}])[0].get('words', []))}")

    return AUTO_FILE_ID


@app.route('/')
def index():
    """主页面 - 自动模式下会加载预设文件"""
    return render_template('editor.html')


@app.route('/api/auto-file', methods=['GET'])
def get_auto_file():
    """获取自动加载的文件信息"""
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
    """上传视频/音频文件并进行ASR处理（兼容手动上传模式）"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    file_id = str(uuid.uuid4())[:8]
    filename = file.filename
    file_path = UPLOAD_FOLDER / f"{file_id}{Path(filename).suffix}"
    file.save(file_path)

    language = request.form.get('language', None)

    try:
        asr_result = run_asr_pipeline(str(file_path), language)

        json_path = OUTPUT_FOLDER / f"{file_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'file_id': file_id,
                'original_filename': filename,
                'file_path': str(file_path),
                'asr_result': asr_result,
            }, f, ensure_ascii=False, indent=2)

        return jsonify({
            'success': True,
            'file_id': file_id,
            'filename': filename,
            'asr_result': asr_result,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/video/<file_id>', methods=['GET'])
def get_video(file_id):
    """获取视频文件"""
    # 自动模式直接使用预设路径
    if file_id == AUTO_FILE_ID and AUTO_VIDEO_PATH:
        return send_file(AUTO_VIDEO_PATH)

    # 否则从JSON元数据读取
    json_path = OUTPUT_FOLDER / f"{file_id}.json"
    if not json_path.exists():
        return jsonify({'error': 'File not found'}), 404

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    file_path = data.get('file_path')
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'Video file not found'}), 404

    return send_file(file_path)


@app.route('/api/asr/<file_id>', methods=['GET'])
def get_asr_result(file_id):
    """获取ASR结果"""
    json_path = OUTPUT_FOLDER / f"{file_id}.json"
    if not json_path.exists():
        return jsonify({'error': 'ASR result not found'}), 404

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return jsonify(data)


@app.route('/api/export', methods=['POST'])
def export_video():
    """根据剪辑点导出视频"""
    data = request.json
    file_id = data.get('file_id')
    cuts = data.get('cuts', [])
    output_format = data.get('format', 'mp4')

    if not file_id or not cuts:
        return jsonify({'error': 'Missing file_id or cuts'}), 400

    # 确定源文件路径
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

    try:
        output_id = str(uuid.uuid4())[:8]
        output_path = OUTPUT_FOLDER / f"{file_id}_exported_{output_id}.{output_format}"

        if len(cuts) == 1:
            cut = cuts[0]
            duration = cut['end'] - cut['start']
            cmd = [
                'ffmpeg', '-y', '-i', source_path,
                '-ss', str(cut['start']),
                '-t', str(duration),
                '-c', 'copy',
                str(output_path)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        else:
            segment_files = []
            try:
                for i, cut in enumerate(cuts):
                    segment_path = OUTPUT_FOLDER / f"{file_id}_segment_{i}.mp4"
                    duration = cut['end'] - cut['start']
                    cmd = [
                        'ffmpeg', '-y', '-i', source_path,
                        '-ss', str(cut['start']),
                        '-t', str(duration),
                        '-c', 'copy',
                        str(segment_path)
                    ]
                    subprocess.run(cmd, check=True, capture_output=True)
                    segment_files.append(segment_path)

                concat_list = OUTPUT_FOLDER / f"{file_id}_concat.txt"
                with open(concat_list, 'w') as f:
                    for seg_file in segment_files:
                        f.write(f"file '{seg_file}'\n")

                cmd = [
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                    '-i', str(concat_list),
                    '-c', 'copy',
                    str(output_path)
                ]
                subprocess.run(cmd, check=True, capture_output=True)

            finally:
                for seg_file in segment_files:
                    if seg_file.exists():
                        seg_file.unlink()
                if concat_list.exists():
                    concat_list.unlink()

        return jsonify({
            'success': True,
            'output_file': str(output_path),
            'download_url': f'/api/download/{output_path.name}'
        })

    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    """下载导出的文件"""
    file_path = OUTPUT_FOLDER / filename
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404

    return send_file(file_path, as_attachment=True)


def main():
    parser = argparse.ArgumentParser(description='Cutx Auto Server')
    parser.add_argument('--video', '-v', required=True, help='视频文件路径')
    parser.add_argument('--json', '-j', help='已有的ASR结果JSON文件路径')
    parser.add_argument('--language', '-l', default='Chinese', help='语言')
    parser.add_argument('--port', '-p', type=int, default=8080, help='服务器端口')
    parser.add_argument('--no-browser', action='store_true', help='不自动打开浏览器')

    args = parser.parse_args()

    # 初始化自动模式
    file_id = init_auto_mode(args.video, args.json, args.language)

    # 构建访问URL
    url = f"http://localhost:{args.port}"

    print(f"\n{'='*60}")
    print(f"Cutx Auto Server 已启动")
    print(f"{'='*60}")
    print(f"访问地址: {url}")
    print(f"文件ID: {file_id}")
    print(f"视频: {args.video}")
    if args.json:
        print(f"JSON: {args.json}")
    print(f"{'='*60}\n")

    # 自动打开浏览器
    if not args.no_browser:
        import webbrowser
        webbrowser.open(url)

    # 启动服务器
    app.run(host='0.0.0.0', port=args.port, debug=False)


if __name__ == '__main__':
    main()
