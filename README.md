<div align="center">

# Orvibo LAN Control

**欧瑞博智能家居 · 局域网离线控制方案**

[![GitHub Release](https://img.shields.io/github/v/release/mozzie1121/orvibo-lan-control)](https://github.com/mozzie1121/orvibo-lan-control/releases)
[![HACS Validation](https://github.com/mozzie1121/orvibo-lan-control/actions/workflows/hacs.yml/badge.svg)](https://github.com/mozzie1121/orvibo-lan-control/actions/workflows/hacs.yml)
[![License: MIT](https://img.shields.io/github/license/mozzie1121/orvibo-lan-control)](LICENSE)

通过局域网 TCP 8088 直接控制 Orvibo 设备，不依赖云端。

</div>

---

## 项目结构

```
orvibo-lan-control/
├── ha/                               # 🤖 Home Assistant 集成
│   └── custom_components/orvibo_lan/ # HACS 可安装的自定义组件
│       ├── __init__.py               # 插件入口 / 配置加载
│       ├── config_flow.py            # UI 配置流
│       ├── coordinator.py            # 轮询协调器 + 网关管理
│       ├── climate.py                # 空调平台
│       ├── light.py                  # 灯光平台
│       ├── cover.py                  # 窗帘平台
│       ├── fan.py                    # 风扇平台
│       ├── lib/                      # 核心协议库
│       │   ├── packet.py             # 封包/解包（AES-ECB）
│       │   ├── lan_controller.py     # TCP 连接管理
│       │   ├── device_control.py     # 设备控制 payload
│       │   └── https_client.py       # 云端 API 客户端
│       └── translations/             # 多语言翻译
├── lib/                              # 📚 核心协议库（独立版）
├── .github/workflows/hacs.yml        # HACS 自动验证
├── .env.example
├── .gitignore
├── LICENSE
├── requirements.txt
└── README.md
```

## 原理

```
┌─────────────────┐     HTTPS（获取设备列表）   ┌──────────┐
│ Home Assistant   │ ───────────────────────→  │ Orvibo   │
│ / orvibo_lan     │                            │ 云端     │
│                  │ ←───────────────────────  │          │
│                  │   返回设备列表 + 网关IP     └──────────┘
│                  │
│                  │     TCP 8088（局域网控制）  ┌──────────┐
│                  │ ───────────────────────→  │ MixPad   │
│                  │                            │ 网关     │
│                  │ ←───────────────────────  │          │
│                  │   回复/状态推送             └──────────┘
└─────────────────┘
```

1. **获取设备列表** — 通过 HTTPS 登录 Orvibo 云端，获取家庭下设备信息和所属网关 IP
2. **TCP 连接网关** — 连接局域网内 MixPad 的 8088 端口
3. **Hello/Login** — 获取 session key 后认证
4. **发送控制** — AES-ECB 加密 JSON payload，通过 TCP 发送
5. **心跳保活** — 每 60s 心跳包

## 安装（Home Assistant）

### 方式一：通过 HACS（推荐）

[![Open in HACS](https://img.shields.io/badge/HACS-Add%20Repository-41BDF5)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mozzie1121&repository=orvibo-lan-control&category=integration)

1. 在 HACS 中添加自定义仓库：`https://github.com/mozzie1121/orvibo-lan-control`
2. 搜索并安装 **Orvibo LAN Control**
3. 重启 Home Assistant
4. 进入 **设置 → 设备与服务 → 添加集成**，搜索 **Orvibo LAN**

### 方式二：手动安装

将 `ha/custom_components/orvibo_lan/` 复制到 Home Assistant 的 `custom_components/` 目录：

```bash
cp -r ha/custom_components/orvibo_lan /path/to/config/custom_components/
```

重启 HA 后添加集成。

### 配置参数

| 参数 | 必填 | 说明 |
|:----|:----:|:------|
| 手机号 | ✅ | Orvibo 账号（手机号） |
| 密码 | ✅ | Orvibo 账号密码 |
| 家庭 ID | ❌ | 可选，不填自动选择第一个家庭 |

> 首次添加后自动拉取设备列表，无需额外配置。

## 支持的设备

| 类型 | 名称 | 控制方式 | 状态 |
|:----:|:-----|:---------|:----:|
| 36 | 风机盘管（空调） | `off` / `mode setting` / `temperature setting` / `wind setting` | ✅ 实测通过 |
| 34 | Zigbee 窗帘 | `open` / `close` / `stop` | ✅ |
| 38 / 102 | 灯 | `on` / `off` | ✅ |
| 501 | 平板灯/吸顶灯 | `set property` | ✅ |
| 502 | 可调光灯 | `set property` + `brightness` | ✅ |
| 503 | 色温灯带 | `set property` + `colorTemp` | ✅ |
| 516 | 新风系统 | `set property` | 🔧 |
| 52 | 电动晾衣架 | cmd=98 | 🔧 |

## 技术细节

- **协议**：TCP 8088，自定义二进制协议
- **加密**：AES-ECB 128
- **默认 key**：`khggd54865SNJHGF`
- **心跳间隔**：60 秒
- **控制 payload**：JSON，加密传输，`source: "ZhiJia365"`

### 空调控制（type=36）

实测通过的格式：

| 操作 | order | value1 | value2 | value3 | value4 |
|:----|:------|:------:|:------:|:------:|:------:|
| 关机 | `off` | 1 | - | - | - |
| 开机+模式 | `mode setting` | 0 | 3制冷/4制热/7送风/2除湿 | - | - |
| 设温度 | `temperature setting` | - | - | - | (temp×100)<<16 |
| 设风速 | `wind setting` | - | - | 1低/2中/3高 | - |

## 开发

```bash
pip install -r requirements.txt
cp .env.example .env   # 填写手机号+密码
```

### UDP 发现网关

```python
from lib.packet import *
from lib.lan_controller import *
# 见 ha/custom_components/orvibo_lan/coordinator.py 的 _udp_discover()
```

## 致谢

- [orvibohomebridge](https://github.com/yinjimmy/orvibohomebridge) — 在线控制版实现参考
- 智家365 APK 反编译 — 协议字段确认

## License

MIT
