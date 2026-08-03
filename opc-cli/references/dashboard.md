# OPC Dashboard - 技能管理面板

统一技能管理界面，技能注册式架构。前端 Vue3，后端 Express API。

## 目录

- [启动](#启动)
- [路由](#路由)
- [API](#api)
- [架构](#架构)

## 启动

```bash
cd dashboard/server
npm install          # 首次安装
npm run build        # 构建前端
node server-prod.js  # 启动（端口 12080）
```

开发模式（前后端分离）：
```bash
node server-api.js   # API 服务器（端口 12081）
npm run dev          # Vite 开发服务器（端口 12080，代理 API）
```

## 路由

| 路径 | 说明 |
|------|------|
| `/` | 着陆页 |
| `/docs` | 文档页 |
| `/dashboard` | 技能管理首页 |
| `/kg` | Prompt 知识图谱可视化（D3.js 力导向图） |
| `/evaluate` | 模型评估对比 |
| `/skill/cut/editor` | Cut 视频剪辑器 |

## API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/skills` | 获取所有技能列表 |
| GET | `/api/kg/data` | 知识图谱数据（实体 + 边 + 模板节点） |
| GET | `/api/eval/results/:alias` | 获取评估结果 |
| GET | `/api/eval/image/:alias/:filename` | 获取评估图片 |
| GET | `/api/eval/prompts` | 获取评估 prompt 列表 |
| GET | `/api/skill/cut/status` | 获取 Cut 技能状态 |
| POST | `/api/skill/cut/init` | 初始化 Cut 技能 |
| POST | `/api/skill/cut/stop` | 停止 Cut 技能 |

### 通过 API 启动 Cut

```bash
curl -X POST http://localhost:12080/api/skill/cut/init \
  -H "Content-Type: application/json" \
  -d '{"video": "/path/to/video.mp4", "port": 8082}'
```

## 架构

```
┌────────────────────────────────────────────────────────────┐
│                  OPC Dashboard (Node.js)                   │
│                  Port: 12080                               │
│  ┌─────────────────┐  ┌──────────────────────────────┐    │
│  │  Vue3 Frontend  │  │       Express API (:12081)   │    │
│  │  - /            │  │  - /api/skills               │    │
│  │  - /kg          │  │  - /api/kg/data              │    │
│  │  - /evaluate    │  │  - /api/eval/*               │    │
│  │  - /skill/cut   │  │  - /api/skill/cut/*          │    │
│  └────────┬────────┘  └─────────────┬────────────────┘    │
│           │                        │ spawn                │
│  ┌────────▼────────────────────────────────────────────┐  │
│  │  iframe (http://localhost:808X)                     │  │
│  │  ┌──────────────────────────────────────────────┐   │  │
│  │  │  Cut Server (Flask)                          │   │  │
│  │  └──────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```
