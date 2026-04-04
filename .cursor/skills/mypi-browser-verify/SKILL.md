---
name: mypi-browser-verify
description: >-
  Requires end-to-end verification of MyPi web and wall flows in Cursor’s
  built-in browser (cursor-ide-browser MCP). Use for any change touching web/,
  pi-server APIs consumed by the web app, preview/on-wall UX, or when the user
  asks for verification, sign-off, or “交付” of UI-related work. Forbids
  declaring work complete from CLI/tests alone when user-visible behavior is in scope.
---

# MyPi：内置浏览器强制验证

## 硬性规则

1. **凡涉及用户可见界面或 Web 所调 API 的改动**，在回复「已完成 / 已修复 / 可交付」前，**必须在 Cursor 内置浏览器**（`cursor-ide-browser` MCP）中跑通关键路径；**禁止**仅凭 `curl`、仅跑 `verify_demo.py`、仅 `npm run build` 或静态代码阅读就宣称 UI 已验证。
2. **未做浏览器验证时**，须明确说明「尚未在内置浏览器中验证」，并继续完成验证；**不得**用含糊表述代替实测。

## 何时必须启用本流程

- 修改了 `web/`（含路由、代理、预览、上墙、时间轴、对话框等）。
- 修改了 `pi-server/` 中影响 Web 的接口或编排（如 `wall/state`、`show-now`、预览图 URL、`/api/v1/output/` 等）。
- 用户要求验收、演示、联调或「交付」且与上述相关。

纯后端内部逻辑、与浏览器无关的脚本：仍应用 `verify_demo.py` / 单测等；**若该次任务同时影响 Web，浏览器验证仍不可省略**。

## 验证前准备

- 在终端启动 **`pi-server`**（如 `PYTHONPATH=. python _dev_serve.py` 或单进程、**避免** `FLASK_DEBUG` 父子双进程导致 `wall/state` 不一致）与 **`web` 的 Vite dev**（默认 `http://127.0.0.1:5173`，`/api` 代理到 5050）。
- 调用 MCP 工具前：**先读对应工具的 schema**（项目 `mcps/cursor-ide-browser/tools/*.json`），再按参数调用。

## 内置浏览器操作顺序（遵守 MCP 说明）

1. `browser_navigate` 打开前端（如 `http://127.0.0.1:5173/`）。
2. `browser_lock`（若需连续操作）。
3. `browser_snapshot` 获取结构后再 `browser_click` / 输入；需要时用 `browser_wait_for` 等待文案出现或消失。
4. 用 **`browser_network_requests`** 或快照确认关键请求：**200**、预期路径（如 `/api/v1/.../show-now`、`/api/v1/output/...`）。
5. 需要视觉确认时用 `browser_take_screenshot`。
6. 结束 `browser_unlock`。

## 交付时回复中应包含

- **在内置浏览器中执行过的步骤**（打开了哪个 URL、点了什么、看到了什么或 Network 里哪些请求成功）。
- 若环境限制无法起服务，说明阻塞原因，并列出**仍待浏览器补验**的项；**不得**将未验证部分写成「已确认无误」。

## 反例（禁止）

- 「已在本地跑通 `verify_demo.py`，故 Web 没问题。」（未开内置浏览器）
- 「理论上代理正确，预览应已恢复。」（未快照 / 未 Network）
- 「构建通过即可交付。」（UI 行为未测）
