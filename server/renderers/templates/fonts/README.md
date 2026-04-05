# 中文字体（每日寄语）

模板会按以下顺序找能显示简中汉字的字体：

1. 环境变量 **`MYPI_CJK_FONT`**（绝对路径指向 `.ttf` / `.otc` / `.ttc`）
2. 本目录下的 **`NotoSansSC-Regular.otf`**（若不存在且未设置 `MYPI_NO_FONT_FETCH=1`，首次渲染时会尝试从 jsDelivr 下载子集字体，约 8MB）
3. Linux **`fc-match`**（`Noto Sans CJK SC` 等）
4. 常见系统字体路径

树莓派离线部署时，可执行：

```bash
sudo apt install fonts-noto-cjk
```

或将本仓库中的 `NotoSansSC-Regular.otf` 放到此目录（可从 [Noto CJK SubsetOTF/SC](https://github.com/notofonts/noto-cjk/tree/main/Sans/SubsetOTF/SC) 获取）。
