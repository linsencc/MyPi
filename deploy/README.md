# 树莓派部署指南

## 前置条件

| 项目 | 要求 |
|------|------|
| 硬件 | Raspberry Pi Zero 2 W（或任何支持 SPI 的 Pi） |
| 显示屏 | Waveshare 13.3″ e-Paper E6 (1600×1200) |
| 系统 | Debian 13 (Trixie) / Raspberry Pi OS |
| 网络 | WiFi 已连接到局域网 |

## 一键部署

### 1. 将代码传到树莓派

```bash
# 方式 A：从开发机推送（在 Windows/Mac 上执行）
scp -r /path/to/MyPi linsen@192.168.1.118:~/MyPi

# 方式 B：在树莓派上 clone
ssh linsen@192.168.1.118
git clone <repo-url> ~/MyPi
```

### 2. 运行部署脚本

```bash
ssh linsen@192.168.1.118
bash ~/MyPi/deploy/deploy.sh
```

脚本会自动完成：
- 启用 SPI 接口
- 安装系统依赖（Python 3、Node.js 20、SPI 库等）
- 克隆 Waveshare e-Paper SDK
- 创建 Python 虚拟环境并安装后端依赖
- 构建前端（`web/dist/`）
- 安装并启动 systemd 服务

### 3. 访问 Web 控制台

部署完成后，在局域网内的任何设备（手机/电脑）打开浏览器访问：

```
http://192.168.1.118:5050
```

## 架构

```
                        LAN (192.168.1.x)
                              │
  浏览器（手机/电脑）──────────┤
                              │
                    ┌─────────▼──────────┐
                    │  Raspberry Pi       │
                    │  :5050              │
                    │                     │
                    │  gunicorn (1 worker)│
                    │    ├─ Flask API     │
                    │    ├─ 前端静态文件   │
                    │    ├─ APScheduler   │
                    │    └─ DisplaySink   │
                    │         │           │
                    │         ▼ SPI       │
                    │    ┌──────────┐     │
                    │    │ E6 e-ink │     │
                    │    │ 1600×1200│     │
                    │    └──────────┘     │
                    └─────────────────────┘
```

生产模式下 Flask 同时提供：
- `/api/v1/*` — REST API
- `/` — 前端 SPA（从 `web/dist/` 提供静态文件）

单进程 gunicorn（1 worker）避免 APScheduler 重复调度。

## 常用命令

```bash
# 查看服务状态
sudo systemctl status mypi

# 查看实时日志
sudo journalctl -u mypi -f

# 重启服务
sudo systemctl restart mypi

# 停止服务
sudo systemctl stop mypi

# 更新代码后重新部署
cd ~/MyPi && git pull
bash ~/MyPi/deploy/deploy.sh
```

## 环境变量

在 `deploy/mypi.service` 中配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MYPI_DISPLAY` | `epd_e6` | 显示驱动：`epd_e6`（真实硬件）或 `mock`（仅日志） |
| `MYPI_EPD_SDK` | `~/e-Paper/.../lib` | Waveshare SDK `lib/` 路径 |
| `MYPI_TZ` | `Asia/Shanghai` | IANA 时区 |
| `PORT` | `5050` | 服务端口 |
| `MYPI_BIND` | `0.0.0.0` | 绑定地址（0.0.0.0 = 所有接口） |

## 故障排查

### SPI 未启用
```bash
ls /dev/spidev*       # 应看到 spidev0.0 和 spidev0.1
sudo raspi-config     # Interface Options → SPI → Enable
sudo reboot
```

### 找不到 DEV_Config.so
```bash
ls ~/e-Paper/E-paper_Separate_Program/13.3inch_e-Paper_E/RaspberryPi/python/lib/DEV_Config_*.so
# 如果缺失，需要在 Pi 上编译 Waveshare 的 C 库（参见 SDK 的 Makefile）
```

### 端口被占用
```bash
sudo lsof -i :5050
sudo systemctl stop mypi
```

### 屏幕不刷新
1. 检查 SPI 连线
2. 查看日志：`sudo journalctl -u mypi -f`
3. 用 mock 模式测试 API：修改 service 文件中 `MYPI_DISPLAY=mock`
