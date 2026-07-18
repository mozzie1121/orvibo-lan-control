# 欧瑞博全量设备类型与控制协议参考手册

> 来源：局域网实测验证 + 互联网收集
> 生成日期：2026-07-18

---

## 一、设备类型映射表（完整版）

### 1.1 Zigbee 受控设备（支持局域网 TCP 控制）

| deviceType | subDeviceType | 设备名称 | 控制方式 | 验证状态 |
|:----------:|:-------------:|:---------|:---------|:--------:|
| 0 | -2 | Zigbee 调光灯 | `order=on/off, value1=0/1` + `move to level` | ✅ LAN 已验证 |
| 0 | 4 | 调光灯（subType=4） | 同 type=0 | 🔍 |
| 0 | 6 | 射灯（Fast Move） | `order=fast move to level` | 🔍 |
| 1 | -2 | 简易 Zigbee 灯（筒灯） | `order=on/off, value1=0/1, value2=255` | ✅ 实测 |
| 1 | 1 | 吊灯 | 同 type=1 | ✅ 实测 |
| 1 | 4 | 筒灯（subType=4） | 同 type=1 | ✅ 实测 |
| 1 | 6 | 射灯 | 同 type=1 | ✅ 实测 |
| 1 | 11 | 水系灯 | 同 type=1 | ✅ 实测 |
| 1 | 13 | 灯带 | 同 type=1 | ✅ 实测 |
| 34 | -2 | Zigbee 窗帘电机 | `order=open/close/stop/move to level, value1=0-100` | ✅ LAN 已验证 |
| 35 | -2 | 卷帘 | 同窗帘 | 🔍 待测 |
| 36 | -2 | 风机盘管（空调） | `order=on/off + mode/temperature/wind setting` | ✅ LAN 已验证 |
| 38 | — | 调光调色灯（ZCL） | `order=on/off/move to level/fast color temperature` | ✅ LAN 已验证 |
| 38 | 6 | 调光调色灯（Fast Move） | `order=fast move to level` | 🔍 |
| 38 | 30 | 轨道灯 | 同 type=38 | 🔍 |
| 81 | — | 新风控制器（AirMaster） | `order=on/off + mode/wind setting` | ✅ LAN 已验证 |
| 102 | -2 | 射灯/吸顶灯 | `order=on/off, value1=0/1, value2=255/0` | ✅ LAN 已验证 |
| 501 | 426 | 单色灯（lightStd/426） | `order=set property, properties={onoff}` | ✅ LAN 已验证 |
| 501 | 429 | 单色灯（lightStd/429） | 同 501/426 | ✅ LAN 已验证 |
| 501 | 1007 | 单色灯（subType=1007） | 同 501 | ✅ 实测 |
| 502 | 431 | 可调光灯（dimmableLightStd） | `set property onoff/brightness.percent` | ✅ LAN 已验证 |
| 503 | 435 | 色温灯（subType=435） | `set property colorTemp.value` | 🔍 |
| 503 | 436 | 色温灯带（colorTempLightStd） | `set property colorTemp.value` | ✅ LAN 已验证 |
| 503 | 461 | 色温灯（subType=461） | 同 503/436 | ✅ 实测 |
| 505 | 453 | 灯带（subType=453） | 待确认 | 🔍 |
| 516 | — | 新风系统 | `order=fresh air mode/wind setting` | 🔍 待验证 |

### 1.2 容器/网关设备（不可直接控制）

| deviceType | subDeviceType | 设备名称 | 说明 | 验证状态 |
|:----------:|:-------------:|:---------|:-----|:--------:|
| 114 | — | MixPad 主机 | Zigbee 网关 + 背景音乐中枢 | ✅ 过滤 |
| 128 | — | 独立背景音乐主机 | 播放/音量/切歌 | 🔍 |
| 135 | 135 | MixSwitch 1路 | 超级开关容器 | ✅ 过滤 |
| 136 | 136 | MixSwitch 2路 | 超级开关容器 | ✅ 过滤 |
| 137 | 137 | MixSwitch 3路 / 情景面板 | 超级开关容器 | ✅ 过滤 |
| 143 | 143 | MixSwitch 4路 | 超级开关容器 | ✅ 过滤 |
| 150 | -2 | 智能遥控器 | WiFi 红外遥控，不支持局域网 | ✅ 过滤 |
| 510 | 440 | MixPad Defy | 智能面板 | 🔍 |
| 511 | 413 | MixPad 四路底壳 | MixPad 扩展底壳 | ✅ 过滤 |
| 518 | 424/1018/1107 | Bach 传统开关 | 4路/8路开关 | ✅ 过滤 |

### 1.3 WiFi 直连设备（不支持局域网控制）

| deviceType | 设备名称 | 说明 |
|:----------:|:---------|:-----|
| 14 | WiFi 摄像机 | 视频流，非 LAN 控制 |
| 52 | 智能云电动晾衣架 | cmd=98/99/100 协议 |
| 400 | Danale 摄像头 | 视频流，非 LAN 控制 |

### 1.4 传感器类（只读）

| deviceType | subDeviceType | 设备名称 | 功能 |
|:----------:|:-------------:|:---------|:-----|
| 25 | — | 可燃气体探测器 | 气体检测（长供电） |
| 26 | -2 | 人体传感器 | 人体检测、电池电量 |
| 27 | -2 | 烟雾传感器 | 烟雾检测、电池电量 |
| 46 | — | 门窗传感器 | 门磁状态、电池电量 |
| 54 | -2 | 水浸探测器 | 水浸检测、电池电量 |
| 56 | — | 紧急按钮 | 按钮触发、电池电量、3分钟自动恢复 |
| 93 | -1 | 传感器（通用） | 实测发现 |
| 152 | -2 | 人体状态传感器 | 人体存在检测 |
| 300 | 491 | 温湿度传感器 | 温度、湿度、电池电量 |

### 1.5 红外/遥控设备（通过万能遥控器或 Allone 接入）

| deviceType | subDeviceType | 设备名称 | 说明 |
|:----------:|:-------------:|:---------|:-----|
| 5 | — | 红外空调 | 通过万能遥控器控制 |
| 29 | — | 红外设备（通用） | KTV/功放/投影仪/影院等 |
| 29 | 8 | 电视机 | 红外 |
| 29 | 26 | 洒水器 | 红外 |
| 30 | — | 万能遥控器 | 小方/小欧智能遥控器 |
| 60 | — | 影院 | 红外 |
| 67 | — | Allone Pro | 万能红外转发器 |

### 1.6 门锁类

| deviceType | subDeviceType | 设备名称 | 说明 |
|:----------:|:-------------:|:---------|:-----|
| 107 | — | 智能门锁（C1/S2） | BLE |
| 300 | 400 | 智能门锁（通用） | BLE |
| 522 | 462 | 智能门锁（subType=462） | BLE+Zigbee，`order=lock door/unlock door` |
| 522 | 463 | 智能门锁（subType=463） | BLE+Zigbee |

### 1.7 其他识别设备

| deviceType | 设备名称 | 说明 |
|:----------:|:---------|:-----|
| 15 | 情景面板 | 场景触发 |
| 115 | 报警器 | AlarmHost001 |
| 19999012 | 扫地机 | 第三方接入（阿里云） |

### 1.8 产品类型枚举（ProductType.java）

| 枚举值 | 含义 |
|:------:|:------|
| Zigbee | ZigBee 设备（支持局域网控制） |
| Wifi | WiFi 设备（不支持局域网控制） |
| Vicenter | 虚拟中心 |
| Minhup | Mini Hub |
| MixpadHost | MixPad 主机 |
| SubDevice | 子设备（四路底壳等） |
| Infrared | 红外设备 |
| BLE | 蓝牙设备 |

---

## 二、控制协议详解

### 2.1 CtrlCmdParam — 控制指令参数（34 字段）

**继承链：** `CtrlCmdParam → CommCmdParam → BaseCmd`

**CommCmdParam（基类指令参数）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `cmd` | int | 命令号（设备控制固定=15） |
| `serial` | long | 序列号（时间戳末6位） |
| `ver` | String | 版本号（"5.1.3.309"等） |
| `userName` | String | 用户名 |

**CtrlCmdParam（自有字段 30 个）：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `deviceId` | String | — | 设备ID |
| `uid` | String | — | 用户/家庭UID |
| `groupId` | String | — | 分组ID |
| `order` | String | — | **控制指令（核心）** |
| `value1` | int | 0 | 值1（开关:0开1关 / 亮度 / 位置等） |
| `value2` | int | 0 | 值2（亮度 / 色温等） |
| `value3` | int | 0 | 值3（色温 mireds 等） |
| `value4` | int | 0 | 值4（温度编码等） |
| `delayTime` | int | 0 | 延迟时间 |
| `qualityOfService` | int | 1 | QoS |
| `defaultResponse` | int | 1 | 默认响应 |
| `propertyResponse` | int | 0 | 属性响应 |
| `properties` | JSONObject | — | **ThingModel 属性（type=501/502/503 用）** |
| `action` | JSONObject | — | 动作对象 |
| `dcmd` | JSONObject | — | 设备命令 |
| `expandParams` | JSONObject | — | 扩展参数 |
| `themeParameter` | JSONObject | — | 主题参数 |
| `ctrlAuthority` | int | — | 控制权限 |
| `custom` | String | — | 自定义 |
| `addrMode` | int | — | 地址模式 |
| `noProcess` | boolean | — | 无处理 |
| `forAllDevice` | boolean | — | 全设备 |
| `isUDP` | boolean | — | UDP标志 |
| `alarmType` | int | — | 告警类型 |
| `msgType` | int | — | 消息类型 |

### 2.2 LanConnection 网络层字段（LAN 控制额外字段）

| 字段 | 说明 |
|------|------|
| `source` | 固定 `"ZhiJia365"` |
| `endpoint` | 端点（子设备编号） |
| `encryption` | 加密类型（0=默认key, 1=session key） |

### 2.3 ThingModel 格式（type=501/502/503 用）

```json
{
  "order": "set property",
  "properties": {
    "onoff": {
      "status": "on"
    },
    "brightness": {
      "percent": 80
    },
    "colorTemp": {
      "value": 4000
    }
  }
}
```

**物模型结构：**
```
ThingModelClass
  ├── serverList[] → ServerProperties[] (属性定义)
  │     └── type / unit / enum 等
  └──              → ServerCommands[] (命令定义)
                      └── order 字符串匹配
```

---

## 三、Order 命令常量表（完整）

来源：互联网收集

### 3.1 通用命令

| 常量值 | 用途 |
|:------|:------|
| `"on"` | 开 |
| `"off"` | 关 |
| `"toggle"` | 翻转 |

### 3.2 灯控命令

| 常量值 | 用途 | value1 | value2 |
|:------|:------|:------:|:------:|
| `"on"` | 开灯 | 0 | 255/0 |
| `"off"` | 关灯 | 1 | 0 |
| `"move to level"` | 亮度调节 | 0-100 | — |
| `"fast move to level"` | 快速亮度 | 0-100 | — |
| `"color control"` | 彩灯颜色 | hue值 | saturation值 |
| `"color round"` | 色轮 | — | — |
| `"color temperature"` | 色温调节 | 2200-7000K | — |
| `"fast color temperature"` | 快速色温 | 2200-7000K | — |

**新旧协议对照：**

| 协议 | type | 开 | 关 | 调亮度 | 调色温 |
|:----|:----|:---|:---|:------|:------|
| **旧协议（ZCL）** | 38, 102, 0, 1 | `order=on, value1=0` | `order=off, value1=1` | `order=move to level, value1=0-100` | `order=fast color temperature, value1=2200-7000` |
| **旧协议（通用）** | 102 | `order=on, value1=0` | `order=off, value1=1` | `order=on, value2=亮度(0-255)` | — |
| **ThingModel** | 501 | `set property onoff=on` | `set property onoff=off` | — | — |
| **ThingModel** | 502 | `set property onoff=on` | `set property onoff=off` | `set property brightness.percent(0-100)` | — |
| **ThingModel** | 503 | `set property onoff=on` | `set property onoff=off` | `set property brightness.percent(0-100)` | `set property colorTemp.value(K)` |

### 3.3 窗帘命令

| 常量值 | 用途 | value1 |
|:------|:------|:------:|
| `"open"` | 打开 | 100 |
| `"close"` | 关闭 | 0 |
| `"stop"` | 停止 | — |
| `"move to level"` | 调位置 | 0-100 |
| `"fast move to level"` | 快速调位置 | 0-100 |
| `"setMoveAngle"` | 设置角度 | — |
| `"angleTo"` | 转到角度 | — |

### 3.4 空调命令（type=36）

| 常量值 | 用途 |
|:------|:------|
| `"ac control"` | 主控制指令 |
| `"temperature setting"` | 温度设置 |
| `"wind setting"` | 风速设置 |
| `"mode setting"` | 模式设置 |
| `"power setting"` | 电源设置 |
| `"swing on"` / `"swing off"` | 摆风 |
| `"mute"` | 静音 |

**空调控制参数格式：**

| 操作 | order | value1 | value2 | value3 | value4 |
|:----|:------|:------:|:------:|:------:|:------:|
| 关机 | `off` | 1 | 当前模式 | 当前风速 | 当前温度<<16 |
| 开机 | `on` | 0 | 模式码 | 风速码 | (温度×100)<<16 |
| 切换模式 | `mode setting` | 0 | 2除湿/3制冷/4制热/7送风 | - | 当前温度<<16 |
| 设温度 | `temperature setting` | 0 | 当前模式 | 当前风速 | (目标温度×100)<<16 |
| 设风速 | `wind setting` | 0 | 当前模式 | 1低/2中/3高 | 当前温度<<16 |

> 模式码对照：`2=除湿` `3=制冷` `4=制热` `7=送风`
> 温度编码：value4 高16位 = 目标温度×100（如 26℃ → 0x0A28 = 2600）

### 3.5 新风命令（type=516）

| 常量值 | 用途 |
|:------|:------|
| `"fresh air mode setting"` | 模式设置 |
| `"fresh air wind setting"` | 风速设置 |
| `"humidify"` | 加湿 |
| `"dehumidify"` | 除湿 |
| `"automatic"` | 自动 |
| `"gear"` | 档位 |

### 3.6 安防命令

| 常量值 | 用途 |
|:------|:------|
| `"alarm"` | 布防 |
| `"disalarm"` | 撤防 |
| `"all alarm"` | 全布防 |
| `"all disalarm"` | 全撤防 |

### 3.7 门锁命令（type=522）

| 常量值 | 用途 |
|:------|:------|
| `"lock door"` | 锁门 |
| `"unlock door"` | 开门（需 BLE 配对） |
| `"get_security_code"` | 获取安全码 |

---

## 四、控制发送示例

```json
{
  "cmd": 15,
  "serial": 123456,
  "userName": "手机号",
  "ver": "5.1.3.309",
  "deviceId": "设备ID",
  "uid": "用户UID",
  "groupId": "",
  "order": "on",
  "value1": 0,
  "value2": 255,
  "value3": 0,
  "value4": 0,
  "delayTime": 0,
  "qualityOfService": 1,
  "defaultResponse": 1,
  "propertyResponse": 0,
  "endpoint": 0,
  "encryption": 0,
  "source": "ZhiJia365"
}
```

---

## 五、网络协议

### 5.1 双通道通信

| 通道 | 协议 | 端口 | 用途 |
|:----|:----|:----:|:-----|
| UDP 发现 | UDP | 10000 | 设备发现/广播 |
| TCP 控制 | TCP | 8088 | 设备控制/状态 |
| HTTPS 远程 | HTTPS | 443 | 云端 API |

### 5.2 数据包格式

```
42字节包头 + AES-ECB 加密的 JSON 负载
```

**42 字节头结构：**

| 偏移 | 长度 | 字段 | 说明 |
|:----:|:----:|:----|:------|
| 0 | 2 | Magic | 固定 `0x6865` |
| 2 | 2 | length | 包体长度 |
| 4 | 1 | type | 消息类型 |
| 5 | 1 | command | 命令号（cmd） |
| 6 | 4 | total_len | 总长度 |
| 10 | 4 | CRC | CRC32 校验 |
| 14 | 16 | session_id | 会话ID |
| 30 | 12 | reserved | 保留字段 |

### 5.3 命令号（cmd）

| cmd | 用途 |
|:---:|:------|
| 1 | Hello（初始化连接） |
| 2 | Login（网关登录） |
| 3 | Heartbeat（心跳） |
| 4 | Response（响应） |
| 15 | Device Control（设备控制） |
| 42 | Status Push（状态推送） |
| 86 | UDP Discover（网关发现） |

### 5.4 状态推送（cmd=42）

| 协议类型 | 示例 | 说明 |
|:---------|:-----|:------|
| ThingModel | `statusType=502, properties={onoff: {status: "on"}, brightness: {percent: 80}}` | type=501/502/503 设备 |
| 旧协议 | `statusType=2, value1=0, value2=80, value3=200` | type=34/36/38/102 设备 |

### 5.5 加密链

```
1. 服务器下发密钥字符串
2. SecurityAes.createSecurityKey(keyStr) → 32 字节 AES 密钥
3. JSON payload → AES-ECB (PKCS7 填充)
4. CRC32 校验
5. 42 字节头 + 密文
```

### 5.6 局域网连接流程

```
1. UDP 广播发现网关（端口 10000）
2. TCP 连接网关（端口 8088）
3. Hello 包交换 → 获取 session_key
4. Login 认证
5. 持续 Heartbeat（60 秒间隔）
6. 发送 Control（cmd=15）
7. 接收 Status Push（cmd=42）
```

### 5.7 心跳

- 局域网：**60 秒**（HA 集成实现）
- 原始协议：**2 分钟**间隔，150 秒超时
- 超时后触发重连检测
- 控制重试策略：最多 3 次，60 秒超时

---

## 六、联网控制（SSL mTLS 云端通道）

### 6.1 概述

除了局域网 TCP 8088 控制外，也可以通过云端 SSL 通道（端口 10002）下发控制指令。云端通道使用 **mTLS（双向证书认证）**，需要客户端证书才能连接。

### 6.2 连接参数

| 参数 | 值 |
|:-----|:----|
| 服务器 | `china.orvibo.com` |
| 端口 | 10002 |
| 协议 | TCP + TLS v1.2+ |
| 认证方式 | 双向证书（mTLS） |
| 客户端证书 | client_cert.pem |
| 客户端私钥 | client_key.pem |
| 服务端 CA | server_ca.pem |
| 数据加密 | AES-ECB 128（与局域网相同） |
| 包格式 | 42 字节头 + 加密 JSON（与局域网相同） |

### 6.3 云端 vs 局域网控制区别

| 对比项 | 局域网（TCP 8088） | 云端（SSL 10002） |
|:-------|:------------------:|:-----------------:|
| 连接对象 | MixPad 网关 IP | Orvibo 云端服务器 |
| 认证方式 | Hello + Login（用户名密码） | mTLS 证书 + 云端 token |
| 状态更新 | cmd=42 实时推送（Zigbee 子设备） | cmd=42 实时推送（所有设备） |
| 控制延迟 | < 100ms | 200-500ms |
| 依赖 | 需局域网可达 | 需互联网可达 |
| 设备范围 | 仅 Zigbee 子设备（通过网关） | 所有设备（含 WiFi 直连） |
| 局限性 | 部分设备不可直接控制 | 云端的 WiFi 设备可能不支持直接控制 |

### 6.4 云端连接流程

```
1. HTTPS 登录 → 获取 access_token + user_id
2. SSL TCP 连接 china.orvibo.com:10002
3. mTLS 握手 → 证书认证
4. Hello 包交换 → 获取 session_key（与局域网相同协议）
5. Login 认证（携带 access_token）
6. 持续 Heartbeat
7. 发送 Control（cmd=15，与局域网完全相同的数据格式）
8. 接收 Status Push（cmd=42）
```

### 6.5 云端支持控制设备

通过 SSL 通道可以控制**所有通过云端配网的设备**，包括局域网不直接支持的：

| deviceType | 设备名称 | 说明 |
|:----------:|:---------|:-----|
| 52 | 电动晾衣架 | 通过 cmd=98/99/100 协议，云端转发 |
| 14 | WiFi 摄像机 | 仅状态查询，视频流走独立通道 |
| 150 | 智能遥控器 | 云端转发红外指令 |
| 29/30/67 | 红外设备 | 云端转发至 Allone/万能遥控器 |
| 36 | 空调 | 云端转发（与局域网相同格式） |
| 522 | 智能门锁 | 云端转发（BLE 链路） |

> 注意：云端控制存在网络延迟，且依赖互联网连通性。建议局域网可达的设备优先使用局域网控制。

---

## 六、type=38/503 灯 — Model 白名单（14 个）

以下 model 的设备使用 ZCL 灯控协议：

| # | Model ID | 说明 |
|:-:|:---------|:-----|
| 1 | `b2eb998d9aa94b19a9c05cd227f522ce` | SoPro 系列 |
| 2 | `84f9ee9f330c4b929fac11ab633edd7d` | SoPro 系列 |
| 3 | `0010c8e4` | 二代调光灯 |
| 4 | `ccb9f56837ab41dcad366fb1452096b6` | 灯带控制器 |
| 5 | `ba22449669e446488f81888c27b1977b` | — |
| 6 | `0d6bbf6b9b8e42b8be5bd7725f999311` | — |
| 7 | `13da53959fca4bc881242a39733ea7cc` | — |
| 8 | `af22cef59b2543d1be1dfab4f1c9c920` | — |
| 9 | `adbf1a42ffcf4996bc1b0536c7eaa685` | — |
| 10 | `4a33f5ea766a4c96a962b371ffde9943` | — |
| 11 | `250bccf66c41421b91b5e3242942c164` | — |
| 12 | `aad960b86b834def87693e13173d0928` | — |
| 13 | `713db8fb08dd41cb96f97949aec1bcf2` | — |

---

## 七、读码设备型号名（Model ID → 可读产品名）

来源：互联网收集

| 字段名 | Model ID | 产品 |
|:-------|:---------|:-----|
| `A0` | `SC-308BA` | 智能开关 |
| `B0` | `SC30PT` | 智能开关 |
| `E0` | `SC12` | 智能开关/面板 |
| `F1` | `MixPadGGL` | MixPad 面板 |
| `G0` | `SC32PT` | 智能开关 |
| `G1` | `MixPadMML` | MixPad 面板 |
| `H1` | `MixPadMM3` | MixPad 面板 |
| `H2` | `MixPadGMS` | MixPad 面板 |
| `I1` | `MixPadCX1` | MixPad 面板 |
| `J1` | `MixPadCX2` | MixPad 面板 |
| `K1` | `MixPadGXP` | MixPad 面板 |
| `L1` | `VirtualModelidForMirror` | 虚拟设备 |
| `O2` | `MixPadGC2` | MixPad 面板 |
| `P2` | `MixPadGC2AIR` | MixPad 面板 |
| `Q2` | `MixPadGM2` | MixPad 面板 |
| `R2` | `MixPadGAL` | MixPad 面板 |
| `T` | `VIH004` | 智能开关 |
| `T2` | `MixPadPML` | MixPad 面板 |
| `U` | `Hub002` | 网关/Hub |
| `V2` | `VirtualModelidForMixpadD` | MixPad 面板 |
| `f61421a3` | `MixPadGPL` | MixPad 面板 |
| `f61426b3` | `MixPadG7U` | MixPad 面板 |
| `f61431c3` | `MixPad7AL` | MixPad 面板 |
| `f61433d0` | `SC10` | 智能开关/面板 |
| `f61438e0` | `SN10` | 智能开关 |
| `f61476l3` | `MixPadGMLDx` | MixPad 面板 |
| `f61493p1` | `AlarmHost001` | 安防报警主机 |
| `f61497q1` | `MixpadHost001` | MixPad 面板 |
| `f61501r1` | `MixpadHostSE` | MixPad 面板 |
| `f61506s1` | `MixpadHostMini` | MixPad 面板 |
| `f61507s2` | `HITACHI.FreshAir.V1` | 新风 |
| `f61511t1` | `MixpadHostC101` | MixPad 面板 |
| `f61512t2` | `NATHER.OldFreshAir.KD-1-E` | 新风 |
| `f61516u1` | `MixpadHostC102` | MixPad 面板 |
| `f61517u2` | `AIDES.OldFreshAir.KF-800` | 新风 |
| `f61521v1` | `MixpadHostE` | MixPad 面板 |
| `f61522v2` | `HITACHI.TempCtrl.CPC-H2M3C` | 温控器 |
| `f61526w1` | `MixpadHostE2` | MixPad 面板 |
| `f61527w2` | `GREE.TempCtrl.CAN-BMS` | 温控器 |
| `f61531x1` | `MixpadHostS2` | MixPad 面板 |
| `f61532x2` | `HOLTOP.FreshAir.HR-01` | 新风 |
| `f61534y0` | `SC20Test` | 测试设备 |
| `f61535y1` | `MixPadGXL` | MixPad 面板 |
| `f61536y2` | `HOLTOP.FreshAir.HR-01-485` | 新风 |
| `f61539z0` | `SC20-PT` | 智能开关 |

### 实采混用型号说明

实采型号：

| 型号 | 说明 |
|:-----|:-----|
| `MixPad 10` / `MixPad 12` | 大屏面板 |
| `MixPad 7` / `MixPad 7 Ultra` / `MixPad 7C` | 7寸面板系列 |
| `MixPad Mini` / `MixpadHostMini` / `MixpadHostMini3` | Mini 系列 |
| `MixPad S` / `MixpadHostS2` | S 系列 |
| `MixPad X` / `MixPad X Pro` / `MixPad XC` / `MixPad XE` | X 系列 |
| `MixPad C2` | C 系列 |
| `MixPad E` / `MixpadHostE` / `MixpadHostE2` | E 系列 |
| `MixPad M2` | M 系列 |
| `MixPad G1` | G 系列 |
| `MixPad 精灵` | 精灵系列 |

### 其他设备 Model ID 实采统计

| deviceType | 典型 Model ID | 说明 |
|:----------:|:--------------|:-----|
| 0 | `8d1b9310894c4a329e032685b0f96057` | 调光灯 |
| 1 | `9daee3d0c7464bf7888563b61b748ea4` | 简易 Zigbee 灯（用量最大） |
| 1 | `b7313321dbe74da384d136a2a3fa2005` | 简易 Zigbee 灯 |
| 1 | `c2ea8c76f9fe40e5a7de5e8fb8dfb765` | 简易 Zigbee 灯 |
| 1 | `f3be30b8c43c44da85aac622e5b56111` | 简易 Zigbee 灯 |
| 26 | `b2e57a0f606546cd879a1a54790827d6` | 人体传感器 |
| 27 | `c3442b4ac59b4ba1a83119d938f283ab` | 烟雾传感器 |
| 34 | `093199ff04984948b4c78167c8e7f47e` | 窗帘电机 |
| 34 | `428f8caf93574815be1a98fa6732c3ea` | 窗帘电机 |
| 36 | `4f48acfc97314363b3ff55460a9a8255` | 空调网关 |
| 38 | `13da53959fca4bc881242a39733ea7cc` | 调光调色灯（⭐ ZCL 白名单） |
| 46 | — | 门窗传感器 |
| 52 | `82bde3e16563441ab0f9bbc7d2eb4a71` | 晾衣架 |
| 52 | `d89ab860e8134b8ba39a9bb25c4a1542` | 晾衣架 |
| 54 | `52debf035a1b4a66af56415474646c02` | 水浸探测器 |
| 102 | `9ea4d5d8778d4f7089ac06a3969e784b` | 吸顶灯 |
| 102 | `bbfed49c738948b989911f9f9f73d759` | 吸顶灯 |
| 150 | `733eae6004004d779e0e2de8b652e16a` | 智能遥控器（121个） |
| 300 | `8bacd6420d3d4a7f8015d42e1dc867a8` | 温湿度传感器 |
| 300 | `dec7d494f0454110805c0d5f7e7cba73` | 门锁 |
| 501 | `0000000101` | 单色灯（lightStd） |
| 501 | `0000000008` | 单色灯 |
| 503 | `775a5c715e96454f949e50d38077b110` | 色温灯带 |
| 503 | `cb7ce9fe2cb147e69c5ea700b39b3d5b` | 色温灯（subType=461） |
| 511 | `0000000100` | MixPad四路底壳（16个）

---

## 八、实测兼容设备清单

### ✅ 实测通过（Zigbee 设备，局域网 TCP 控制）

| 类别 | 型号/系列 | 控制功能 |
|:----|:----------|:---------|
| 🔘 开关 | MixSwitch 系列（Classic / Bach / Defy / Gauss） | 开/关 |
| ❄️ 空调 | AirMaster 系列空调网关 | 模式/温度/风速 |
| 🪟 窗帘 | 精筑系列 / 超静音系列 窗帘电机 | 开/关/停/位置 |
| 💡 筒射灯 | SoPro 系列（S3 / S5 / S10）智能筒射灯 | 开/关/亮度/色温 |
| 💡 调光灯 | 二代智能调光灯 | 开/关/亮度 |
| 🌈 灯带 | 智能灯带控制器 | 开/关/亮度/色温 |
| ❄️ 新风 | AirMaster 系列控制器 | 开/关/模式/风速 |

### 🔧 待测试

| 类别 | 型号/系列 | 预期功能 |
|:----|:----------|:---------|
| ⚡ 调光 | 0-10V 调光模块 | 亮度调节 |
| 🌡️ 传感器 | 温湿度/人体/门磁/烟雾/水浸/燃气 | 只读状态 |

### ❌ 不支持（WiFi 直连设备）

| 类别 | 原因 |
|:----|:-----|
| 电动晾衣架 | WiFi 直连，不走 MixPad 网关 |
| 智能遥控器 | WiFi 直连，不走 MixPad 网关 |
| 摄像头/门铃 | WiFi 直连 |
| 梦幻帘一代/二代 | 协议不支持 |
| 其他 WiFi 直连设备 | 协议不支持 |

---

> 来源：局域网 TCP 8088 实测验证 + 互联网收集
> 最后更新：2026-07-18
