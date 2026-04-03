# 树莓派 VPN（Mihomo + Yacd）运维速查

## 1. 入口与面板

| 项目 | 值 |
|------|----|
| 代理端口 | `7890`（`mixed-port`） |
| 面板端口 | `9090`（`external-controller`） |
| UI | `http://<IP>:9090/ui/` |
| API | `http://<IP>:9090` |
| Secret | 以 `/etc/clash/config.yaml` 中 `secret` 为准（不要写进仓库） |

本机临时走代理：

```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
```

---

## 2. 关键文件

| 路径 | 用途 |
|------|------|
| `/usr/local/bin/mihomo` | 内核二进制 |
| `/usr/local/bin/clash` | 符号链接（指向 mihomo） |
| `/etc/clash/config.yaml` | 主配置 |
| `/etc/clash/ui/yacd` | Yacd（`external-ui`） |
| `/var/log/clash/clash.log` | 日志 |
| `/etc/systemd/system/clash.service` | systemd 单元 |

---

## 3. 常用命令

```bash
sudo systemctl status clash
sudo systemctl restart clash
sudo journalctl -u clash -f

sudo clash -t -d /etc/clash
clash -v
```

---

## 4. TUN 开关（影响树莓派本机）

```bash
sudo clash-tun status
sudo clash-tun on
sudo clash-tun off
```

脚本：`/usr/local/sbin/clash-tun`