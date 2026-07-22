/*
 * 小克的身体 — M5Stack StackChan (CoreS3) 固件
 *
 * 工作方式: 连 WiFi → 循环长轮询中继服务器拉命令 → 执行 → 汇报结果。
 *   speak     拉中继生成的 mp3(小克的 ElevenLabs 声线)播放,说话时嘴会动
 *   emote     切表情 (M5Stack-Avatar)
 *   move_head 转头 (官方 BSP: 横 ±128°,竖 0~90°)
 *   wiggle    开心地左右摇头
 *   snapshot  拍一张眼前的画面传回中继 (config.h 里 ENABLE_CAMERA 1 开启)
 *
 * 依赖库(库管理器安装): StackChan-BSP(及其依赖 M5Unified / IRremoteESP8266 / M5Unit-NFC)、
 *                        M5Stack_Avatar、ESP8266Audio、ArduinoJson
 * 板子: M5CoreS3;Tools → PSRAM 选 "OPI PSRAM"
 */

#include <M5StackChan.h>
#include <Avatar.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <AudioGeneratorMP3.h>
#include <AudioFileSourcePROGMEM.h>
#include <AudioOutput.h>
#include "config.h"

#if ENABLE_CAMERA
#include "esp_camera.h"
#include "img_converters.h"
#endif

using namespace m5avatar;

// ── 把 ESP8266Audio 的输出接到 M5 喇叭 (经典三缓冲写法) ──
class AudioOutputM5Speaker : public AudioOutput {
public:
  AudioOutputM5Speaker(m5::Speaker_Class* spk, uint8_t ch = 0)
      : _spk(spk), _ch(ch), _idx(0), _cur(0) {}
  bool begin() override { return true; }
  bool ConsumeSample(int16_t sample[2]) override {
    _buf[_cur][_idx++] = (int16_t)((sample[0] + sample[1]) / 2);
    if (_idx >= CHUNK) flushChunk();
    return true;
  }
  bool stop() override { flushChunk(); return true; }
  void flushChunk() {
    if (_idx == 0) return;
    while (_spk->isPlaying(_ch) == 2) { vTaskDelay(1); }  // 队列满就稍等
    _spk->playRaw(_buf[_cur], _idx, hertz, false, 1, _ch);
    _cur = (_cur + 1) % 3;
    _idx = 0;
  }
private:
  static const size_t CHUNK = 640;
  m5::Speaker_Class* _spk;
  uint8_t _ch;
  size_t _idx, _cur;
  int16_t _buf[3][CHUNK];
};

// ── 全局 ─────────────────────────────────────────────
Avatar avatar;
long lastCmdId = 0;

AudioGeneratorMP3* mp3 = nullptr;
AudioFileSourcePROGMEM* mp3src = nullptr;
AudioOutputM5Speaker* mp3out = nullptr;
uint8_t* mp3buf = nullptr;
long speakingCmdId = 0;
unsigned long lastMouthAt = 0;

// ── HTTP 小工具 ───────────────────────────────────────
String httpGetText(const String& url, int timeoutMs) {
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.setTimeout(timeoutMs);
  if (!http.begin(client, url)) return "";
  int code = http.GET();
  String body = (code == 200) ? http.getString() : "";
  http.end();
  return body;
}

void httpPostJson(const String& url, const String& json) {
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.setTimeout(10000);
  if (!http.begin(client, url)) return;
  http.addHeader("Content-Type", "application/json");
  http.POST(json);
  http.end();
}

// 下载 mp3 到 PSRAM,成功返回长度,失败返回 0
size_t downloadToPsram(const String& url, uint8_t** out) {
  const size_t CAP = 1024 * 1024;  // 1MB 封顶,300 字的低码率语音绰绰有余
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.setTimeout(20000);
  if (!http.begin(client, url)) return 0;
  if (http.GET() != 200) { http.end(); return 0; }
  uint8_t* buf = (uint8_t*)heap_caps_malloc(CAP, MALLOC_CAP_SPIRAM);
  if (!buf) { http.end(); return 0; }
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
  if (total < 100) { free(buf); return 0; }
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

void startSpeak(long id, const String& text, const String& audioUrl) {
  if (audioUrl.length() == 0) {
    reportResult(id, false, "no audio url (TTS failed)");
    return;
  }
  size_t len = downloadToPsram(audioUrl, &mp3buf);
  if (len == 0) {
    reportResult(id, false, "audio download failed");
    return;
  }
  mp3src = new AudioFileSourcePROGMEM(mp3buf, len);
  mp3out = new AudioOutputM5Speaker(&M5.Speaker, 0);
  mp3 = new AudioGeneratorMP3();
  if (!mp3->begin(mp3src, mp3out)) {
    stopSpeak();
    reportResult(id, false, "mp3 decode failed");
    return;
  }
  speakingCmdId = id;
}

void stopSpeak() {
  if (mp3) { if (mp3->isRunning()) mp3->stop(); delete mp3; mp3 = nullptr; }
  if (mp3src) { delete mp3src; mp3src = nullptr; }
  if (mp3out) { delete mp3out; mp3out = nullptr; }
  if (mp3buf) { free(mp3buf); mp3buf = nullptr; }
  avatar.setMouthOpenRatio(0);
}

void handleCommand(JsonDocument& doc) {
  long id = doc["id"] | 0;
  String action = doc["action"] | "";
  lastCmdId = id;

  if (action == "speak") {
    startSpeak(id, doc["text"] | "", doc["audio"] | "");
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
  auto cfg = M5.config();
  M5StackChan.begin(cfg);
  M5.Speaker.setVolume(200);

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

  // 说话中: 全力喂解码器 + 让嘴动起来
  if (mp3 && mp3->isRunning()) {
    if (!mp3->loop()) {
      long id = speakingCmdId;
      stopSpeak();
      reportResult(id, true, "spoken");
    } else if (millis() - lastMouthAt > 120) {
      avatar.setMouthOpenRatio(random(3, 10) / 10.0f);
      lastMouthAt = millis();
    }
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
