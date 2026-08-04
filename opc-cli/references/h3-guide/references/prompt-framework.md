# H3 Prompt Framework

## 目录

- 通用结构
- T2V 模板
- I2V 模板
- R2V 生成模板
- R2V 编辑模板
- 声音与文字
- opc 命令模板

## 通用结构

按以下优先级组织 Prompt。越靠前越接近“合同”，越靠后越接近美术修饰。

1. **输出合同**：时长、画幅、连续镜头或剪辑结构、真实/动画媒介。
2. **全局不变量**：身份、产品、Logo、机位、布局、原声音等必须固定的内容。
3. **参考绑定**：逐个说明 `<Picture N>`、`<Video N>`、`<Audio N>` 的唯一职责。
4. **动作时间轴**：按秒或按镜头描述主体动作、状态变化和转场触发点。
5. **镜头语言**：景别、机位、焦段感、运镜速度、对焦、遮挡和剪辑。
6. **视觉语法**：色彩、光线、材质、颗粒、排版、动画工艺。
7. **声音设计**：对白、口型、环境声、拟音、音乐结构和结尾 hit。
8. **文字/MG**：精确文案、出现次数、可读时长、入退场和禁止乱码。
9. **禁止项**：只写最可能出现且会毁掉结果的问题。

让每个镜头包含“主体 + 动作 + 场景 + 镜头 + 声音”，避免只列名词。

## T2V 模板

```text
生成一支 [时长]、[画幅] 的 [类型]。

核心概念：[一句话冲突、奇观或产品承诺]。
场景与主体：[空间、人物/物体、材质、时间、天气]。

[0–Xs] [镜头1：景别、动作、运镜、转场触发]
[X–Ys] [镜头2：景别、动作、运镜、转场触发]
[Y–结束] [高潮、品牌/情绪落点、定格或结尾]

视觉：[具体构图、光线、色彩、媒介、颗粒或动画工艺]。
声音：[环境声、拟音、音乐节拍、对白及情绪]。
文字：[精确字符串、出现一次、位置、动效、停留时长]。
避免：[最关键的 3–6 个失败模式]。
```

适合纯文生的强项：真实生活中的异常事件、短片气氛、风格化动画、具有清晰动作弧线的一镜到底。没有固定资产时，不要为了“更丰富”强行添加参考图。

## I2V 模板

```text
以首帧为严格的主体、构图、产品与色彩参考。[如有尾帧：以尾帧为严格的结束状态。]

保持：[身份、产品几何、Logo、服装、背景布局]。
允许变化：[动作、镜头、光影或界面状态]。

[分秒描述从首帧自然发生的动作]
[如有尾帧：描述如何通过材质、遮挡、镜头或状态变化无缝到达尾帧]

镜头：[具体运动和速度曲线]。
声音：[与动作同步的拟音/音乐/对白]。
禁止：[画面开裂、硬切、身份漂移、产品变形、Logo 乱码等]。
```

首尾帧转场优先寻找两张图之间的“形态同构”：咖啡泡沫到沙丘、织物褶皱到山谷、玻璃反射到水面。把共同的纹理、方向和遮挡瞬间写清楚，比写“丝滑转场”有效。

## R2V 生成模板

```text
生成一支 [时长/画幅] 的 [类型]。

参考绑定：
- <Picture 1>：严格身份/产品参考，只负责 [身份或产品]。
- <Picture 2>：场景与光线参考，只负责 [场景]。
- <Picture 3>：版式/材质风格参考，不改变主体身份。
- <Video 1>：只参考动作、表演节奏和运镜；不要复制其中人物外观。
- <Audio 1>：只参考音色/音乐结构/环境声。

全局保持：[身份、服装、产品、画幅等]。
[分秒镜头与动作]
视觉与声音：[具体要求]
禁止：[参考职责串线、身份融合、场景带入错误等]。
```

一组多参考图不要全部写成“风格参考”。把人物三视图绑定为身份，把 moodboard 绑定为场景，把 storyboard 绑定为镜头顺序。

## R2V 编辑模板

```text
Use <Video 1> as the strict source for camera, composition, timing, pose, motion path,
occlusion, environment, lighting continuity and soundtrack.

Make exactly these edits:
1. [对象/区域] 从 [原状态] 改为 [目标状态]。
2. [如有第二项，单独列出]。

Target identity/appearance:
- <Picture 1> strictly defines [脸/身体/服装/产品几何]。
- <Picture 2> only defines [材质/背景/效果]。

Preserve everything else unchanged: [列出最重要的不变量]。
Keep all actions and occlusions temporally coherent. Synchronize mouth/action events to the retained or generated audio.

Do not preserve [原对象最显著、容易残留的属性]。
Do not introduce [参考图中的无关背景/人物/文字]。
No morphing, flicker, duplicate subjects, reframing or unintended relighting.
```

编辑主体与原主体外形差异大时，同时写“目标是什么”和“原对象哪些属性不得保留”。

## 声音与文字

### 声音

- 指定对白原文、说话人、语言、情绪、音量距离和动作同步点。
- 指定音乐的结构，不要只写曲风：前奏、节拍进入、层次增加、高潮和结尾 hit。
- 指定环境声和关键拟音，避免模型用无关音乐填满空间。
- 参考视频默认携带音轨时，它会占用音频序号；独立音频的 `<Audio N>` 以 `opc` 当前规则为准。若希望独立音频成为 `<Audio 1>`，考虑对视频使用 `--no-reference-video-audio`。

### 文字/MG

- 所有必须正确的字符串逐字给出，并声明“只出现一次”。
- 规定字号感、字重、字距、材质、位置、进入方式、停留时长和退出方式。
- 片头署名要约束姓名/职位不可重复，禁止同一人承担多个职位。
- 动效要绑定节拍或遮挡：线框画出、遮罩揭示、字距展开、残影或硬切；避免只写“炫酷文字”。
- 重要长文案不要把生成模型当排版引擎，优先生成干净底片后在后期叠字。

## opc 命令模板

执行前读取 `opc` skill 并用 `opc video info` 核对当前参数。

```bash
# 文生视频
opc video --workflow h3-t2v \
  --prompt-file prompt.txt \
  --width 864 --height 480 --duration 5 --steps 20 \
  --output ./output

# 首帧/首尾帧
opc video --workflow h3-i2v \
  --prompt-file prompt.txt \
  --first-frame first.png --last-frame last.png \
  --width 864 --height 480 --duration 5 --steps 20 \
  --output ./output

# 多参考/视频编辑：命令行顺序就是 Picture/Video/Audio 序号
opc video --workflow h3-r2v \
  --prompt-file prompt.txt \
  --reference-image identity.png \
  --reference-image scene.png \
  --reference-video motion.mp4 \
  --reference-audio voice.wav \
  --ref-image-size match \
  --width 864 --height 480 --duration 5 --steps 20 \
  --output ./output
```

首次执行优先 dry-run（若当前 CLI 支持），核对媒体序号、帧数、音轨和输出目录，再提交真实任务。
