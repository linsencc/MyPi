---
name: mypi-browser-regression
description: >-
  Requires Cursor IDE browser regression after substantive changes in the MyPi
  repo. Use for any agent edit touching web/, server/, or demo/; before
  marking work complete, sign-off, or “交付”; whenever the user asks for
  regression or 回测. Complements mypi-browser-verify (how) with a default-on
  project policy (when).
---

# MyPi：改动后 Cursor 浏览器回测（项目默认）

## 策略

在本仓库内完成**实质性改动**后，在宣称「已完成 / 可交付」前，**须用 Cursor 内置浏览器**（`cursor-ide-browser` MCP）做**与本次改动相关的回测**，除非下方「可豁免」明确适用。

这与仅跑 `verify_demo.py`、`npm run build`、或静态读代码**不矛盾**：脚本能过仍**不能**代替对 Web 联调路径的浏览器回测（当改动落在适用范围内时）。

## 必须做浏览器回测的范围

满足任一即适用：

- 修改了 **`web/`**（任意文件）。
- 修改了 **`server/`**（任意文件：API、编排、模板、配置读写、静态路由等——只要可能影响控制台或 `/api` 行为）。
- 修改了 **`demo/`** 且本次任务与联调、演示或「和 web 行为对齐」有关。

回测时应覆盖**与改动点相关的**关键路径（例如：首页加载、场景编辑、立即上墙、预览图、Network 中关键 `GET/POST` 为 200 等），具体操作步骤见同仓库 `.cursor/skills/mypi-browser-verify/SKILL.md`。

## 可豁免（不做浏览器回测）

- 仅改 **纯文档**（如根目录说明、与运行无关的注释），且**不**改 `web/` / `server/` / `demo/` 下可执行代码或配置结构。
- 仅改 **`.cursor/`** 规则或技能文本本身（本 skill 除外：若改了浏览器相关 skill，应用浏览器自洽验证可选）。
- 用户**明确**声明本次任务只需脚本/单测、不要求浏览器。

若因环境无法起 `server`+`web` dev：**不得**声称已做浏览器回测；须说明阻塞原因与待补测项（与同目录 `mypi-browser-verify` 技能一致）。

## 交付时在回复中写明

- 浏览器中打开的 **URL**、执行的 **关键操作**、**快照/Network** 中确认到的结果（或截图说明）。
- 若属「可豁免」范围，**一句话说明豁免理由**。

## 与其他 skill 的关系

- **`mypi-browser-verify`**：具体操作顺序与 MCP 注意事项（**怎么做**）。
- **`mypi-delivery-boundaries`**：禁止为验收加产品外测试 UI（**不要**用加页面代替回测，也**不要**为回测往产品里塞专用块）。
