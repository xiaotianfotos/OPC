# H3 Reference Image Library

## 目录

- 使用方法
- 总览图
- 品牌、电影与时尚
- MG、视觉包装与剧情
- 产品、UI、游戏与动画
- 多模态、动作与编辑
- 推荐组合

## 使用方法

这些图片来自用户可访问的飞书文档《MiniMax H3 Brief》（Docx revision 1347），已于 2026-08-03 通过 lark-cli 用户身份读取，并缩放压缩为适合快速预览和 H3 参考的 JPG。使用具体图片前必须调用 `view_image` 实际检查，不要只根据文件名推断。

资产目录：`../assets/reference-images/`

把资产作为视觉语法或测试素材使用，不要把 contact sheet 直接当多角色身份图。若生成真实项目，优先使用用户自己的品牌、角色和产品资产。

## 总览图

- `../assets/contact-brand-visual-story.jpg`
- `../assets/contact-product-game-animation.jpg`
- `../assets/contact-reference-editing.jpg`

## 品牌、电影与时尚

### 望远镜窥视品牌片（连续关键帧）

- `brand-film-telescope-01.jpg`
- `brand-film-telescope-02.jpg`
- `brand-film-telescope-03.jpg`
- `brand-film-telescope-04.jpg`

### 科幻预告

- `brand-space-opera.jpg`
- `brand-scifi-gate-atmosphere.jpg`
- `brand-scifi-gate-character.jpg`

### 荒漠时尚 Campaign

- `fashion-desert-scene.jpg`
- `fashion-desert-character.jpg`
- `fashion-desert-bag.jpg`
- `fashion-desert-logo.jpg`

### 火场/VHS 时尚片

- `fashion-fire-atmosphere.jpg`
- `fashion-fire-character.jpg`

## MG、视觉包装与剧情

### 复古日系犯罪动画片头

- `visual-anime-opening-01.jpg`
- `visual-anime-opening-02.jpg`
- `visual-anime-opening-03.jpg`
- `visual-anime-opening-04.jpg`
- `visual-anime-opening-05.jpg`

### Dark-pop、zine 与动态海报

- `visual-dark-pop-01.jpg`
- `visual-dark-pop-02.jpg`
- `visual-motion-poster.jpg`

### 武侠、家庭和吸血鬼短剧

- `story-wuxia-01.jpg`
- `story-wuxia-02.jpg`
- `story-family-01.jpg`
- `story-family-02.jpg`
- `story-vampire-character.jpg`
- `story-vampire-scene.jpg`

## 产品、UI、游戏与动画

### 眼镜和人体工学椅

- `product-eyewear-scene.jpg`
- `product-eyewear-character.jpg`
- `product-eyewear-design.jpg`
- `product-chair-detail.jpg`
- `product-chair-image.jpg`

### 游戏与网页 UI

- `game-character.jpg`
- `game-ui-style.jpg`
- `web-product.jpg`
- `web-car-ui.jpg`
- `web-poster-ui.jpg`

### 动画、二次元与 CG

- `animation-clay-fox.jpg`
- `animation-fps.jpg`
- `animation-xianxia-character.jpg`
- `animation-xianxia-storyboard.jpg`
- `animation-otome-character.jpg`
- `animation-otome-pv-board.jpg`
- `animation-otome-ui-first.jpg`
- `animation-otome-ui-last.jpg`
- `animation-romance-character.jpg`
- `animation-romance-scene.jpg`

## 多模态、动作与编辑

### 六帧镜头序列

- `multimodal-sequence-01.jpg`
- `multimodal-sequence-02.jpg`
- `multimodal-sequence-03.jpg`
- `multimodal-sequence-04.jpg`
- `multimodal-sequence-05.jpg`
- `multimodal-sequence-06.jpg`

### 材质转场与局部风格

- `multimodal-coffee.jpg`
- `multimodal-desert.jpg`
- `multimodal-voxel-style.jpg`

### 角色与动作参考

- `motion-couple-character.jpg`
- `motion-dance-character.jpg`
- `motion-dance-style.jpg`

### 精确编辑素材

- `edit-dog.jpg`
- `edit-jacket.jpg`
- `edit-window-scene.jpg`
- `instruction-magicians.jpg`
- `instruction-doodle.jpg`

## 推荐组合

| 目标 | 图片职责组合 |
|---|---|
| 时尚 TVC | 场景 moodboard + 人物三视图 + 产品三视图 + Logo |
| 科幻预告 | 氛围关键帧 + 人物身份图；文字样式写在 Prompt |
| 动画片头/MG | 3–5 张版式关键帧；不要混入真人身份图 |
| 产品功能片 | 产品白底图 + 功能说明图；场景可纯文字描述 |
| 游戏 UI 演示 | 角色图 + UI 风格图，时间轴写清界面状态 |
| 仙侠/乙游 PV | 角色三视图 + 分镜板；分镜只管镜头不管脸 |
| 材质无缝转场 | 首图 + 尾图，明确共享纹理和遮挡瞬间 |
| 动作迁移 | 身份图 + 动作视频；视频只负责动作和运镜 |
| 精确视频编辑 | 原视频 + 目标物体/场景图；先列原视频不变量 |

使用这些资产调用 `opc video` 时，命令行路径应指向实际文件：

```text
/Users/matrix/.codex/skills/h3-guide/assets/reference-images/<filename>.jpg
```
