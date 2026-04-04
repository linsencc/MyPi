# Pi 后端（Flask + APScheduler）

开发：在 `pi-server` 目录下

```powershell
$env:PYTHONPATH = (Get-Location).Path
python app/factory.py
```

若开启 **`FLASK_DEBUG=1`**，Werkzeug 会起父子双进程，浏览器可能打到**未执行过上墙**的那个进程，导致 `wall/state` 与「立即上墙」不同步、预览仍像未上墙。本地联调 Web 预览时可改用**单进程**：

```powershell
$env:PYTHONPATH = (Get-Location).Path
python _dev_serve.py
```

默认端口 `5050`。前端 `web` / `demo` 的 Vite 将 `/api` 代理到该端口。

环境变量：

- **`MYPI_TZ`**：IANA 时区名（如 `Asia/Shanghai`）。非法或缺失时回退为 `Asia/Shanghai`。
- **`FLASK_DEBUG=1`**：使用 Werkzeug 重载时，仅在**子进程**启动 APScheduler，避免父、子各起一套调度器。

生产：`gunicorn --bind 0.0.0.0:5050 wsgi:application` 或 `gunicorn "app.factory:create_app()" --factory`
