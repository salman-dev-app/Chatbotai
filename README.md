# Gemini AI Telegram Bot 🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://www.python.org/)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram)](https://t.me/your_bot_username)
<!-- উপরের টেলিগ্রাম লিঙ্কে your_bot_username এর জায়গায় আপনার বটের ইউজারনেম দিন -->

A powerful, feature-rich, and multi-language Telegram bot powered by Google's Gemini API. This bot is designed to be a versatile AI assistant with a complete admin panel, group membership management, and a user-friendly interface.

---

## ✨ ডেমো (Demo)

<!-- এখানে আপনার বটের একটি স্ক্রিনশট বা GIF যোগ করুন -->
<!-- ![Bot Demo](https://i.imgur.com/your-image-link.png) -->
*বটের কার্যকারিতার একটি স্ক্রিনশট এখানে যোগ করলে README ফাইলটি আরও আকর্ষণীয় হবে।*

---

## 🌟 বৈশিষ্ট্য (Features)

### 👤 ব্যবহারকারীদের জন্য (For Users)
- **🧠 ইন্টেলিজেন্ট চ্যাট:** Google Gemini 1.5 Flash মডেল দ্বারা চালিত দ্রুত এবং বুদ্ধিমান উত্তর।
- **🌐 বহুভাষিক সমর্থন:** বটটি ব্যবহারকারীর পছন্দের ভাষায় (ইংরেজি/বাংলা) ইন্টারফেস প্রদর্শন করে এবং যেকোনো ভাষায় চ্যাট করতে পারে।
- **💬 সহজবোধ্য কমান্ড:**
  - `/start` - তিনটি বাটনসহ প্রধান মেন্যু (AI চ্যাট, সদস্যপদ তথ্য, অ্যাডমিন যোগাযোগ)।
  - `/language` - ইন্টারফেসের ভাষা পরিবর্তন করার অপশন।
  - `/help` - বট কীভাবে ব্যবহার করতে হয় তার নির্দেশনা।
  - `/myinfo` - আপনার সংরক্ষিত তথ্য (ইউজার আইডি, ভাষা) দেখা।
  - `/about` - বট এবং নির্মাতার সম্পর্কে তথ্য।

### 👑 অ্যাডমিনদের জন্য (For Admins)
- **🔒 সুরক্ষিত অ্যাডমিন প্যানেল:** শুধুমাত্র অ্যাডমিনের জন্য উপলব্ধ শক্তিশালী কমান্ড।
- **➕ গ্রুপ ম্যানেজমেন্ট:**
  - `/addgroup` - নতুন গ্রুপকে বট ব্যবহারের অনুমতি দেওয়া।
  - `/removegroup` - কোনো গ্রুপের অনুমতি বাতিল করা।
  - `/listgroups` - অনুমোদিত সমস্ত গ্রুপের তালিকা দেখা।
- **🚫 ইউজার ম্যানেজমেন্ট:**
  - `/ban` - কোনো ব্যবহারকারীকে বট ব্যবহার থেকে নিষিদ্ধ করা।
  - `/unban` - কোনো ব্যবহারকারীর নিষেধাজ্ঞা তুলে নেওয়া।
  - `/listbanned` - নিষিদ্ধ ব্যবহারকারীদের তালিকা দেখা।
- **📢 ব্রডকাস্ট সিস্টেম:** সকল ব্যবহারকারীকে একবারে বার্তা পাঠানোর সুবিধা।
- **📊 পরিসংখ্যান:** মোট ব্যবহারকারী, অনুমোদিত গ্রুপ এবং নিষিদ্ধ ব্যবহারকারীর সংখ্যা দেখা।

---

## 🛠️ ব্যবহৃত প্রযুক্তি (Tech Stack)

- **ভাষা (Language):** Python 3.9+
- **ফ্রেমওয়ার্ক (Framework):** `python-telegram-bot`
- **এআই ইঞ্জিন (AI Engine):** Google Gemini API (`google-generativeai`)
- **ডেটা স্টোরেজ (Data Storage):** `data.json` (JSON File)
- **হোস্টিং (Deployment):** Koyeb

---

## 🚀 যেভাবে শুরু করবেন (Getting Started)

এই বটটি সেটআপ এবং চালানোর জন্য নিচের ধাপগুলো অনুসরণ করুন।

### পূর্বশর্ত (Prerequisites)
- Python 3.9 বা তার নতুন সংস্করণ।
- Git ইনস্টল করা থাকতে হবে।

### ইনস্টলেশন (Installation)

1.  **রিপোজিটরিটি ক্লোন করুন:**
    ```bash
    git clone https://github.com/your-username/your-repository.git
    cd your-repository
    ```
    *(your-username এবং your-repository এর জায়গায় আপনার সঠিক তথ্য দিন)*

2.  **ভার্চুয়াল এনভায়রনমেন্ট তৈরি করুন (প্রস্তাবিত):**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # macOS / Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **প্রয়োজনীয় লাইব্রেরি ইনস্টল করুন:**
    ```bash
    pip install -r requirements.txt
    ```

### এনভায়রনমেন্ট ভ্যারিয়েবল সেটআপ
এই প্রজেক্টটি চালানোর জন্য কিছু গোপন তথ্য (API কী এবং টোকেন) প্রয়োজন। **কখনোই এই তথ্যগুলো সরাসরি কোডে লিখবেন না।**

| ভ্যারিয়েবল             | বিবরণ                                            | কোথা থেকে পাবেন                                      |
| --------------------- | ------------------------------------------------- | ---------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`  | আপনার টেলিগ্রাম বটের ইউনিক টোকেন।                  | Telegram-এ **@BotFather** থেকে                      |
| `GEMINI_API_KEY`      | গুগল জেমিনি এপিআই ব্যবহারের জন্য কী।             | **Google AI Studio** থেকে                           |
| `ADMIN_ID`            | বটের অ্যাডমিন হিসেবে আপনার টেলিগ্রাম ইউজার আইডি।     | Telegram-এ **@userinfobot** থেকে                     |

আপনি এই ভ্যারিয়েবলগুলো আপনার হোস্টিং প্ল্যাটফর্মে (যেমন Koyeb) সরাসরি যোগ করবেন।

---

## ☁️ Koyeb-এ ডিপ্লয়মেন্ট (Deployment on Koyeb)

1.  Koyeb-এ লগইন করুন এবং একটি নতুন অ্যাপ তৈরি করুন।
2.  আপনার এই GitHub রিপোজিটরিটি কানেক্ট করুন।
3.  সার্ভিস টাইপ হিসেবে **Worker** সিলেক্ট করা আছে কি না তা নিশ্চিত করুন।
4.  **Environment Variables** সেকশনে উপরে উল্লিখিত তিনটি (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ADMIN_ID`) ভ্যারিয়েবল যোগ করুন।
5.  **Deploy** বাটনে ক্লিক করুন। আপনার বট কয়েক মিনিটের মধ্যেই অনলাইনে চলে আসবে!

---

## 📂 প্রজেক্টের কাঠামো (Project Structure).
├── bot.py # মূল বট কোড এবং সমস্ত লজিক
├── requirements.txt # প্রয়োজনীয় পাইথন লাইব্রেরির তালিকা
├── Procfile # Koyeb-কে বট চালানোর নির্দেশ দেওয়ার জন্য
├── .gitignore # গিটকে কোন ফাইলগুলো উপেক্ষা করতে হবে তার তালিকা
└── README.md # এই ফাইলটি
---

## 🙏 কৃতজ্ঞতা এবং যোগাযোগ (Acknowledgements & Contact)

Made with ❤️ by **MD Salman**.

যেকোনো প্রশ্ন বা সহায়তার জন্য, অ্যাডমিনের সাথে যোগাযোগ করুন: [@otakuosenpai](https://t.me/otakuosenpai)
