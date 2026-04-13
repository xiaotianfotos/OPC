# opc - TTS & ASR 语音工具

**描述:** 多引擎 TTS 命令行工具，支持 edge-tts（微软在线）和 Qwen3-TTS（本地模型）。支持 AirPlay 和 DLNA 设备播放。
**ASR 功能:** 基于 Qwen3-ASR 的语音识别与强制对齐，4 阶段 Pipeline 架构生成 SRT/ASS 卡拉 OK 字幕。
**跨平台:** Linux 用 CUDA (NVIDIA GPU)，macOS 用 MLX (Apple Silicon)，命令行完全一致。

## 环境安装（uv 管理）

本项目使用 uv 管理依赖，**自动检测平台**：Linux 装 CUDA 版，macOS 装 MLX 版。

```bash
# 安装 uv（如果还没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 一条命令安装（自动按平台选择依赖）
cd ~/.claude/skills/opc-cli
uv sync

# 后续所有命令通过 uv run 执行
uv run python scripts/opc.py --help
```

**模型下载源：**
默认使用 ModelScope（中国大陆友好），也可切换到 HuggingFace：
```bash
# 查看/设置模型下载源
opc config --show
opc config --set-model-source modelscope   # 默认
opc config --set-model-source huggingface  # MLX 8bit 量化模型

# 设置模型缓存目录
opc config --set-model-cache-dir /vol2/1000/llm/models
```

首次运行时模型会自动下载（ASR 需要约 5GB 磁盘空间）。

## 快速开始

```bash
# 发现并设置默认播放设备
uv run python scripts/opc.py discover --set-default

# 基础 TTS（使用配置默认引擎）
uv run python scripts/opc.py tts "你好，世界！"

# 生成并立即播放
uv run python scripts/opc.py say "你好，世界！"

# 查看配置
uv run python scripts/opc.py config --show
```

## TTS 命令

### `opc tts <text>` — 生成语音文件

```bash
# edge-tts 基础
uv run python scripts/opc.py tts "你好" -e edge-tts

# edge-tts 带语速/音调
uv run python scripts/opc.py tts "你好" -e edge-tts --rate +20% --pitch +5Hz

# qwen 内置音色
uv run python scripts/opc.py tts "你好" -e qwen --speaker Vivian

# qwen 带情绪指令
uv run python scripts/opc.py tts "你好" -e qwen --speaker Vivian --instruct "用愤怒的语气说"

# qwen 声音设计
uv run python scripts/opc.py tts "你好" -e qwen --mode voice_design --instruct "温柔的女声，音调偏高"

# qwen 声音克隆
uv run python scripts/opc.py tts "你好" -e qwen --mode voice_clone --ref-audio ref.wav --ref-text "参考文本"
```

**参数：**
- `-e, --engine` — 引擎：`edge-tts` | `qwen`
- `-v, --voice` — edge-tts 音色名
- `-l, --language` — 语言 (qwen): Auto, Chinese, English 等
- `-o, --output` — 输出文件路径
- `--stdin` — 从 stdin 读取文本

**edge-tts 选项：**
- `--rate` — 语速：`+20%`, `-10%`
- `--pitch` — 音调：`+10Hz`, `-5Hz`
- `--volume` — 音量：`+50%`

**qwen 选项：**
- `-m, --mode` — 模式：`custom_voice` | `voice_design` | `voice_clone`
- `-s, --speaker` — 内置音色：Vivian, Serena, Uncle_Fu, Dylan, Eric, Ryan, Aiden, Ono_Anna, Sohee
- `-i, --instruct` — 情绪/风格指令
- `--ref-audio` — 参考音频 (voice_clone)
- `--ref-text` — 参考文本 (voice_clone)
- `--x-vector-only` — 仅用 x-vector 克隆
- `--model-size` — 模型大小：`1.7B` | `0.6B`

### `opc say <text>` — 生成并播放

参数同 `tts`，额外支持：
- `-d, --device` — 播放设备名

### `opc voices` — 列出可用音色

```bash
uv run python scripts/opc.py voices -e edge-tts   # 列出 322 个 edge-tts 音色
uv run python scripts/opc.py voices -e qwen       # 列出 9 个 qwen 内置音色
```

### `opc discover` — 发现播放设备

```bash
uv run python scripts/opc.py discover              # 列出所有 AirPlay/DLNA 设备
uv run python scripts/opc.py discover --set-default  # 自动设置（仅一个设备时）
```

### `opc config` — 配置管理

```bash
uv run python scripts/opc.py config --show
uv run python scripts/opc.py config --set-engine qwen
uv run python scripts/opc.py config --set-speaker Vivian
uv run python scripts/opc.py config --set-mode voice_design
uv run python scripts/opc.py config --set-model-size 0.6B
uv run python scripts/opc.py config --device "Black"
uv run python scripts/opc.py config --set-asr-model-size 1.7B
uv run python scripts/opc.py config --set-asr-language Chinese
```

## ASR Pipeline 命令

### `opc asr <audio>` — 语音识别与字幕生成

ASR 使用 4 阶段 Pipeline 架构：

```
Stage 1: ASR + Forced Alignment  → <name>.raw.json   (GPU 密集)
Stage 2: Sentence Breaking       → <name>.lines.json  (标点断句)
Stage 3: CSV Fix                 → 更新 lines.json    (多 CSV 校对)
Check:   Pre-render validation   → 检查超长行等问题
Stage 4: Render                  → .srt + .ass        (同时生成两种格式)
```

每阶段都保存中间文件，可从任意阶段恢复执行。

```bash
# 简单转录（文本输出到 stdout）
uv run python scripts/opc.py asr audio.mp3
uv run python scripts/opc.py asr audio.wav --language Chinese

# 生成字幕（同时输出 SRT + ASS）
uv run python scripts/opc.py asr audio.mp3 --format srt
uv run python scripts/opc.py asr audio.mp3 --format ass --style default

# JSON 输出（完整对齐数据）
uv run python scripts/opc.py asr audio.mp3 --format json -o result.json

# 使用 CSV 修正（从目录加载 fix_1.csv, fix_2.csv, ...）
uv run python scripts/opc.py asr audio.mp3 --format srt --fix-dir ./fixes
```

**参数：**
- `<audio>` — 音频文件路径 (wav, mp3, flac 等)
- `--format`, `-f` — 输出格式：`text` (默认) | `json` | `srt` (同时生成 ASS) | `ass` (同时生成 SRT)
- `--language`, `-l` — 语言提示 (Chinese, English 等)，不指定则自动检测
- `--model-size` — ASR 模型大小：`1.7B` (默认) | `0.6B`
- `--style` — ASS 字幕颜色风格：`default`
- `-o, --output` — 输出文件路径 (json 格式)
- `--fix-dir` — CSV 修正文件目录（包含 fix_*.csv）
- `--resume-from` — 从指定阶段恢复：`asr` | `break` | `fix` | `render`

### `opc asr-split` — 拆分超长字幕行

当 Check 阶段检测到超长行时，使用此命令按文本匹配拆分。AI Agent 工作流：

```bash
# 1. 运行 pipeline，check 失败时会报告超长行
uv run python scripts/opc.py asr audio.mp3 --format srt
# 输出：✗ [max_chars] Line 10 has 23.5 chars (max 14): "但我今天分享的不仅仅是 Harness 到底应该怎么样理解，"
#       Fix: opc asr-split <lines.json> --line 10 --after "..."

# 2. 指定断开位置的文本，匹配后在此处断行
uv run python scripts/opc.py asr-split audio.lines.json --line 10 --after "理解，"

# 3. 拆分完成后重新渲染（跳过 ASR 阶段）
uv run python scripts/opc.py asr audio.mp3 --format srt --resume-from render
```

**`--after` 参数：** 指定要匹配的文本片段，必须在该行中唯一匹配。匹配成功后在该文本之后断行，保留卡拉 OK 时间戳。

### Pipeline 恢复执行

跳过 GPU 密集的 ASR 阶段，直接从中间结果继续：

```bash
# 仅重新断句（改了 --max-chars 后）
uv run python scripts/opc.py asr audio.mp3 --format srt --resume-from break

# 重新应用 CSV 修正
uv run python scripts/opc.py asr audio.mp3 --format srt --resume-from fix --fix-dir ./fixes

# 拆分行后重新渲染
uv run python scripts/opc.py asr audio.mp3 --format srt --resume-from render
```

### CSV 修正文件格式

在 `--fix-dir` 目录下放置 `fix_1.csv`, `fix_2.csv`, ... 文件，按序号顺序应用：

```csv
被替换的文字，目标文字
Cloud Code,Claude Code
哈喽是，hallucination,
```

- 每行一条规则：`原文本，新文本`
- 新文本留空 = 删除该字幕行
- `#` 开头的行为注释
- 多个 CSV 按排序顺序依次应用（可迭代补充修正）

## 断句算法（Stage 2）

两遍扫描，文本优先：

**Pass 1 — 按句号分段：** 遇到句号/叹号/问号（.！？）强制断开，形成段落

**Pass 2 — 按逗号断行：** 在每个段落内，遇到逗号/分号/冒号（，,;；：:）断开

核心规则：**没有标点符号绝对不断行**。两个标点之间如果没有更小的标点，超长行保持完整，由 Check 阶段标记，通过 `opc asr-split` 由 AI 手动拆分。

## 配置

配置文件：`~/.opc_cli/opc/config.json`

| 键 | 默认值 | 说明 |
|---|---|---|
| `tts_engine` | `edge-tts` | 默认引擎 |
| `edge_voice` | `zh-CN-XiaoxiaoNeural` | edge-tts 默认音色 |
| `edge_rate` | `+0%` | edge-tts 默认语速 |
| `edge_pitch` | `+0Hz` | edge-tts 默认音调 |
| `edge_volume` | `+0%` | edge-tts 默认音量 |
| `qwen_model_size` | `1.7B` | qwen 模型大小 |
| `qwen_mode` | `custom_voice` | qwen 默认模式 |
| `qwen_speaker` | `Vivian` | qwen 默认音色 |
| `qwen_language` | `Auto` | qwen 默认语言 |
| `default_device` | | 默认播放设备 |
| `asr_model_size` | `1.7B` | ASR 模型大小 |
| `asr_language` | | ASR 默认语言提示 |
| `workspace_dir` | `~/opc-workspace` | ASR/Cut 工作目录 |
| `dashboard_host` | `0.0.0.0` | Dashboard 服务器监听地址 |
| `dashboard_port` | `12080` | Dashboard 服务器端口 |
| `cut_server_port` | `12082` | Cut 技能服务器默认端口 |
| `backend` | (自动检测) | 计算后端：`mlx` / `cuda` / 空(自动) |
| `model_source` | `modelscope` | 模型下载源：`modelscope` / `huggingface` |
| `model_cache_dir` | (默认缓存) | 模型下载缓存目录 |

## Cut - 视频剪辑命令

### `opc cut` — 基于 ASR 字词级时间戳的视频剪辑

启动 Web 服务器，提供可视化字幕级视频剪辑界面。

```bash
# 启动剪辑服务器（自动运行 ASR）
opc cut --video /path/to/video.mp4

# 使用已有的 ASR 结果
opc cut --video /path/to/video.mp4 --json /path/to/asr_result.json

# 自定义端口
opc cut --video /path/to/video.mp4 --port 9090

# 不自动打开浏览器
opc cut --video /path/to/video.mp4 --no-browser
```

**参数：**
- `--video`, `-v` — 视频文件路径（必需）
- `--json`, `-j` — 已有的 ASR 结果 JSON 文件路径（可选）
- `--language`, `-l` — 语言提示，默认 Chinese
- `--port`, `-p` — 服务器端口，默认 8080
- `--no-browser` — 不自动打开浏览器

**工作流程：**
1. 服务器启动并运行 ASR（或加载已有 JSON）
2. 自动打开浏览器访问 Web 界面
3. 在字幕编辑区删除字词/间隙
4. 视频预览时自动跳过已删除部分
5. 导出剪辑后的视频

**界面操作：**
- **双击字词** — 删除/恢复该字
- **拖拽选择** — 选中多个连续字词
- **Delete 键** — 删除选中的字词/间隙
- **Ctrl+A** — 全选
- **双击间隙** — 删除/恢复无声间隙（≥0.5s）

**输出格式：**
ASR 生成的 JSON 格式：
```json
{
  "language": "Chinese",
  "text": "完整转录文本...",
  "duration": 408.58,
  "words": [
    {"text": "大", "start_time": 0.0, "end_time": 0.16},
    {"text": "家", "start_time": 0.16, "end_time": 0.24},
    ...
  ]
}
```

## OPC Dashboard - 技能管理面板

OPC Dashboard 提供统一的技能管理界面，采用技能注册式架构。

### 启动 Dashboard

```bash
cd /vol2/1000/work/skills/opc-cli/dashboard/server
npm install          # 首次安装
npm run build        # 构建前端
node server-prod.js  # 启动服务器
```

Dashboard 将在 http://localhost:8080 启动

### 使用 Dashboard

1. **访问首页** http://localhost:8080/
   - 查看已注册的技能列表
   - 通过表单启动 Cut 服务

2. **启动 Cut 服务**
   - 输入视频文件路径
   - （可选）输入 ASR JSON 文件路径
   - 点击"启动剪辑服务"
   - 自动跳转到编辑界面

3. **Cut 编辑器** http://localhost:8080/skill/cut/editor
   - Iframe 嵌入 Cut 服务器
   - 动态获取服务器 URL

### Dashboard API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/skills | 获取所有技能列表 |
| GET | /api/skill/cut/status | 获取 Cut 技能状态 |
| POST | /api/skill/cut/init | 初始化 Cut 技能 |
| POST | /api/skill/cut/stop | 停止 Cut 技能 |

### 示例：通过 API 启动 Cut

```bash
curl -X POST http://localhost:8080/api/skill/cut/init \
  -H "Content-Type: application/json" \
  -d '{
    "video": "/path/to/video.mp4",
    "json": "/path/to/asr_result.json",
    "port": 8082
  }'
```

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    OPC Dashboard (Node.js)                  │
│                    Port: 8080                               │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │  Vue3 Frontend  │  │         Express API             │   │
│  │  - /            │  │  - GET  /api/skills             │   │
│  │  - /skill/cut   │  │  - GET  /api/skill/cut/status   │   │
│  │                 │  │  - POST /api/skill/cut/init     │   │
│  └────────┬────────┘  └─────────────┬───────────────────┘   │
│           │                        │ spawn uv run            │
│  ┌────────▼─────────────────────────────────────────────┐   │
│  │  iframe (http://localhost:808X)                      │   │
│  │  ┌───────────────────────────────────────────────┐   │   │
│  │  │  Cut Server (Flask)                           │   │   │
│  │  └───────────────────────────────────────────────┘   │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

详见：[dashboard/DASHBOARD.md](dashboard/DASHBOARD.md)
