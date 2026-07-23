# 小克身体固件 — 烧录指南(保姆级)🔧

只做一次,以后升级固件也是同样流程。全程机器人用 USB-C 线连电脑。

## 一、装 Arduino IDE(约 10 分钟)

1. https://www.arduino.cc/en/software 下载 Windows 版,一路下一步装好
2. 打开后 **File → Preferences**,`Additional boards manager URLs` 里粘贴:
   ```
   https://static-cdn.m5stack.com/resource/arduino/package_m5stack_index.json
   ```
3. **Tools → Board → Boards Manager**,搜 `M5Stack`,装 **M5Stack by M5Stack官方**(几百 MB,耐心)
4. **Tools → Manage Libraries**,逐个搜索安装:
   - `StackChan-BSP`(官方身体支持库)
   - `M5Unified`、`IRremoteESP8266`、`M5Unit-NFC`(BSP 的三个依赖,提示一起装就点 Install All)
   - `M5Stack_Avatar`(那张脸)
   - `ESP8266Audio`(放 mp3 用,名字带 8266 但支持 ESP32,别疑惑)
   - `ArduinoJson`

## 二、填配置

记事本打开 `stackchan_body\config.h`,填四样:

- WiFi 名 + 密码(**必须 2.4GHz**,5G 连不上)
- 中枢地址:**填电脑的局域网地址** `http://电脑IPv4:8011`(cmd 里 `ipconfig` 查;
  身体和电脑同在一个家,直连比绕 Cloudflare 快一百倍,实测隧道路线会慢到音频下载不完)
- `RELAY_KEY` = 电脑 `stackchan\token.txt` 里那串暗号
- `ENABLE_CAMERA` 首次先 `0`,跑通了再改 `1` 重烧一次

## 三、编译烧录

1. Arduino IDE 打开 `stackchan_body\stackchan_body.ino`
2. **Tools → Board** 选 `M5CoreS3`;**Tools → PSRAM** 选 `QSPI PSRAM`(嘉嘉这台实测;开机串口若报 `octal_psram` 错误说明选反了,QSPI/OPI 换着试);**Tools → USB CDC On Boot** 选 `Enabled`(串口日志靠它)
3. USB 线连上机器人,**Tools → Port** 选新冒出来的 COM 口
4. 点左上 **→(Upload)**,等它编译+烧录(第一次要几分钟)
5. 完成后机器人重启:困脸 → 连 WiFi → 笑一下 → 平静脸 = **他住进去了**

## 四、验收

手机官端跟小克说:

> 你的身体上线了,动一动试试?

他会调 `stackchan_status`(应显示在线)→ `stackchan_wiggle`(摇头)→ `stackchan_speak`(开口说话,是他自己的声音!)

## 常见问题

| 症状 | 解法 |
|---|---|
| 编译报错 | 整段错误复制发给 fable,一般是库版本小事 |
| 找不到 COM 口 | 换根 USB 线(有些线只能充电);或装 CH9102 驱动 |
| 一直困脸 | WiFi 没连上 —— 检查 config.h 的名字密码、确认是 2.4G |
| 悲伤脸 + "WiFi...?" | 同上,连了 30 秒没连上 |
| 有脸没声音 | 中枢窗口看有没有 `✓ 声音: 复用 voice-bar 配置` |
| status 显示不在线 | token.txt 暗号和 config.h 的 RELAY_KEY 不一致 |
| 局域网直连不通 | Windows 防火墙拦了 8011 入站:控制面板→防火墙→允许应用,给 Python 勾上"专用网络";或首次弹窗时点"允许" |
| 电脑 IP 变了导致失联 | 路由器后台给电脑绑定静态 IP(DHCP 保留),一劳永逸 |

## 已知取舍

- 竖轴硬件行程 0~90°(抬头),"低头"指令会按回正处理
- 说话时嘴型是节奏随机张合(不是真声纹对口型),观感已经很像了
- 摄像头和内部 I2C 共线,官方同款处理;若开摄像头后触摸异常,把 ENABLE_CAMERA 关回 0 并告诉 fable
