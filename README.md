# MyPi

树莓派侧电子画框/上墙：Python 后端提供 API 与调度，Web 控制台与独立画框 UI 通过 Vite 开发并代理 `/api`。

## 目录

| 路径 | 说明 |
|------|------|
| `server/` | Flask 服务（`/api/v1`）、APScheduler、渲染管线（`pipeline/`、`renderers/`）、上墙输出（`display/`）、编排（`orchestrator/`）、领域与存储（`domain/`、`storage/`）、静态/产物目录（`data/`）。入口见包内 [README](server/README.md)。 |
| `web/` | 正式控制台（React + Vite），对接 `server`。 |
| `demo/` | 电子画框演示前端；`legacy-static/` 为旧版静态资源。 |
| `.cursor/` | Cursor 规则与 Agent 技能。 |

本地联调：先在 `server` 启动后端（默认 `5050`），再在 `web` 或 `demo` 下 `npm run dev`。
