import discord
from discord.ext import commands
import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables for secure token storage
load_dotenv()

# Set up the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# API URL
MLBB_API_BASE = "https://api-mobilelegends.vercel.app/api"

# API interaction functions
def fetch_heroes():
    try:
        response = requests.get(f"{MLBB_API_BASE}/heroes")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching heroes: {response.status_code}")
            return None
    except Exception as e:
        print(f"API request failed: {str(e)}")
        return None

def fetch_hero_details(hero_id):
    try:
        response = requests.get(f"{MLBB_API_BASE}/hero/{hero_id}")
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"API request failed: {str(e)}")
        return None

# Convert API hero format to our application format
def convert_heroes_data(api_heroes):
    heroes = {}
    for hero in api_heroes:
        hero_id = str(hero.get('id', '')).lower()
        heroes[hero_id] = {
            "name": hero.get('name', 'Unknown Hero'),
            "role": hero.get('role', 'Unknown'),
            "synergies": {},  # Will need to be populated based on hero relationships
            "counters": {},   # Will need to be populated based on hero relationships
            "meta_score": hero.get('difficulty', 5)  # Using difficulty as a placeholder
        }
    return heroes

# Data storage with API integration
def initialize_data():
    # Try to fetch data from API first
    api_heroes = fetch_heroes()
    
    if api_heroes:
        heroes = convert_heroes_data(api_heroes)
        with open('heroes.json', 'w') as f:
            json.dump(heroes, f, indent=4)
    elif not os.path.exists('heroes.json'):
        # Fallback to default data
        heroes = {
            "hero1": {
                "name": "Hero 1",
                "role": "Tank",
                "synergies": {"hero2": 8, "hero3": 6},
                "counters": {"hero4": 9, "hero5": 7},
                "meta_score": 7
            },
            # Add more heroes as needed
        }
        with open('heroes.json', 'w') as f:
            json.dump(heroes, f, indent=4)
    
    if not os.path.exists('meta_updates.json'):
        meta_updates = {
            "last_update": datetime.now().strftime("%Y-%m-%d"),
            "trends": [
                {
                    "trend": "Tank-heavy compositions are strong",
                    "heroes_affected": ["hero1", "hero7"],
                    "impact": "high"
                }
            ]
        }
        with open('meta_updates.json', 'w') as f:
            json.dump(meta_updates, f, indent=4)

def load_hero_data():
    with open('heroes.json', 'r') as f:
        return json.load(f)

def load_meta_updates():
    with open('meta_updates.json', 'r') as f:
        return json.load(f)

def calculate_synergy(team_comp):
    heroes = load_hero_data()
    synergy_score = 0
    interactions = 0
    
    for i, hero1 in enumerate(team_comp):
        for hero2 in team_comp[i+1:]:
            if hero1 in heroes and hero2 in heroes:
                if hero2 in heroes[hero1].get("synergies", {}):
                    synergy_score += heroes[hero1]["synergies"][hero2]
                    interactions += 1
    
    return synergy_score / max(interactions, 1)

def recommend_counters(enemy_comp):
    heroes = load_hero_data()
    counter_scores = {}
    
    for hero_id, hero_data in heroes.items():
        score = 0
        for enemy in enemy_comp:
            if enemy in hero_data.get("counters", {}):
                score += hero_data["counters"][enemy]
        if score > 0:
            counter_scores[hero_id] = score
    
    return sorted(counter_scores.items(), key=lambda x: x[1], reverse=True)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    initialize_data()

@bot.command(name='synergy')
async def synergy(ctx, *heroes):
    """Calculates synergy score for a team composition"""
    if len(heroes) < 2:
        await ctx.send("Please provide at least 2 heroes to calculate synergy.")
        return
        
    synergy_score = calculate_synergy(heroes)
    await ctx.send(f"Team synergy score: {synergy_score:.2f}/10")

@bot.command(name='counter')
async def counter(ctx, *enemy_heroes):
    """Recommends heroes to counter the enemy team"""
    if not enemy_heroes:
        await ctx.send("Please provide enemy heroes to find counters.")
        return
        
    counters = recommend_counters(enemy_heroes)
    heroes = load_hero_data()
    
    if counters:
        response = "Recommended counters:\n"
        for hero_id, score in counters[:5]:
            response += f"- {heroes[hero_id]['name']} (Counter score: {score:.2f})\n"
        await ctx.send(response)
    else:
        await ctx.send("No effective counters found.")

@bot.command(name='meta')
async def meta(ctx):
    """Shows current meta trends"""
    meta_data = load_meta_updates()
    heroes = load_hero_data()
    
    response = f"**Meta Update ({meta_data['last_update']})**\n\n"
    for trend in meta_data["trends"]:
        response += f"**{trend['trend']}**\n"
        response += f"*Impact: {trend['impact']}*\n"
        response += "Heroes affected: " + ", ".join([heroes.get(h, {}).get("name", h) for h in trend["heroes_affected"]]) + "\n\n"
    
    await ctx.send(response)

@bot.command(name='refresh')
async def refresh(ctx):
    """Refresh hero data from API"""
    await ctx.send("Refreshing hero data from Mobile Legends API...")
    initialize_data()
    await ctx.send("Hero data refreshed successfully!")

# Run the bot with token from environment variables
# Store your token in a .env file or environment variable for security
bot.run(os.getenv('DISCORD_TOKEN'))
