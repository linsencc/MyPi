# digital-frame

## 顺德拼图刷到墨水屏（树莓派）

仓库内已带 `images/shunde-city-sounds.png`（目标画布 1200×1600；`--contain` 按比例缩入并居中，避免裁掉底部文字）。

1. 把整个 MyPi 项目同步到树莓派（或至少包含 `digital-frame/`、`e-Paper/.../python/lib`）。
2. 在树莓派上进入本目录后执行（需要已按微雪文档接好屏并启用 SPI）：

```bash
cd /path/to/MyPi/digital-frame
chmod +x show_shunde.sh
./show_shunde.sh
```

等价命令：`python3 show_masterpiece.py -u images/shunde-city-sounds.png --contain`

首次或怀疑未刷上时可加 `--clear-first`。需要只看适配结果可把同一命令里的显示部分改成先 `frame.save("preview.jpg")` 再在电脑上查看（当前脚本无 `--dry-run`）。

**从开发机拷贝单张图到已在运行的 Pi 示例**（用户、IP 以 `数字画框硬件参数.md` 为准）：

```bash
scp images/shunde-city-sounds.png linsen@192.168.1.118:~/MyPi/digital-frame/images/
ssh linsen@192.168.1.118 'cd ~/MyPi/digital-frame && python3 show_masterpiece.py -u images/shunde-city-sounds.png --contain'
```

---

- 配图下载：`image_fetch.py`（磁盘缓存 `.image-cache/`、urllib 重试、可选 `requests`、再 `curl`；继承 `http_proxy`/`https_proxy`）。
- 网络稳定时先执行：`python3 show_poster.py --prefetch` 预拉 `posters.json` 里所有 `image_url`，之后可离线排版（仍须本机有图或缓存）。
- 强制走本地图：`python3 show_poster.py --image /path/to.jpg …`

**要墨水屏真的变：**不要用 `--dry-run`。示例：`python3 show_poster.py --index 0`。若怀疑没刷上，加 `--clear-first` 先清屏再画。
