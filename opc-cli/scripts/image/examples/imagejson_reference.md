# imagejson.org 参考分析

## URL
https://www.imagejson.org/nano-banana-prompt?type=text_to_image

## 核心发现

### 1. Prompt 格式：纯 JSON，无 enhancement 步骤
- 所有 prompt 都是**嵌套 JSON 对象**，直接用于生成
- **没有 prompt enhancement / rewrite 环节**
- 用户或 AI 直接输出结构化 JSON，模型消费 JSON

### 2. 常见顶层字段结构

| 字段 | 用途 | 示例值 |
|------|------|--------|
| `subject` / `main_subject` | 主体描述（可嵌套） | `structure: {lenses, mask_base, filtration_unit}` |
| `artistic_style` / `medium` | 视觉渲染方式 | `["Quilling", "Layered Cutouts", "Pop-up Book"]` |
| `composition` / `camera` | 构图、镜头、景深 | `aperture: "f/1.8", focal_length: "85mm"` |
| `lighting_*` | 光源、阴影、氛围 | `neon rim light, cool cyan ambient` |
| `background_*` / `environment` | 场景环境 | `dark gradient indigo-blue twilight sky` |
| `color_palette` | 调色板（支持 hex） | `["#FF00FF", "#32CD32", "#E69FB2"]` |
| `negative_constraints` / `exclusions` | 排除项 | `["Blurry", "Vector art", "3D render"]` |
| `technical_specs` | 技术参数 | `resolution, lens, render engine` |
| `thematic_elements` | 主题元素（可带时代子对象） | `wwii_era, viral_outbreak, solarpunk` |
| `typography_and_text` | 文字排版（海报类） | `credits, title_treatment` |
| `visual_breakdown` | 视觉分解（拼贴类） | `artistic_interventions, glitch_effects` |
| `prompt_recreation_guide` | 元信息：人类可读总结 | 纯文本说明 |

### 3. 特殊结构模式

**负向约束（explicit negative constraints）**
```json
{
  "exclusions": ["Blurry anti-aliasing", "Vector art", "3D render", "Photorealistic"],
  "rendering": "No photorealistic skin; everything must look like paper"
}
```

**双层渲染（CGI + traditional）**
```json
{
  "techniques": ["Hyper-realistic CGI combined with digital painting"],
  "medium": "Digital Papercraft / 3D Paper Art Diorama"
}
```

**元文档字段**
```json
{
  "prompt_structure": {
    "meta": {"format": "JSON Image Definition", "version": "v1.5"},
    "prompt_generation_hints": ["keyword1", "keyword2"]
  }
}
```

### 4. 工作流程（无 enhancement）

1. **Template selection** — 从库中选择模板（按 model/type/category 过滤）
2. **Direct JSON copy** — 复制 JSON prompt
3. **Remix** — 基于模板修改生成变体

### 5. 与当前系统的对比

| 维度 | imagejson.org | 当前系统 |
|------|---------------|----------|
| Prompt 格式 | 嵌套 JSON | 纯文本字符串 |
| Enhancement | 无 | 有（TextGenerate + 专用模型） |
| Negative | 明确的 JSON 字段 | 无（workflow 中 ConditioningZeroOut） |
| Color palette | hex 代码 | 无 |
| Background | 独立字段 | 无（合并在文本中） |
| Technical specs | 独立字段 | 无 |
| 文字内容 | `typography_and_text` | 无独立字段 |

### 6. 建议补充到 KG 的 categories

- `background` / `environment` — 场景环境
- `color_palette` — 调色板风格
- `negative_constraints` — 排除/禁止项
- `technical_specs` — 技术参数（质量、镜头、渲染引擎）
- `text_content` — 画面文字内容（海报、UI 等）
