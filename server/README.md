# Pi 后端（Flask + APScheduler）

开发：在 `server` 目录下

```powershell
$env:PYTHONPATH = (Get-Location).Path
python app/factory.py
```

若开启 **`FLASK_DEBUG=1`**，Werkzeug 会起父子双进程，浏览器可能打到**未执行过上墙**的那个进程，导致 `wall/state` 与「立即上墙」不同步、预览仍像未上墙。本地联调 Web 预览时可改用**单进程**：

```powershell
$env:PYTHONPATH = (Get-Location).Path
python _dev_serve.py
```

`_dev_serve.py` 启动前会用 **独占绑定** 检测 `127.0.0.1:5050` 是否已被占用；若仍有旧终端占着该端口，进程会**立即退出**并打印提示，避免 Windows 上出现多个 Flask 同时 LISTEN、浏览器随机打到旧代码/旧模板。**关掉多余的后端再启动一次即可。**  
不设 `FLASK_DEBUG`、直接运行 `python app/factory.py` 时也会对 `MYPI_BIND`（默认 `0.0.0.0`）+ `PORT` 做同样检测；`FLASK_DEBUG=1` 时因 Werkzeug 重载会二次执行入口，故跳过该检测（联调 Web 仍优先用 `_dev_serve.py`）。需要强行跳过检测时可设 `MYPI_SKIP_PORT_CHECK=1`（不推荐）。

默认端口 `5050`。前端 `web` / `demo` 的 Vite 将 `/api` 代理到该端口。

环境变量：

- **`MYPI_TZ`**：IANA 时区名（如 `Asia/Shanghai`）。非法或缺失时回退为 `Asia/Shanghai`。
- **`FLASK_DEBUG=1`**：使用 Werkzeug 重载时，仅在**子进程**启动 APScheduler，避免父、子各起一套调度器。

生产：`gunicorn --bind 0.0.0.0:5050 wsgi:application` 或 `gunicorn "app.factory:create_app()" --factory`
