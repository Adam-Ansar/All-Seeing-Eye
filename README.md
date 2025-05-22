# All-Seeing-Eye: MLBB Discord Bot

All-Seeing-Eye is a feature-rich Discord bot for [Mobile Legends: Bang Bang (MLBB)](https://m.mobilelegends.com/en), designed to provide hero statistics, counter picks, synergy data, trivia, and fun utilities for your server.

---

## Features

### 🏆 Hero & Game Stats
- **Hero Rankings:** View top 10 heroes by win rate, pick rate, and ban rate for any rank and time period.
- **Counter Picks:** Get the top 3 counters for any hero, with detailed reasoning and skill highlights.
- **Synergy & Anti-Synergy:** Discover the best and worst hero partners, with win rate trends over match duration.
- **Random Hero/Role:** Get a random hero or role suggestion for your next game.

### 🎮 Fun & Utility
- **MLBB Trivia:** Start a trivia game about MLBB heroes (moderator-only).
- **Magic 8-Ball:** Ask any question and get a random answer.
- **Roasts & Compliments:** Send a roast or a wholesome compliment to yourself or a friend.
- **Crazy Copypasta:** Enjoy a classic Discord copypasta.
- **Uptime & Ping:** Check bot uptime and latency.

---

## Getting Started

### 1. Prerequisites

- Python 3.8+
- [Discord bot token](https://discord.com/developers/applications)
- [OpenAI API key](https://platform.openai.com/account/api-keys) (for advanced counter explanations)
- The following Python packages:
  - `discord.py`
  - `python-dotenv`
  - `aiohttp`
  - `thefuzz`
  - `openai`

Install dependencies:
```sh
pip install discord.py python-dotenv aiohttp thefuzz openai
```

### 2. Setup

1. **Clone the repository:**
   ```sh
   git clone <your-repo-url>
   cd All-Seeing-Eye
   ```

2. **Configure environment variables:**
   Create a `.env` file in the project root:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   OPENAI_API_KEY=your_openai_api_key
   ```

3. **Run the bot:**
   ```sh
   python Main.py
   ```

---

## Usage

### Command Prefix

All commands use the `!mlbb` prefix.

### Hero & Game Stats

- `!mlbb ranks [rank] [days]`  
  Show top 10 hero rankings.  
  - `rank`: all, epic, legend, mythic, honor, glory  
  - `days`: 7 or 30  
  - Example: `!mlbb ranks mythic 30`

- `!mlbb counter [hero]`  
  Show top 3 counters for a hero, with detailed reasoning.

- `!mlbb synergy [hero]`  
  Show synergy and anti-synergy stats for a hero.

- `!mlbb pick`  
  Get a random hero suggestion.

- `!mlbb role pick`  
  Get a random role to play.

### Fun & Utility

- `!mlbb trivia`  
  Start a MLBB trivia game (moderator-only).

- `!mlbb 8ball [question]`  
  Ask the Magic 8-Ball a question.

- `!mlbb roast [@user]`  
  Roast yourself or a friend.

- `!mlbb compliment [@user]`  
  Compliment yourself or a friend.

- `!mlbb crazy`  
  Sends the "crazy" copypasta.

- `!mlbb uptime`  
  Show how long the bot has been running.

- `!mlbb help`  
  Show detailed help for all commands.

---

## ⚠️ Usage Restrictions

**This bot and its source code are private. You may not use, copy, modify, or host this bot or any part of its code without explicit written permission from the owner.**

If you wish to use or deploy this bot, please contact the repository owner for authorization.

---

## Data Sources

- **Hero stats and details:**  
  [api-mobilelegends.vercel.app](https://api-mobilelegends.vercel.app/api/)

- **Counter and synergy logic:**  
  - [`counter_hero_list.py`](counter_hero_list.py)
  - [`generalised_counter_reasoning.py`](generalised_counter_reasoning.py)

---

## File Structure

- [`Main.py`](Main.py): Main bot logic and command definitions.
- [`counter_hero_list.py`](counter_hero_list.py): Per-hero counter and synergy lists.
- [`generalised_counter_reasoning.py`](generalised_counter_reasoning.py): Generalized counter groupings and explanations.
- [`hero_list.py`](hero_list.py): List of all MLBB heroes.
- `.env`: Environment variables (not tracked by git).
- `.gitignore`: Files and folders to ignore in git.

---

## Permissions

- The bot requires the following Discord permissions:
  - Read Messages/View Channels
  - Send Messages
  - Embed Links
  - Use Slash Commands (optional)
  - Manage Messages (for trivia command)

---

## Troubleshooting

- **Bot not responding:**  
  - Check if the bot is running and connected to Discord.
  - Ensure your `.env` file has the correct tokens.
  - Make sure the bot has the necessary permissions in your server.

- **API errors:**  
  - The bot relies on a public MLBB stats API. If the API is down, some commands may not work.

- **OpenAI errors:**  
  - If you do not provide an OpenAI API key, the bot will use fallback explanations for counter picks.

---

## Contributing

Pull requests and suggestions are welcome! Please open an issue or submit a PR.

---

## License

This project is private and not licensed for public or commercial use.  
**All rights reserved. Unauthorized use, copying, or distribution is strictly prohibited.**

---

## Credits

- [discord.py](https://github.com/Rapptz/discord.py)
- [api-mobilelegends.vercel.app](https://api-mobilelegends.vercel.app/)
- [OpenAI](https://openai.com/)
- MLBB community for hero data and inspiration

---

## Libraries & Imports Used

The bot uses the following Python libraries and modules:

### Core Libraries
- `os` — For environment variable access and file paths
- `time` — For uptime and timing features
- `re` — For regular expressions (e.g., cleaning HTML tags)
- `json` — For parsing API responses
- `asyncio` — For asynchronous background tasks

### Third-Party Libraries
- `discord` and `discord.ext.commands` — For Discord bot functionality ([discord.py](https://github.com/Rapptz/discord.py))
- `python-dotenv` (`dotenv`) — For loading environment variables from a `.env` file
- `aiohttp` — For making asynchronous HTTP requests to APIs
- `thefuzz` — For fuzzy string matching (hero name matching)
- `openai` — For generating advanced counter explanations (optional)

### Project Modules
- `counter_hero_list` — Contains hero counter lists
- `generalised_counter_reasoning` — Contains generalized counter groupings and explanations
- `hero_list` — Contains the full list of MLBB heroes

---

## Contact

For permission requests, questions, or support, please contact:  
[Adam11801@outlook.com] or open an issue in this repository.

---

## Changelog

- v1.0.0: Initial release