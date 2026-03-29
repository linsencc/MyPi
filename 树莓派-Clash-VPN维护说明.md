# 树莓派 Clash（Mihomo）VPN 维护说明

本文记录树莓派上 **Mihomo（Clash.Meta）+ Yacd** 的部署要点，便于后续维护与排障。**订阅链接、节点账号等敏感信息只应保存在树莓派 `/etc/clash/config.yaml` 或机场控制台，请勿把完整订阅 URL 提交到公开仓库。**

---

## 1. 架构一览

| 组件 | 说明 |
|------|------|
| 内核 | **Mihomo**（即 Clash.Meta；本机 **`/usr/local/bin/mihomo`**，**`/usr/local/bin/clash`** 为其符号链接） |
| 系统服务 | **`clash.service`**：`ExecStart=/usr/local/bin/clash -d /etc/clash`，**User=root** |
| Web 面板 | Yacd 静态目录 **`/etc/clash/ui/yacd`**（`external-ui` 指向此处） |
| 规则与节点 | 机场 **Clash 订阅**（当前为 **Ghelper** YAML，已合并进 `config.yaml`） |

---

## 2. 端口与访问方式

| 端口 | 用途 |
|------|------|
| **7890** | `mixed-port`：HTTP + SOCKS 合一入口（本机 `127.0.0.1`；局域网设备可用 `allow-lan`） |
| **9090** | 外部控制器（REST API + Yacd UI） |

**局域网浏览器打开面板：**

- UI：`http://<树莓派局域网IP>:9090/ui/`
- API 基址：`http://<树莓派局域网IP>:9090`
- 面板认证密钥（`secret`）：与 `config.yaml` 中 `secret` 一致（当前为 **`1020`**，强度较弱，建议日后改为长随机串并限制 `9090` 访问来源）
- 首次打开 Yacd 时，在界面中填写 **API 地址**（如上）与 **Secret**；REST 调用也可使用请求头 **`Authorization: Bearer <secret>`**。
- `external-controller` 为 **`0.0.0.0:9090`** 且 **`allow-lan: true`** 时，**同局域网设备**可访问面板；若不需要，应改为仅本机监听并配合防火墙策略。

**本机终端临时走代理示例：**

```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
```

---

## 3. 关键路径（树莓派上）

| 路径 | 说明 |
|------|------|
| `/etc/clash/config.yaml` | 主配置（订阅合并后规则、代理、`tun`、DNS 等） |
| `/etc/clash/ui/yacd` | Yacd 前端（`external-ui` 指向此目录） |
| `/etc/clash/geoip.metadb` | GeoIP 数据（`GEOIP` 规则依赖） |
| `/etc/clash/geosite.dat` | GeoSite 数据 |
| `/var/log/clash/clash.log` | 服务日志（由 systemd 追加写入） |
| `/etc/systemd/system/clash.service` | systemd 单元 |

**配置备份：**

- 执行 **`sudo clash-tun on` / `off`** 时，脚本会在 **`/etc/clash/`** 下自动生成 **`config.yaml.bak.<时间戳>`**。
- **手工编辑** `config.yaml` 前，请自行执行例如：`sudo cp -a /etc/clash/config.yaml /etc/clash/config.yaml.bak.manual.$(date +%Y%m%d%H%M%S)`。

---

## 4. 常用命令

```bash
# 服务状态
sudo systemctl status clash
sudo systemctl restart clash
sudo journalctl -u clash -f

# 配置语法检查（读取 /etc/clash/config.yaml，不常驻运行）
sudo clash -t -d /etc/clash

# 查看内核版本（排障时可贴出版本号）
clash -v
```

---

## 5. TUN 全局代理开关

需求：**默认不全局**；需要时开启 **TUN**，让**本机**流量按 `mode: rule` 进入 Mihomo（仍遵守订阅里的直连/代理规则）。

| 命令 | 说明 |
|------|------|
| `sudo clash-tun status` | 查看 `tun.enable` |
| `sudo clash-tun on` | 开启 TUN，校验配置后 `systemctl restart clash` |
| `sudo clash-tun off` | 关闭 TUN 并重启 |

脚本路径：`/usr/local/sbin/clash-tun`（`/usr/local/bin/clash-tun` 为符号链接）。

**`tun` 段要点（以 `config.yaml` 为准，当前部署大致如下）：**

- `enable`：`true` / `false`（默认 **`false`**）
- `device`：`tun0`；`stack`：**`system`**
- `dns-hijack`：`any:53`、`tcp://any:53`（与 `dns.enable` 配合，减少 DNS 绕过）
- `auto-route`、`auto-redirect`、`auto-detect-interface`：均为 **`true`**
- `strict-route`：**`true`**
- `route-exclude-address`：已包含 `10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、`169.254.0.0/16`，降低 SSH 与局域网管理断连风险
- 若某内网/Docker 网段仍异常，可在该列表中**追加**对应 CIDR 后 **`sudo systemctl restart clash`**（或 `clash-tun off`/`on` 前先改好配置）

**注意：** TUN 仅影响**树莓派本机**；家里其他设备不会自动翻墙，除非单独为其配置代理或网关。

---

## 6. 代理何时生效（回顾）

| 场景 | 是否经过 Clash |
|------|----------------|
| 应用/环境变量指向 `7890` | 是，再按规则分流 |
| 未设代理、TUN 关闭 | 否，直连 |
| TUN 开启 | 本机流量按系统路由进入 TUN，再由规则决定直连或走节点 |

---

## 7. 更新订阅 / 轮换链接

1. 在机场控制台**生成新订阅链接**（若怀疑旧链接泄露，应轮换）。
2. 在树莓派上拉取新订阅并**合并**以下固定项（避免面板与端口丢失）：
   - `mixed-port: 7890`
   - `allow-lan: true`
   - `external-controller: 0.0.0.0:9090`
   - `secret`（与 Yacd 一致）
   - `external-ui: /etc/clash/ui/yacd`
   - `tun:` 整段（若继续使用 TUN 开关）
3. 执行 `sudo clash -t -d /etc/clash`，通过后 `sudo systemctl restart clash`。

（若使用自动化脚本合并，需保证订阅里 `MATCH` 等规则无 YAML 语法问题，例如 **`MATCH,策略组` 逗号后不要多余空格**；合并后勿覆盖 **`geoip.metadb` / `geosite.dat`**，除非你有意更新 Geo 数据。）

---

## 8. 网络与下载说明（备忘）

树莓派直连 GitHub 可能极慢或失败；实际部署时曾采用 **在 Windows 等本机经镜像站下载 + `scp` 传到树莓派** 的方式安装 **Mihomo 二进制** 与 **Yacd**。**Geo** 可使用 [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) 发布的 **`geoip.metadb`**、**`geosite.dat`**，经镜像加速后保存到 **`/etc/clash/`**，避免首次加载 `GEOIP`/`GEOSITE` 规则时在线下载超时。

---

## 9. 排障提示

- **服务起不来：** `sudo journalctl -u clash -xe`、`sudo clash -t -d /etc/clash`。
- **规则含 `GEOIP` 报错：** 检查 `/etc/clash/geoip.metadb` 是否存在、大小是否正常（异常小或 0 字节多为下载中断）。
- **`external-ui` 路径报错：** 使用 **`-d /etc/clash`** 时，**`external-ui` 须落在该目录允许路径下**；当前为 **`/etc/clash/ui/yacd`**（勿随意改到 `/root/...` 等，否则 `-t` 可能报 SAFE_PATHS）。
- **开 TUN 后 SSH 异常：** 优先 **`sudo clash-tun off`**；仍有问题时检查 `route-exclude-address` 是否需增加你的网段，或暂时将 **`strict-route`** 改为 `false` 后再观察（需理解可能增加泄漏面）。
- **「全局」但部分 HTTPS 失败：** 属规则/SNI/线路差异常见现象；可用 **`curl -v`**、面板连接日志与 **`http://www.gstatic.com/generate_204`** 等与 **`https://`** 对照排查。

---

## 10. 与本仓库 / 本机协作

- 从 **Windows** 管理树莓派：若已配置 SSH 别名（如 `my_pi`），可 `ssh my_pi` 执行上述命令。
- 本文档仅描述**约定与路径**；**真实订阅 URL、节点密码**请以树莓派上实际 `config.yaml` 与机场控制台为准。

---

*文档目的：沉淀 VPN 关键信息，便于后续维护与使用。*

*校对说明：已与树莓派上实际 `clash.service`、`/usr/local/bin/{mihomo,clash}`、`/etc/clash/ui/yacd`、`geoip.metadb` / `geosite.dat` 及 `clash-tun` 行为对照修订；若你日后升级内核或改路径，请同步更新本文。*
