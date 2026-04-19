---
name: mypi-agent-execute
description: >-
  Requires the agent to fix MyPi local environment itself via shell (netstat,
  Stop-Process/taskkill, starting server/web), not delegate step-by-step
  instructions to the user. Use when ports conflict (e.g. 5050), duplicate
  Flask listeners, dev servers need restart, or the user asks to 解决/处理/
  排查/验证/清端口; also when the user objects that the agent should have acted
  instead of telling them to run commands.
---

# MyPi：能执行就必须执行，禁止把运维甩给用户

## 复盘（曾犯的错误）

- 已具备 **本机 Shell + 网络**，且用户意图是**解决问题 / 验证 / 清端口**，却把 `netstat`、`taskkill`、起 `_dev_serve.py` 等写成「请你本机执行」。
- 这与仓库协作目标相悖：**用户要的是代理代劳**，不是再领一份待办清单。
- **正确做法**：在确认风险可接受的前提下，**直接运行命令**完成排查与修复，再在回复里说明**做了什么、结果如何**；仅当客观无法执行时才说明阻塞原因。

## 硬性规则

1. **环境、进程、端口、本地服务**类任务：默认 **由代理执行** PowerShell / `cmd` / `curl` 等，**禁止**用「你可以运行下列命令」代替代理自己跑（除非下述豁免）。
2. **结束占用端口的进程**（如 5050 上多个 `LISTENING`）：先 `netstat -ano | findstr :5050`（或 `Get-NetTCPConnection -LocalPort 5050 -State Listen`），对 **TCP LISTEN** 对应 PID 使用 `Stop-Process -Id … -Force` / `taskkill /PID … /F`，**不要**只把步骤写给用户。
3. **需要起后端 / 前端做验证**：在后台或会话中 **直接启动** `server` 下 `_dev_serve.py`、`web` 下 `npm run dev`，再 `curl` 或内置浏览器验证；不要假设用户已手动起好。
4. **与 `mypi-browser-verify` 一致**：浏览器 MCP 能用时要用；同时 **Shell 能做的准备**（杀重复进程、单实例监听）必须先做，**不要**让用户先去「清环境」再让你测。

## 豁免（才可以只说明、不代执行）

- 需要 **管理员权限 / UAC** 且当前 Shell 无法提升。
- 需要 **用户密码、密钥、硬件操作**（插拔设备、点物理键）。
- 用户 **明确**说「只告诉我怎么做、不要在我机器上执行」。

豁免时须写清：**为何**不能代执行、**仍缺什么**用户侧输入。

## MyPi 常见一键路径（代理应主动走）

- **5050 被占 / 双 Flask**：查监听 PID → 结束多余进程 → 仅保留或重启 **一个** `python _dev_serve.py` → `curl` `/api/v1/templates` 确认与当前代码一致（如含 `misc_gallery`、`ai_motto`）。
- **验证模板 / API**：`cd server` + `PYTHONPATH=. python verify_demo.py`（代理执行，而非只建议用户执行）。

## 与其他技能的关系

- **`mypi-browser-verify`**：怎么做浏览器验证；**本技能**强调 Shell 侧也由代理做完，**不要**把清端口、杀进程留给用户后再测。
- **`mypi-delivery-boundaries`**：禁止往产品里塞验收专用 UI；与「代理要亲自跑命令」不冲突。
