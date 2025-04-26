# Scriptly

[![Python Version](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Discord.py Version](https://img.shields.io/badge/discord.py-v2.x-blue?logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![MongoDB](https://img.shields.io/badge/Database-MongoDB-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

![Scriptly Banner](assets/banner.png)

**Scriptly** is an intelligent Discord assistant powered by the **Google Gemini API**. It provides AI-driven responses within your server, featuring a modular command structure (`discord.py` Cogs), server-specific configurations stored in MongoDB, and a custom logging system for straightforward monitoring.

---

## Features

*   **AI Chat:** Engage in conversations by mentioning the bot and it replies with generated messages using Google's Gemini API.
*   **Per-Channel Configuration:** Use MongoDB to store settings, such as which channels the bot is allowed to interact in.
*   **Modular Commands:** Built with `discord.py` cogs.
*   **Custom Logging:** Includes a logging setup with file rotation for easier debugging and tracking bot activity.
*   **Dynamic Presence:** A background task keeps the bot's Discord status updated (e.g., "Watching Low Usage").

---

## Requirements

*   **Python 3.10+**
*   **MongoDB URI:** Connection string for your MongoDB instance.
*   **Discord Bot Token:** Obtainable from the [Discord Developer Portal](https://discord.com/developers/applications).
*   **Google Gemini API Key:** Get yours from [Google AI Studio](https://aistudio.google.com/app/apikey).
*   **Required Python Packages:**
    *   `discord.py`
    *   `motor`
    *   `python-dotenv`
    *   `google-generativeai`

---

## Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/CanaryTeam/Scriptly.git
    cd scriptly
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Edit the`.env` file** in the root directory and add your credentials:
    ```ini
    DISCORD_TOKEN=your_discord_bot_token_here
    MONGO_URI=your_mongodb_connection_string_here
    GOOGLE_GEMINI_API_KEY=your_google_gemini_api_key_here
    ```

4.  **Run the bot:**
    ```bash
    python main.py
    ```
    
5.  **Instructions**
    You can also edit the instructions file to your liking.

---

## Recommended Tools

[![Visual Studio Code](https://img.shields.io/badge/Visual%20Studio%20Code-Code%20Editor-blue?logo=visualstudiocode&logoColor=white)](https://code.visualstudio.com/)  
[![MongoDB Atlas](https://img.shields.io/badge/MongoDB%20Atlas-Cloud%20Database-green?logo=mongodb&logoColor=white)](https://www.mongodb.com/cloud/atlas)  
[![Discord Developer Portal](https://img.shields.io/badge/Discord%20Developer%20Portal-Bot%20Management-5865F2?logo=discord&logoColor=white)](https://discord.com/developers/applications)  
[![Google AI Studio](https://img.shields.io/badge/Google%20AI%20Studio-Gemini%20API%20Key-4285F4?logo=google&logoColor=white)](https://aistudio.google.com/app/apikey)  

---

## Usage

*   **AI Interaction:** Mention the bot directly in an allowed channel (e.g., `@Scriptly i need help with my dumb code?`).
*   **Commands:** Use `;scriptly` to get a help message that also shows what channels its active in).
*   **Configuration:** Conifgure the bot with the `/options` command.

---

## Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/CanaryTeam/Scriptly/issues) (if you plan to use GitHub Issues).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
