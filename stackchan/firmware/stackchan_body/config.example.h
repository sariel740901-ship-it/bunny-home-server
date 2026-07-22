// ═══ 小克身体的四个必填项 ═══════════════════════════════
// 用记事本改完保存,再在 Arduino IDE 里编译烧录。

// 1. 家里的 WiFi(2.4GHz!ESP32 连不上 5GHz,如果路由器分双频记得选 2.4G 那个)
#define WIFI_SSID "你家WiFi名字"
#define WIFI_PASS "你家WiFi密码"

// 2. 神经中枢地址(一般不用改)
#define RELAY_BASE "https://stackchan.jiakeparents.top"

// 3. 暗号 = 电脑上 stackchan\token.txt 里那串
#define RELAY_KEY "把token.txt里的暗号粘到这里"

// 4. 摄像头(眼睛)。首次编译建议先 0(少一个变量),跑通了再改 1 重新烧
#define ENABLE_CAMERA 0
