# digital-frame

- 配图下载：`image_fetch.py`（磁盘缓存 `.image-cache/`、urllib 重试、可选 `requests`、再 `curl`；继承 `http_proxy`/`https_proxy`）。
- 网络稳定时先执行：`python3 show_poster.py --prefetch` 预拉 `posters.json` 里所有 `image_url`，之后可离线排版（仍须本机有图或缓存）。
- 强制走本地图：`python3 show_poster.py --image /path/to.jpg …`

**要墨水屏真的变：**不要用 `--dry-run`。示例：`python3 show_poster.py --index 0`。若怀疑没刷上，加 `--clear-first` 先清屏再画。
