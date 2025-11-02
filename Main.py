import json
import os
import random
from dotenv import load_dotenv
import re
import time
import asyncio
from datetime import datetime, timezone
from threading import Lock
from thefuzz import fuzz, process
import aiohttp
import discord
from discord.ext import commands
from counter_hero_list import mlbb_hero_counters as COUNTER_HERO_LIST
import openai
from generalised_counter_reasoning import counter_groups

# =========================
# Configuration & Constants
# =========================

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BASE_API_URL = "https://api-mobilelegends.vercel.app/api/"

# Configure intents
intents = discord.Intents.default()
intents.message_content = True

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


# =========================
# Bot Initialization
# =========================

bot_start_time = time.time()  # Track bot start time

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,

    activity=discord.Activity(
        type=discord.ActivityType.watching, name="MLBB Statistics"
    ),
)


# =========================
# Global Hero Data Caches
# =========================

HERO_DETAILS_CACHE = {}       # hero_id (str) -> full hero detail JSON
HERO_NAME_TO_ID_MAP = {}      # hero_name (lowercase str) -> hero_id (str)
HERO_ID_TO_NAME_MAP = {}      # hero_id (str) -> hero_name (str)
ACTIVE_TRIVIA_GAME = {}       # channel_id (int) -> bool

# =========================
# Tournament Registration Store
# =========================

TOURNEY_REGISTRATION_FILE = os.path.join(
    os.path.dirname(__file__), "tournament_registrations.json"
)
TOURNEY_DATA_LOCK = Lock()
TOURNEY_DATA = {"solos": [], "duos": []}


def _copy_tourney_data_unlocked():
    return {
        "solos": [dict(entry) for entry in TOURNEY_DATA.get("solos", [])],
        "duos": [dict(entry) for entry in TOURNEY_DATA.get("duos", [])],
    }


def _write_tourney_file(data):
    with open(TOURNEY_REGISTRATION_FILE, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)


def load_tourney_data():
    """Load tournament registrations from disk."""
    global TOURNEY_DATA
    try:
        with open(TOURNEY_REGISTRATION_FILE, "r", encoding="utf-8") as fp:
            raw_data = json.load(fp)
            if not isinstance(raw_data, dict):
                raise ValueError("Tournament registration file must be a dict")
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        raw_data = {"solos": [], "duos": []}

    with TOURNEY_DATA_LOCK:
        TOURNEY_DATA = {
            "solos": list(raw_data.get("solos", [])),
            "duos": list(raw_data.get("duos", [])),
        }
        snapshot = _copy_tourney_data_unlocked()

    _write_tourney_file(snapshot)


def add_solo_registration(entry):
    """Persist a solo registration to memory and disk."""
    with TOURNEY_DATA_LOCK:
        TOURNEY_DATA.setdefault("solos", []).append(entry)
        snapshot = _copy_tourney_data_unlocked()
    _write_tourney_file(snapshot)


def add_duo_registration(entry):
    """Persist a duo registration to memory and disk."""
    with TOURNEY_DATA_LOCK:
        TOURNEY_DATA.setdefault("duos", []).append(entry)
        snapshot = _copy_tourney_data_unlocked()
    _write_tourney_file(snapshot)


def user_already_registered(user_id):
    """Check if a Discord user already has a registration on file."""
    with TOURNEY_DATA_LOCK:
        for solo in TOURNEY_DATA.get("solos", []):
            if solo.get("discord_id") == user_id:
                return True
        for duo in TOURNEY_DATA.get("duos", []):
            if duo.get("primary_discord_id") == user_id:
                return True
            if duo.get("partner_discord_id") == user_id:
                return True
    return False


def get_tourney_snapshot():
    """Return a copy of the tournament registrations."""
    with TOURNEY_DATA_LOCK:
        return _copy_tourney_data_unlocked()


load_tourney_data()

# Helper Functions
# =========================


def clean_html_tags(text):
    """Remove <font ...> and </font> tags from a string.
    Handles non-string input."""
    if not isinstance(text, str):
        return ""
    return re.sub(r'<font[^>]*>', '', text).replace('</font>', '')


async def fetch_and_cache_hero_data():
    """Fetch and cache all hero data at startup."""
    global HERO_DETAILS_CACHE, HERO_NAME_TO_ID_MAP, HERO_ID_TO_NAME_MAP
    # Clear caches at the very beginning of this function to ensure a fresh
    # start
    HERO_DETAILS_CACHE.clear()
    HERO_NAME_TO_ID_MAP.clear()
    HERO_ID_TO_NAME_MAP.clear()
    print("DEBUG: Caches cleared before fetching new data.")

    try:
        async with aiohttp.ClientSession() as session:
            # --- Step 1: Fetch all hero IDs and names ---
            hero_list_url = f"{BASE_API_URL}hero-list/"
            print(f"DEBUG: Attempting to fetch hero list from: "
                  f"{hero_list_url}")
            async with session.get(hero_list_url) as resp:
                resp.raise_for_status()
                hero_list = await resp.json()
                print(f"DEBUG: Successfully fetched hero list. Contains "
                      f"{len(hero_list)} entries.")

            hero_ids_to_fetch_details = []
            for hero_id, hero_name in hero_list.items():
                hero_id_str = str(hero_id)
                lower_hero_name = hero_name.strip().lower()
                HERO_NAME_TO_ID_MAP[lower_hero_name] = hero_id_str
                HERO_ID_TO_NAME_MAP[hero_id_str] = hero_name
                hero_ids_to_fetch_details.append(hero_id_str)

            print(f"DEBUG: Populated name-to-ID maps. Total heroes: "
                  f"{len(HERO_NAME_TO_ID_MAP)}")

            # --- Step 2: Concurrently fetch all hero details ---
            async def fetch_hero_detail(session_inner, hero_id_str_inner):
                detail_url = f"{BASE_API_URL}hero-detail/{hero_id_str_inner}/"
                try:
                    async with session_inner.get(detail_url) as resp_detail:
                        resp_detail.raise_for_status()
                        return hero_id_str_inner, await resp_detail.json()
                except aiohttp.ClientError as e:
                    # Log the specific network/client error for this hero
                    print(f"⚠️ Network error fetching detail for ID "
                          f"{hero_id_str_inner}: {e}")
                    return hero_id_str_inner, None
                except json.JSONDecodeError:
                    # Log JSON decode errors for this hero
                    print(f"⚠️ JSON decode error for hero ID "
                          f"{hero_id_str_inner}.")
                    return hero_id_str_inner, None
                except Exception as e:
                    # Catch any other unexpected errors
                    print(f"⚠️ Unexpected error fetching detail for ID "
                          f"{hero_id_str_inner}: {e}")
                    return hero_id_str_inner, None

            # Create tasks for all detail fetches, passing the session
            tasks = [fetch_hero_detail(session, hid) for hid in
                     hero_ids_to_fetch_details]

            # Run tasks concurrently, capturing exceptions
            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful_fetches = 0
            for result in results:
                if isinstance(result, tuple) and len(result) == 2:
                    hero_id_str_result, detail_json_result = result
                    if detail_json_result:
                        HERO_DETAILS_CACHE[hero_id_str_result] = \
                            detail_json_result
                        successful_fetches += 1
                    else:
                        hero_name_for_debug = HERO_ID_TO_NAME_MAP.get(
                            hero_id_str_result, "Unknown Hero")
                        print(f"DEBUG: Failed to cache details for "
                              f"{hero_name_for_debug} (ID: "
                              f"{hero_id_str_result}) due to API issue.")
                elif isinstance(result, Exception):
                    # An exception was returned directly from asyncio.gather
                    print(f"DEBUG: An unhandled exception occurred during a "
                          f"detail fetch: {result}")
                else:
                    print(f"DEBUG: Unexpected result format from fetch_hero_"
                          f"detail: {result}")

            print(f"DEBUG: Detail caching complete. Successfully cached "
                  f"{successful_fetches} hero details.")
            print(f"DEBUG: HERO_NAME_TO_ID_MAP size: "
                  f"{len(HERO_NAME_TO_ID_MAP)}")
            print(f"DEBUG: HERO_DETAILS_CACHE size: "
                  f"{len(HERO_DETAILS_CACHE)}")

            if "ling" in HERO_NAME_TO_ID_MAP:
                print(f"DEBUG: 'ling' found in HERO_NAME_TO_ID_MAP. ID: "
                      f"{HERO_NAME_TO_ID_MAP['ling']}")
            else:
                print("DEBUG: 'ling' NOT found in HERO_NAME_TO_ID_MAP.")
            if "layla" in HERO_NAME_TO_ID_MAP:
                print(f"DEBUG: 'layla' found in HERO_NAME_TO_ID_MAP. ID: "
                      f"{HERO_NAME_TO_ID_MAP['layla']}")
            else:
                print("DEBUG: 'layla' NOT found in HERO_NAME_TO_ID_MAP.")

        return True  # Indicate success
    except aiohttp.ClientError as e:
        print(f"❌ Network error fetching hero list: {e}")
        return False
    except json.JSONDecodeError:
        print("❌ JSON decode error for hero list. API response might be "
              "malformed.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during initial hero list fetch: {e}")
        return False


async def background_hero_data_refresh():
    """Periodically refresh hero data cache in the background."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        print("🔄 Refreshing hero data cache in background...")
        success = await fetch_and_cache_hero_data()
        if success:
            print("✅ Hero data cache refreshed.")
        else:
            print("❌ Failed to refresh hero data cache.")
        await asyncio.sleep(3600)  # Refresh every hour (3600 seconds)


async def prompt_user_response(ctx, prompt_text, timeout=90):
    """Prompt a user for input within the invoking channel."""
    embed = discord.Embed(
        title="Tournament Registration",
        description=prompt_text,
        color=COLORS["info"],
    )
    await ctx.send(embed=embed)

    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel

    try:
        message = await ctx.bot.wait_for("message", timeout=timeout, check=check)
    except asyncio.TimeoutError:
        await ctx.send(
            embed=discord.Embed(
                title="⏰ Registration Timed Out",
                description=(
                    "No response received in time. Please run the command again "
                    "when you're ready."
                ),
                color=COLORS["error"],
            )
        )
        return None

    return message.content.strip()


async def prompt_nonempty_response(ctx, prompt_text, timeout=90, attempts=3):
    """Prompt until a non-empty response is supplied or attempts are exhausted."""
    for attempt in range(attempts):
        response = await prompt_user_response(ctx, prompt_text, timeout=timeout)
        if response is None:  # Timed out
            return None
        if response.strip():
            return response.strip()
        if attempt < attempts - 1:
            await ctx.send(
                embed=discord.Embed(
                    title="⚠️ Invalid Response",
                    description="Please provide a valid response to continue.",
                    color=COLORS["error"],
                )
            )

    await ctx.send(
        embed=discord.Embed(
            title="❌ Registration Cancelled",
            description="Too many invalid responses were provided.",
            color=COLORS["error"],
        )
    )
    return None


def normalize_signup_choice(response_text):
    """Normalise a player's signup choice to solo or duo."""
    if not response_text:
        return None
    cleaned = response_text.strip().lower()
    solo_keywords = {"solo", "alone", "single", "just me"}
    duo_keywords = {"duo", "pair", "friend", "with friend", "with a friend"}

    if cleaned in solo_keywords:
        return "solo"
    if cleaned in duo_keywords:
        return "duo"
    return None


def build_partner_metadata(guild, partner_input):
    """Extract partner metadata (id, name, mention) from raw input."""
    if not partner_input:
        return {"partner_id": None, "partner_name": "", "partner_mention": None}

    cleaned = partner_input.strip()
    match = re.match(r"<@!?(\d+)>", cleaned)
    partner_id = None
    if match:
        try:
            partner_id = int(match.group(1))
        except ValueError:
            partner_id = None

    partner_name = cleaned
    partner_mention = None

    if partner_id and guild:
        member = guild.get_member(partner_id)
        if member:
            partner_name = member.display_name
            partner_mention = member.mention
        else:
            partner_mention = f"<@{partner_id}>"
    elif partner_id:
        partner_mention = f"<@{partner_id}>"

    return {
        "partner_id": partner_id,
        "partner_name": partner_name,
        "partner_mention": partner_mention,
    }


def chunk_lines_for_embed(lines, limit=900):
    """Break a list of lines into chunks suitable for Discord embed fields."""
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > limit:
            if current:
                chunks.append(current.rstrip())
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current.rstrip())
    return chunks


def current_timestamp_iso():
    """Return the current UTC timestamp formatted for storage."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# =========================
# Events
# =========================

@bot.event
async def on_ready():
    """Handle bot startup."""
    print(f"✅ {bot.user} is connected to Discord!")
    print(f"Guilds: {len(bot.guilds)}")
    # Leave unauthorized servers
    for guild in bot.guilds:
        if guild.id not in ALLOWED_GUILD_IDS:
            print(f"Leaving unauthorized server: {guild.name} ({guild.id})")
            await guild.leave()
    print("⏳ Caching hero data...")
    # Ensure caching completes before setting up background task
    success = await fetch_and_cache_hero_data()
    if success:
        print("✅ Hero data cache complete.")
    else:
        print("❌ Hero data cache failed on startup.")

    # Start background refresh task only once after initial caching
    if not hasattr(bot, "hero_refresh_task"):
        bot.hero_refresh_task = bot.loop.create_task(
            background_hero_data_refresh()
        )
        print("DEBUG: Background hero refresh task scheduled.")


@bot.event
async def on_guild_join(guild):
    if guild.id not in ALLOWED_GUILD_IDS:
        print(
            f"Bot was added to unauthorized server: {guild.name} "
            f"({guild.id}). Leaving..."
        )
        await guild.leave()
    else:
        print(f"Bot joined authorized server: {guild.name} ({guild.id})")


# ====== Restrict Bot to Specific Guilds ======
ALLOWED_GUILD_IDS = [
    1349123127006728243,
    1141162319569756230,
    1359311947291430962,
    1360066145029197914,
]


def guild_only():
    async def predicate(ctx):
        return ctx.guild and ctx.guild.id in ALLOWED_GUILD_IDS
    return commands.check(predicate)

# =========================
# Command Groups & Commands
# =========================

# ---- MLBB Command Group ----


@bot.group(name="mlbb", invoke_without_command=True)
@guild_only()
async def mlbb(ctx):
    """Main command group for MLBB features."""
    embed = discord.Embed(
        title="🏆 Mobile Legends: Bang Bang Bot",
        description="Your ultimate companion for MLBB statistics and fun!",
        color=COLORS["primary"],
    )
    embed.add_field(
        name="📊 Hero & Game Stats",
        value=(
            "• `!mlbb ranks [rank] [days]` — Top 10 hero rankings\n"
            "• `!mlbb counter [hero]` — Top 3 counters for a hero\n"
            "• `!mlbb synergy [hero]` — Synergy & anti-synergy stats\n"
            "• `!mlbb pick` — Get a random hero suggestion\n"
            "• `!mlbb role pick` — Get a random role to play"
        ),
        inline=False,
    )
    embed.add_field(
        name="🎮 Fun & Utility",
        value=(
            "• `!mlbb trivia` — Start a MLBB trivia game *(moderator-only)*\n"
            "• `!mlbb ping` — Check bot latency\n"
            "• `!mlbb uptime` — Show bot uptime\n"
            "• `!mlbb 8ball [question]` — Ask the Magic 8-Ball\n"
            "• `!mlbb roast [@user]` — Roast yourself or a friend\n"
            "• `!mlbb compliment [@user]`  - Compliment yourself or a friend\n"
            "• `!mlbb crazy` — No idea what this is... did I code that?\n"
            "• `!mlbb help` — Show detailed help for all commands"
        ),
        inline=False,
    )
    embed.add_field(
        name="🏟 Tournament Tools",
        value=(
            "• `!mlbb tourney signup` — Register as a solo or duo for events\n"
            "• `!mlbb tourney list` — Mods can review the signup list"
        ),
        inline=False,
    )
    embed.set_footer(
        text=(
            f"Requested by {ctx.author.display_name} • "
            "Use !mlbb help for more details."
        )
    )
    await ctx.send(embed=embed)


@mlbb.command(name="trivia")
@commands.has_permissions(manage_messages=True)
async def trivia(ctx):
    """Start a MLBB trivia game (moderator-only)."""
    channel_id = ctx.channel.id
    if ACTIVE_TRIVIA_GAME.get(channel_id):
        await ctx.send(embed=discord.Embed(
            title="❗ Trivia Already Running",
            description="A trivia game is already active in this channel.",
            color=COLORS["error"]
        ))
        return

    if not HERO_DETAILS_CACHE:
        await ctx.send(embed=discord.Embed(
            title="⚠️ No Heroes Cached",
            description="Hero data is not loaded yet. Please try again later.",
            color=COLORS["error"]
        ))
        return

    ACTIVE_TRIVIA_GAME[channel_id] = True
    try:
        hero_id = random.choice(list(HERO_DETAILS_CACHE.keys()))
        # Corrected path for hero_info in trivia command
        hero_info = (
            HERO_DETAILS_CACHE[hero_id]
            .get("data", {})
            .get("records", [{}])[0]
            .get("data", {})
        )
        qtype = random.choice(
            ["role", "lane", "background"]
        )  # Define qtype here

        correct_answer = None  # Initialize correct_answer
        question_text = None    # Initialize question_text

        if qtype == "role":
            role = (
                hero_info.get("hero", {})
                .get("data", {})
                .get("sortlabel", ["Unknown"])
            )
            correct_answer = role[0] if role else "Unknown"
            hero_name = HERO_ID_TO_NAME_MAP.get(hero_id, "Unknown Hero")
            question_text = (
                f"Which **role** does **{hero_name}** primarily belong to?"
            )
        elif qtype == "lane":
            lane = (
                hero_info.get("hero", {})
                .get("data", {})
                .get("roadsortlabel", ["Unknown"])
            )
            correct_answer = lane[0] if lane else "Unknown"
            hero_name = HERO_ID_TO_NAME_MAP.get(hero_id, "Unknown Hero")
            question_text = (
                f"Which **lane** is recommended for **{hero_name}**?"
            )
        elif qtype == "background":
            bg = clean_html_tags(hero_info.get("background", ""))
            hero_name = HERO_ID_TO_NAME_MAP.get(hero_id, "Unknown Hero")

            # Split background into sentences and try to pick one
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', bg)
                         if s.strip()]

            if not sentences or len(bg) < 50:  # If no sentences or too short
                qtype = "role"  # Fallback to role question
                role = (
                    hero_info.get("hero", {})
                    .get("data", {})
                    .get("sortlabel", ["Unknown"])
                )
                correct_answer = role[0] if role else "Unknown"
                question_text = (
                    f"Which **role** does **{hero_name}** primarily "
                    f"belong to?"
                )
            else:
                # Select a random sentence or a short excerpt
                chosen_excerpt = random.choice(sentences)
                if len(chosen_excerpt) > 150:  # Truncate long sentences
                    chosen_excerpt = chosen_excerpt[:150] + "..."

                correct_answer = hero_name.lower()
                question_text = (f"I am thinking of a hero whose background "
                                 f"story includes: \"*{chosen_excerpt}*\". "
                                 f"Who is this hero?")
        else:
            correct_answer = "Unknown"
            question_text = "Question type is unknown."

        if not correct_answer or not question_text:
            raise ValueError("Failed to generate trivia question.")

        embed = discord.Embed(
            title="MLBB Trivia",
            description=question_text,
            color=COLORS["info"]
        )
        await ctx.send(embed=embed)

        def check(m):
            return (
                m.channel == ctx.channel and not m.author.bot
            )

        try:
            msg = await ctx.bot.wait_for('message', timeout=30.0, check=check)
            user_answer = msg.content.strip().lower()

            similarity = fuzz.WRatio(user_answer, correct_answer.lower())
            if similarity >= 85:
                await ctx.send(
                    embed=discord.Embed(
                        title="🎉 Correct!",
                        description=(
                            f"{msg.author.mention} got it right! "
                            f"The answer was **{correct_answer.title()}**."
                        ),
                        color=COLORS["success"]
                    )
                )
            else:
                await ctx.send(
                    embed=discord.Embed(
                        title="❌ Incorrect!",
                        description=(
                            f"Sorry, {msg.author.mention}, that's incorrect. "
                            f"The correct answer was "
                            f"**{correct_answer.title()}**."
                        ),
                        color=COLORS["error"]
                    )
                )
        except asyncio.TimeoutError:
            await ctx.send(
                embed=discord.Embed(
                    title="⏰ Time's up!",
                    description="No one answered in time!",
                    color=COLORS["error"]
                )
            )
        except Exception as e:
            await ctx.send(
                embed=discord.Embed(
                    title="⚠️ Error",
                    description=f"An error occurred: {str(e)}",
                    color=COLORS["error"]
                )
            )
    except (KeyError, IndexError):
        await ctx.send(embed=discord.Embed(
            title="⚠️ Error",
            description=(
                "Failed to generate trivia question. Please try again."
            ),
            color=COLORS["error"]
        ))
    except ValueError as e:
        await ctx.send(
            embed=discord.Embed(
                title="⚠️ Error",
                description=f"Failed to generate trivia question: {e}",
                color=COLORS["error"]
            )
        )
    finally:
        ACTIVE_TRIVIA_GAME[channel_id] = False


@trivia.error
async def trivia_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            embed=discord.Embed(
                title="🚫 Permission Denied",
                description=(
                    "You need the **Manage Messages** permission to use "
                    "this command."
                ),
                color=COLORS["error"],
            )
        )
    else:
        await ctx.send(embed=discord.Embed(
            title="⚠️ Trivia Error",
            description="An error occurred while running the trivia command.",
            color=COLORS["error"]
        ))


# ---- Update Help Command ----

@mlbb.command(name="help")
async def help_command(ctx):
    """Show detailed help and support for MLBB commands."""
    embed = discord.Embed(
        title="📚 MLBB Bot Help & Support",
        description=(
            "If you need help or found a bug, please contact a "
            "server moderator (preferably anyone other than Bachkeda 😉).\n\n"
            "Below are all available MLBB bot commands and usage tips."
        ),
        color=COLORS["info"],
    )
    embed.add_field(
        name="Hero & Game Stats",
        value=(
            "`!mlbb ranks [rank] [days]` — Top 10 hero rankings.\n"
            "• `rank`: all, epic, legend, mythic, honor, glory\n"
            "• `days`: 7 or 30\n"
            "Example: `!mlbb ranks mythic 30`\n"
            "`!mlbb counter [hero]` — Top 3 counters for a hero, "
            "with details.\n"
            "`!mlbb synergy [hero]` — Synergy & anti-synergy stats "
            "for a hero.\n"
            "`!mlbb pick` — Get a random hero suggestion.\n"
            "`!mlbb role pick` — Get a random role to play."
        ),
        inline=False,
    )
    embed.add_field(
        name="Fun & Utility",
        value=(
            "`!mlbb trivia` — Start a MLBB trivia game *(moderator-only)*\n"
            "`!mlbb ping` — Check bot latency.\n"
            "`!mlbb uptime` — Show bot uptime.\n"
            "`!mlbb 8ball [question]` — Ask the Magic 8-Ball.\n"
            "`!mlbb roast` — Roast yourself or a friend.\n"
            "`!mlbb crazy` — No idea who added that\n"
            "`!mlbb help` — Show this help and support menu."
        ),
        inline=False
    )
    embed.add_field(
        name="Tournament Support",
        value=(
            "`!mlbb tourney signup` — Register as a solo or duo.\n"
            "`!mlbb tourney list` — Moderators can review signups."
        ),
        inline=False
    )
    embed.add_field(
        name="Role Commands",
        value=(
            "`!mlbb role` — Show role command help.\n"
            "`!mlbb role pick` — Get a random role to play."
        ),
        inline=False
    )
    await ctx.send(embed=embed)


@mlbb.group(name="tourney", invoke_without_command=True)
@guild_only()
async def mlbb_tourney(ctx):
    """Overview of tournament registration commands."""
    embed = discord.Embed(
        title="🏟 MLBB Tournament Registration",
        description=(
            "Each competitive team will be composed of **two duos** and "
            "**one solo** player. Register below so moderators can balance the "
            "squads."
        ),
        color=COLORS["primary"],
    )
    embed.add_field(
        name="Players",
        value=(
            "• `!mlbb tourney signup` — Register alone or with a duo partner.\n"
            "  Provide your MLBB ID and peak rank when prompted."
        ),
        inline=False,
    )
    embed.add_field(
        name="Moderators",
        value=(
            "• `!mlbb tourney list` — Review current solo and duo signups.\n"
            "  Use this when building balanced teams."
        ),
        inline=False,
    )
    embed.set_footer(
        text=(
            "Solos will be assigned by moderators to keep teams balanced. "
            "Be sure your duo partner is aware of the registration."
        )
    )
    await ctx.send(embed=embed)


@mlbb_tourney.command(name="signup")
@guild_only()
@commands.cooldown(1, 10, commands.BucketType.user)
async def tourney_signup(ctx):
    """Register as a solo player or duo for the tournament."""
    if user_already_registered(ctx.author.id):
        await ctx.send(
            embed=discord.Embed(
                title="✅ Already Registered",
                description=(
                    "You're already on the registration list. If you need to "
                    "make changes, please contact a moderator."
                ),
                color=COLORS["info"],
            )
        )
        return

    signup_choice = None
    for _ in range(3):
        response = await prompt_user_response(
            ctx,
            (
                "Are you signing up **solo** or with a **duo partner**? "
                "Please reply with `solo` or `duo`."
            ),
        )
        if response is None:
            return
        signup_choice = normalize_signup_choice(response)
        if signup_choice:
            break
        await ctx.send(
            embed=discord.Embed(
                title="⚠️ Invalid Choice",
                description="Please respond with `solo` or `duo` to continue.",
                color=COLORS["error"],
            )
        )

    if not signup_choice:
        await ctx.send(
            embed=discord.Embed(
                title="❌ Registration Cancelled",
                description=(
                    "We couldn't determine your signup type. Please run the "
                    "command again to try once more."
                ),
                color=COLORS["error"],
            )
        )
        return

    player_mlbb_id = await prompt_nonempty_response(
        ctx,
        "What's your MLBB ID? (Numbers only, no spaces)",
    )
    if player_mlbb_id is None:
        return
    player_mlbb_id = player_mlbb_id.replace(" ", "")

    player_peak_rank = await prompt_nonempty_response(
        ctx,
        "What's your **peak rank**? (e.g., Mythic, Legend V)",
    )
    if player_peak_rank is None:
        return

    timestamp = current_timestamp_iso()

    if signup_choice == "solo":
        solo_entry = {
            "signup_type": "solo",
            "discord_id": ctx.author.id,
            "display_name": ctx.author.display_name,
            "discord_tag": str(ctx.author),
            "mlbb_id": player_mlbb_id,
            "peak_rank": player_peak_rank.strip(),
            "registered_at": timestamp,
        }
        add_solo_registration(solo_entry)

        await ctx.send(
            embed=discord.Embed(
                title="✅ Solo Registration Received",
                description=(
                    f"{ctx.author.mention}, you're signed up as a **solo** player.\n"
                    f"• MLBB ID: `{player_mlbb_id}`\n"
                    f"• Peak Rank: `{player_peak_rank.strip()}`\n"
                    "Moderators will match solos with duos to balance the teams."
                ),
                color=COLORS["success"],
            )
        )
        return

    partner_name_input = await prompt_nonempty_response(
        ctx,
        "Please @mention or type the name of your duo partner.",
    )
    if partner_name_input is None:
        return

    partner_meta = build_partner_metadata(ctx.guild, partner_name_input)
    if partner_meta.get("partner_id") == ctx.author.id:
        await ctx.send(
            embed=discord.Embed(
                title="⚠️ Invalid Partner",
                description="Your duo partner can't be yourself. Please try again.",
                color=COLORS["error"],
            )
        )
        return

    partner_mlbb_id = await prompt_nonempty_response(
        ctx,
        "What's your partner's MLBB ID?",
    )
    if partner_mlbb_id is None:
        return
    partner_mlbb_id = partner_mlbb_id.replace(" ", "")

    partner_peak_rank = await prompt_nonempty_response(
        ctx,
        "What's your partner's peak rank?",
    )
    if partner_peak_rank is None:
        return

    duo_entry = {
        "signup_type": "duo",
        "primary_discord_id": ctx.author.id,
        "primary_display_name": ctx.author.display_name,
        "primary_discord_tag": str(ctx.author),
        "primary_mlbb_id": player_mlbb_id,
        "primary_peak_rank": player_peak_rank.strip(),
        "partner_discord_id": partner_meta.get("partner_id"),
        "partner_display_name": partner_meta.get("partner_name"),
        "partner_reference": partner_name_input.strip(),
        "partner_mention": partner_meta.get("partner_mention"),
        "partner_mlbb_id": partner_mlbb_id,
        "partner_peak_rank": partner_peak_rank.strip(),
        "registered_at": timestamp,
    }
    add_duo_registration(duo_entry)

    partner_label = (
        partner_meta.get("partner_mention")
        or (
            f"<@{partner_meta.get('partner_id')}>"
            if partner_meta.get("partner_id")
            else partner_meta.get("partner_name")
        )
        or partner_name_input.strip()
    )

    await ctx.send(
        embed=discord.Embed(
            title="✅ Duo Registration Received",
            description=(
                f"{ctx.author.mention}, your duo registration is locked in!\n"
                f"• You — MLBB ID: `{player_mlbb_id}`, Peak Rank: `{player_peak_rank.strip()}`\n"
                f"• Partner — {partner_label} | ID: `{partner_mlbb_id}`, "
                f"Peak Rank: `{partner_peak_rank.strip()}`\n"
                "Moderators will add solo players to complete balanced teams."
            ),
            color=COLORS["success"],
        )
    )


@mlbb_tourney.command(name="list")
@guild_only()
@commands.has_permissions(manage_messages=True)
async def tourney_list(ctx):
    """Allow moderators to inspect current tournament registrations."""
    snapshot = get_tourney_snapshot()
    solos = snapshot.get("solos", [])
    duos = snapshot.get("duos", [])

    embed = discord.Embed(
        title="🏟 Tournament Signup Overview",
        description=(
            f"**Duos:** {len(duos)} • **Solos:** {len(solos)}\n"
            "Each team uses two duos and one solo. Assign solos manually for the "
            "best balance."
        ),
        color=COLORS["info"],
        timestamp=datetime.now(timezone.utc),
    )

    solo_lines = []
    for index, entry in enumerate(solos, start=1):
        player_label = (
            f"<@{entry['discord_id']}>"
            if entry.get("discord_id")
            else entry.get("display_name")
            or entry.get("discord_tag")
            or "Unknown Player"
        )
        solo_lines.append(
            f"{index}. {player_label} — MLBB ID: `{entry.get('mlbb_id', 'N/A')}` | "
            f"Peak: `{entry.get('peak_rank', 'N/A')}`"
        )

    duo_lines = []
    for index, entry in enumerate(duos, start=1):
        primary_label = (
            f"<@{entry['primary_discord_id']}>"
            if entry.get("primary_discord_id")
            else entry.get("primary_display_name")
            or entry.get("primary_discord_tag")
            or "Unknown Player"
        )
        partner_label = (
            entry.get("partner_mention")
            or (
                f"<@{entry['partner_discord_id']}>"
                if entry.get("partner_discord_id")
                else None
            )
            or entry.get("partner_display_name")
            or entry.get("partner_reference")
            or "Unknown Partner"
        )
        duo_lines.append(
            f"{index}. {primary_label} + {partner_label}\n"
            f"   IDs: `{entry.get('primary_mlbb_id', 'N/A')}` / "
            f"`{entry.get('partner_mlbb_id', 'N/A')}` | Peaks: "
            f"`{entry.get('primary_peak_rank', 'N/A')}` / "
            f"`{entry.get('partner_peak_rank', 'N/A')}`"
        )

    if solo_lines:
        for chunk_index, chunk in enumerate(chunk_lines_for_embed(solo_lines)):
            field_name = "Solo Signups" if chunk_index == 0 else "Solo Signups (cont.)"
            embed.add_field(name=field_name, value=chunk, inline=False)
    else:
        embed.add_field(
            name="Solo Signups",
            value="No solo players have registered yet.",
            inline=False,
        )

    if duo_lines:
        for chunk_index, chunk in enumerate(chunk_lines_for_embed(duo_lines)):
            field_name = "Duo Signups" if chunk_index == 0 else "Duo Signups (cont.)"
            embed.add_field(name=field_name, value=chunk, inline=False)
    else:
        embed.add_field(
            name="Duo Signups",
            value="No duos have registered yet.",
            inline=False,
        )

    await ctx.send(embed=embed)


@tourney_list.error
async def tourney_list_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            embed=discord.Embed(
                title="🚫 Permission Required",
                description=(
                    "You need the **Manage Messages** permission to review the "
                    "tournament signup list."
                ),
                color=COLORS["error"],
            )
        )
    else:
        raise error


# ---- Hero Commands ----
@mlbb.command(name="pick")
@commands.cooldown(1, 5, commands.BucketType.user)  # 1 use per 5 seconds per
async def random_hero(ctx):
    """Randomly select a hero for players to use."""
    if not HERO_NAME_TO_ID_MAP:
        error_embed = discord.Embed(
            title="⚠️ No Heroes Cached",
            description="Hero data is not loaded yet. "
                        "Please try again later.",
            color=COLORS["error"],
        )
        await ctx.send(embed=error_embed)
        return
    hero_names = list(HERO_NAME_TO_ID_MAP.keys())
    selected_hero = random.choice(hero_names)
    embed = discord.Embed(
        title="🎲 Random Hero Selector",
        description=(
            f"**You should play:** "
            f"{HERO_ID_TO_NAME_MAP[HERO_NAME_TO_ID_MAP[selected_hero]]}"
        ),
        color=COLORS["primary"],
    )
    await ctx.send(embed=embed)


@mlbb.command(name="counter")
@commands.cooldown(1, 5, commands.BucketType.user)     # Per-user: 1 use per 5s
@commands.cooldown(2, 10, commands.BucketType.default)  # Global: 2 uses per 10
async def counter(ctx, *, hero_name: str = None):
    """
    Show top 3 counters for the specified hero using COUNTER_HERO_LIST and
    generalized reasoning. Prioritize by winrate using /api/hero-rank/.
    """
    if not HERO_NAME_TO_ID_MAP or not HERO_DETAILS_CACHE:
        embed = discord.Embed(
            title="⚠️ Hero Data Not Cached",
            description="Hero data is not loaded yet. Please try again later.",
            color=COLORS["error"],
        )
        await ctx.send(embed=embed)
        return

    if not hero_name:
        embed = discord.Embed(
            title="⚠️ Hero Name Required",
            description=(
                "Please specify a hero name. Example: `!mlbb counter Ling`"
            ),
            color=COLORS["error"],
        )
        await ctx.send(embed=embed)
        return

    hero_key = hero_name.strip().lower()
    hero_id = HERO_NAME_TO_ID_MAP.get(hero_key)

    # Fuzzy match if not found
    if not hero_id:
        # Find the closest match from HERO_NAME_TO_ID_MAP keys
        choices = list(HERO_NAME_TO_ID_MAP.keys())
        match, score = process.extractOne(hero_key, choices)
        if score >= 80:  # Accept if similarity is high enough
            hero_id = HERO_NAME_TO_ID_MAP[match]
            hero_display_name = HERO_ID_TO_NAME_MAP.get(hero_id, match.title())
        else:
            embed = discord.Embed(
                title="⚠️ Hero Not Found",
                description=(
                    f"Hero '{hero_name}' not found. Check spelling.\n"
                    "Try `!mlbb pick` for an example."
                ),
                color=COLORS["error"],
            )
            await ctx.send(embed=embed)
            return
    else:
        hero_display_name = HERO_ID_TO_NAME_MAP.get(hero_id, hero_name.title())

    # Find counters from COUNTER_HERO_LIST
    hero_counters = COUNTER_HERO_LIST.get(hero_display_name)
    if not hero_counters or not isinstance(hero_counters, dict):
        embed = discord.Embed(
            title=f"🛡️ No Counter Data for {hero_display_name}",
            description="No counter data available for this hero.",
            color=COLORS["info"],
        )
        await ctx.send(embed=embed)
        return

    counters = hero_counters.get("weak_against", [])
    if not counters:
        embed = discord.Embed(
            title=f"🛡️ No Counter Data for {hero_display_name}",
            description="No counter data available for this hero.",
            color=COLORS["info"],
        )
        await ctx.send(embed=embed)
        return

    # --- Fetch winrate data for prioritization ---
    api_url = f"{BASE_API_URL}hero-rank/?rank=all&days=7"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                response.raise_for_status()
                json_data = await response.json()
                hero_records = json_data.get("data", {}).get("records", [])
    except Exception:
        hero_records = []

    # Build a mapping: hero name (lower) -> winrate
    winrate_map = {}
    for record in hero_records:
        hero_data = record.get("data", {})
        name = (
            hero_data.get("main_hero", {})
            .get("data", {})
            .get("name", "")
        )
        win_rate = hero_data.get("main_hero_win_rate", 0)
        if name:
            winrate_map[name.strip().lower()] = win_rate

    # Sort counters by winrate (descending), fallback to original order
    def counter_sort_key(counter_name):
        return winrate_map.get(counter_name.strip().lower(), 0)

    sorted_counters = sorted(counters, key=counter_sort_key, reverse=True)
    top_counters = sorted_counters[:3]

    embed = discord.Embed(
        title=f"🛡️ Top Counters for {hero_display_name}",
        color=COLORS["primary"],
    )

    async def get_openai_reason(hero, counter):
        prompt = (
            f"In Mobile Legends, explain in 2-3 sentences why {counter} is a "
            f"strong counter to {hero}. Focus on gameplay mechanics, skills, "
            "and matchups. Avoid generic statements."
        )
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return "No detailed reason available."

    def get_group_reason(counter_hero):
        for group in counter_groups.values():
            if "heroes" in group and any(
                h.lower() == counter_hero.lower() for h in group["heroes"]
            ):
                return group["reason"]
        return None

    # Show up to 3 counters
    for idx, counter_hero in enumerate(top_counters, 1):
        counter_id = HERO_NAME_TO_ID_MAP.get(counter_hero.lower())
        counter_name = counter_hero

        # Ensure counter_id is not None before proceeding to fetch details
        if not counter_id:
            print(f"DEBUG: Skipping counter '{counter_name}' as its ID was "
                  f"not found in cache.")
            continue  # Skip this counter if its ID isn't in the map

        counter_full_data = HERO_DETAILS_CACHE.get(counter_id, {})

        # Corrected path to the nested hero data within the full detail JSON
        hero_details_for_counter = (
            counter_full_data.get("data", {})
            .get("records", [{}])[0]
            .get("data", {})
        )

        role = (
            hero_details_for_counter.get("hero", {})
            .get("data", {})
            .get("sortlabel", ["Unknown"])[0]
            if hero_details_for_counter.get("hero", {})
            .get("data", {})
            .get("sortlabel") else "Unknown"
        )
        specialties = (
            ", ".join(hero_details_for_counter.get("hero", {})
                      .get("data", {})
                      .get("speciality", []))
            if hero_details_for_counter.get("hero", {})
            .get("data", {})
            .get("speciality") else "Unknown"
        )

        # Try to get a reason from generalised_counter_reasoning
        reason = get_group_reason(counter_name)

        # If not found, use OpenAI
        if not reason or len(reason) < 15:
            reason = await get_openai_reason(hero_display_name, counter_name)

        # Skills summary (show up to 2, only names)
        skills_to_display = []
        # Correct path to heroskilllist within the cached hero_info
        heroskilllist = (
            hero_details_for_counter.get("hero", {})
            .get("data", {})
            .get("heroskilllist", [])
        )
        for group in heroskilllist:
            for skill in group.get("skilllist", []):
                if len(skills_to_display) >= 2:
                    break
                skill_name = skill.get("skillname", "Skill")
                skills_to_display.append(f"• {skill_name}")
            if len(skills_to_display) >= 2:
                break

        attributes_summary = (
            f"Key Counter Attributes: {specialties}"
            if specialties != "Unknown" else ""
        )

        # Removed winrate_display section

        field_value = (
            f"**Reason:** {reason}\n"
            f"{attributes_summary}\n"
            f"**Key Skills:**\n" +
            ("\n".join(skills_to_display) if skills_to_display
             else "No skill data.")
        )

        field_name = f"#{idx} {counter_name} ({role})"
        embed.add_field(name=field_name, value=field_value, inline=False)

    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)


@mlbb.command(name="ranks")
@commands.cooldown(1, 5, commands.BucketType.user)    # Per-user: 1 use per 5s
@commands.cooldown(2, 10, commands.BucketType.default)  # Global: 2 uses per 10
async def ranks(ctx, rank_filter: str = "all", days_filter: int = 7):
    """
    Show top 10 hero rankings.
    Usage: !mlbb ranks [rank_filter] [days_filter]
    """
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
                        (
                            (
                                "The API reported an issue in data.\n"
                                f"Message: {err_msg}"
                            )
                        )
                    )
                    error_embed = discord.Embed(
                        title="⚠️ Data Retrieval Issue",
                        description=error_desc,
                        color=COLORS["error"],
                    )
                    await ctx.send(embed=error_embed)
                    return

                if not hero_records:
                    title_rank_filter = (
                        rank_filter.capitalize()
                        if rank_filter.lower() != "all"
                        else "All Ranks"
                    )
                    embed_title = (
                        f"🏆 Top 10 Heroes - {title_rank_filter} "
                        f"({days_filter} Days)"
                    )
                    embed = discord.Embed(
                        title=embed_title,
                        description="No hero ranking data available.",
                        color=COLORS.get(
                            rank_filter.lower(), COLORS["primary"]
                        ),
                    )
                    await ctx.send(embed=embed)
                    return
                embed_color = COLORS.get(
                    rank_filter.lower(), COLORS["primary"]
                )

                if rank_filter.lower() != "all":
                    title_rank_filter = rank_filter.capitalize()
                else:
                    title_rank_filter = "All Ranks"
                embed_title = (
                    (
                        f"🏆 Top 10 Heroes - {title_rank_filter} "
                        f"({days_filter} Days)"
                    )
                )
                embed_description = "*Sorted by Win Rate (Descending)*"

                embed = discord.Embed(
                    title=embed_title,
                    description=embed_description,
                    color=embed_color,
                )
                rank_display_list = []
                medals = ["🥇", "🥈", "🥉"]

                for idx, record in enumerate(hero_records[:10]):
                    hero_data = record.get("data")
                    if hero_data:
                        name = (
                            hero_data.get("main_hero", {})
                            .get("data", {})
                            .get("name", "Unknown")
                        )
                        win_rate = hero_data.get("main_hero_win_rate", 0)
                        pick_rate = hero_data.get(
                            "main_hero_appearance_rate", 0
                        )
                        ban_rate = hero_data.get("main_hero_ban_rate", 0)

                        rank_prefix = (
                            medals[idx] if idx < 3 else f"`#{idx + 1:02}`"
                        )

                        hero_entry = (
                            f"{rank_prefix} **{name}**\n"
                            f" ▸ WR: `{win_rate:.2%}` \u200b | "
                            f"PR: `{pick_rate:.2%}` "
                            f"\u200b | BR: `{ban_rate:.2%}`"
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
                    f"Requested by {ctx.author.display_name}"
                )
                embed.set_footer(text=footer_text)
                await ctx.send(embed=embed)

    except aiohttp.ClientResponseError as e:
        error_embed = discord.Embed(
            title="⚠️ API Request Error (Ranks)",
            description=(f"The API returned an error: {e.status} {e.message}"),
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


@mlbb.command(name="synergy")
@commands.cooldown(1, 5, commands.BucketType.user)     # Per-user: 1 use per 5s
@commands.cooldown(2, 15, commands.BucketType.default)  # Global: 2 uses per 15
async def mlbb_synergy(ctx, *, hero_name: str = None):
    """
    Show advanced synergy and anti-synergy stats for a hero, including
    best/worst partners, win/appearance rates, and time-segment trends.
    Usage: !mlbb synergy [hero]
    """
    if not HERO_NAME_TO_ID_MAP or not HERO_DETAILS_CACHE:
        await ctx.send(embed=discord.Embed(
            title="⚠️ Hero Data Not Cached",
            description="Hero data is not loaded yet. Please try again later.",
            color=COLORS["error"],
        ))
        return

    if not hero_name:
        await ctx.send(embed=discord.Embed(
            title="⚠️ Hero Name Required",
            description=(
                "Please specify a hero name. Example: `!mlbb synergy Ling`"
            ),
            color=COLORS["error"],
        ))
        return

    hero_key = hero_name.strip().lower()
    hero_id = HERO_NAME_TO_ID_MAP.get(hero_key)

    # Fuzzy match if not found
    if not hero_id:
        choices = list(HERO_NAME_TO_ID_MAP.keys())
        match, score = process.extractOne(hero_key, choices)
        if score >= 80:
            hero_id = HERO_NAME_TO_ID_MAP[match]
            hero_display_name = HERO_ID_TO_NAME_MAP.get(hero_id, match.title())
        else:
            await ctx.send(embed=discord.Embed(
                title="⚠️ Hero Not Found",
                description=f"Hero '{hero_name}' not found. Check spelling.",
                color=COLORS["error"],
            ))
            return
    else:
        hero_display_name = HERO_ID_TO_NAME_MAP.get(hero_id, hero_name.title())

    api_url = f"{BASE_API_URL}hero-detail-stats/{hero_id}/"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                response.raise_for_status()
                json_data = await response.json()
    except Exception as e:
        await ctx.send(embed=discord.Embed(
            title="⚠️ API Error",
            description=f"Failed to fetch synergy data: {e}",
            color=COLORS["error"],
        ))
        return

    records = json_data.get("data", {}).get("records", [])
    if not records:
        await ctx.send(embed=discord.Embed(
            title="⚠️ No Synergy Data",
            description="No synergy data found for this hero.",
            color=COLORS["error"],
        ))
        return

    hero_stats = records[0]["data"]
    main_win = hero_stats.get("main_hero_win_rate", 0)
    main_pick = hero_stats.get("main_hero_appearance_rate", 0)
    main_ban = hero_stats.get("main_hero_ban_rate", 0)
    sub_hero = hero_stats.get("sub_hero", [])
    sub_hero_last = hero_stats.get("sub_hero_last", [])

    def format_time_segments(h):
        # Collect all min_win_rate* fields
        segments = []
        for k in [
            "min_win_rate6_8", "min_win_rate8_10", "min_win_rate10_12",
            "min_win_rate12_14", "min_win_rate14_16", "min_win_rate16_18",
            "min_win_rate18_20", "min_win_rate20"
        ]:
            if k in h:
                segments.append(f"`{k[12:].replace('_', '-')}`: {h[k]:.2%}")
        return " | ".join(segments) if segments else "No time-segment data."

    embed = discord.Embed(
        title=f"🤝 Synergy Stats for {hero_display_name}",
        description=(
            f"**Win Rate:** `{main_win:.2%}` | "
            f"Pick Rate: `{main_pick:.2%}` | "
            f"Ban Rate: `{main_ban:.2%}`\n"
            f"Top synergy and anti-synergy partners below.\n\n"
            f"**What is 'Win Rate by Time'?**\n"
            "Shows how the win rate for the hero pairing changes depending on "
            "how long the match lasts. "
            "For example, `14-16` means the win rate when games last between "
            "14 and 16 minutes."
        ),
        color=COLORS["primary"],
    )

    # Top synergy partners
    if sub_hero:
        for h in sub_hero[:3]:
            heroid = h.get("heroid")
            name = HERO_ID_TO_NAME_MAP.get(str(heroid), f"ID {heroid}")
            wr = h.get("hero_win_rate", 0)
            pr = h.get("hero_appearance_rate", 0)
            wr_diff = h.get("increase_win_rate", 0)
            time_seg = format_time_segments(h)
            embed.add_field(
                name=f"🟢 {name} (+{wr_diff:.2%} WR)",
                value=(
                    f"Win Rate: `{wr:.2%}` | Appearance: `{pr:.2%}`\n"
                    f"Win Rate by Time: {time_seg}"
                ),
                inline=False,
            )
    else:
        embed.add_field(
            name="🟢 No strong synergy partners found.",
            value="No positive synergy data.",
            inline=False,
        )

    # Top anti-synergy partners
    if sub_hero_last:
        for h in sub_hero_last[:2]:
            heroid = h.get("heroid")
            name = HERO_ID_TO_NAME_MAP.get(str(heroid), f"ID {heroid}")
            wr = h.get("hero_win_rate", 0)
            pr = h.get("hero_appearance_rate", 0)
            wr_diff = h.get("increase_win_rate", 0)
            time_seg = format_time_segments(h)
            embed.add_field(
                name=f"🔴 {name} ({wr_diff:.2%} WR)",
                value=(
                    f"Win Rate: `{wr:.2%}` | Appearance: `{pr:.2%}`\n"
                    f"Win Rate by Time: {time_seg}"
                ),
                inline=False,
            )
    else:
        embed.add_field(
            name="🔴 No negative synergy partners found.",
            value="No anti-synergy data.",
            inline=False,
        )

    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)


@mlbb.command(name="roast")
@commands.cooldown(1, 10, commands.BucketType.user)   # Per-user: 1 use per 10s
@commands.cooldown(2, 20, commands.BucketType.default)  # Global: 2 uses per 20
async def roast(ctx, member: discord.Member = None):
    """
    Delivers a hilarious roast to a user or the invoker.
    Usage: !mlbb roast [optional @user]
    """
    roast_lines = [
        "Your win rate is so low, even AFK players question your dedication.",
        "I've seen better rotations from a broken washing machine.",
        "You play so safe, you make Estes look aggressive.",
        "Your KDA is so bad, even your teammates think you're an enemy spy.",
        "I bet you play without a mini-map, don't you?",
        "You're the reason they invented the surrender button.",
        "Did you accidentally pick a support and then forget to support?",
        "Your micro skills are worse than a broken joystick.",
        "You're like a walking bush: always there, never useful.",
        "If MLBB was a school, you'd be held back a rank.",
        "I've seen better ganks from a minion wave.",
        "Your last hit game is so weak, even the jungle creeps laugh at you.",
        "You ping 'Request Backup' more often than you use your ult.",
        "Even Layla has better escape skills than you.",
        "You die so much, they should call you 'Respawn Timer'.",
        "Your turret dives are bolder than your life choices.",
        "I've seen slower internet connections than your reaction time."
    ]

    chosen_roast = random.choice(roast_lines)

    if member:
        # If a member is mentioned, roast them
        embed = discord.Embed(
            title="🔥 Roast Session! 🔥",
            description=f"{member.mention}, {chosen_roast}",
            color=COLORS["primary"]  # Or a 'roast' specific color
        )
    else:
        # If no member is mentioned, roast the invoker
        embed = discord.Embed(
            title="🔥 Self-Roast! 🔥",
            description=f"{ctx.author.mention}, {chosen_roast}",
            color=COLORS["primary"]
        )

    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)


@mlbb.command(name="crazy")
@commands.cooldown(1, 10, commands.BucketType.user)  # 1 use per 10 seconds per
async def mlbb_crazy(ctx):
    """Responds with the 'crazy' copypasta."""
    lines = [
        "Crazy?",
        "I was crazy once",
        "They locked me in a room",
        "A rubber room",
        "A rubber room with rats",
        "And rats make me crazy!"
    ]
    await ctx.send("\n".join(lines))


@mlbb.command(name="8ball")
@commands.cooldown(1, 5, commands.BucketType.user)  # 1 use per 5 seconds per
async def eightball(ctx, *, question: str):
    """
    Ask the Magic 8-Ball a question.
    Usage: !mlbb 8ball [your question]
    """
    responses = [
        "It is certain.",
        "It is decidedly so.",
        "Without a doubt.",
        "Yes, definitely.",
        "You may rely on it.",
        "As I see it, yes.",
        "Most likely.",
        "Outlook good.",
        "Yes.",
        "Signs point to yes.",
        "Reply hazy, try again.",
        "Ask again later.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Concentrate and ask again.",
        "Don't count on it.",
        "My reply is no.",
        "My sources say no.",
        "Outlook not so good.",
        "Very doubtful."
    ]

    if not question.endswith("?"):
        embed = discord.Embed(
            title="❓ Invalid Question",
            description=(
                "Please ask a question that ends with a question mark (?)."
            ),
            color=COLORS["error"]
        )
        await ctx.send(embed=embed)
        return

    response = random.choice(responses)

    embed = discord.Embed(
        title="🎱 Magic 8-Ball Says...",
        description=f"**Question:** {question}\n**Answer:** {response}",
        color=COLORS["info"]
    )
    embed.set_footer(text=f"Asked by {ctx.author.display_name}")
    await ctx.send(embed=embed)


@mlbb.command(name="uptime")
async def mlbb_uptime(ctx):
    """Show how long the bot has been running."""
    uptime_seconds = int(time.time() - bot_start_time)
    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = (
        f"{days}d {hours}h {minutes}m {seconds}s"
        if days else f"{hours}h {minutes}m {seconds}s"
    )
    embed = discord.Embed(
        title="⏱️ Bot Uptime",
        description=f"The bot has been running for **{uptime_str}**.",
        color=COLORS["info"],
    )
    await ctx.send(embed=embed)

# ---- Role Command Group ----


@mlbb.group(name="role", invoke_without_command=True)
async def mlbb_role(ctx):
    """Group for role-related commands."""
    embed = discord.Embed(
        title="🎭 MLBB Role Commands",
        description="Use `!mlbb role pick` to get a random role.",
    )
    await ctx.send(embed=embed)


@mlbb_role.command(name="pick")
async def mlbb_role_pick(ctx):
    """Randomly select a role for the player."""
    roles = ["Tank", "Fighter", "Assassin", "Mage", "Marksman", "Support"]
    selected_role = random.choice(roles)
    embed = discord.Embed(
        title="🎲 Random Role Selector",
        description=f"**You should play:** {selected_role}",
        color=COLORS["primary"],
    )
    await ctx.send(embed=embed)


@mlbb.command(name="compliment")
@commands.cooldown(1, 10, commands.BucketType.user)  # 1 use per 10 seconds
async def compliment(ctx, member: discord.Member = None):
    """
    Delivers a wholesome compliment to a user or the invoker.
    Usage: !mlbb compliment [optional @user]
    """
    compliment_lines = [
        "Your map awareness is sharper than a Ling dash!",
        "You support your team better than Estes on a healing spree.",
        "Your rotations are smoother than Lancelot's dashes.",
        "You make every game feel like a Mythic rank match.",
        "Your positivity is more contagious than Angela's heartguard.",
        "You land skills as precisely as Selena's arrows.",
        "Your teamfights are legendary—like a Lord steal at 20 minutes.",
        "You inspire your squad more than a Franco hook lands.",
        "You farm gold faster than a jungle emblem on steroids.",
        "You bring more joy to the team than a Layla with full build.",
        "Your shotcalling is as clear as Kagura's umbrella path.",
        "You make even defeat feel like a victory.",
        "You dodge skills better than Wanwan in crossbow mode.",
        "Your presence is as game-changing as a surprise Lord push.",
        "You’re the MVP, even when the scoreboard disagrees.",
        "You make every hero look S-tier.",
        "Your gameplay is the real highlight of the match!"
    ]

    chosen_compliment = random.choice(compliment_lines)

    if member:
        # Compliment the mentioned member
        embed = discord.Embed(
            title="🌟 Compliment Time! 🌟",
            description=f"{member.mention}, {chosen_compliment}",
            color=COLORS["success"]
        )
    else:
        # Compliment the invoker
        embed = discord.Embed(
            title="🌟 Self-Compliment! 🌟",
            description=f"{ctx.author.mention}, {chosen_compliment}",
            color=COLORS["success"]
        )

    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)


@compliment.error
async def compliment_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏳ Slow Down!",
            description=(
                "That command is on cooldown. "
                f"Try again in `{error.retry_after:.1f}` seconds."
            ),
            color=COLORS["error"]
        )
        await ctx.send(embed=embed)


@roast.error
async def roast_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏳ Whoa There!",
            description=(
                "Roast is on cooldown. "
                f"Try again in `{error.retry_after:.1f}` seconds."
            ),
            color=COLORS["error"]
        )
        await ctx.send(embed=embed)


@mlbb_crazy.error
async def crazy_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏳ Not So Fast!",
            description=(
                "That command is on cooldown. "
                f"Try again in `{error.retry_after:.1f}` seconds."
            ),
            color=COLORS["error"]
        )
        await ctx.send(embed=embed)


@eightball.error
async def eightball_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏳ Magic 8-Ball Needs a Break!",
            description=(
                f"Try again in `{error.retry_after:.1f}` seconds."
            ),
            color=COLORS["error"]
        )
        await ctx.send(embed=embed)


@mlbb.command(name="ping")
async def mlbb_ping(ctx):
    """Check bot latency."""
    latency = ctx.bot.latency * 1000  # Convert to ms
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: `{latency:.2f} ms`",
        color=COLORS["info"]
    )
    await ctx.send(embed=embed)

# =========================
# Run the Bot
# =========================

if __name__ == "__main__":
    if TOKEN is None:
        print("❌ DISCORD_TOKEN not found in environment variables.")
    else:
        bot.run(TOKEN)
