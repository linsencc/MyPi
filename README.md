# MyPi 电子画框管理系统

**MyPi** 是一个专为水墨屏设计的自动化画面渲染与调度更新系统。它可以根据预设的时间规则，将天气、日历、待办事项等丰富内容自动、平滑地推送到屏幕上。

---

## 🌟 核心特性

- 模板化扩展：通过简单的后端代码即可接入各类「画面模板」（如每日天气、专属寄语等），并在 Web 控制台中提供可视化管理。
- 灵活的场景调度：基于模板创建带有特定时间规则的「场景实例」。例如：*每天早 7 点推送“今日天气”，工作日晚 8 点推送“晚间待办”。*
- 实例互不干扰：同一个画面模板可被实例化为多个独立运行的场景，拥有各自独立的参数与调度规则，互不影响。
- 自动化任务编排：后台统一接管所有场景的时间线。系统会自动处理并发冲突、合并排队，确保在最合适的时机刷新屏幕，无需人工干预。

## 🚀 快速开始

本地开发环境分为前后端两部分，开发时需要开启**两个终端**分别运行。

### 1. 启动后端服务 (Python)

后端基于 Python 构建，建议使用 **Python 3.11+**。

```bash
# 安装依赖
pip install -r requirements.txt

# 启动单进程开发服务器 (推荐本地联调使用)
PYTHONPATH=. python _dev_serve.py
```

### 2. 启动前端控制台 (React + Vite)

前端是一个基于 React 的可视化管理控制台。

```bash
cd web
npm install
npm run dev
```

启动成功后，在浏览器访问 `**http://localhost:5173/**` 即可进入 Web 控制台进行配置与预览。

---

## 📖 核心概念与工作流

为了帮助您快速理解系统架构，我们对核心领域模型进行了统一抽象：


| 概念       | 英文标识           | 核心职责与说明                                                |
| -------- | -------------- | ------------------------------------------------------ |
| **模板**   | `Template`     | 面向开发者。定义了画面内容的排版与数据获取机制（例如一段渲染“天气信息”的 Python 代码）。      |
| **场景**   | `Scene`        | 面向用户。是“模板” + “用户参数” + “调度规则”的组合实例。在 Web 控制台上表现为一张配置卡片。 |
| **画框**   | `Wall`         | 系统的输出目标与状态载体。代指最终的物理屏幕硬件及其当前呈现的画面状态。                   |
| **编排器**  | `Orchestrator` | 后台调度的核心大脑。负责将多个可能同时触发的场景按时间线进行排队、去重和防冲突处理。             |
| **渲染管线** | `Pipeline`     | 画面上屏的流水线。负责从模板取数据、出图、视觉调校，并最终推送到物理屏幕上。                 |


## 🎨 如何开发新增模板

系统基于动态发现机制，无需繁琐的注册表配置，**通常两步**即可完成一个新模板的接入，并在 Web 端立刻生效可用。若需要用户在 Web 上填写「模板入参」，再完成第 3 步。

1. **新建模板文件**
  在 `server/renderers/templates/` 目录下创建一个 Python 文件（如 `my_template.py`）。
2. **继承并实现接口**
  引入 `WallTemplate` 基类并实现 `render` 方法，直接返回 `PIL.Image.Image` 对象即可。
3. **（可选）声明 Web 入参表单**  
   不要在 `template_base.py` 里写具体模板字段。任选其一：
   - **声明式**：与 `template.py` 同目录放置 `param_schema.json`（根为字段数组，或 `{"fields": [...]}`）。每项至少含 `key`、`type`（`string` 或 `boolean`）；可选 `required`、`default`、`description`（Web 仅在鼠标悬浮 `key` 时用 Tooltip 展示说明，无 `label` / `maxLength`）。类体中一行：  
     `param_schema = load_param_schema_json(Path(__file__).resolve().parent / "param_schema.json")`  
     （`load_param_schema_json` 见 `renderers.templates.ui_params`，可参考 `ai_motto/param_schema.json`。）
   - **程序化**：用 `renderers.templates.ui_params` 中的 `field_string` / `field_boolean` 组装列表赋给 `param_schema`。
   - **落库与 API**：`POST/PUT /api/v1/scenes` 写入前会经 `ui_params.normalize_scene_template_params` 与 `validate_scene_template_params_required` 处理：仅保留当前模板 schema 中的键、做类型与长度规范化；必填字符串在后端同样校验。业务模板无需在路由里手写上述逻辑。

```python
from PIL import Image, ImageDraw
from renderers.template_base import RenderContext, WallTemplate

class MyCustomTemplate(WallTemplate):
    display_name = "我的自定义模板"  # Web 端显示的友好名称

    def render(self, ctx: RenderContext) -> Image.Image:
        # 获取场景中配置的用户参数（可选）
        params = ctx.scene.template_params or {}
        
        # 1. 根据设备分辨率创建画布
        w = ctx.device_profile.get("width", 800)
        h = ctx.device_profile.get("height", 600)
        img = Image.new("RGB", (w, h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((100, 100), "Hello, MyPi!", fill=(0, 0, 0))
        
        # 2. 直接返回画布对象，系统管线会自动处理落盘和推流上屏
        return img
```

完成以上代码后，重启后端服务，**新的模板卡片即会自动出现在 Web 控制台的创建场景列表中**，您可以直接配置调度规则并推送到画框。

## 🛠️ 技术栈与目录结构

- **后端**: Python 3.11+, Flask 3, Pydantic v2, APScheduler, Pillow
- **前端**: React, TypeScript, Vite

### 核心目录树

```text
MyPi/
├── server/               # 后端服务
│   ├── api/              # RESTful API 路由层
│   ├── app/              # Flask 应用构建与入口
│   ├── display/          # 屏幕输出适配层
│   ├── domain/           # 核心业务模型与对齐逻辑
│   ├── orchestrator/     # 场景时间线编排器
│   ├── pipeline/         # 渲染与上屏管线
│   ├── renderers/        # 画面模板系统与自定义模板实现
│   └── storage/          # 配置与状态的本地持久化
├── web/                  # 官方 Web 控制台 (React SPA)
└── .cursor/              # 编辑器规则与 Agent 技能指令
```

