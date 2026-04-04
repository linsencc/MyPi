# MyPi Web（正式控制台）

对接本仓库 [server](../server) 的 `GET/PUT /api/v1/*`，无本地 mock 场景数据。界面与交互参考 `demo/`，但 **`demo/` 不参与构建**，请勿从本包引用 `demo` 路径。

## 开发

1. 启动后端（仓库根目录下 `server`，默认 `5050`）：

   ```powershell
   cd server
   $env:PYTHONPATH = (Get-Location).Path
   python app/factory.py
   ```

2. 启动本前端（Vite 将 `/api` 代理到 `http://127.0.0.1:5050`）：

   ```powershell
   cd web
   npm install
   npm run dev
   ```

浏览器打开终端提示的本地地址（一般为 `http://localhost:5173`）。

## 生产构建

```powershell
npm run build
```

产物在 `web/dist/`。可由 nginx 反代静态资源，或由 Flask 托管该目录（需在 server 侧自行配置）。

## 预览图说明（重要）

- 后端 `wall/state` 中的 `currentPreviewUrl` 当前常为 `null`，`wall/runs` 里的 `outputPath` 为**服务器本地路径**，浏览器无法直接作为 `<img src>` 使用。
- 本应用在主画框与卡片上优先使用：
  1. 当前上墙且 `currentPreviewUrl` 为 **http(s)** 时使用该 URL；
  2. 否则使用场景配置中的 **`previewImageUrl`**（须为可访问的 http(s) 地址）；
  3. 否则使用应用内嵌的 **data URI** 占位图（不依赖 `public/` 路径，避免 base/部署差异导致占位图 404）。
- 若要在浏览器中展示真实渲染缩略图，需要在 **server** 增加静态文件或签名 URL 路由，并在编排器写入可访问的 `currentPreviewUrl`（或等价字段）。此为后端增强，与本文档并列排期即可。
