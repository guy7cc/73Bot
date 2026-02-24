import os
import asyncio
import discord
from discord.ext import commands
import requests
import signal
import sys

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://tts-backend:8000")

if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable not set. Please check your .env file.")

# Load Opus library for voice support on Linux
if not discord.opus.is_loaded():
    try:
        discord.opus.load_opus("libopus.so.0")
        print("Opus library loaded successfully.")
    except Exception as e:
        print(f"Warning: Failed to load Opus library: {e}")

class TTSBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        # Dictionary to store {guild_id: text_channel_id} mapping for TTS monitoring
        self.monitored_channels = {}

    async def setup_hook(self):
        print(f"Opus loaded: {discord.opus.is_loaded()}")
        # Check if PyNaCl is available (required for encryption)
        try:
            import nacl.secret
            print("PyNaCl (nacl) is available.")
        except ImportError:
            print("Warning: PyNaCl (nacl) is NOT available. Voice connection will likely fail.")

        try:
            await self.tree.sync()
            print("Slash commands synced successfully.")
        except Exception as e:
            print(f"Failed to sync slash commands: {e}")

    async def on_ready(self):
        print(f"Logged in as {self.user.name} ({self.user.id})")
        print("Bot is ready and listening.")

bot = TTSBot()

@bot.tree.command(name="join", description="ボイスチャンネルに接続し、このテキストチャンネルの読み上げを開始します")
async def join_command(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("ボイスチャンネルに接続してから実行してください。", ephemeral=True)
        return
    
    channel = interaction.user.voice.channel
    try:
        # Bind the current text channel for monitoring
        bot.monitored_channels[interaction.guild_id] = interaction.channel_id
        
        if interaction.guild.voice_client is None:
            await channel.connect()
            await interaction.response.send_message(f"{channel.name} に接続しました！このチャンネルのメッセージを読み上げます。")
        else:
            await interaction.guild.voice_client.move_to(channel)
            await interaction.response.send_message(f"{channel.name} に移動しました！これからはこのチャンネルのメッセージを読み上げます。")
    except Exception as e:
        await interaction.response.send_message(f"接続エラー: {e}")

@bot.tree.command(name="leave", description="ボイスチャンネルから退出します")
async def leave_command(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client:
        # Clear monitoring for this guild
        if interaction.guild_id in bot.monitored_channels:
            del bot.monitored_channels[interaction.guild_id]
            
        await voice_client.disconnect()
        await interaction.response.send_message("退出しました。")
    else:
        await interaction.response.send_message("現在ボイスチャンネルに接続していません。", ephemeral=True)

@bot.tree.command(name="status", description="システムの稼働状況と利用可能なボイス一覧を確認します")
async def status_command(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        res = requests.get(f"{BACKEND_URL}/status", timeout=10)
        res.raise_for_status()
        data = res.json()
        
        embed = discord.Embed(
            title="73Bot システムステータス",
            color=discord.Color.blue() if data["coeiroink_connection"] == "connected" else discord.Color.red()
        )
        embed.add_field(name="Backend", value="✅ Online", inline=True)
        embed.add_field(name="COEIROINK", value="✅ Connected" if data["coeiroink_connection"] == "connected" else "❌ Disconnected", inline=True)
        
        speakers = data.get("speakers", [])
        if speakers:
            embed.add_field(name=f"利用可能なボイス ({len(speakers)})", value="、".join(speakers[:20]) + ("..." if len(speakers) > 20 else ""), inline=False)
        else:
            embed.add_field(name="利用可能なボイス", value="見つかりませんでした。", inline=False)
            
        # Add current monitored channel info
        monitored_id = bot.monitored_channels.get(interaction.guild_id)
        if monitored_id:
            channel = bot.get_channel(monitored_id)
            channel_name = channel.name if channel else f"ID: {monitored_id}"
            embed.add_field(name="読み上げ対象チャンネル", value=channel_name, inline=False)
        else:
            embed.add_field(name="読み上げ対象チャンネル", value="設定されていません（/join を実行してください）", inline=False)

        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"ステータス取得エラー: {e}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Process only if the guild is being monitored and the channel matches
    monitored_channel_id = bot.monitored_channels.get(message.guild.id)
    if not monitored_channel_id or message.channel.id != monitored_channel_id:
        return

    voice_client = message.guild.voice_client
    if voice_client and voice_client.is_connected():
        text = message.clean_content
        if not text:
            return

        def fetch_audio(t):
            res = requests.post(f"{BACKEND_URL}/synthesize", json={"text": t}, timeout=30)
            res.raise_for_status()
            return res.content

        try:
            audio_data = await bot.loop.run_in_executor(None, fetch_audio, text)
            
            filename = f"temp_{message.id}.wav"
            with open(filename, "wb") as f:
                f.write(audio_data)

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

async def main():
    # Signal handler for graceful shutdown
    async def shutdown(sig, loop):
        print(f"Received exit signal {sig.name}...")
        
        # Disconnect all active voice clients
        for vc in bot.voice_clients:
            print(f"Disconnecting from {vc.channel.name}...")
            await vc.disconnect()
            
        # Close the bot connection
        print("Closing bot connection...")
        await bot.close()
        
        # Cancel all pending tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
        print("Shutdown complete.")
        loop.stop()

    loop = asyncio.get_running_loop()
    # Add handlers for SIGTERM and SIGINT
    # Note: On Windows, some signals might behave differently, but in Docker (Linux) this is standard.
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop)))

    try:
        await bot.start(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"Bot execution error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
