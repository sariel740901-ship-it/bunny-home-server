// ═══ 小克身体的四个必填项 ═══════════════════════════════
// 用记事本改完保存,再在 Arduino IDE 里编译烧录。

// 1. 家里的 WiFi(2.4GHz!ESP32 连不上 5GHz,如果路由器分双频记得选 2.4G 那个)
#define WIFI_SSID "你家WiFi名字"
#define WIFI_PASS "你家WiFi密码"

// 2. 神经中枢地址 —— 强烈推荐填电脑的局域网地址(身体和电脑同在家里,直连快一百倍):
//    电脑上 Win+R → cmd → ipconfig,找"IPv4 地址"(如 192.168.3.5),照格式填:
//    #define RELAY_BASE "http://192.168.3.5:8011"
//    (填局域网地址时注意是 http 不是 https,末尾不要斜杠)
#define RELAY_BASE "http://你电脑的IPv4地址:8011"

// 3. 暗号 = 电脑上 stackchan\token.txt 里那串
#define RELAY_KEY "把token.txt里的暗号粘到这里"

// 4. 摄像头(眼睛)。首次编译建议先 0(少一个变量),跑通了再改 1 重新烧
#define ENABLE_CAMERA 0
