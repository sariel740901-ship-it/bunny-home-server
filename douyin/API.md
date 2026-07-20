# MediaCrawlerPro API 接口文档

## 目录

- [抖音 (Douyin)](#抖音-douyin)

---

## 抖音 (Douyin)

### 基础信息

| 项目 | 值 |
|------|-----|
| API 基础 URL | `https://www.douyin.com` |
| 客户端类 | `DouYinApiClient` |
| 文件路径 | `media_platform/douyin/client.py` |

### 通用请求参数 (_common_params)

每个 GET/POST 请求都会**自动合并**以下通用参数：

| 参数名 | 类型 | 值 | 说明 |
|--------|------|-----|------|
| device_platform | str | `webapp` | 设备平台标识 |
| aid | str | `6383` | 应用ID |
| channel | str | `channel_pc_web` | 渠道标识 |
| publish_video_strategy_type | int | `2` | 视频发布策略类型 |
| update_version_code | int | `170400` | 更新版本代码 |
| pc_client_type | int | `1` | PC客户端类型 |
| version_code | int | `170400` | 版本代码 |
| version_name | str | `17.4.0` | 版本名称 |
| cookie_enabled | str | `true` | Cookie是否启用 |
| screen_width | int | `2560` | 屏幕宽度 |
| screen_height | int | `1440` | 屏幕高度 |
| browser_language | str | `zh-CN` | 浏览器语言 |
| browser_platform | str | `MacIntel` | 浏览器平台 |
| browser_name | str | `Chrome` | 浏览器名称 |
| browser_version | str | `135.0.0.0` | 浏览器版本 |
| browser_online | str | `true` | 浏览器在线状态 |
| engine_name | str | `Blink` | 渲染引擎名称 |
| engine_version | str | `135.0.0.0` | 渲染引擎版本 |
| os_name | str | `Mac+OS` | 操作系统名称 |
| os_version | str | `10.15.7` | 操作系统版本 |
| cpu_core_num | int | `8` | CPU核心数 |
| device_memory | int | `8` | 设备内存(GB) |
| platform | str | `PC` | 平台类型 |
| downlink | float | `4.45` | 下行速度(Mbps) |
| effective_type | str | `4g` | 有效网络类型 |
| round_trip_time | int | `100` | 往返时延(ms) |

### 验证参数 (_verify_params)

每个请求都会自动添加以下验证参数：

| 参数名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| webid | str | `common_verfiy_params.webid` | 网页ID，由TokenManager生成 |
| msToken | str | `common_verfiy_params.ms_token` | MS令牌，由TokenManager生成 |

---

### 验证参数生成算法

所有验证参数通过 `get_common_verify_params(user_agent)` 函数统一获取，包含 4 个关键参数的生成逻辑。

#### 1. msToken 生成 (TokenManager.get_msToken)

**生成策略**: 优先尝试生成真实 msToken，失败时降级为假 msToken

##### 方法 A: 真实 msToken (gen_real_msToken)

**请求接口**: `POST https://mssdk.bytedance.com/web/common`

**请求参数**:
```json
{
  "magic": 538969122,
  "version": 1,
  "dataType": 8,
  "strData": "<DOUYIN_MS_TOKEN_REQ_STR_DATA>",
  "tspFromClient": <current_timestamp_ms>,
  "url": 0
}
```

**请求头**:
```json
{
  "Content-Type": "application/json; charset=utf-8",
  "User-Agent": "<user_agent>"
}
```

**响应处理**:
- 从响应 Cookie 中提取 `msToken` 字段
- 验证长度：必须为 120 或 128 位
- 失败抛出异常：`获取msToken内容不符合要求`

**strData 常量**:
- 长度：约 12KB 的 Base64 编码字符串
- 来源：`DOUYIN_MS_TOKEN_REQ_STR_DATA` 常量
- 用途：客户端指纹特征数据

##### 方法 B: 假 msToken (gen_fake_msToken)

**算法**:
```python
ms_token = random_string(126) + "=="
```

**生成规则**:
- 126 位随机字符串（包含大小写字母和数字）
- 末尾添加 `==` 补齐到 128 位
- 格式示例：`abcdefghij...xyz123456789==`

**触发条件**: 真实 msToken 生成失败时自动降级

---

#### 2. webid 生成 (TokenManager.gen_webid)

**生成策略**: 优先请求服务器生成，失败时使用本地算法

##### 方法 A: 服务器生成 (推荐)

**请求接口**: `POST https://mcs.zijieapi.com/webid?aid=6383&sdk_version=5.1.18_zip&device_platform=web`

**请求参数**:
```json
{
  "app_id": 6383,
  "referer": "https://www.douyin.com/",
  "url": "https://www.douyin.com/",
  "user_agent": "<user_agent>",
  "user_unique_id": ""
}
```

**请求头**:
```json
{
  "User-Agent": "<user_agent>",
  "Content-Type": "application/json; charset=UTF-8",
  "Referer": "https://www.douyin.com/"
}
```

**响应处理**:
- 从响应 JSON 中提取 `web_id` 字段
- 失败抛出异常：`获取webid失败`

##### 方法 B: 本地算法生成 (get_web_id)

**算法实现**:
```python
def e(t):
    if t is not None:
        return str(t ^ (int(16 * random.random()) >> (t // 4)))
    else:
        # 生成模板: "10000000-1000-4000-8000-100000000000"
        return "".join([
            str(int(1e7)),   # 10000000
            "-",
            str(int(1e3)),   # 1000
            "-",
            str(int(4e3)),   # 4000
            "-",
            str(int(8e3)),   # 8000
            "-",
            str(int(1e11)),  # 100000000000
        ])

# 生成 UUID-like 字符串
template = e(None)  # "10000000-1000-4000-8000-100000000000"

# 将模板中的 '0', '1', '8' 替换为随机计算值
web_id_full = "".join(e(int(x)) if x in "018" else x for x in template)

# 移除连字符并截取前19位
web_id = web_id_full.replace("-", "")[:19]
```

**生成特点**:
- 基于 UUID v4 格式
- 使用 XOR 运算和随机数混合
- 最终输出 19 位数字字符串
- 格式示例：`1234567890123456789`

**触发条件**: 服务器请求失败时自动降级

---

#### 3. verifyFp 生成 (VerifyFpManager.gen_verify_fp)

**算法**: 时间戳 Base36 编码 + 随机 UUID

**详细步骤**:

##### 步骤 1: 生成 Base36 时间戳
```python
base_str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
milliseconds = int(round(time.time() * 1000))  # 当前毫秒时间戳
base36 = ""

# 将毫秒时间戳转换为 Base36 格式
while milliseconds > 0:
    remainder = milliseconds % 36
    if remainder < 10:
        base36 = str(remainder) + base36
    else:
        base36 = chr(ord("a") + remainder - 10) + base36
    milliseconds = int(milliseconds / 36)
```

**Base36 编码规则**:
- 字符集：0-9 (10个) + a-z (26个) = 36进制
- 示例：时间戳 `1704326400000` → Base36 `"lkm8abc0"`

##### 步骤 2: 生成 36 位随机 UUID
```python
o = [""] * 36
o[8] = o[13] = o[18] = o[23] = "_"  # 固定位置插入下划线
o[14] = "4"                          # UUID v4 版本号

for i in range(36):
    if not o[i]:
        n = int(random.random() * 62)  # 随机索引 0-61
        if i == 19:
            n = 3 & n | 8              # UUID 变体位：强制为 8-b
        o[i] = base_str[n]             # 从字符集随机选择

uuid_part = "".join(o)  # 例如: "a1b2c3d4_e5f6_4g7h_8i9j_k0l1m2n3o4p5"
```

**UUID 格式**:
- 长度：36 位
- 分隔符：第 8, 13, 18, 23 位为 `_`
- 第 14 位固定为 `4` (表示 UUID v4)
- 第 19 位：通过位运算确保符合 UUID 规范

##### 步骤 3: 拼接最终结果
```python
verify_fp = "verify_" + base36 + "_" + uuid_part
```

**格式示例**:
```
verify_lkm8abc0_a1b2c3d4_e5f6_4g7h_8i9j_k0l1m2n3o4p5
```

**结构说明**:
- 前缀：`verify_`
- 时间戳：Base36 编码（长度可变，通常 8-10 位）
- 分隔符：`_`
- UUID：36 位随机字符串

---

#### 4. s_v_web_id 生成 (VerifyFpManager.gen_s_v_web_id)

**算法**: 与 `verifyFp` 完全相同

```python
s_v_web_id = gen_verify_fp()
```

**说明**:
- 调用相同的 `gen_verify_fp()` 方法
- 格式和生成规则完全一致
- 通常与 `verifyFp` 值不同（因为随机性和时间差异）

---

### 验证参数生成流程图

```
调用 get_common_verify_params(user_agent)
    │
    ├─→ TokenManager.get_msToken()
    │       ├─→ 尝试 gen_real_msToken()  (POST → mssdk.bytedance.com)
    │       │       ├─ 成功 → 返回 120/128位真实token
    │       │       └─ 失败 ↓
    │       └─→ 降级 gen_fake_msToken()  (126位随机 + "==")
    │
    ├─→ TokenManager.gen_webid()
    │       ├─→ 尝试服务器生成  (POST → mcs.zijieapi.com)
    │       │       ├─ 成功 → 返回19位数字ID
    │       │       └─ 失败 ↓
    │       └─→ 降级本地算法  (UUID-like 19位)
    │
    ├─→ VerifyFpManager.gen_verify_fp()
    │       └─→ Base36时间戳 + UUID → verify_xxx_xxx
    │
    └─→ VerifyFpManager.gen_s_v_web_id()
            └─→ 调用 gen_verify_fp() (同上)
```

---

### 验证参数示例

**完整生成结果示例**:
```python
{
  "ms_token": "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKL==",
  "webid": "1234567890123456789",
  "verify_fp": "verify_lkm8abc0_a1b2c3d4_e5f6_4g7h_8i9j_k0l1m2n3o4p5",
  "s_v_web_id": "verify_lkm8abd1_f6g7h8i9_j0k1_4l2m_8n3o_p4q5r6s7t8u9"
}
```

**参数有效性**:
- **msToken**: 每次生成不同，有效期未知（建议定期更新）
- **webid**: 作为设备标识，建议在会话期间保持不变
- **verifyFp**: 每次生成不同（时间戳 + 随机），单次请求有效
- **s_v_web_id**: 每次生成不同，单次请求有效

---

### 签名服务 (Sign Service)

所有请求在发送前都需要通过**独立的签名服务**生成 `a_bogus` 参数（除 `/aweme/v1/web/general/search/single/` 接口外）。

#### 签名服务配置

| 配置项 | 默认值 | 环境变量 | 说明 |
|--------|--------|----------|------|
| 签名服务地址 | `localhost` | `SIGN_SRV_HOST` | 签名服务主机地址 |
| 签名服务端口 | `8989` | `SIGN_SRV_PORT` | 签名服务端口 |
| 签名接口路径 | `/signsrv/v1/douyin/sign` | - | 抖音签名接口路径 |

#### 签名请求参数 (DouyinSignRequest)

向签名服务发送 POST 请求时的参数：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| uri | str | 是 | 请求的URI路径（如：`/aweme/v1/web/aweme/detail/`） |
| query_params | str | 是 | URL编码后的完整查询参数字符串 |
| user_agent | str | 是 | 请求使用的User-Agent |
| cookies | str | 是 | 请求使用的Cookie字符串 |

**签名请求示例：**

```json
POST http://localhost:8989/signsrv/v1/douyin/sign
Content-Type: application/json

{
  "uri": "/aweme/v1/web/aweme/detail/",
  "query_params": "aweme_id=7123456789&device_platform=webapp&aid=6383&...",
  "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
  "cookies": "sessionid=xxx; ..."
}
```

#### 签名响应 (DouyinSignResponse)

| 字段 | 类型 | 说明 |
|------|------|------|
| biz_code | int | 业务状态码（0=成功） |
| msg | str | 响应消息 |
| isok | bool | 是否成功 |
| data | DouyinSignResult | 签名结果数据 |
| data.a_bogus | str | **生成的签名参数** |

**签名响应示例：**

```json
{
  "biz_code": 0,
  "msg": "OK!",
  "isok": true,
  "data": {
    "a_bogus": "0dB4M2ZwYDMifEhBbjhAbOjm8fVDY1uF4Nc/8R9Oz6H5cBdO"
  }
}
```

---

## 请求加密完整流程

本节详细说明抖音 API 请求从参数准备到最终发送的完整加密和处理流程。

### 加密参数概览

| 参数类型 | 参数名 | 生成方式 | 作用 | 是否必需 |
|---------|--------|---------|------|---------|
| 验证参数 | msToken | TokenManager 生成 | 客户端追踪令牌 | 是 |
| 验证参数 | webid | TokenManager 生成 | 设备唯一标识 | 是 |
| 验证参数 | verifyFp | VerifyFpManager 生成 | 浏览器指纹验证 | 部分接口 |
| 验证参数 | s_v_web_id | VerifyFpManager 生成 | Web 站点验证 ID | 否 |
| 签名参数 | a_bogus | 签名服务生成 | **核心反爬签名** | 大部分接口 |
| 通用参数 | 31个设备/浏览器参数 | 固定配置 | 设备指纹特征 | 是 |
| Cookie | sessionid 等 | 账号池提供 | 用户登录凭证 | 是 |

---

### 核心加密参数：a_bogus

#### 重要性等级：⭐⭐⭐⭐⭐ (最高)

`a_bogus` 是抖音 API 最核心的反爬虫签名参数，**没有正确的 a_bogus 签名，请求将被直接拒绝或返回空数据**。

#### 作用机制

| 项目 | 说明 |
|------|------|
| 签名对象 | URL 查询参数 + User-Agent + Cookie |
| 签名算法 | **专有加密算法**（需独立签名服务实现） |
| 签名长度 | 约 48-52 位字符串 |
| 有效期 | 单次请求有效（不可重复使用） |
| 验证位置 | 服务器端实时验证 |
| 错误后果 | 返回 `blocked` 或空响应 |

#### 签名生成过程

**步骤 1: 准备签名输入**
```python
# 合并所有查询参数
final_params = {
    **common_params,        # 通用参数 (31个)
    **verify_params,        # 验证参数 (webid, msToken)
    **specific_params       # 接口特定参数
}

# URL 编码所有参数
query_string = urllib.parse.urlencode(final_params)
# 例如: "device_platform=webapp&aid=6383&aweme_id=7123456789&..."
```

**步骤 2: 调用签名服务**
```python
sign_request = {
    "uri": "/aweme/v1/web/aweme/detail/",
    "query_params": query_string,
    "user_agent": "Mozilla/5.0 ...",
    "cookies": "sessionid=xxx; ..."
}

# POST 到签名服务
response = requests.post(
    "http://localhost:8989/signsrv/v1/douyin/sign",
    json=sign_request
)

a_bogus = response.json()["data"]["a_bogus"]
# 例如: "0dB4M2ZwYDMifEhBbjhAbOjm8fVDY1uF4Nc/8R9Oz6H5cBdO"
```

**步骤 3: 添加签名到最终请求**
```python
final_params["a_bogus"] = a_bogus

# 最终请求 URL
final_url = f"https://www.douyin.com{uri}?{urllib.parse.urlencode(final_params)}"
```

#### a_bogus 签名算法说明

**注意**: 抖音的 a_bogus 签名算法是**闭源专有算法**，本项目通过独立的签名服务 (MediaCrawlerPro-SignSrv) 实现。

**算法特点**:
- 高度混淆: 使用字节码混淆、反调试、动态代码生成
- 动态更新: 抖音定期更新算法，需要签名服务同步更新
- 多因子: 综合考虑 URI、参数顺序、时间戳、User-Agent、Cookie
- 精确匹配: 参数顺序、大小写、编码方式必须完全一致

---

#### a_bogus 加密实现 (JavaScript)

**加密文件**: `douyin.js`

**加密函数**: `get_abogus(query_params, post_data, user_agent)`

| 参数 | 类型 | 说明 |
|------|------|------|
| query_params | string | URL 编码后的查询参数字符串 |
| post_data | string | POST 请求体 (GET 请求传空字符串 `""`) |
| user_agent | string | 浏览器 User-Agent |

**返回值**: `string` - a_bogus 签名值

---

**签名验证流程**:
```
客户端 → 准备参数 → URL编码 → 调用签名服务
                                    ↓
                            签名服务 (execjs + douyin.js)
                            ├─ 解析参数
                            ├─ 执行 get_abogus() 函数
                            └─ 返回 a_bogus
                                    ↓
客户端 ← 添加签名 ← 构建最终请求 ← 获取签名
```

---

### URL 参数编码规则

#### 标准 URL 编码 (urllib.parse.urlencode)

所有查询参数在签名前必须进行标准 URL 编码。

**编码规则**:
```python
# Python 标准库实现
urllib.parse.urlencode(params)
```

**编码对照表**:
| 原始字符 | 编码后 | 说明 |
|---------|--------|------|
| 空格 | `%20` | 空格编码为 %20（不是 +） |
| `+` | `%2B` | 加号编码 |
| `=` | `%3D` | 等号编码（键值分隔符不编码） |
| `&` | `%26` | 与号编码（参数分隔符不编码） |
| `/` | `%2F` | 斜杠编码 |
| `:` | `%3A` | 冒号编码 |
| `{` | `%7B` | 左花括号编码 |
| `}` | `%7D` | 右花括号编码 |
| `"` | `%22` | 双引号编码 |
| 中文 | UTF-8编码 | 例如: "美食" → `%E7%BE%8E%E9%A3%9F` |

**编码示例**:
```python
# 原始参数
params = {
    "keyword": "美食",
    "filter_selected": '{"sort_type":"1","publish_time":"7"}',
    "offset": 0
}

# 编码后
# keyword=%E7%BE%8E%E9%A3%9F&filter_selected=%7B%22sort_type%22%3A%221%22%2C%22publish_time%22%3A%227%22%7D&offset=0
```

#### Referer URL 编码 (urllib.parse.quote)

评论接口的 Referer 头使用特殊编码规则，保留 `:` 和 `/` 不编码。

**编码规则**:
```python
# 保留 : 和 / 符号
urllib.parse.quote(referer_url, safe=":/")
```

**对比示例**:
```python
original = "https://www.douyin.com/search/美食?aid=xxx&type=general"

# 标准编码（全部编码）
standard = "https%3A%2F%2Fwww.douyin.com%2Fsearch%2F%E7%BE%8E%E9%A3%9F%3Faid%3Dxxx%26type%3Dgeneral"

# Referer 编码（保留 :/ ）
referer = "https://www.douyin.com/search/%E7%BE%8E%E9%A3%9F?aid=xxx&type=general"
```

---

### Cookie 认证机制

#### Cookie 的作用

| 用途 | 说明 |
|------|------|
| 用户认证 | 标识登录用户身份（sessionid） |
| 会话保持 | 维持用户登录状态 |
| 签名输入 | 作为 a_bogus 签名的输入之一 |
| 权限控制 | 某些接口需要登录才能访问 |

#### 关键 Cookie 字段

| Cookie 名称 | 作用 | 示例值 | 必需 |
|------------|------|--------|------|
| sessionid | 会话ID | `abc123def456...` | 是 |
| sessionid_ss | 会话ID（安全） | `abc123def456...` | 是 |
| ttwid | 设备ID | `1%7Cxxx...` | 是 |
| msToken | MS追踪令牌 | `xxx...==` | 否（查询参数优先） |
| __ac_nonce | 随机数（防重放） | `0123456789abc` | 否 |

#### Cookie 获取方式

**方式 1: 浏览器手动提取（推荐）**
```bash
1. 打开浏览器，访问 https://www.douyin.com
2. 登录账号
3. 按 F12 打开开发者工具
4. Application → Cookies → https://www.douyin.com
5. 复制所有 Cookie，格式化为字符串
```

**方式 2: 账号池自动管理**
```python
# 从配置文件或数据库读取
cookies = account_pool.get_account().cookies
# 格式: "sessionid=xxx; ttwid=yyy; ..."
```

#### Cookie 在请求中的使用

**请求头注入**:
```python
headers = {
    "Cookie": "sessionid=xxx; sessionid_ss=xxx; ttwid=xxx; ...",
    "User-Agent": "Mozilla/5.0 ...",
    # ...其他请求头
}
```

**签名服务输入**:
```python
# Cookie 作为签名输入的一部分
sign_request = {
    "uri": "/aweme/v1/web/aweme/detail/",
    "query_params": "...",
    "user_agent": "...",
    "cookies": "sessionid=xxx; ..."  # ← Cookie 参与签名计算
}
```

---

### 完整请求加密流程

以 `get_video_by_id(aweme_id="7123456789")` 为例，展示从调用到响应的完整流程。

#### 阶段 1: 参数准备

```python
# 1.1 接口特定参数
specific_params = {
    "aweme_id": "7123456789",
    "verifyFp": "verify_lkm8abc0_...",
    "fp": "verify_lkm8abc0_..."
}

# 1.2 合并通用参数
params = {**common_params, **specific_params}
# 现在包含 33+ 个参数

# 1.3 合并验证参数
params.update({
    "webid": "1234567890123456789",
    "msToken": "abcd...=="
})
# 现在包含 35+ 个参数
```

#### 阶段 2: 参数编码

```python
# 2.1 URL 编码所有参数
query_string = urllib.parse.urlencode(params)
# 结果: "device_platform=webapp&aid=6383&aweme_id=7123456789&..."
```

#### 阶段 3: 签名生成

```python
# 3.1 构建签名请求
sign_request = {
    "uri": "/aweme/v1/web/aweme/detail/",
    "query_params": query_string,
    "user_agent": "Mozilla/5.0 (Macintosh; ...) Chrome/135.0.0.0 ...",
    "cookies": "sessionid=xxx; ttwid=yyy; ..."
}

# 3.2 调用签名服务
response = httpx.post(
    "http://localhost:8989/signsrv/v1/douyin/sign",
    json=sign_request,
    timeout=60
)

# 3.3 提取签名
a_bogus = response.json()["data"]["a_bogus"]
# 例如: "0dB4M2ZwYDMifEhBbjhAbOjm8fVDY1uF4Nc/8R9Oz6H5cBdO"
```

#### 阶段 4: 构建最终请求

```python
# 4.1 添加签名到参数
params["a_bogus"] = a_bogus

# 4.2 构建最终 URL
final_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?{urllib.parse.urlencode(params)}"

# 4.3 准备请求头
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "accept-language": "zh-CN,zh;q=0.9",
    "Cookie": "sessionid=xxx; ttwid=yyy; ...",
    "origin": "https://www.douyin.com",
    "referer": "https://www.douyin.com/user/self",
    "user-agent": "Mozilla/5.0 ..."
}

# 4.4 配置代理（如果启用）
proxies = {
    "http://": "http://username:password@proxy.com:8080",
    "https://": "http://username:password@proxy.com:8080"
}
```

#### 阶段 5: 发送请求

```python
# 5.1 发送 GET 请求
response = httpx.get(
    url=final_url,
    headers=headers,
    proxies=proxies,
    timeout=10
)

# 5.2 解析响应
if response.text == "" or response.text == "blocked":
    raise DataFetchError("请求被阻止或返回空响应")

data = response.json()

# 5.3 提取视频信息
aweme_detail = data.get("aweme_detail", {})
video = DouyinAweme(**aweme_detail)
```

---

### 加密流程完整示意图

```
┌─────────────────────────────────────────────────────────────┐
│  调用接口: get_video_by_id("7123456789")                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
         ┌────────────────▼────────────────┐
         │   1. 参数准备 (Parameter Prep)    │
         │  ├─ 接口特定参数 (aweme_id, fp) │
         │  ├─ 通用参数 (31个设备参数)      │
         │  └─ 验证参数 (webid, msToken)   │
         └────────────────┬────────────────┘
                          │
         ┌────────────────▼────────────────┐
         │   2. 参数编码 (URL Encoding)      │
         │  └─ urlencode(params)           │
         │     → query_string              │
         └────────────────┬────────────────┘
                          │
         ┌────────────────▼────────────────┐
         │   3. 签名生成 (a_bogus Signing)   │
         │  ├─ 输入: URI + query + UA + Cookie │
         │  ├─ POST → 签名服务 (8989端口)   │
         │  └─ 输出: a_bogus 签名参数       │
         └────────────────┬────────────────┘
                          │
         ┌────────────────▼────────────────┐
         │   4. 请求构建 (Request Building)   │
         │  ├─ params["a_bogus"] = 签名     │
         │  ├─ 构建完整 URL                │
         │  ├─ 准备请求头 (Headers + Cookie)│
         │  └─ 配置代理 (Proxy)             │
         └────────────────┬────────────────┘
                          │
         ┌────────────────▼────────────────┐
         │   5. 发送请求 (HTTP Request)      │
         │  └─ GET https://www.douyin.com  │
         │     + 完整参数 + 签名 + Cookie   │
         └────────────────┬────────────────┘
                          │
         ┌────────────────▼────────────────┐
         │   6. 响应处理 (Response Handling) │
         │  ├─ 检查空响应/blocked           │
         │  ├─ JSON 解析                   │
         │  └─ 提取数据模型                │
         └────────────────┬────────────────┘
                          │
         ┌────────────────▼────────────────┐
         │   7. 返回结果 (Return)            │
         │  └─ DouyinAweme 对象             │
         └─────────────────────────────────┘
```

---

### 各接口加密参数对照表

| 接口 | a_bogus | verifyFp | fp | webid | msToken | 特殊处理 |
|------|---------|----------|----|----|---------|----------|
| 登录检查 | ✅ | ❌ | ❌ | ✅ | ✅ | - |
| 关键字搜索 | ❌ | ❌ | ❌ | ✅ | ✅ | **不需要签名** |
| 视频详情 | ✅ | ✅ | ✅ | ✅ | ✅ | 移除 Origin 头 |
| 评论列表 | ✅ | ✅ | ✅ | ✅ | ✅ | Referer 特殊编码 |
| 子评论 | ✅ | ✅ | ✅ | ✅ | ✅ | Referer 特殊编码 |
| 用户信息 | ✅ | ✅ | ✅ | ✅ | ✅ | - |
| 用户作品 | ✅ | ✅ | ✅ | ✅ | ✅ | - |
| 推荐流 | ❌ | ❌ | ❌ | ❌ | ❌ | **完全不签名** (POST) |

**图例**:
- ✅ 需要该参数
- ❌ 不需要该参数

---

### 加密参数失效处理

#### 常见失效场景

| 场景 | 错误表现 | 解决方案 |
|------|---------|---------|
| Cookie 过期 | `status_code: 8, status_msg: "用户未登录"` | 重新登录获取新 Cookie |
| a_bogus 错误 | 返回空响应或 `"blocked"` | 检查签名服务是否正常运行 |
| msToken 无效 | 某些接口返回错误 | 重新生成 msToken |
| IP 被封禁 | 所有请求返回 403/blocked | 更换 IP 代理 |
| 签名服务离线 | 连接超时异常 | 启动签名服务 |
| User-Agent 不匹配 | 签名验证失败 | 确保 UA 与签名时一致 |

#### 自动重试机制

```python
# 内置重试策略
@retry(stop=stop_after_attempt(5), wait=wait_fixed(1))
async def request(method, url, **kwargs):
    # 1. 检查 IP 是否过期
    await check_ip_expired()

    # 2. 发送请求
    response = await httpx.request(method, url, **kwargs)

    # 3. 验证响应
    if response.text in ["", "blocked"]:
        raise DataFetchError("请求被阻止")

    return response.json()

# 重试失败后的降级策略
try:
    result = await request(...)
except RetryError:
    # 更换账号和 IP
    await update_account_info()
    # 重新生成所有验证参数
    # 再次尝试请求
```

---

### 安全注意事项

⚠️ **重要提示**:

1. **Cookie 安全**:
   - Cookie 包含登录凭证，**切勿泄露或公开**
   - 定期轮换账号，避免单账号频繁使用
   - 使用账号池管理，自动标记失效账号

2. **签名服务安全**:
   - 签名服务应**部署在内网**或受保护的环境
   - 不要将签名服务暴露到公网
   - 定期更新签名算法以应对平台更新

3. **请求频率控制**:
   - 使用 `MAX_CONCURRENCY_NUM` 限制并发数
   - 添加随机延迟避免规律性请求
   - 启用 IP 代理池分散请求来源

4. **参数顺序**:
   - 某些接口对参数顺序敏感
   - 使用 `urllib.parse.urlencode` 确保编码一致性
   - 不要手动拼接查询字符串

5. **User-Agent 一致性**:
   - 同一会话中 UA 必须保持不变
   - UA 必须与签名时使用的完全一致
   - 推荐使用 `DOUYIN_FIXED_USER_AGENT` 常量

---

### 调试加密问题

#### 调试步骤

**步骤 1: 检查签名服务**
```bash
# 测试签名服务是否正常
curl http://localhost:8989/signsrv/pong

# 预期响应: {"message": "pong"}
```

**步骤 2: 验证参数编码**
```python
# 打印编码后的查询字符串
print(urllib.parse.urlencode(params))

# 检查特殊字符是否正确编码
# 检查中文是否正确转换为 UTF-8
```

**步骤 3: 测试签名生成**
```python
# 独立测试签名服务
async def test_sign():
    response = await httpx.post(
        "http://localhost:8989/signsrv/v1/douyin/sign",
        json={
            "uri": "/aweme/v1/web/aweme/detail/",
            "query_params": "aweme_id=123&...",
            "user_agent": "Mozilla/5.0 ...",
            "cookies": "sessionid=xxx"
        }
    )
    print(response.json())
```

**步骤 4: 检查请求日志**
```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看完整请求 URL 和响应
utils.logger.info(f"Final URL: {final_url}")
utils.logger.info(f"Response: {response.text[:500]}")
```

**步骤 5: 对比浏览器请求**
```bash
# 使用浏览器开发者工具
1. F12 → Network → XHR/Fetch
2. 找到相同的 API 请求
3. 复制 Request URL 和 Headers
4. 对比参数顺序、编码、签名值
```

---

### 加密性能优化

| 优化项 | 建议 | 效果 |
|--------|------|------|
| 验证参数缓存 | 复用 msToken、webid（会话期间） | 减少 90% 生成时间 |
| 签名服务连接池 | 使用 HTTP 连接池 | 减少 30% 网络开销 |
| 批量签名 | 一次请求签名多个接口 | 减少 50% 签名服务调用 |
| 本地签名缓存 | 缓存相同参数的签名（谨慎使用） | 减少 80% 签名请求 |
| 异步并发 | 使用 asyncio 并发生成参数 | 提升 3-5 倍吞吐量 |

**注意**: 签名缓存需谨慎，`a_bogus` 通常为单次有效，缓存可能导致请求失败。

---

### 请求头 (Headers)

所有请求都会携带以下请求头：

| 请求头名称 | 值 | 说明 |
|-----------|-----|------|
| Content-Type | `application/json` | 内容类型（GET请求） |
| Content-Type | `application/x-www-form-urlencoded; charset=UTF-8` | 内容类型（POST请求） |
| Accept | `application/json` | 接受的响应类型 |
| accept-language | `zh-CN,zh;q=0.9` | 接受的语言 |
| Cookie | `<from_account_pool>` | 账号池中的Cookie |
| origin | `https://www.douyin.com` | 请求来源 |
| referer | `https://www.douyin.com/user/self` | 引用页面（GET请求） |
| referer | `https://www.douyin.com/discover` | 引用页面（POST请求） |
| user-agent | `<DOUYIN_FIXED_USER_AGENT>` | 固定的User-Agent |
| X-Secsdk-Csrf-Token | `DOWNGRADE` | CSRF令牌（仅POST请求） |

**固定User-Agent:**
```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36
```

---

### 接口列表

#### 1. 检查登录状态

| 属性 | 值 |
|------|-----|
| 方法名 | `check_login_status_via_user_self()` |
| 请求方式 | GET |
| URL | `https://www.douyin.com/aweme/v1/web/history/read/` |
| 需要签名 | 是 |

**接口特定参数 (Query)**

> **注意**: 实际请求会自动合并 [通用参数](#通用请求参数-_common_params) + [验证参数](#验证参数-_verify_params) + `a_bogus` 签名参数 + 以下特定参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| max_cursor | int | 否 | 0 | 分页游标 |
| count | int | 否 | 20 | 每页数量 |

**响应示例**

```json
// 已登录
{
    "status_code": 0,
    "status_msg": "",
    "aweme_list": [...]
}

// 未登录
{
    "status_code": 8,
    "status_msg": "用户未登录"
}
```

**返回值**: `bool` - True 表示已登录，False 表示未登录

---

#### 2. 关键字搜索

| 属性 | 值 |
|------|-----|
| 方法名 | `search_info_by_keyword()` |
| 请求方式 | GET |
| URL | `https://www.douyin.com/aweme/v1/web/general/search/single/` |
| 需要签名 | **否**（特例：此接口不添加 a_bogus 参数） |

**接口特定参数 (Query)**

> **注意**: 实际请求会自动合并 [通用参数](#通用请求参数-_common_params) + [验证参数](#验证参数-_verify_params) + 以下特定参数（无需 a_bogus）

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| keyword | str | 是 | - | 搜索关键字 |
| offset | int | 否 | 0 | 分页偏移量 |
| search_channel | SearchChannelType | 否 | `aweme_general` | 搜索渠道 |
| sort_type | SearchSortType | 否 | 0 | 排序类型 |
| publish_time | PublishTimeType | 否 | 0 | 发布时间范围 |
| search_id | str | 否 | "" | 搜索会话ID |
| count | str | 否 | "10" | 每页数量 |
| enable_history | str | 否 | "1" | 启用历史记录 |
| search_source | str | 否 | "tab_search" | 搜索来源 |
| query_correct_type | str | 否 | "1" | 查询纠正类型 |
| is_filter_search | str/int | 否 | "0" | 是否筛选搜索 |
| from_group_id | str | 否 | "7378810571505847586" | 来源组ID |
| need_filter_settings | str | 否 | "1" | 需要筛选设置 |
| list_type | str | 否 | "multi" | 列表类型 |
| filter_selected | str | 条件 | - | 当sort_type或publish_time非默认值时，为JSON字符串 |

**filter_selected 参数格式** (当 `sort_type != 0` 或 `publish_time != 0` 时):
```json
{
  "sort_type": "1",
  "publish_time": "7"
}
```

**搜索渠道枚举 (SearchChannelType)**

| 枚举值 | 值 | 说明 |
|--------|-----|------|
| GENERAL | `aweme_general` | 综合搜索 |
| VIDEO | `aweme_video_web` | 视频搜索 |
| USER | `aweme_user_web` | 用户搜索 |
| LIVE | `aweme_live` | 直播搜索 |

**排序类型枚举 (SearchSortType)**

| 枚举值 | 值 | 说明 |
|--------|-----|------|
| GENERAL | 0 | 综合排序 |
| MOST_LIKE | 1 | 最多点赞 |
| LATEST | 2 | 最新发布 |

**发布时间枚举 (PublishTimeType)**

| 枚举值 | 值 | 说明 |
|--------|-----|------|
| UNLIMITED | 0 | 不限时间 |
| ONE_DAY | 1 | 一天内 |
| ONE_WEEK | 7 | 一周内 |
| SIX_MONTH | 180 | 半年内 |

**返回值**: `Dict` - API 原始响应，包含搜索结果列表

---

#### 3. 获取视频详情

| 属性 | 值 |
|------|-----|
| 方法名 | `get_video_by_id()` |
| 请求方式 | GET |
| URL | `https://www.douyin.com/aweme/v1/web/aweme/detail/` |
| 需要签名 | 是 |
| 特殊说明 | 请求头中会移除 `Origin` 字段 |

**接口特定参数 (Query)**

> **注意**: 实际请求会自动合并 [通用参数](#通用请求参数-_common_params) + [验证参数](#验证参数-_verify_params) + `a_bogus` 签名参数 + 以下特定参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| aweme_id | str | 是 | - | 视频ID |
| verifyFp | str | 是 | - | 验证指纹（来自 common_verfiy_params） |
| fp | str | 是 | - | 设备指纹（同 verifyFp） |

**返回值**: `Optional[DouyinAweme]`

**DouyinAweme 数据结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| aweme_id | str | 视频ID |
| aweme_type | str | 视频类型 |
| title | str | 视频标题 |
| desc | str | 视频描述 |
| create_time | str | 发布时间戳 |
| liked_count | str | 点赞数 |
| comment_count | str | 评论数 |
| share_count | str | 分享数 |
| collected_count | str | 收藏数 |
| aweme_url | str | 视频URL |
| cover_url | str | 封面图URL |
| video_download_url | str | 下载链接 |
| source_keyword | str | 搜索来源关键字 |
| is_ai_generated | int | 是否AI生成 (0=否) |
| user_id | str | 用户ID |
| sec_uid | str | 用户安全ID |
| short_user_id | str | 短用户ID |
| user_unique_id | str | 唯一ID |
| nickname | str | 昵称 |
| avatar | str | 头像URL |
| user_signature | str | 签名 |
| ip_location | str | IP地址 |

---

#### 4. 获取视频评论列表

| 属性 | 值 |
|------|-----|
| 方法名 | `get_aweme_comments()` |
| 请求方式 | GET |
| URL | `https://www.douyin.com/aweme/v1/web/comment/list/` |
| 需要签名 | 是 |
| 特殊说明 | Referer 会动态设置为搜索关键字页面 |

**接口特定参数 (Query)**

> **注意**: 实际请求会自动合并 [通用参数](#通用请求参数-_common_params) + [验证参数](#验证参数-_verify_params) + `a_bogus` 签名参数 + 以下特定参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| aweme_id | str | 是 | - | 视频ID |
| cursor | int | 否 | 0 | 分页游标 |
| count | int | 否 | 20 | 每页数量 |
| item_type | int | 否 | 0 | 项目类型 |
| verifyFp | str | 是 | - | 验证指纹（来自 common_verfiy_params） |
| fp | str | 是 | - | 设备指纹（同 verifyFp） |

**特殊请求头：**

| 请求头 | 值示例 | 说明 |
|--------|--------|------|
| Referer | `https://www.douyin.com/search/<keyword>?aid=...&publish_time=0&sort_type=0&source=search_history&type=general` | URL编码后的搜索页面地址 |

**返回值**: `Tuple[List[DouyinAwemeComment], Dict]`
- 第一个元素: 评论列表
- 第二个元素: 元数据 (包含 cursor, has_more 等)

**DouyinAwemeComment 数据结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| comment_id | str | 评论ID |
| aweme_id | str | 视频ID |
| content | str | 评论内容 |
| create_time | str | 评论时间 |
| sub_comment_count | str | 回复数 |
| parent_comment_id | str | 父评论ID |
| reply_to_reply_id | str | 目标评论ID |
| like_count | str | 点赞数 |
| pictures | str | 评论图片 (逗号分隔URL) |
| ip_location | str | IP地址 |
| user_id | str | 用户ID |
| sec_uid | str | 用户安全ID |
| short_user_id | str | 短用户ID |
| user_unique_id | str | 唯一ID |
| nickname | str | 昵称 |
| avatar | str | 头像URL |
| user_signature | str | 签名 |

---

#### 5. 获取子评论 (回复)

| 属性 | 值 |
|------|-----|
| 方法名 | `get_sub_comments()` |
| 请求方式 | GET |
| URL | `https://www.douyin.com/aweme/v1/web/comment/list/reply/` |
| 需要签名 | 是 |
| 特殊说明 | Referer 会动态设置为搜索关键字页面 |

**接口特定参数 (Query)**

> **注意**: 实际请求会自动合并 [通用参数](#通用请求参数-_common_params) + [验证参数](#验证参数-_verify_params) + `a_bogus` 签名参数 + 以下特定参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| comment_id | str | 是 | - | 父评论ID |
| cursor | int | 否 | 0 | 分页游标 |
| count | int | 否 | 20 | 每页数量 |
| item_type | int | 否 | 0 | 项目类型 |
| verifyFp | str | 是 | - | 验证指纹（来自 common_verfiy_params） |
| fp | str | 是 | - | 设备指纹（同 verifyFp） |

**特殊请求头：**

| 请求头 | 值示例 | 说明 |
|--------|--------|------|
| Referer | `https://www.douyin.com/search/<keyword>?aid=...&publish_time=0&sort_type=0&source=search_history&type=general` | URL编码后的搜索页面地址 |

**返回值**: `Tuple[List[DouyinAwemeComment], Dict]`
- 数据结构同 `get_aweme_comments()`

---

#### 6. 获取用户信息

| 属性 | 值 |
|------|-----|
| 方法名 | `get_user_info()` |
| 请求方式 | GET |
| URL | `https://www.douyin.com/aweme/v1/web/user/profile/other/` |
| 需要签名 | 是 |

**接口特定参数 (Query)**

> **注意**: 实际请求会自动合并 [通用参数](#通用请求参数-_common_params) + [验证参数](#验证参数-_verify_params) + `a_bogus` 签名参数 + 以下特定参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| sec_user_id | str | 是 | - | 用户安全ID |
| publish_video_strategy_type | int | 否 | 2 | 视频策略类型 |
| personal_center_strategy | int | 否 | 1 | 个人中心策略 |
| verifyFp | str | 是 | - | 验证指纹（来自 common_verfiy_params） |
| fp | str | 是 | - | 设备指纹（同 verifyFp） |

**返回值**: `Optional[DouyinCreator]`

**DouyinCreator 数据结构**

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | str | 用户ID |
| nickname | str | 昵称 |
| avatar | str | 头像URL |
| ip_location | str | IP地址 |
| desc | str | 签名/描述 |
| gender | str | 性别 ("男"/"女"/"未知") |
| follows | str | 关注数 |
| fans | str | 粉丝数 |
| interaction | str | 获赞总数 |
| videos_count | str | 作品数 |

---

#### 7. 获取用户作品列表

| 属性 | 值 |
|------|-----|
| 方法名 | `get_user_aweme_posts()` |
| 请求方式 | GET |
| URL | `https://www.douyin.com/aweme/v1/web/aweme/post/` |
| 需要签名 | 是 |

**接口特定参数 (Query)**

> **注意**: 实际请求会自动合并 [通用参数](#通用请求参数-_common_params) + [验证参数](#验证参数-_verify_params) + `a_bogus` 签名参数 + 以下特定参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| sec_user_id | str | 是 | - | 用户安全ID |
| count | int | 否 | 18 | 每页视频数 |
| max_cursor | str | 否 | "0" | 分页游标 |
| locate_query | str | 否 | "false" | 位置查询 |
| publish_video_strategy_type | int | 否 | 2 | 视频策略类型 |
| verifyFp | str | 是 | - | 验证指纹（来自 common_verfiy_params） |
| fp | str | 是 | - | 设备指纹（同 verifyFp） |

**返回值**: `Dict` - API 原始响应，包含用户视频列表及分页信息

---

#### 8. 获取首页推荐视频

| 属性 | 值 |
|------|-----|
| 方法名 | `get_homefeed_aweme_list()` |
| 请求方式 | POST |
| URL | `https://www.douyin.com/aweme/v1/web/module/feed/` |
| 需要签名 | **否** (need_sign=False) |
| 特殊说明 | 不使用签名服务，不添加 a_bogus 参数 |

**完整请求参数 (Query)**

> **注意**: 此接口**不合并**通用参数和验证参数，直接使用以下完整参数列表

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| device_platform | str | 是 | `webapp` | 设备平台 |
| aid | str | 是 | `6383` | 应用ID |
| channel | str | 是 | `channel_pc_web` | 渠道标识 |
| module_id | str | 是 | `3003101` | 模块ID |
| count | int | 否 | 20 | 返回视频数量 |
| filterGids | str | 否 | `""` | 过滤GID |
| presented_ids | str | 否 | `""` | 已展示ID列表 |
| refresh_index | int | 否 | 0 | 刷新索引 |
| refer_id | str | 否 | `""` | 引用ID |
| refer_type | str | 否 | `10` | 引用类型 |
| awemePcRecRawData | str | 是 | `{"is_xigua_user":0,"is_client":false}` | 推荐原始数据 |
| Seo-Flag | str | 否 | `0` | SEO标志 |
| install_time | str | 否 | `1749390216` | 安装时间戳 |
| tag_id | int | 是 | - | **内容分类标签ID** |
| use_lite_type | str | 否 | `0` | 轻量版类型 |
| xigua_user | str | 否 | `0` | 西瓜用户 |
| pc_client_type | str | 是 | `1` | PC客户端类型 |
| pc_libra_divert | str | 否 | `Mac` | PC分流 |
| update_version_code | str | 是 | `170400` | 更新版本代码 |
| support_h265 | str | 否 | `1` | 支持H265 |
| support_dash | str | 否 | `1` | 支持DASH |
| version_code | str | 是 | `170400` | 版本代码 |
| version_name | str | 是 | `17.4.0` | 版本名称 |
| cookie_enabled | str | 是 | `true` | Cookie启用状态 |
| screen_width | str | 是 | `2560` | 屏幕宽度 |
| screen_height | str | 是 | `1440` | 屏幕高度 |
| browser_language | str | 是 | `en` | 浏览器语言 |
| browser_platform | str | 是 | `MacIntel` | 浏览器平台 |
| browser_name | str | 是 | `Chrome` | 浏览器名称 |
| browser_version | str | 是 | `135.0.0.0` | 浏览器版本 |
| browser_online | str | 是 | `true` | 浏览器在线状态 |
| engine_name | str | 是 | `Blink` | 渲染引擎名称 |
| engine_version | str | 是 | `135.0.0.0` | 渲染引擎版本 |
| os_name | str | 是 | `Mac OS` | 操作系统名称 |
| os_version | str | 是 | `10.15.7` | 操作系统版本 |
| cpu_core_num | str | 是 | `10` | CPU核心数 |
| device_memory | str | 是 | `8` | 设备内存(GB) |
| platform | str | 是 | `PC` | 平台类型 |
| downlink | str | 是 | `10` | 下行速度(Mbps) |
| effective_type | str | 是 | `4g` | 有效网络类型 |
| round_trip_time | str | 是 | `100` | 往返时延(ms) |

**推荐标签枚举 (HomeFeedTagIdType)**

| 枚举值 | 值 | 说明 |
|--------|-----|------|
| ALL | 0 | 全部 |
| KNOWLEDGE | 300213 | 知识 |
| SPORTS | 300207 | 体育 |
| AUTO | 300218 | 汽车 |
| ANIME | 300206 | 二次元 |
| GAME | 300205 | 游戏 |
| MOVIE | 300215 | 影视 |
| LIFE_VLOG | 300216 | 生活vlog |
| TRAVEL | 300221 | 旅行 |
| MINI_DRAMA | 300214 | 小剧场 |
| FOOD | 300204 | 美食 |
| AGRICULTURE | 300219 | 三农 |
| MUSIC | 300209 | 音乐 |
| ANIMAL | 300220 | 动物 |
| PARENTING | 300217 | 亲子 |
| FASHION | 300222 | 美妆穿搭 |

**返回值**: `Dict` - API 原始响应，包含推荐视频列表

---

### 接口总览表

| 接口 | 方法名 | 请求方式 | URL | 返回类型 |
|------|--------|---------|-----|----------|
| 登录检查 | `check_login_status_via_user_self()` | GET | `https://www.douyin.com/aweme/v1/web/history/read/` | `bool` |
| 关键字搜索 | `search_info_by_keyword()` | GET | `https://www.douyin.com/aweme/v1/web/general/search/single/` | `Dict` |
| 视频详情 | `get_video_by_id()` | GET | `https://www.douyin.com/aweme/v1/web/aweme/detail/` | `Optional[DouyinAweme]` |
| 评论列表 | `get_aweme_comments()` | GET | `https://www.douyin.com/aweme/v1/web/comment/list/` | `Tuple[List, Dict]` |
| 子评论 | `get_sub_comments()` | GET | `https://www.douyin.com/aweme/v1/web/comment/list/reply/` | `Tuple[List, Dict]` |
| 用户信息 | `get_user_info()` | GET | `https://www.douyin.com/aweme/v1/web/user/profile/other/` | `Optional[DouyinCreator]` |
| 用户作品 | `get_user_aweme_posts()` | GET | `https://www.douyin.com/aweme/v1/web/aweme/post/` | `Dict` |
| 推荐流 | `get_homefeed_aweme_list()` | POST | `https://www.douyin.com/aweme/v1/web/module/feed/` | `Dict` |

---

### 异常类型

| 异常类 | 说明 | 触发场景 |
|--------|------|----------|
| `DataFetchError` | 数据获取失败 | 返回空响应、blocked响应、JSON解析异常 |
| `IPBlockError` | IP被阻止 | 请求过于频繁导致IP被临时封禁 |

---

### 使用示例

#### 搜索并获取视频详情

```python
from media_platform.douyin.client import DouYinApiClient

async def example():
    client = DouYinApiClient()
    await client.async_initialize()

    # 搜索关键字
    search_result = await client.search_info_by_keyword(
        keyword="美食",
        offset=0,
        sort_type=SearchSortType.MOST_LIKE
    )

    # 获取视频详情
    aweme_id = search_result["data"][0]["aweme_info"]["aweme_id"]
    video = await client.get_video_by_id(aweme_id)

    # 获取评论
    comments, meta = await client.get_aweme_comments(aweme_id, cursor=0)
```

#### 获取创作者信息和作品

```python
async def get_creator_content():
    client = DouYinApiClient()
    await client.async_initialize()

    # 获取用户信息
    creator = await client.get_user_info(sec_user_id="MS4wLjABAAAA...")

    # 获取用户作品列表
    posts = await client.get_user_aweme_posts(
        sec_user_id="MS4wLjABAAAA...",
        max_cursor="0"
    )
```
