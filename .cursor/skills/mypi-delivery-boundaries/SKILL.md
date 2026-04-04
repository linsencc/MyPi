---
name: mypi-delivery-boundaries
description: >-
  Separates acceptance testing from shipped product in MyPi. Forbids adding
  user-visible UI or features whose only purpose is to verify APIs or cases.
  Use when the user asks for verification, 验收, test cases, TC-*, UT-*, or
  when tempted to expose wall/state or schedule fields on the page for testing;
  also when editing web/ for “easier QA”.
---

# MyPi：验收与交付边界

## 近期已犯的错误（勿再犯）

1. **为「方便验收」往正式 Web 里加测试专用界面**  
   例如在 `web/` 增加仅用于展示 `wall/state.upcoming`、调度文案的区块，或任何**用户未要求、产品未立项**的「计划中的自动上墙」式面板。  
   **后果**：交付物混入非产品需求，客户/用户看到测试痕迹，回滚与文档同步成本高。

2. **把「能验证」等同于「可以改产品」**  
   验证应通过**脚本、Network 响应、已有界面行为**完成，而不是新增产品路径。

## 硬性规则

- **禁止**：为口头「验一下 case」或临时验收而**新增**面向最终用户的组件、路由、菜单或常驻文案（除非用户**明确**要求该能力作为产品功能）。
- **允许**：运行仓库内已有脚本（如 `server/verify_demo.py`、`verify_acceptance.py`、`verify_schedule.py`）；在浏览器 **DevTools → Network** 中查看已有请求的 **Response**（如 `GET .../wall/state`）；用**已有**对话框/页面做点击与取消等操作验证。
- **若确实需要把调度信息展示给用户**：单独当作**产品需求**讨论与实现，不得在 issue/PR 里写成「为了 TC/UT 能通过」。

## 验证方式优先级（不污染 `web/`）

1. **自动化**：优先 `verify_*.py` 与 CI/本地脚本能断言的行为。  
2. **浏览器**：在**不新增产品 UI** 的前提下，用内置浏览器走真实用户路径 + Network 状态码与响应体。  
3. **说明**：在 PR/讨论里写清如何用 `verify_*.py`、Network 响应等验收即可，**不要**写「页面上必须有某验收专用区块」。

## 与 `mypi-browser-verify` 的关系

- `mypi-browser-verify`：**必须**用浏览器验证用户可见行为时，要真的打开页面测。  
- 本 skill：**禁止**用「加一块验收 UI」替代上述验证。二者同时成立：既实测，又不往交付物里塞测试界面。

## 开发环境（避免误判）

- **单进程**提供后端（在 `server/`，避免双监听 5050 导致 `wall/state` 不一致）；遵循仓库内对 `_dev_serve.py` / `threaded` 的说明。环境不稳时**先修环境**，不要加页面来「对齐状态」。
