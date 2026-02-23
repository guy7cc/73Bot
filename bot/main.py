import os
import asyncio
import discord
from discord.ext import commands
import requests

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://tts-backend:8000")

if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable not set. Please check your .env file.")

class TTSBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        try:
            await self.tree.sync()
            print("Slash commands synced successfully.")
        except Exception as e:
            print(f"Failed to sync slash commands: {e}")

    async def on_ready(self):
        print(f"Logged in as {self.user.name} ({self.user.id})")
        print("Bot is ready and listening.")

bot = TTSBot()

@bot.tree.command(name="join", description="ボイスチャンネルに接続します")
async def join_command(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("ボイスチャンネルに接続してから実行してください。", ephemeral=True)
        return
    
    channel = interaction.user.voice.channel
    try:
        # Ignore response timeout by immediate defer if logic might be slow, 
        # but connect is usually fast.
        if interaction.guild.voice_client is None:
            await channel.connect()
            await interaction.response.send_message(f"{channel.name} に接続しました！")
        else:
            await interaction.guild.voice_client.move_to(channel)
            await interaction.response.send_message(f"{channel.name} に移動しました！")
    except Exception as e:
        await interaction.response.send_message(f"接続エラー: {e}")

@bot.tree.command(name="leave", description="ボイスチャンネルから退出します")
async def leave_command(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client:
        await voice_client.disconnect()
        await interaction.response.send_message("退出しました。")
    else:
        await interaction.response.send_message("現在ボイスチャンネルに接続していません。", ephemeral=True)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Process audio only if the bot is in a voice channel
    voice_client = message.guild.voice_client
    if voice_client and voice_client.is_connected():
        text = message.clean_content
        if not text:
            return

        def fetch_audio(t):
            res = requests.post(f"{BACKEND_URL}/synthesize", params={"text": t}, timeout=30)
            res.raise_for_status()
            return res.content

        try:
            # Block the caller asynchronously, keeping discord loop alive
            audio_data = await bot.loop.run_in_executor(None, fetch_audio, text)
            
            filename = f"temp_{message.id}.wav"
            with open(filename, "wb") as f:
                f.write(audio_data)

            # Cleanup the temporary wave file after play finishes
            def after_play(error):
                try:
                    if os.path.exists(filename):
                        os.remove(filename)
                except Exception as e:
                    print(f"Failed to delete {filename}: {e}")
                if error:
                    print(f"Player error: {error}")

            if voice_client.is_playing():
                voice_client.stop()
                
            audio_source = discord.FFmpegPCMAudio(filename)
            voice_client.play(audio_source, after=after_play)

        except Exception as e:
            print(f"Error generating/playing TTS: {e}")

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
