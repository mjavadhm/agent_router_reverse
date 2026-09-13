# AgentRouter Reverse Proxy (OpenAI -> Cline Spoofing)

یک ریورس پروکسی سریع و بهینه‌سازی‌شده برای وب‌سرویس [AgentRouter](https://agentrouter.org).

این پروکسی به شما اجازه می‌دهد از هر نرم‌افزار، کلاینت یا افزونه سازگار با استاندارد OpenAI (مثل **Cursor**، **Continue**، کتابخانه پایتون **`openai`**، **Open-WebUI**، و cURL) به مدل‌های AgentRouter متصل شوید؛ بدون آنکه با خطای `unauthorized client detected` مواجه شوید.

---

## نحوه کارکرد

سرویس AgentRouter تنها به کلاینت‌های مجاز (مانند Cline) پاسخ می‌دهد و هدرهای زیر را بررسی می‌کند:
- `User-Agent: Cline/4.1.17`
- `X-Stainless-Lang: js`
- `X-Stainless-Runtime: node`

این ریورس پروکسی درخواست‌های استاندارد OpenAI را دریافت کرده، به صورت خودکار هدرهای فوق را تزریق می‌کند و پاسخ (استریم SSE یا عادی) را بدون بافرینگ و با سرعت لحظه‌ای به کلاینت بازمی‌گرداند.

> **نکته امنیتی در مورد کلید API:** هیچ کلید پیش‌فرضی روی سرور ذخیره نمی‌شود. کلاینت شما هر کلیدی ارسال کند مستقیماً به AgentRouter فرستاده می‌شود و در صورت خالی بودن، خالی ارسال می‌گردد.

---

## راه‌اندازی سریع در ویندوز

تنها کافیست روی فایل زیر دابل‌کلیک کنید:
```
start.bat
```
این اسکریپت محیط مجازی پایتون (`.venv`) را فعال کرده و سرور را روی پورت `28471` بالا می‌آورد.

### یا اجرای دستی با ترمینال:
```powershell
.venv\Scripts\python.exe main.py
```

پس از اجرا، آدرس پروکسی شما خواهد بود:
- **Base URL:** `http://127.0.0.1:28471/v1`
- **Health Check:** `http://127.0.0.1:28471/health`

---

## نحوه اتصال کلاینت‌ها

### ۱. استفاده در کتابخانه پایتون `openai`

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:28471/v1",
    api_key="sk-nJRLolenzlVQAxALe2URP6oqOVr0iXpxBWCDsNnYYw3tWfNz",  # کلید AgentRouter شما
)

# تست استریم
response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "سلام! یک جوک کوتاه بگو."}],
    stream=True,
)

for chunk in response:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)
```

---

### ۲. استفاده در Cursor / Continue / VS Code Extensions

در بخش تنظیمات مدل سفارشی (Custom OpenAI Model):
- **API Base / URL:** `http://127.0.0.1:28471/v1`
- **API Key:** کلید اختصاصی شما از AgentRouter
- **Model Name:** نام مدل‌های موجود در پنل (مثل `claude-opus-4-8`, `deepseek-v4-flash`, `glm-5.3`, `claude-opus-5`)

---

### ۳. تست با cURL

```bash
curl -X POST http://127.0.0.1:28471/v1/chat/completions \
  -H "Authorization: Bearer sk-nJRLolenzlVQAxALe2URP6oqOVr0iXpxBWCDsNnYYw3tWfNz" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": "Hi"}],
    "stream": false
  }'
```

---

## تست خودکار سلامت و عملکرد

یک اسکریپت تست کامل در پروژه قرار دارد:
```powershell
.venv\Scripts\python.exe test_client.py
```
این اسکریپت موارد زیر را بررسی می‌کند:
1. سلامت سرور و متغیرهای پروکسی (`/health`)
2. دریافت لیست مدل‌ها بدون نیاز به هدرهای اختصاصی کلاینت (`/v1/models`)
3. ارسال درخواست عادی (Non-Streaming) و دریافت پاسخ موفق
4. ارسال درخواست استریمینگ زنده (SSE Streaming)
5. صحت اعتبارسنجی و عدم تزریق خودکار کلید در درخواست‌های بدون احراز هویت

---

## تنظیمات پیشرفته (`.env`)

در فایل `.env` می‌توانید تنظیمات پروکسی را سفارشی‌سازی کنید:
```env
UPSTREAM_URL=https://agentrouter.org
CLINE_USER_AGENT=Cline/4.1.17
STAINLESS_LANG=js
STAINLESS_RUNTIME=node
HOST=0.0.0.0
PORT=28471
```
