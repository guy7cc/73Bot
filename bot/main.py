import discord
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
BACKEND_URL = os.getenv('BACKEND_URL', 'http://tts-backend:8000')

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logging.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logging.info('------')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong! TTS Bot is alive.')

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined {channel.name}")
    else:
        await ctx.send("You are not connected to a voice channel.")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
        await ctx.send("Disconnected from voice channel.")
    else:
        await ctx.send("I'm not in a voice channel.")

if __name__ == '__main__':
    if not TOKEN or TOKEN == "your_discord_bot_token_here":
        logging.error("DISCORD_TOKEN is not set or is still the default. Please configure .env")
    else:
        bot.run(TOKEN)
