# CLAUDE.md — opc-cli 项目约定

## 运行命令

**所有 Python 脚本必须通过 `uv run` 执行：**

```bash
uv run python scripts/opc.py <command>
# 或在 scripts/ 目录下：
cd scripts && uv run python opc.py <command>
```

不要直接用 `python3` 跑脚本，会有模块导入问题。

## 项目结构

```
opc-cli/
├── scripts/
│   ├── opc.py              # CLI 入口
│   ├── shared/config.py    # 配置管理
│   ├── image/              # 图片生成模块
│   │   ├── comfyui.py      # ComfyUI HTTP 客户端
│   │   ├── workflow.py     # 工作流加载与参数注入
│   │   ├── json_prompt.py  # JSON prompt schema + 验证 + 转换
│   │   ├── kg/             # Prompt 知识图谱
│   │   ├── workflows/      # ComfyUI 工作流 JSON + meta
│   │   ├── templates/      # 模板定义
│   │   ├── examples/       # 示例 prompt JSON
│   │   └── eval/           # 评估框架
│   ├── tts/                # TTS 语音合成
│   └── asr/                # ASR 语音识别
├── dashboard/server/       # Dashboard Web UI (Node.js)
├── references/             # Skill 参考文档
├── SKILL.md                # Skill 主文件
└── CLAUDE.md               # 本文件
```

## 关键设计决策

### JSON Prompt 的 layout 字段

所有包含文字的图片 prompt 应有 `layout` 字段。`json_prompt.py` 的 `validate_json_prompt()` 会在有 `text_content`/`typography_layout` 但缺少 `layout` 时发出 WARNING。layout 是自由格式：可以是字符串、结构化对象、或任意 JSON。

### ComfyUI 工作流参数

每个工作流的 `meta.json` 必须声明所有可注入的参数（包括 `batch_size`），否则 `inject_params()` 会静默忽略未声明的参数。

### ERNIE-Image 文字渲染

- JSON 模式：原始 JSON 字符串直接传入 ComfyUI（不经过 `json_prompt_to_text()` 转换）
- `--text` 模式：纯文本直接传入
- 中文文字渲染有随机性，多样本（batch_size=4）验证是必要的

## Dashboard

Dashboard 是 Node.js 应用，在 `dashboard/server/` 下：
```bash
cd dashboard/server && npm run dev
```

API 端点在 `server-api.js`，前端 Vue 组件在 `src/views/`。
