# 墙模板插件约定

实现：`server/renderers/templates/` 下新增/改包即可；**默认不改** `template_base.py`、`registry.py`、`renderers/__init__.py`、`ui_params.py`、以及 `server/api/` 里模板/场景的**通用**逻辑。

## 注册与 `template_id`

- `registry.discover_templates()`：① 导入 `templates/` 下**顶层**非 `_` 前缀的 `.py`；② 对每个**子包** `walk_packages` 导入其下所有非包子模块。
- 每个 `WallTemplate` 子类（≠ 基类）会 `()` 注册；若存在模块级 `template: WallTemplate` 也会注册。同一模块里**不要**既保留可发现的子类又导出指向**同类实例**的 `template`，否则会 `duplicate template_id`。
- `template_id` = 类名经 `_to_snake_case`，再以 `_template` 结尾则去掉该后缀（共 9 个字符）。例：`AiMottoTemplate` → `ai_motto`。

## 类契约

- `display_name`、`param_schema`（`ClassVar[list]`）、`render(self, ctx: RenderContext) -> Image`。
- `ctx.scene.template_id` / `template_params`、`ctx.device_profile`（常用 `width`/`height`）、`ctx.frame_tuning`。
- **入参**：场景创建/更新在路由里经 `scene_template_params_after_model`（内部：`normalize_scene_template_params` + `validate_scene_template_params_required`）。带 `templateParams` 的 **show-now** 用 `merge_incoming_template_params`。`render` 仍应对缺键、空值做防御。

## `param_schema`

- 仅 `string` / `boolean`（`ui_params`）；其它 type 丢弃并打 log。
- `load_param_schema_json(…/param_schema.json)` 或 `field_string` / `field_boolean`；JSON 根为数组或 `{"fields": [...]}`。

## 实现建议

- 弱设备优先纯 PIL；若用 HTML 截图，见 `weekend_outing/html_chromium.py` 的 `render_html_to_image`，应用 **env 开关** 在失败或禁用时回退（见 `weekend_outing/template.py`）。
- 跨模板复用：import 已有模块；新共享逻辑放在 `templates/` 的 helper `.py`（无 `WallTemplate` 子类则不占 id）。

## 自检

`template_id` 唯一；schema 的 key 与 `render` 一致；子包内 `.py` 语法错误会导致整次发现失败；Chromium/网络/LLM 有降级。