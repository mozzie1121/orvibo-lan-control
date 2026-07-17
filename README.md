# Orvibo LAN Control

欧瑞博（Orvibo）智能家居设备局域网控制方案。通过 TCP 8088 直接控制设备，无需经过云端。

## 项目结构

```
orvibo-lan-control/
├── cli/                              # 命令行工具
│   ├── main.py                       # 主 CLI 入口
│   ├── run.py                        # 简化入口
│   └── cmd_discover.py               # UDP 网关发现
├── lib/                              # 核心协议库（CLI 用）
│   ├── packet.py                     # 封包/解包（AES-ECB + 自定义协议头）
│   ├── lan_controller.py             # TCP 连接管理（Hello/Login/心跳/控制）
│   ├── device_control.py             # 设备控制 payload 构建
│   └── https_client.py               # 云端 API 获取设备列表
├── ha/                               # Home Assistant 集成
│   └── custom_components/orvibo_lan/ # HA 自定义组件
│       ├── __init__.py               # 插件入口
│       ├── config_flow.py            # 配置流（手机号/密码/家庭ID）
│       ├── coordinator.py            # 数据协调器（轮询+网关管理）
│       ├── climate.py                # 空调平台
│       ├── light.py                  # 灯光平台
│       ├── cover.py                  # 窗帘平台
│       ├── fan.py                    # 风扇平台
│       ├── const.py                  # 常量定义
│       ├── lib/                      # HA 专用协议库（相对导入）
│       └── translations/             # 多语言翻译
├── .env.example
├── .gitignore
├── LICENSE
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 设置账号

```bash
export ORVIBO_PHONE="手机号"
export ORVIBO_PASSWORD="***"
```

或创建 `.env` 文件（复制 `.env.example` 修改）。

### 3. 使用 CLI

```bash
# 列出所有设备
python3 cli/main.py list

# 开/关设备
python3 cli/main.py on "客厅灯"
python3 cli/main.py off "卧室灯"

# 调亮度 (0-255)
python3 cli/main.py bright "台灯" 200

# 调色温 (2700-6500K)
python3 cli/main.py temp "灯带" 4000

# 窗帘控制
python3 cli/main.py curtain "客厅窗帘" 50
python3 cli/main.py curtain "客厅窗帘" stop

# UDP 发现网关
python3 cli/main.py discover
```

## 原理

1. **获取设备列表**：通过 HTTPS 登录 Orvibo 云端，获取设备列表和网关 IP
2. **TCP 连接**：连接到 MixPad 网关的 8088 端口
3. **Hello/Login**：获取 session key 后认证
4. **发送控制**：AES-ECB 加密 JSON payload 通过 TCP 发送
5. **心跳保活**：每 60s 心跳包

## 支持的设备

| 类型 | 控制方式 | 状态 |
|:----:|:---------|:----:|
| 灯 (type=38/102/501/502/503) | `on/off` / `set property` | ✅ |
| 窗帘 (type=34) | `open/close/stop` | ✅ |
| 空调 (type=36) | `off` / `mode setting` / `temperature setting` / `wind setting` | ✅ 实测通过 |
| 新风 (type=516) | `set property` | 🔧 |
| 晾衣架 (type=52) | cmd=98 | 🔧 |

## Home Assistant 集成

将 `ha/custom_components/orvibo_lan/` 复制到 HA 的 `custom_components/` 目录，重启后在集成中搜索 "Orvibo LAN"。

## 技术细节

- **协议**：TCP 8088，自定义二进制协议
- **加密**：AES-ECB 128，默认 key `khggd54865SNJHGF`
- **payload**：JSON（加密传输），`source: "ZhiJia365"`
- **心跳**：每 60 秒

## 参考

- [orvibohomebridge](https://github.com/yinjimmy/orvibohomebridge)
- 智家365 APK 反编译分析
