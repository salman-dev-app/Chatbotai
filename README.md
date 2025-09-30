# Gemini AI Telegram Bot 🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://www.python.org/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-blue?logo=telegram)](https://core.telegram.org/bots/api)

A powerful, feature-rich, and multi-language Telegram bot powered by Google's Gemini API. This bot is designed to be a versatile AI assistant with a complete admin panel, group membership management, and a user-friendly interface.

---

## ✨ Demo

<!-- Add a screenshot or GIF of your bot in action here -->
![Bot Demo](https://files.catbox.moe/vnko8p.png)
![](https://files.catbox.moe/qcpo2a.png)
<!-- To make this file more attractive, add a screenshot of the bot's functionality. -->

---

## 🌟 Features

This bot is packed with features for both regular users and administrators.

### 👤 For Users
- **🧠 Intelligent AI Chat:** Get fast and intelligent responses powered by the Google Gemini 1.5 Flash model.
- **🌐 Multi-Language Support:** The bot's interface (menus, buttons) can be switched between English and Bengali, while the AI can chat in virtually any language.
- **💬 Intuitive Command Menu:**
  - `/start` - Access the main menu with primary actions: Start Chat, Membership Info, and Contact Admin.
  - `/language` - Change the interface language.
  - `/help` - Get instructions on how to use the bot.
  - `/myinfo` - View your stored information (User ID, selected language).
  - `/about` - Learn more about the bot and its creator.

### 👑 For Admins
- **🔒 Secure Admin Panel:** A comprehensive set of commands accessible only to the bot administrator.
- **➕ Group Membership Management:**
  - `/addgroup <group_id>` - Authorize the bot to operate in a new group.
  - `/removegroup <group_id>` - Revoke the bot's access from a group.
  - `/listgroups` - Display a list of all authorized group IDs.
- **🚫 User Control System:**
  - `/ban <user_id>` - Ban a user from interacting with the bot.
  - `/unban <user_id>` - Lift a user's ban.
  - `/listbanned` - Show a list of all banned user IDs.
- **📢 Broadcast System:** Send a message to all users who have started the bot simultaneously. Includes a confirmation step to prevent accidental messages.
- **📊 Bot Statistics:**
  - `/stats` - Get real-time statistics, including the total number of users, authorized groups, and banned users.
- **⚙️ Automated Group Management:** The bot automatically leaves any group it's added to if the group is not on the authorized list.

---

## 🛠️ Tech Stack

- **Language:** Python 3.9+
- **Framework:** `python-telegram-bot`
- **AI Engine:** Google Gemini API (`google-generativeai`)
- **Data Storage:** `data.json` (JSON File)
- **Deployment:** Koyeb

---

## 🚀 Getting Started

Follow these steps to set up and run the bot on your own.

### Prerequisites
- Python 3.9 or newer.
- Git installed on your machine.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/your-repository.git
    cd your-repository
    ```
    *(Replace `your-username` and `your-repository` with your actual GitHub details.)*

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # For Windows
    python -m venv venv
    .\venv\Scripts\activate

    # For macOS / Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required libraries:**
    ```bash
    pip install -r requirements.txt
    ```

### Setting Up Environment Variables
This project requires secret keys and tokens to function. **Never hardcode these values directly in your code.**

| Variable             | Description                                       | Where to Get It                                      |
| --------------------- | ------------------------------------------------- | ---------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`  | The unique token for your Telegram bot.           | From **@BotFather** on Telegram.                     |
| `GEMINI_API_KEY`      | The API key to use the Google Gemini service.     | From the **Google AI Studio** website.               |
| `ADMIN_ID`            | Your personal Telegram User ID for admin access.  | From **@userinfobot** on Telegram.                   |

You will add these variables directly to your hosting platform (e.g., Koyeb).

---

## ☁️ Deployment on Koyeb

1.  Log in to your Koyeb account and create a new App.
2.  Select **Git** as the deployment method and connect your GitHub repository.
3.  Ensure the service type is set to **Worker**, which Koyeb should detect automatically from the `Procfile`.
4.  Navigate to the **Environment Variables** section and add the three secret variables mentioned above (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ADMIN_ID`).
5.  Click **Deploy**. Your bot will be online in a few moments!



## 🙏 Acknowledgements & Contact

Made with ❤️ by **MD Salman**.

For any questions or support, please contact the admin: [@otakuosenpai](https://t.me/otakuosenpai)
