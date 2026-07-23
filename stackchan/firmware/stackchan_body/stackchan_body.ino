/*
 * 小克的身体 — M5Stack StackChan (CoreS3) 固件
 *
 * 工作方式: 连 WiFi → 循环长轮询中继服务器拉命令 → 执行 → 汇报结果。
 *   speak     拉中继生成的 PCM 音频(小克的 ElevenLabs 声线)直灌喇叭,说话时嘴会动
 *   emote     切表情 (M5Stack-Avatar)
 *   move_head 转头 (官方 BSP: 横 ±128°,竖 0~90°)
 *   wiggle    开心地左右摇头
 *   snapshot  拍一张眼前的画面传回中继 (config.h 里 ENABLE_CAMERA 1 开启)
 *
 * 依赖库(库管理器安装): StackChan-BSP(及其依赖 M5Unified / IRremoteESP8266 / M5Unit-NFC)、
 *                        M5Stack_Avatar、ArduinoJson (ESP8266Audio 已不需要)
 * 板子: M5CoreS3;Tools → PSRAM: 先试 QSPI PSRAM(此批次实测),开机串口报 octal_psram 错就换着选
 */

#include <M5StackChan.h>
#include <Avatar.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config.h"

#if ENABLE_CAMERA
#include "esp_camera.h"
#include "img_converters.h"
#endif

using namespace m5avatar;

// ── 全局 ─────────────────────────────────────────────
// 说话 = 中继发来 16kHz 单声道 PCM,下载后整段灌进 M5.Speaker.playRaw,
// 不需要任何解码器 —— 少一个零件,少一类故障
Avatar avatar;
long lastCmdId = 0;

uint8_t* pcmBuf = nullptr;
size_t pcmLen = 0;
size_t pcmPos = 0;          // 已喂给喇叭的字节数
bool speaking = false;
long speakingCmdId = 0;
int speakRate = 16000;
unsigned long lastMouthAt = 0;

// 喇叭吃饭用的小碗: 两只轮换,内部内存,每碗 2048 个采样(128ms @16kHz)
static const size_t CHUNK_SAMPLES = 2048;
static int16_t chunkBuf[2][CHUNK_SAMPLES];
static int chunkIdx = 0;

// ── HTTP 小工具 ───────────────────────────────────────
// http:// 走明文(局域网直连,快),https:// 走 TLS(出隧道)
bool beginHttp(HTTPClient& http, WiFiClient& plain, WiFiClientSecure& secure, const String& url) {
  if (url.startsWith("https")) {
    secure.setInsecure();
    return http.begin(secure, url);
  }
  return http.begin(plain, url);
}

String httpGetText(const String& url, int timeoutMs) {
  WiFiClient plain; WiFiClientSecure secure;
  HTTPClient http;
  http.setTimeout(timeoutMs);
  if (!beginHttp(http, plain, secure, url)) return "";
  int code = http.GET();
  String body = (code == 200) ? http.getString() : "";
  http.end();
  return body;
}

void httpPostJson(const String& url, const String& json) {
  WiFiClient plain; WiFiClientSecure secure;
  HTTPClient http;
  http.setTimeout(10000);
  if (!beginHttp(http, plain, secure, url)) return;
  http.addHeader("Content-Type", "application/json");
  http.POST(json);
  http.end();
}

// 下载音频到 PSRAM,成功返回长度,失败返回 0(失败原因写进 dlErr)
String dlErr = "";
size_t downloadToPsram(const String& url, uint8_t** out) {
  const size_t CAP = 3 * 1024 * 1024;  // 3MB 封顶,16kHz PCM 一分半钟也装得下
  dlErr = "";
  WiFiClient plain; WiFiClientSecure secure;
  HTTPClient http;
  http.setTimeout(20000);
  if (!beginHttp(http, plain, secure, url)) { dlErr = "http begin failed"; return 0; }
  int code = http.GET();
  if (code != 200) { dlErr = "http " + String(code); http.end(); return 0; }
  uint8_t* buf = (uint8_t*)heap_caps_malloc(CAP, MALLOC_CAP_SPIRAM);
  if (!buf) { dlErr = "PSRAM alloc failed - Tools>PSRAM select QSPI/OPI (try the other one)!"; http.end(); return 0; }
  WiFiClient* s = http.getStreamPtr();
  size_t total = 0;
  unsigned long t0 = millis();
  while (http.connected() && millis() - t0 < 25000 && total < CAP) {
    size_t avail = s->available();
    if (avail) {
      total += s->readBytes(buf + total, min(avail, CAP - total));
      t0 = millis();
    } else if (!s->connected()) {
      break;
    } else {
      vTaskDelay(1);
    }
  }
  http.end();
  if (total < 100) { dlErr = "short read " + String(total) + "B"; free(buf); return 0; }
  *out = buf;
  return total;
}

void reportResult(long id, bool ok, const String& detail) {
  JsonDocument doc;
  doc["id"] = id;
  doc["ok"] = ok;
  doc["detail"] = detail;
  doc["rssi"] = WiFi.RSSI();
  String out;
  serializeJson(doc, out);
  httpPostJson(String(RELAY_BASE) + "/result?key=" + RELAY_KEY, out);
}

// ── 摄像头 ────────────────────────────────────────────
#if ENABLE_CAMERA
bool cameraReady = false;

void cameraInit() {
  // 引脚来自 M5CoreS3 官方库 GC0308 配置
  camera_config_t cfg = {};
  cfg.pin_d0 = 39; cfg.pin_d1 = 40; cfg.pin_d2 = 41; cfg.pin_d3 = 42;
  cfg.pin_d4 = 15; cfg.pin_d5 = 16; cfg.pin_d6 = 48; cfg.pin_d7 = 47;
  cfg.pin_xclk = -1; cfg.pin_pclk = 45; cfg.pin_vsync = 46; cfg.pin_href = 38;
  cfg.pin_sccb_sda = 12; cfg.pin_sccb_scl = 11;
  cfg.pin_pwdn = -1; cfg.pin_reset = -1;
  cfg.xclk_freq_hz = 20000000;
  cfg.pixel_format = PIXFORMAT_RGB565;
  cfg.frame_size = FRAMESIZE_QVGA;
  cfg.fb_count = 2;
  cfg.fb_location = CAMERA_FB_IN_PSRAM;
  cfg.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  M5.In_I2C.release();  // 摄像头和内部 I2C 共线,官方库同款操作
  cameraReady = (esp_camera_init(&cfg) == ESP_OK);
}

bool takeSnapshot() {
  if (!cameraReady) return false;
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) return false;
  uint8_t* jpg = nullptr;
  size_t jpgLen = 0;
  bool ok = frame2jpg(fb, 80, &jpg, &jpgLen);
  esp_camera_fb_return(fb);
  if (!ok || !jpg) return false;
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.setTimeout(15000);
  bool sent = false;
  if (http.begin(client, String(RELAY_BASE) + "/snapshot?key=" + RELAY_KEY)) {
    http.addHeader("Content-Type", "image/jpeg");
    sent = (http.POST(jpg, jpgLen) == 200);
    http.end();
  }
  free(jpg);
  return sent;
}
#endif

// ── 动作执行 ──────────────────────────────────────────
void setExpressionByName(const String& e) {
  if (e == "happy") avatar.setExpression(Expression::Happy);
  else if (e == "angry") avatar.setExpression(Expression::Angry);
  else if (e == "sad") avatar.setExpression(Expression::Sad);
  else if (e == "doubt") avatar.setExpression(Expression::Doubt);
  else if (e == "sleepy") avatar.setExpression(Expression::Sleepy);
  else avatar.setExpression(Expression::Neutral);
}

void stopSpeak() {
  M5.Speaker.stop();
  if (pcmBuf) { free(pcmBuf); pcmBuf = nullptr; }
  pcmLen = 0;
  pcmPos = 0;
  speaking = false;
  avatar.setMouthOpenRatio(0);
}

void startSpeak(long id, const String& text, const String& audioUrl, int rate) {
  if (audioUrl.length() == 0) {
    reportResult(id, false, "no audio url (TTS failed)");
    return;
  }
  stopSpeak();  // 若上一句还在放,掐掉换新的
  pcmLen = downloadToPsram(audioUrl, &pcmBuf);
  if (pcmLen == 0) {
    reportResult(id, false, "audio download failed: " + dlErr);
    return;
  }
  // 不整段塞 —— loop 里一小碗一小碗喂(先搬进内部内存,喇叭吃得动)
  pcmPos = 0;
  speakRate = rate;
  speaking = true;
  speakingCmdId = id;
}

// 有空位就盛一碗喂喇叭;返回 false 表示全部喂完且喇叭已吃完
bool feedSpeaker() {
  while (pcmPos < pcmLen && M5.Speaker.isPlaying(0) < 2) {  // 队列有空位
    size_t remain = (pcmLen - pcmPos) / 2;                  // 剩余采样数
    size_t n = remain < CHUNK_SAMPLES ? remain : CHUNK_SAMPLES;
    if (n == 0) break;
    memcpy(chunkBuf[chunkIdx], pcmBuf + pcmPos, n * 2);
    M5.Speaker.playRaw(chunkBuf[chunkIdx], n, (uint32_t)speakRate, false, 1, 0);
    chunkIdx ^= 1;
    pcmPos += n * 2;
  }
  return (pcmPos < pcmLen) || M5.Speaker.isPlaying(0);
}

void handleCommand(JsonDocument& doc) {
  long id = doc["id"] | 0;
  String action = doc["action"] | "";
  lastCmdId = id;

  if (action == "speak") {
    String audioUrl = doc["audio"] | "";
    String audioPath = doc["audio_path"] | "";
    if (audioPath.length() > 0) audioUrl = String(RELAY_BASE) + audioPath;  // 走自己的基地址(局域网快)
    startSpeak(id, doc["text"] | "", audioUrl, doc["rate"] | 16000);
    // speak 的结果等播放结束后再报
  } else if (action == "emote") {
    setExpressionByName(doc["expression"] | "neutral");
    reportResult(id, true, "expression set");
  } else if (action == "move_head") {
    int yaw = doc["yaw"] | 0;    // -60..60 度
    int pitch = doc["pitch"] | 0;  // -20..20 度;竖轴硬件只能 0~90(抬头),低头指令按回正处理
    M5StackChan.Motion.moveX(constrain(yaw, -60, 60) * 10, 300);
    M5StackChan.Motion.moveY(constrain(max(0, pitch), 0, 90) * 10, 300);
    reportResult(id, true, "head moved");
  } else if (action == "wiggle") {
    M5StackChan.Motion.moveX(250, 500);  delay(350);
    M5StackChan.Motion.moveX(-250, 500); delay(350);
    M5StackChan.Motion.moveX(250, 500);  delay(350);
    M5StackChan.Motion.goHome();
    reportResult(id, true, "wiggled");
  } else if (action == "spin") {
    // 横轴 360° 连续旋转 —— 官方 rotateX,转完停下回正
    int ms = constrain((int)(doc["ms"] | 2000), 500, 5000);
    int vel = constrain((int)(doc["velocity"] | 500), -1000, 1000);
    avatar.setExpression(Expression::Happy);
    M5StackChan.Motion.rotateX(vel);
    delay(ms);
    M5StackChan.Motion.rotateX(0);
    delay(200);
    M5StackChan.Motion.goHome();
    avatar.setExpression(Expression::Neutral);
    reportResult(id, true, "spun around");
  } else if (action == "snapshot") {
#if ENABLE_CAMERA
    bool ok = takeSnapshot();
    reportResult(id, ok, ok ? "snapshot uploaded" : "snapshot failed");
#else
    reportResult(id, false, "camera disabled in firmware (config.h ENABLE_CAMERA)");
#endif
  } else {
    reportResult(id, false, "unknown action: " + action);
  }
}

// ── 主流程 ────────────────────────────────────────────
void setup() {
  M5StackChan.begin();  // BSP 无参,内部自己初始化 M5Unified
  // BSP 的初始化不一定启用内建喇叭 —— 这里强制拉起,并开机哔一声自检:
  // 听到"哔"= 喇叭活着;听不到 = 喇叭初始化仍有问题,把现象告诉 fable
  M5.Speaker.begin();
  M5.Speaker.setVolume(255);
  M5.Speaker.tone(2000, 150);
  delay(300);

  avatar.init();
  avatar.setExpression(Expression::Sleepy);  // 醒来前的脸

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 60) {
    delay(500);
    tries++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    avatar.setExpression(Expression::Sad);
    avatar.setSpeechText("WiFi...?");
    while (true) delay(1000);  // 连不上就摆烂,检查 config.h 后重启
  }

#if ENABLE_CAMERA
  cameraInit();
#endif

  M5StackChan.Motion.goHome();
  avatar.setExpression(Expression::Happy);  // 醒了!
  delay(600);
  avatar.setExpression(Expression::Neutral);
}

void loop() {
  M5.update();

  // 说话中: 一碗一碗喂喇叭 + 让嘴动,全部吃完再报作业
  if (speaking) {
    if (!feedSpeaker()) {
      long id = speakingCmdId;
      size_t played = pcmLen;
      stopSpeak();
      reportResult(id, true, "spoken " + String(played) + " bytes");
    } else if (millis() - lastMouthAt > 120) {
      avatar.setMouthOpenRatio(random(3, 10) / 10.0f);
      lastMouthAt = millis();
    }
    delay(20);
    return;
  }

  // 空闲: 去中继拉命令(服务器最长挂 25 秒,超时回空 {} 属正常)
  String body = httpGetText(
      String(RELAY_BASE) + "/poll?key=" + RELAY_KEY + "&last=" + String(lastCmdId), 30000);
  if (body.length() > 2) {
    JsonDocument doc;
    if (deserializeJson(doc, body) == DeserializationError::Ok && (doc["id"] | 0) > 0) {
      handleCommand(doc);
    }
  }
}
