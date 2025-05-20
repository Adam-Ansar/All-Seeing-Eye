import json
import os
import random
from dotenv import load_dotenv
import re  # Required for cleaning HTML tags from skill descriptions

import aiohttp
import discord
from discord.ext import commands

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

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
    activity=discord.Activity(
        type=discord.ActivityType.watching, name="MLBB Statistics"
    ),
)


# =========================
# Events
# =========================


@bot.event
async def on_ready():
    """Handle bot startup."""
    print(f"✅ {bot.user} is connected to Discord!")
    print(f"Guilds: {len(bot.guilds)}")


# =========================
# Command Groups & Commands
# =========================

# ---- MLBB Command Group ----


@bot.group(name="mlbb", invoke_without_command=True)
async def mlbb(ctx):
    """Main command group for MLBB features."""
    desc = (
        "Your ultimate companion for MLBB statistics and rankings!\n\n"
        "**Available Commands:**\n"
        "`!mlbb ranks [rank] [days]` - Show top 10 hero rankings. "
        "Filters: rank = all/epic/legend/mythic/honor/glory, days = 7/30\n"
        "`!mlbb pick` - Get a random hero suggestion.\n"
        "`!mlbb role pick` - Get a random role to play.\n"
        "`!mlbb counter [hero]` - Show top 3 counters for a hero\n"
        "`!ping` - Check bot latency.\n"
        "`!mlbb help` - Show detailed help for all commands."
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
    """Show detailed help and support for MLBB commands."""
    embed = discord.Embed(
        title="📚 MLBB Bot Help & Support",
        description=(
            "If you need help or found a bug, please contact a "
            "server moderator "
            "(preferably anyone other than Bachkeda 😉).\n\n"
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
            "`!mlbb counter [hero]` — Top 3 counters for a hero,\n"
            "with details.\n"
            "`!mlbb pick` — Get a random hero suggestion.\n"
            "`!mlbb role pick` — Get a random role to play."
        ),
        inline=False,
    )
    embed.add_field(
        name="Utility",
        value=(
            "`!mlbb ping` — Check bot latency.\n"
            "`!mlbb help` — Show this help and support menu."
        ),
        inline=False,
    )
    embed.set_footer(
        text="For more help, contact a server moderator (just not Bachkeda)."
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
                # The API returns a dict: { "ID": "HeroName", ... }
                if isinstance(data, dict) and data:
                    hero_names = list(data.values())
                else:
                    print(
                        "API hero list is not a dict or is empty. Response:",
                        data
                    )
                    hero_names = []

                if not hero_names:
                    error_embed = discord.Embed(
                        title="⚠️ No Heroes Found",
                        description=(
                            "Could not retrieve hero list from the API."
                        ),
                        color=COLORS["error"],
                    )
                    await ctx.send(embed=error_embed)
                    return

                selected_hero = random.choice(hero_names)
                embed = discord.Embed(
                    title="🎲 Random Hero Selector",
                    description=f"**You should play:** {selected_hero}",
                    color=COLORS["primary"],
                )
                await ctx.send(embed=embed)
    except aiohttp.ClientError as e:
        print(f"AIOHTTP ClientError in random_hero: {e}")
        error_embed = discord.Embed(
            title="⚠️ API Error During Hero Pick",
            description="Could not fetch hero list from the API.",
            color=COLORS["error"],
        )
        await ctx.send(embed=error_embed)
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError in random_hero: {e}")
        error_embed = discord.Embed(
            title="⚠️ Oops! Something Went Wrong During Hero Pick",
            description=f"An unexpected error occurred: {e}",
            color=COLORS["error"],
        )
        await ctx.send(embed=error_embed)
        

@mlbb.command(name="ranks")
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
                    f"Requested by {ctx.author.display_name} • "
                    f"Data from api-mobilelegends.vercel.app"
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


# ---- Counter Command ----


@mlbb.command(name="counter")
async def counter(ctx, *, hero_name: str = None):
    """Show top 3 counters for the specified hero with hero details."""

    print(
        f"DEBUG: !mlbb counter command received with hero_name='{hero_name}'"
    )
    if not hero_name:
        embed = discord.Embed(
            title="⚠️ Hero Name Required",
            description=(
                "Please specify a hero name. Example: `!counter Ling`"
            ),
            color=COLORS["error"],
        )
        await ctx.send(embed=embed)
        return

    # Use a single session for all API calls within this command
    async with aiohttp.ClientSession() as session:
        try:
            # --- Fetch hero list from API ---
            api_url = f"{BASE_API_URL}hero-list/"
            print(f"DEBUG: Fetching hero list from: {api_url}")
            async with session.get(api_url) as response:
                response.raise_for_status()  # Ensure success for hero list
                api_data = await response.json()
                print(f"DEBUG: Hero List API raw data (first 500 chars): "
                      f"{str(api_data)[:500]}")

            name_to_id_map = (
                {v.strip().lower(): k for k, v in api_data.items()}
                if isinstance(api_data, dict) else {}
            )
            id_to_name_map = (
                {k: v for k, v in api_data.items()}
                if isinstance(api_data, dict) else {}
            )

            print(f"DEBUG: name_to_id_map size: {len(name_to_id_map)}")
            print(f"DEBUG: id_to_name_map size: {len(id_to_name_map)}")

            hero_id = name_to_id_map.get(hero_name.strip().lower())
            print(f"DEBUG: Requested hero_name: '{hero_name}', "
                  f"resolved hero_id: '{hero_id}'")
            if not hero_id:
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

            try:
                hero_id_int = int(hero_id)
            except ValueError:
                print(f"ERROR: Hero ID '{hero_id}' could not be "
                      f"converted to integer.")
                embed = discord.Embed(
                    title="⚠️ Internal Error",
                    description="Hero ID could not be converted to integer.",
                    color=COLORS["error"],
                )
                await ctx.send(embed=embed)
                return

            # --- Fetch Main Hero Detail Data (relations & reasons) ---
            main_hero_detail_data = None
            main_hero_relation_data = None
            detail_url = f"{BASE_API_URL}hero-detail/{hero_id_int}/"
            print(f"DEBUG: Fetching main hero detail from: {detail_url}")
            try:
                async with session.get(detail_url) as response:
                    response.raise_for_status()  # Ensure success
                    detail_data = await response.json()
                    main_hero_detail_data = (
                        detail_data.get("data", {})
                        .get("records", [{}])[0]
                        .get("data", {})
                    )
                    main_hero_relation_data = main_hero_detail_data.get(
                        "relation"
                    )
                    print(f"DEBUG: Main hero detail API raw data "
                          f"(first 500 chars): {str(detail_data)[:500]}")
                    print(f"DEBUG: Extracted main_hero_relation_data: "
                          f"{main_hero_relation_data}")
            except aiohttp.ClientResponseError as e:
                print(f"ERROR: API Response Error (Main Hero Detail): "
                      f"Status={e.status}, Message={e.message}")
            except aiohttp.ClientError as e:
                print(f"ERROR: API Network Error (Main Hero Detail): {e}")
            except json.JSONDecodeError:
                print("ERROR: Invalid JSON response from Main Hero Detail "
                      "API.")
            except Exception as e:
                print(
                    f"ERROR: Unexpected error fetching Main Hero Detail: {e}"
                )

            # --- Fetch Counter Hero List ---
            counter_url = f"{BASE_API_URL}hero-counter/{hero_id_int}/"
            print(f"DEBUG: Fetching Hero Counter from: {counter_url}")
            async with session.get(counter_url) as response:
                response.raise_for_status()  # Ensure success
                data = await response.json()
                print(f"DEBUG: Hero Counter raw data (first 500 chars): "
                      f"{str(data)[:500]}")

            records = data.get("data", {}).get("records", [])
            if not records or not records[0].get("data"):
                embed = discord.Embed(
                    title=f"🛡️ No Counter Data for {hero_name}",
                    description="API returned no valid counter data.",
                    color=COLORS["info"],
                )
                await ctx.send(embed=embed)
                print("DEBUG: No valid records[0].data found in "
                      "Hero Counter.")
                return

            counter_list = records[0]["data"].get("sub_hero", [])
            print(f"DEBUG: Initial counter_list length from API: "
                  f"{len(counter_list)}")

            # --- Filter out self-counters and duplicates ---
            valid_counters_for_display = []
            added_hero_ids = set()
            main_hero_id_str = str(hero_id)
            print("DEBUG: Starting counter filtering loop.")
            for counter_hero_entry in counter_list:
                counter_hero_id_from_api = counter_hero_entry.get("heroid")
                counter_hero_id_str = (
                    str(counter_hero_id_from_api)
                    if counter_hero_id_from_api is not None
                    else None
                )
                print(f"DEBUG: Processing counter item heroid: "
                      f"'{counter_hero_id_from_api}' for filtering.")
                # Skip if self-counter or invalid or duplicate
                if (
                    counter_hero_id_str == main_hero_id_str
                    or counter_hero_id_str is None
                    or counter_hero_id_str in added_hero_ids
                ):
                    print(
                        f"DEBUG: Skipping counter ID '{counter_hero_id_str}' "
                        f"(Self-counter, invalid, or duplicate)."
                    )
                    continue
                valid_counters_for_display.append(counter_hero_entry)
                added_hero_ids.add(counter_hero_id_str)
                if len(valid_counters_for_display) >= 3:
                    print("DEBUG: Collected 3 valid counters. Breaking "
                          "filtering loop.")
                    break
            print(f"DEBUG: Final valid_counters_for_display length "
                  f"after filtering: {len(valid_counters_for_display)}")
            # --- End filter ---

            if not valid_counters_for_display:
                embed = discord.Embed(
                    title=f"🛡️ No Counters for {hero_name}",
                    description="No specific counters from the API.",
                    color=COLORS["info"],
                )
                await ctx.send(embed=embed)
                print("DEBUG: No valid distinct counter heroes "
                      "after filtering.")
                return

            # --- Fetch Details for Each Counter Hero ---
            counter_hero_details = {}
            print("DEBUG: Starting fetch for each counter hero's details.")
            for counter_hero_entry in valid_counters_for_display:
                counter_heroid_str = str(counter_hero_entry.get("heroid"))
                detail_url = (
                    f"{BASE_API_URL}hero-detail/{counter_heroid_str}/"
                )
                print(f"DEBUG: Fetching detail for counter ID "
                      f"'{counter_heroid_str}' from: {detail_url}")
                try:
                    async with session.get(detail_url) as resp:
                        resp.raise_for_status()  # Ensure success
                        detail_json = await resp.json()
                        hero_data = (
                            detail_json.get("data", {})
                            .get("records", [{}])[0]
                            .get("data", {})
                        )
                        counter_hero_details[counter_heroid_str] = hero_data
                        print(f"DEBUG: Successfully fetched detail for "
                              f"'{counter_heroid_str}'.")
                except aiohttp.ClientResponseError as e:
                    print(f"ERROR: API Request Error (Counter Hero Detail "
                          f"'{counter_heroid_str}'): Status={e.status}, "
                          f"Message={e.message}")
                    counter_hero_details[counter_heroid_str] = {}
                except aiohttp.ClientError as e:
                    print(f"ERROR: API Network Error (Counter Hero Detail "
                          f"'{counter_heroid_str}'): {e}")
                    counter_hero_details[counter_heroid_str] = {}
                except json.JSONDecodeError:
                    print(f"ERROR: Invalid JSON response from Counter Hero "
                          f"Detail API for '{counter_heroid_str}'.")
                    counter_hero_details[counter_heroid_str] = {}
                except Exception as e:
                    print(f"ERROR: Unexpected error fetching detail for "
                          f"counter hero '{counter_heroid_str}': {e}")
                    counter_hero_details[counter_heroid_str] = {}
            print("DEBUG: Finished fetching all counter hero details.")

            # --- Build Embed ---
            embed = discord.Embed(
                title=f"🛡️ Top Counters for {hero_name}",
                color=COLORS["primary"],
            )

            for idx, counter_hero_entry in enumerate(
                valid_counters_for_display, 1
            ):
                counter_hero_id_from_api = counter_hero_entry.get("heroid")
                counter_hero_id_str = (
                    str(counter_hero_id_from_api)
                    if counter_hero_id_from_api is not None
                    else None
                )
                counter_hero_name = id_to_name_map.get(
                    counter_hero_id_str, "Unknown Hero (ID not in map)"
                )
                print(f"DEBUG: Building embed field for counter: "
                      f"{counter_hero_name} (ID: {counter_hero_id_str})")

                reason_text = ("Specific counter reason for this hero not "
                               "available from API.")
                if main_hero_relation_data and counter_hero_id_str:
                    strong_relations = main_hero_relation_data.get(
                        "strong", {}
                    )
                    weak_relations = main_hero_relation_data.get(
                        "weak", {}
                    )

                    strong_ids = [
                        str(x)
                        for x in strong_relations.get("target_hero_id", [])
                    ]
                    weak_ids = [
                        str(x)
                        for x in weak_relations.get("target_hero_id", [])
                    ]
                    
                    if (
                        counter_hero_id_str in strong_ids
                        and strong_relations.get("desc")
                    ):
                        reason_text = strong_relations["desc"]
                        print(f"DEBUG: Reason found (strong): {reason_text}")
                    elif (
                        counter_hero_id_str in weak_ids
                        and weak_relations.get("desc")
                    ):
                        reason_text = (
                            f"Exploits {hero_name}'s weakness: "
                            f"{weak_relations['desc']}"
                        )
                        print(f"DEBUG: Reason found (weak): {reason_text}")
                    else:
                        print(f"DEBUG: Counter ID '{counter_hero_id_str}' not "
                              f"found in strong/weak relations with desc.")
                else:
                    print(f"DEBUG: main_hero_relation_data is None "
                          f"({main_hero_relation_data}) or "
                          f"counter_hero_id_str is None.")

                # --- Extract and format Counter Hero's Key Information ---
                hero_detail_data = counter_hero_details.get(
                    counter_hero_id_str, {}
                )
                counter_hero_inner_data = (
                    hero_detail_data.get("hero", {})
                    .get("data", {})
                )
                
                role = (
                    counter_hero_inner_data.get("sortlabel", ["Unknown"])[0]
                    if counter_hero_inner_data.get("sortlabel")
                    else "Unknown"
                )
                
                specialties = (
                    ", ".join(counter_hero_inner_data.get("speciality", []))
                    if counter_hero_inner_data.get("speciality")
                    else "Unknown"
                )

                skills_to_display_list = []
                skill_tags_for_summary = []
                heroskilllist = counter_hero_inner_data.get(
                    "heroskilllist", []
                )

                for group in heroskilllist:
                    for skill in group.get("skilllist", []):
                        if len(skills_to_display_list) >= 2:
                            break
                        skill_name = skill.get("skillname", "Skill")
                        
                        skill_tags_raw = skill.get("skilltag", [])
                        tag_names = [
                            tag.get("tagname", "") for tag in skill_tags_raw
                            if tag.get("tagname")
                        ]
                        skill_tag_str_for_display = (
                            ", ".join(tag_names) if tag_names else ""
                        )
                        skill_tags_for_summary.extend(tag_names)

                        skill_desc = skill.get("skilldesc", "")
                        
                        cleaned_skill_desc = re.sub(
                            r'<font[^>]*>', '', skill_desc
                        ).replace('</font>', '')
                        skill_brief = (
                            skill_tag_str_for_display
                            or (
                                cleaned_skill_desc[:60] + "..."
                                if len(cleaned_skill_desc) > 60
                                else cleaned_skill_desc
                            )
                        )
                        skills_to_display_list.append(
                            f"**{skill_name}:** {skill_brief}"
                        )
                    if len(skills_to_display_list) >= 2:
                        break

                # Combine Specialties and Skill Tags for attributes summary
                all_attributes = list(set(
                    specialties.split(", ") + skill_tags_for_summary
                ))
                all_attributes = [
                    attr for attr in all_attributes
                    if attr and attr != "Unknown"
                ]
                attributes_summary_line = (
                    f"Key Counter Attributes: {', '.join(all_attributes)}"
                    if all_attributes else "No specific attributes."
                )
                
                # Get win rate from counter_hero_entry (from hero-counter API)
                win_rate = counter_hero_entry.get("increase_win_rate", None)
                print(f"DEBUG: Raw increase_win_rate for "
                      f"{win_rate}")

                win_rate_suffix = ""
                if isinstance(win_rate, (float, int)):
                    win_rate_suffix = (
                        f"Increases win rate by `{win_rate:.2%}`\n"
                    )
                print(f"DEBUG: win_rate_suffix for {win_rate} "
                      f"'{win_rate_suffix.strip()}'")

                # Compose value string with new order
                skills_text = "\n".join(skills_to_display_list)
                field_value = (
                    f"**Reason:** {reason_text}\n"
                    f"  {attributes_summary_line}\n"
                    f"{win_rate_suffix}"
                    f"**Key Skills:**\n{skills_text}"
                )
                print(f"DEBUG: Final field_value for {counter_hero_name} "
                      f"(first 200 chars): {field_value[:200]}")

                field_name = f"#{idx} {counter_hero_name} ({role})"
                embed.add_field(name=field_name, value=field_value,
                                inline=False)
                print(f"DEBUG: Added field for {counter_hero_name}.")

            if not embed.fields:
                embed.description = ("Could not retrieve counter details or "
                                     "found no valid counters.")
                print("DEBUG: No fields added to embed.")

            embed.set_footer(
                text=f"Requested by {ctx.author.display_name}"
            )
        finally:
            pass


# ---- Utility Commands ----


@mlbb.command(name="ping")
async def mlbb_ping(ctx):
    """Check bot latency as a subcommand of !mlbb."""
    latency = round(ctx.bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot latency: {latency}ms",
        color=COLORS["success"],
    )
    await ctx.send(embed=embed)


# ---- Role Pick Command ----

@mlbb.command(name="role")
async def role_pick(ctx, subcommand: str = None):
    """
    Randomly pick a role for the user to play.
    Usage: !mlbb role pick
    """
    if subcommand is not None and subcommand.lower() == "pick":
        roles = ["Support", "Tank", "Fighter", "Marksman", "Mage", "Assassin"]
        selected_role = random.choice(roles)
        embed = discord.Embed(
            title="🎲 Random Role Picker",
            description=f"**You should play:** {selected_role}",
            color=COLORS["primary"],
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="ℹ️ Usage: !mlbb role pick",
            description="Use `!mlbb role pick` to get a random role pick.",
            color=COLORS["info"],
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
