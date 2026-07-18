<div align="center">

# Orvibo LAN Control

**欧瑞博智能家居 · 局域网离线控制方案**

[![GitHub Release](https://img.shields.io/github/v/release/mozzie1121/orvibo-lan-control)](https://github.com/mozzie1121/orvibo-lan-control/releases)
[![HACS Validation](https://github.com/mozzie1121/orvibo-lan-control/actions/workflows/hacs.yml/badge.svg)](https://github.com/mozzie1121/orvibo-lan-control/actions/workflows/hacs.yml)
[![License: MIT](https://img.shields.io/github/license/mozzie1121/orvibo-lan-control)](LICENSE)

通过局域网 TCP 8088 直接控制 Orvibo Zigbee 设备，不依赖云端。

</div>

---

> ⚠️ **重要说明**：本地控制仅支持通过 MixPad 网关接入的 **Zigbee 子设备**。WiFi 直连设备（如晾衣架等）尚不支持本地局域网控制。

## 项目结构

```
orvibo-lan-control/
├── custom_components/orvibo_lan/   # 🤖 Home Assistant 自定义组件
│   ├── __init__.py                 # 插件入口 / 配置加载
│   ├── config_flow.py              # UI 配置流
│   ├── coordinator.py              # 协调器 + 网关管理 + 状态监听
│   ├── climate.py                  # 空调平台
│   ├── light.py                    # 灯光平台
│   ├── cover.py                    # 窗帘平台
│   ├── fan.py                      # 风扇平台
│   ├── lib/                        # 核心协议库
│   │   ├── packet.py               # 封包/解包（AES-ECB）
│   │   ├── lan_controller.py       # TCP 连接管理
│   │   ├── device_control.py       # 设备控制 payload
│   │   └── https_client.py         # 云端 API 客户端
│   └── translations/               # 多语言翻译
├── .github/workflows/release.yml   # 自动发布
├── hacs.json
├── LICENSE
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
│                  │   回复/状态推送 (cmd=42)    └──────────┘
└─────────────────┘
```

1. **获取设备列表** — 通过 HTTPS 登录 Orvibo 云端，获取家庭下设备信息和所属网关 IP
2. **TCP 连接网关** — 连接局域网内 MixPad 的 8088 端口
3. **Hello/Login** — 获取 session key 后认证
4. **发送控制** — AES-ECB 加密 JSON payload，通过 TCP 发送
5. **状态推送** — 网关实时推送设备状态变化（cmd=42），无需轮询
6. **心跳保活** — 每 60s 心跳包

## 安装（Home Assistant）

### 方式一：通过 HACS（推荐）

[![Open in HACS](https://img.shields.io/badge/HACS-Add%20Repository-41BDF5)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mozzie1121&repository=orvibo-lan-control&category=integration)

1. 在 HACS 中添加自定义仓库：`https://github.com/mozzie1121/orvibo-lan-control`
2. 搜索并安装 **Orvibo LAN Control**
3. 重启 Home Assistant
4. 进入 **设置 → 设备与服务 → 添加集成**，搜索 **Orvibo LAN**

### 方式二：手动安装

将 `custom_components/orvibo_lan/` 复制到 Home Assistant 的 `custom_components/` 目录：

```bash
cp -r custom_components/orvibo_lan /path/to/config/custom_components/
```

重启 HA 后添加集成。

### 配置参数

| 参数 | 必填 | 说明 |
|:----|:----:|:------|
| 手机号 | ✅ | Orvibo 账号（手机号） |
| 密码 | ✅ | Orvibo 账号密码 |
| 家庭 ID | ❌ | 可选，不填自动选择第一个家庭 |

> 首次添加后自动拉取设备列表，无需额外配置。设备区域根据 App 中的房间设置自动同步。

## 支持的设备

> ⚠️ 仅支持通过 MixPad 网关接入的 **Zigbee 子设备**。WiFi 直连设备不支持本地控制。

### ✅ 实测通过

| 类别 | 型号/系列 | 功能 |
|:----|:----------|:-----|
| 🔘 **开关** | MixSwitch 系列（Classic / Bach / Defy / Gauss） | 开/关 |
| ❄️ **空调** | AirMaster 系列空调网关 | 模式/温度/风速 |
| 🪟 **窗帘** | 精筑系列 / 超静音系列 窗帘电机 | 开/关/停/位置 |
| 💡 **筒射灯** | SoPro 系列（S3 / S5 / S10）智能筒射灯 | 开/关/亮度/色温 |
| 💡 **调光灯** | 二代智能调光灯 | 开/关/亮度 |
| 🌈 **灯带** | 智能灯带控制器 | 开/关/亮度/色温 |
| ❄️ **空调/新风** | AirMaster 系列控制器 | 开/关/模式/温度/风速 |

### 🔧 待测试

| 类别 | 型号/系列 | 功能 |
|:----|:----------|:-----|
| ⚡ **调光** | 0-10V 调光模块 | 待验证 |

### ❌ 不支持（WiFi 直连设备）

| 类别 | 原因 |
|:----|:-----|
| 电动晾衣架 | WiFi 直连，不走 MixPad 网关 |
| 智能遥控器 | WiFi 直连，不走 MixPad 网关 |
| 摄像头/门铃 | WiFi 直连 |
| 梦幻帘一代/二代 | 协议不支持 |
| 其他 WiFi 直连设备 | 协议不支持 |

## 技术细节

- **协议**：TCP 8088，自定义二进制协议
- **加密**：AES-ECB 128
- **默认 key**：`khggd54865SNJHGF`
- **心跳间隔**：60 秒
- **控制 payload**：JSON，加密传输，`source: "ZhiJia365"`
- **状态反馈**：网关实时推送 cmd=42，支持两种格式：
  - **ThingModel**（statusType=501/502/503）：properties.onoff / brightness.percent / colorTemp.value
  - **旧协议**（statusType=2）：value1=开关、value2=亮度、value3=色温(mired)、value4=预留
- **区域同步**：首次配置时通过 readtable API 的 room[] 映射自动分配 HA 区域

### 空调控制（type=36）

|通过抓包分析，各操作使用的命令格式如下：

| 操作 | order | value1 | value2 | value3 | value4 |
|:----|:------|:------:|:------:|:------:|:------:|
| 关机 | `off` | 1 | 当前模式 | 当前风速 | 当前温度<<16 |
| 开机 | `on` | 0 | 模式码 | 风速码 | (温度×100)<<16 |
| 切换模式 | `mode setting` | 0 | 2除湿/3制冷/4制热/7送风 | - | 当前温度<<16 |
| 设温度 | `temperature setting` | 0 | 当前模式 | 当前风速 | (目标温度×100)<<16 |
| 设风速 | `wind setting` | 0 | 当前模式 | 1低/2中/3高 | 当前温度<<16 |

> 所有控制命令都保持 `groupId=""`、`qualityOfService=1`、`defaultResponse=1`、`propertyResponse=0`，与 App 行为一致。

**模式码对照：** `2=除湿` `3=制冷` `4=制热` `7=送风`

**温度编码：** `value4` 高16位 = 目标温度×100（如 26℃ → `0x0A28` = 2600）

### 灯控制

| 类型 | 开 | 关 | 调亮度 | 调色温 |
|:----|:---|:---|:------|:------|
| 38（调光调色灯） | `order=on` | `order=off` | `order=move to level` | `order=fast color temperature` |
| 102 / 通用 | `order=on, value1=0` | `order=off, value1=1` | `order=on, value2=亮度` | - |
| 501 | `set property onoff=on` | `set property onoff=off` | - | - |
| 502 | `set property onoff=on` | `set property onoff=off` | `set property brightness.percent` | - |
| 503 | `set property onoff=on` | `set property onoff=off` | `set property brightness.percent` | `set property colorTemp.value` |

### 窗帘控制（type=34）

- **开：** `order="open"`
- **关：** `order="close"`
- **停止：** `order="stop"`
- **设定位置：** 传 position=0~100，≥50 发 `"on"`，<50 发 `"off"`

## 开发

### UDP 发现网关

```python
from lib.packet import *
from lib.lan_controller import *
# 见 coordinator.py 的 _udp_discover()
```

### 协议分析

通过对比智家365 App 发出的控制包，确定正确字段格式。关键发现：

- AC 控制 **不能用** `order="set property"` — 实测无效
- 必须传 `groupId=""`（空字符串），删除后网关不转发给子设备
- `value2`/`value3`/`value4` 应保留当前设备的模式/风速/温度状态（App 始终携带）

## 版本历史

### v0.3.0（2026-07-18）
- 局域网状态推送（cmd=42），实时光效不轮询
- 设备区域自动同步（从 App 房间配置映射到 HA 区域）
- 网关设备注册修复（via_device 兼容 HA 2025.12+）
- 所有日志降级为 debug，减少日志量

### v0.2.0（2026-07-17）
- 修复空调开机（改用 `order="on"`）
- 修复空调风速控制（补全 `value2` 当前模式、`value4` 当前温度）
- 修复温度设定（补全 `value2` 当前模式、`value3` 当前风速）
- 保留 `groupId` 字段（不再被 `_to_lan` 删除）
- 对齐智家365 App 抓包格式

### v0.1.0（2026-07-17）
- 初始版本
- 基础设备控制：灯、窗帘、风扇
- 空调基础控制（`order="off"` / `"mode setting"` / `"temperature setting"` / `"wind setting"`）
- UDP 自动发现多网关
- 心跳保活

## 致谢

- [orvibohomebridge](https://github.com/yinjimmy/orvibohomebridge) — 在线控制版实现参考

## License

MIT
