# Pi 后端（Flask + APScheduler）

开发：在 `pi-server` 目录下

```powershell
$env:PYTHONPATH = (Get-Location).Path
python app/factory.py
```

默认端口 `5050`。前端 `demo` 已配置 Vite 将 `/api` 代理到该端口。

环境变量：

- **`MYPI_TZ`**：IANA 时区名（如 `Asia/Shanghai`）。非法或缺失时回退为 `Asia/Shanghai`。
- **`FLASK_DEBUG=1`**：使用 Werkzeug 重载时，仅在**子进程**启动 APScheduler，避免父、子各起一套调度器。

生产：`gunicorn --bind 0.0.0.0:5050 wsgi:application` 或 `gunicorn "app.factory:create_app()" --factory`
