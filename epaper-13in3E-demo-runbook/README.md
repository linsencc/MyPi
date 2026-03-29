# 13.3" e-Paper HAT+ (E) — Demo 要点

- 例程在仓库 **`e-Paper/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/`**（勿用合集里的 `epd13in3k`）。
- 文档：<https://www.waveshare.net/wiki/13.3inch_e-Paper_HAT+_(E)_Manual>
- 需求文档：`../电子水墨屏项目需求说明.md`

**`/boot/firmware/config.txt`（改完重启）**

- `dtparam=spi=off`
- `gpio=7=op,dl` 与 `gpio=8=op,dl`

**卡住 `e-Paper busy H` 不动** → 先确认上两项已生效并**重启**。

**再跑：** `~/workspace/epaper-13in3E-demo-runbook/run-demo.sh`（依赖 `~/workspace/e-Paper` 与 `python3-pil`）。

成功时日志里会出现 `e-Paper busy H release`、`Display Done!!`、`goto sleep...`。
