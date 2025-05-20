import json
import os
import random
from dotenv import load_dotenv

import aiohttp
# BeautifulSoup is no longer needed for the ranks command with the new JSON API
# from bs4 import BeautifulSoup
import discord
from discord.ext import commands

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
# Update the base API URL
BASE_API_URL = "https://api-mobilelegends.vercel.app/api/"

# Configure intents
intents = discord.Intents.default()
intents.message_content = True

# Initialize bot
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
    activity=discord.Activity(
        type=discord.ActivityType.watching, name="MLBB Statistics"
    ),
)

# Custom color palette
COLORS = {
    "primary": 0xFFD700,  # Gold
    "success": 0x00FF00,  # Green
    "error": 0xFF0000,    # Red
    "info": 0x0099FF,     # Blue
    "mythic": 0xC0392B,   # Mythic Red
    "legend": 0xF1C40F,   # Legend Yellow
    "epic": 0x8E44AD,     # Epic Purple
}

# Predefined hero list (updated 2024) - Used as a fallback
HERO_LIST = [
    "Kalea", "Lukas", "Suyou", "Zhuxin", "Chip", "Cici", "Nolan", "Ixia",
    "Arlott", "Novaria", "Joy", "Fredrinn", "Julian", "Xavier", "Melissa",
    "Yin", "Floryn", "Edith", "Valentina", "Aamon", "Aulus", "Natan",
    "Phoveus", "Beatrix", "Gloo", "Paquito", "Mathilda", "Yve", "Brody",
    "Barats", "Khaleed", "Benedetta", "Luo Yi", "Yu Zhong",
    "Popol and Kupa", "Atlas", "Carmilla", "Cecilion", "Silvanna",
    "Wanwan", "Masha", "Baxia", "Lylia", "Dyrroth", "Ling", "X.Borg",
    "Terizla", "Esmeralda", "Guinevere", "Granger", "Khufra", "Badang",
    "Faramis", "Kadita", "Minsitthar", "Harith", "Thamuz", "Kimmy",
    "Belerick", "Hanzo", "Lunox", "Leomord", "Vale", "Aldous", "Selena",
    "Kaja", "Chang'e", "Hanabi", "Uranus", "Martis", "Gusion", "Angela",
    "Jawhead", "Lesley", "Pharsa", "Helcurt", "Zhask", "Diggie",
    "Lancelot", "Odette", "Argus", "Grock", "Irithel", "Harley",
    "Gatotkaca", "Karrie", "Roger", "Vexana", "Lapu-Lapu", "Aurora",
    "Hilda", "Estes", "Cyclops", "Johnson", "Moskov", "Yi Sun-shin",
    "Ruby", "Alpha", "Chou", "Kagura", "Natalia", "Gord", "Freya",
    "Hayabusa", "Lolita", "Layla", "Fanny", "Zilong", "Eudora",
    "Rafaela", "Clint", "Bruno", "Bane", "Franco", "Akai", "Karina",
    "Alucard", "Tigreal", "Nana", "Alice", "Saber", "Balmond", "Miya",
    "Minotaur", "Sun", "Hylos", "Valir", "Claude",
]

# Hero ID Map - crucial for the counter command
HERO_ID_MAP = {
    "Kalea": 128, "Lukas": 127, "Suyou": 126, "Zhuxin": 125, "Chip": 124,
    "Cici": 123, "Nolan": 122, "Ixia": 121, "Arlott": 120, "Novaria": 119,
    "Joy": 118, "Fredrinn": 117, "Julian": 116, "Xavier": 115, "Melissa": 114,
    "Yin": 113, "Floryn": 112, "Edith": 111, "Valentina": 110, "Aamon": 109,
    "Aulus": 108, "Natan": 107, "Phoveus": 106, "Beatrix": 105, "Gloo": 104,
    "Paquito": 103, "Mathilda": 102, "Yve": 101, "Brody": 100, "Barats": 99,
    "Khaleed": 98, "Benedetta": 97, "Luo Yi": 96, "Yu Zhong": 95,
    "Popol and Kupa": 94, "Atlas": 93, "Carmilla": 92, "Cecilion": 91,
    "Silvanna": 90, "Wanwan": 89, "Masha": 88, "Baxia": 87, "Lylia": 86,
    "Dyrroth": 85, "Ling": 84, "X.Borg": 83, "Terizla": 82, "Esmeralda": 81,
    "Guinevere": 80, "Granger": 79, "Khufra": 78, "Badang": 77, "Faramis": 76,
    "Kadita": 75, "Minsitthar": 74, "Harith": 73, "Thamuz": 72, "Kimmy": 71,
    "Belerick": 70, "Hanzo": 69, "Lunox": 68, "Leomord": 67, "Vale": 66,
    "Claude": 65, "Aldous": 64, "Selena": 63, "Kaja": 62, "Chang'e": 61,
    "Hanabi": 60, "Uranus": 59, "Martis": 58, "Valir": 57, "Gusion": 56,
    "Angela": 55, "Jawhead": 54, "Lesley": 53, "Pharsa": 52, "Helcurt": 51,
    "Zhask": 50, "Hylos": 49, "Diggie": 48, "Lancelot": 47, "Odette": 46,
    "Argus": 45, "Grock": 44, "Irithel": 43, "Harley": 42, "Gatotkaca": 41,
    "Karrie": 40, "Roger": 39, "Vexana": 38, "Lapu-Lapu": 37, "Aurora": 36,
    "Hilda": 35, "Estes": 34, "Cyclops": 33, "Johnson": 32, "Moskov": 31,
    "Yi Sun-shin": 30, "Ruby": 29, "Alpha": 28, "Sun": 27, "Chou": 26,
    "Kagura": 25, "Natalia": 24, "Gord": 23, "Freya": 22, "Hayabusa": 21,
    "Lolita": 20, "Minotaur": 19, "Layla": 18, "Fanny": 17, "Zilong": 16,
    "Eudora": 15, "Rafaela": 14, "Clint": 13, "Bruno": 12, "Bane": 11,
    "Franco": 10, "Akai": 9, "Karina": 8, "Alucard": 7, "Tigreal": 6,
    "Nana": 5, "Alice": 4, "Saber": 3, "Balmond": 2, "Miya": 1,
}


@bot.event
async def on_ready():
    """Handle bot startup."""
    print(f"✅ {bot.user} is connected to Discord!")
    print(f"Guilds: {len(bot.guilds)}")


@bot.group(name="mlbb", invoke_without_command=True)
async def mlbb(ctx):
    """Main command group for MLBB features."""
    desc = (
        "Your ultimate companion for MLBB statistics and rankings!\n\n"
        "**Available Commands:**\n"
        "`!mlbb ranks [rank_filter] [days]` - Show top 10 hero rankings.\n"
        "  *Example: `!mlbb ranks mythic 30`*\n"
        "`!mlbb pick` - Get a random hero suggestion.\n"
        "`!mlbb counter [hero]` - Show hero counters."
    )
    embed = discord.Embed(
        title="🏆 Mobile Legends: Bang Bang Bot",
        description=desc,
        color=COLORS["primary"],
    )
    footer_text = (
        f"Requested by {ctx.author.display_name} • "
        "Use !mlbb help for more details."
    )
    embed.set_footer(text=footer_text)
    await ctx.send(embed=embed)


@mlbb.command(name="help")
async def help_command(ctx):
    """Show detailed help menu for MLBB commands."""
    embed = discord.Embed(
        title="📚 MLBB Bot Commands Help",
        color=COLORS["info"]
    )
    utility_cmds_value = (
        "`!ping` - Check bot latency.\n"
        "`!mlbb help` - Show this help menu."
    )
    embed.add_field(
        name="⚙️ Utility Commands",
        value=utility_cmds_value,
        inline=False,
    )
    game_cmds_value = (
        "`!mlbb counter [hero_name]` - Shows top 3 counters for the "
        "specified hero.\n"
        "`!mlbb ranks [rank_filter] [days_filter]` - Shows top 10 hero "
        "rankings.\n"
        "  `rank_filter`: `all` (default), `epic`, `legend`, `mythic`,\n"
        "  `honor`, `glory`.\n"
        "`!mlbb ranks [rank_filter] [days_filter]` - Shows top 10 hero "
        "rankings.\n"
        "  Parameters are optional and have defaults.\n"
        "  `rank_filter`: `all` (default), `epic`, `legend`, `mythic`,\n"
        "  `honor`, `glory`.\n"
        "  `days_filter`: `7` (default), `30`.\n"
        "  *Example: `!mlbb ranks glory 30`*"
    )
    embed.add_field(
        name="🎮 Game Commands",
        value=game_cmds_value,
        inline=False,
    )
    embed.set_footer(
        text="Powered by MLBB Stats API • Version 2.1.0"
    )
    await ctx.send(embed=embed)


@mlbb.command(name="pick")
async def random_hero(ctx):
    """Randomly select a hero for players to use."""
    api_url = f"{BASE_API_URL}hero-list/"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                response.raise_for_status()
                data = await response.json()
                heroes_from_api = data.get("data", [])

                if (
                    not heroes_from_api
                    or not isinstance(heroes_from_api, list)
                ):
                    print(
                        "API hero list empty or not a list, using fallback. "
                        f"Response: {data}"
                    )
                    heroes_to_choose_from = HERO_LIST
                else:
                    heroes_to_choose_from = heroes_from_api

            selected_hero = random.choice(heroes_to_choose_from)
            embed = discord.Embed(
                title="🎲 Random Hero Selector",
                description=f"**You should play:** {selected_hero}",
                color=COLORS["primary"],
            )
            await ctx.send(embed=embed)
    except aiohttp.ClientError as e:
        print(f"AIOHTTP ClientError in random_hero: {e}")
        selected_hero = random.choice(HERO_LIST)
        error_desc = (
            "Don't worry, I picked one from my local list for you!"
        )
        error_embed = discord.Embed(
            title="⚠️ API Error During Hero Pick",
            description=error_desc,
            color=COLORS["error"],
        )
        error_embed.add_field(
            name="Random Hero (Fallback)", value=selected_hero, inline=False
        )
        await ctx.send(embed=error_embed)
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError in random_hero: {e}")
        selected_hero = random.choice(HERO_LIST)
        error_desc = (
            "The API returned data I couldn't understand.\n"
            "I picked one from my local list instead!"
        )
        error_embed = discord.Embed(
            title="⚠️ API Response Error During Hero Pick",
            description=error_desc,
            color=COLORS["error"],
        )
        error_embed.add_field(
            name="Random Hero (Fallback)", value=selected_hero, inline=False
        )
        await ctx.send(embed=error_embed)
    except Exception as e:
        print(f"Unexpected error in random_hero: {e}")
        selected_hero = random.choice(HERO_LIST)
        error_desc = (
            f"An unexpected error occurred: {e}\n"
            "Using a fallback hero for now!"
        )
        error_embed = discord.Embed(
            title="⚠️ Oops! Something Went Wrong During Hero Pick",
            description=error_desc,
            color=COLORS["error"],
        )
        error_embed.add_field(
            name="Random Hero (Fallback)", value=selected_hero, inline=False
        )
        await ctx.send(embed=error_embed)


@mlbb.command(name="ranks")
async def ranks(ctx, rank_filter: str = "all", days_filter: int = 7):
    # Validate parameters
    valid_ranks = ["all", "epic", "legend", "mythic", "honor", "glory"]
    if rank_filter.lower() not in valid_ranks:
        rank_filter = "all"
    if days_filter not in [7, 30]:
        days_filter = 7

    api_url = (
        f"{BASE_API_URL}hero-rank/?rank={rank_filter.lower()}"
        f"&days={days_filter}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                response.raise_for_status()
                json_data = await response.json()
                api_status = json_data.get("code")
                hero_records = json_data.get("data", {}).get("records")

                if api_status != 0 or hero_records is None:
                    err_msg = json_data.get("message", "No message from API.")
                    error_desc = (
                        "The API reported an issue or returned unexpected "
                        "data.\n"
                        f"Message: {err_msg}"
                    )
                    error_embed = discord.Embed(
                        title="⚠️ Data Retrieval Issue",
                        description=error_desc,
                        color=COLORS["error"],
                    )
                    await ctx.send(embed=error_embed)
                    return

                if not hero_records:
                    embed = discord.Embed(
                        title="📊 No Hero Data Found",
                        description="No ranking data available",
                        color=COLORS["info"],
                    )
                    await ctx.send(embed=embed)
                    return

                embed_color = COLORS.get(
                    rank_filter.lower(),
                    COLORS["primary"]
                )
                title_rank_filter = (
                    rank_filter.capitalize()
                    if rank_filter.lower() != "all"
                    else "All Ranks"
                )
                embed_title = (
                    f"🏆 Top 10 Heroes - {title_rank_filter} "
                    f"({days_filter} Days)"
                )
                embed_description = "*Sorted by Win Rate (Descending)*"

                embed = discord.Embed(
                    title=embed_title,
                    description=embed_description,
                    color=embed_color,
                )

                rank_display_list = []
                medals = ["🥇", "🥈", "🥉"]

                for idx, record in enumerate(
                    hero_records[:10]
                ):  # Limit to top 10
                    hero_data = record.get("data")
                    if hero_data:
                        name = hero_data.get(
                            "main_hero", {}
                        ).get("data", {}).get("name", "Unknown")
                        win_rate = hero_data.get(
                            "main_hero_win_rate", "N/A"
                        )
                        pick_rate = hero_data.get(
                            "main_hero_appearance_rate", "N/A"
                        )
                        ban_rate = hero_data.get(
                            "main_hero_ban_rate", "N/A"
                        )
                        # The API response doesn't directly provide the number
                        # of games played. You might need to adjust your
                        # output accordingly.

                        rank_prefix = (
                            medals[idx] if idx < 3 else f"`#{idx + 1:02}`"
                        )

                        hero_entry = (
                            f"{rank_prefix} **{name}**\n"
                            f" ▸ WR: `{win_rate:.2%}` \u200B | "
                            f"PR: `{pick_rate:.2%}` "
                            f"\u200B | BR: `{ban_rate:.2%}`"
                        )
                        rank_display_list.append(hero_entry)

                if rank_display_list:
                    embed.add_field(
                        name="Hero Stats",
                        value="\n\n".join(rank_display_list),
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="No Data",
                        value="Could not format hero data.",
                        inline=False,
                    )

                footer_text = (
                    f"Requested by {ctx.author.display_name} • "
                    f"Data from api-mobilelegends.vercel.app"
                )
                embed.set_footer(text=footer_text)
                await ctx.send(embed=embed)

    except aiohttp.ClientResponseError as e:
        error_embed = discord.Embed(
            title="⚠️ API Request Error (Ranks)",
            description=f"The API returned an error: {e.status} {e.message}",
            color=COLORS["error"],
        )
        await ctx.send(embed=error_embed)
    except aiohttp.ClientError as e:
        error_embed = discord.Embed(
            title="⚠️ API Network Error (Ranks)",
            description=f"Failed to fetch ranking data: {e}",
            color=COLORS["error"],
        )
        await ctx.send(embed=error_embed)
    except json.JSONDecodeError:
        error_embed = discord.Embed(
            title="⚠️ Invalid API Response (Ranks)",
            description="The API returned data that was not valid JSON.",
            color=COLORS["error"],
        )
        await ctx.send(embed=error_embed)
    except Exception as e:
        print(f"An unexpected error occurred in ranks command: {e}")
        error_embed = discord.Embed(
            title="⚠️ Oops! Something Went Wrong (Ranks)",
            description=f"An unexpected error occurred: {str(e)}",
            color=COLORS["error"],
        )
        await ctx.send(embed=error_embed)


@mlbb.command(name="counter")
async def counter(ctx, *, hero_name: str):
    """Suggest top 3 counters for the specified hero."""
    hero_name_lower = hero_name.strip().lower()
    matched_hero = next(
        (name for name in HERO_ID_MAP if name.lower() == hero_name_lower), None
    )

    if not matched_hero:
        desc = (
            f"Hero '{hero_name}' not found. Please check the spelling.\n"
            "You can try `!mlbb pick` to see a random hero name as an example."
        )
        embed = discord.Embed(
            title="⚠️ Hero Not Found",
            description=desc,
            color=COLORS["error"],
        )
        await ctx.send(embed=embed)
        return

    hero_id = HERO_ID_MAP[matched_hero]
    counter_url = f"{BASE_API_URL}hero-counter/{hero_id}/"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(counter_url) as response:
                response.raise_for_status()
                data = await response.json()

                # --- FIX START ---
                # Access the 'records' list, then the first item's 'data', then 'sub_hero'
                records = data.get("data", {}).get("records", [])
                if not records or not records[0].get("data"):
                    embed = discord.Embed(
                        title=f"🛡️ No Counter Data Found for {matched_hero}",
                        description=(
                            "The API returned no valid data for this hero's counters."
                        ),
                        color=COLORS["info"],
                    )
                    await ctx.send(embed=embed)
                    return

                # Get the 'sub_hero' list which contains the counters
                counter_list = records[0]["data"].get("sub_hero", [])

                if not counter_list:
                    embed = discord.Embed(
                        title=f"🛡️ No Specific Counters Found for {matched_hero}",
                        description=(
                            "No specific counter data available from the API "
                            "for this hero."
                        ),
                        color=COLORS["info"],
                    )
                    await ctx.send(embed=embed)
                    return

                embed = discord.Embed(
                    title=f"🛡️ Top Counters for {matched_hero}",
                    color=COLORS["primary"],
                )

                # Iterate through the top 3 counter heroes
                for idx, counter_hero_data in enumerate(counter_list[:3], 1):
                    # Extract hero name from nested 'hero' -> 'data' -> 'name'
                    name = counter_hero_data.get("hero", {}).get("data", {}).get("name", "Unknown Hero")
                    
                    # The API doesn't provide a 'reason' directly for each counter.
                    # We can use 'increase_win_rate' to indicate how effective they are.
                    # If you still need a 'reason', it would require static data or another API call.
                    increase_win_rate = counter_hero_data.get("increase_win_rate")

                    if increase_win_rate is not None:
                        # Format as percentage and indicate effectiveness
                        reason_text = f"Increases {matched_hero}'s Win Rate by: `{increase_win_rate:.2%}`"
                    else:
                        reason_text = "No specific effectiveness data provided."

                    embed.add_field(
                        name=f"{idx}. {name}",
                        value=f"▸ {reason_text}", # Updated to use increase_win_rate
                        inline=False,
                    )

                # This check is less likely to be hit now with the checks above,
                # but good to keep as a general safeguard.
                if not embed.fields:
                    embed.description = "Could not retrieve counter details."

                embed.set_footer(
                    text=f"Requested by {ctx.author.display_name}"
                )
                await ctx.send(embed=embed)

        except aiohttp.ClientResponseError as e:
            error_desc = f"The API returned an error: {e.status} {e.message}"
            error_embed = discord.Embed(
                title="⚠️ API Request Error (Counters)",
                description=error_desc,
                color=COLORS["error"],
            )
            await ctx.send(embed=error_embed)
        except aiohttp.ClientError as e:
            error_embed = discord.Embed(
                title="⚠️ API Network Error (Counters)",
                description=f"Failed to fetch counter data: {e}",
                color=COLORS["error"],
            )
            await ctx.send(embed=error_embed)
        except json.JSONDecodeError:
            error_embed = discord.Embed(
                title="⚠️ Invalid API Response (Counters)",
                description=(
                    "The API returned data that was not valid JSON "
                    "when fetching counters."
                ),
                color=COLORS["error"],
            )
            await ctx.send(embed=error_embed)
        except Exception as e:
            print(f"Unexpected error in counter command: {e}")
            error_embed = discord.Embed(
                title="⚠️ Oops! Something Went Wrong (Counters)",
                description=f"An unexpected error occurred: {str(e)}",
                color=COLORS["error"],
            )
            await ctx.send(embed=error_embed)


@bot.command()
async def ping(ctx):
    """Check bot latency."""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: {latency}ms",
        color=COLORS["success"],
    )
    await ctx.send(embed=embed)


if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print(
            "❌ DISCORD_TOKEN environment variable not found. "
            "Please set it in your .env file."
        )
