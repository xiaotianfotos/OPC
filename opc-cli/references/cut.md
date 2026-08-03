# Cut - 视频剪辑命令

基于 ASR 字词级时间戳的视频剪辑，启动 Web 可视化界面。

**前置：** 需要 ASR 环境，参见 [SKILL.md](../SKILL.md) 的环境安装和 ASR 命令章节。

## 目录

- [启动](#启动)
- [界面操作](#界面操作)
- [输出格式](#输出格式)

## 启动

```bash
# 启动剪辑服务器（自动运行 ASR）
opc cut --video /path/to/video.mp4

# 使用已有 ASR 结果
opc cut --video /path/to/video.mp4 --json /path/to/asr_result.json

# 自定义端口
opc cut --video /path/to/video.mp4 --port 9090

# 不自动打开浏览器
opc cut --video /path/to/video.mp4 --no-browser
```

**参数：**
- `--video`, `-v` — 视频文件路径（必需）
- `--json`, `-j` — 已有的 ASR 结果 JSON（可选）
- `--language`, `-l` — 语言提示，默认 Chinese
- `--port`, `-p` — 服务器端口，默认 8080
- `--no-browser` — 不自动打开浏览器

**工作流程：**
1. 服务器启动并运行 ASR（或加载已有 JSON）
2. 自动打开浏览器访问 Web 界面
3. 在字幕编辑区删除字词/间隙
4. 视频预览时自动跳过已删除部分
5. 导出剪辑后的视频

## 界面操作

- **双击字词** — 删除/恢复该字
- **拖拽选择** — 选中多个连续字词
- **Delete 键** — 删除选中的字词/间隙
- **Ctrl+A** — 全选
- **双击间隙** — 删除/恢复无声间隙（≥0.5s）

## 输出格式

ASR 生成的 JSON 格式：
```json
{
  "language": "Chinese",
  "text": "完整转录文本...",
  "duration": 408.58,
  "words": [
    {"text": "大", "start_time": 0.0, "end_time": 0.16},
    {"text": "家", "start_time": 0.16, "end_time": 0.24}
  ]
}
```
