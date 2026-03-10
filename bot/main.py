import os
import asyncio
import discord
from discord.ext import commands
import requests
import signal
import sys
import json
import io

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

class UserSettings:
    def __init__(self, filename="user_settings.json"):
        self.filename = filename
        self.settings = {}
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
            except Exception as e:
                print(f"Error loading user settings: {e}")
                self.settings = {}

    def save(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving user settings: {e}")

    def get_voice(self, user_id: int):
        return self.settings.get(str(user_id))

    def set_voice(self, user_id: int, voice_name: str):
        self.settings[str(user_id)] = voice_name
        self.save()

class TTSBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        # Dictionary to store {guild_id: text_channel_id} mapping for TTS monitoring
        self.monitored_channels = {}
        self.user_settings = UserSettings()
        # Session for connection pooling to tts-backend
        self.session = requests.Session()

    async def setup_hook(self):
        print(f"Opus loaded: {discord.opus.is_loaded()}")
        # Check if PyNaCl is available (required for encryption)
        try:
            import nacl.secret
            print("PyNaCl (nacl) is available.")
        except ImportError:
            print("Warning: PyNaCl (nacl) is NOT available. Voice connection will likely fail.")

        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} slash commands successfully.")
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

@bot.tree.command(name="voice", description="読み上げに使用するあなたの個別のボイスを設定します")
@discord.app_commands.describe(name="利用可能なボイス名を入力または選択してください")
async def voice_command(interaction: discord.Interaction, name: str):
    try:
        # Retrieve available speakers from backend to validate
        res = requests.get(f"{BACKEND_URL}/status", timeout=10)
        res.raise_for_status()
        speakers = res.json().get("speakers", [])
        
        if name not in speakers:
            await interaction.response.send_message(f"エラー: '{name}' は利用可能なボイス一覧にありません。`/status` で確認してください。", ephemeral=True)
            return
            
        bot.user_settings.set_voice(interaction.user.id, name)
        await interaction.response.send_message(f"ボイスを `{name}` に設定しました！", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"エラーが発生しました: {e}", ephemeral=True)

@voice_command.autocomplete("name")
async def voice_autocomplete(interaction: discord.Interaction, current: str):
    try:
        res = requests.get(f"{BACKEND_URL}/status", timeout=5)
        res.raise_for_status()
        speakers = res.json().get("speakers", [])
        return [
            discord.app_commands.Choice(name=s, value=s)
            for s in speakers if current.lower() in s.lower()
        ][:25]
    except Exception:
        return []

@bot.event
async def on_voice_state_update(member, before, after):
    """
    Automatically leave the voice channel if the bot is the only human left.
    """
    voice_client = member.guild.voice_client
    if not voice_client:
        return

    # Special case: If the bot itself moved channel or disconnected, check its new channel
    # Usually we care about the channel the bot is currently in
    channel = voice_client.channel
    
    # Check current membership in the bot's channel
    # Filter to count non-bot humans
    human_members = [m for m in channel.members if not m.bot]
    
    if len(human_members) == 0:
        print(f"No humans left in {channel.name}. Auto-leaving...")
        
        # Clear monitoring for this guild
        if member.guild.id in bot.monitored_channels:
            del bot.monitored_channels[member.guild.id]
            
        await voice_client.disconnect()

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Process only if the guild is being monitored and the channel matches
    monitored_channel_id = bot.monitored_channels.get(message.guild.id)
    if not monitored_channel_id or message.channel.id != monitored_channel_id:
        return

    voice_client = message.guild.voice_client
    
    # Wait briefly if the voice client just connected but isn't fully ready
    if voice_client and not voice_client.is_connected():
        await asyncio.sleep(0.5)
        voice_client = message.guild.voice_client

    if voice_client and voice_client.is_connected():
        text = message.clean_content
        if not text:
            return

        def fetch_audio(t, speaker_name=None):
            payload = {"text": t}
            if speaker_name:
                payload["speaker"] = speaker_name
            res = bot.session.post(f"{BACKEND_URL}/synthesize", json=payload, timeout=30)
            res.raise_for_status()
            return res.content

        try:
            speaker = bot.user_settings.get_voice(message.author.id)
            audio_data = await bot.loop.run_in_executor(None, fetch_audio, text, speaker)
            
            # Use BytesIO for in-memory audio instead of writing to disk
            audio_buffer = io.BytesIO(audio_data)

            if voice_client.is_playing():
                voice_client.stop()
                
            # Play from buffer using pipe:True
            audio_source = discord.FFmpegPCMAudio(audio_buffer, pipe=True)
            voice_client.play(audio_source)

        except Exception as e:
            print(f"Error generating/playing TTS: {e}")
    else:
        # Logging for debugging why messages are skipped
        if not voice_client:
            pass # Normal case: bot not in voice
        elif not voice_client.is_connected():
            print(f"Message skipped: Voice client exists but is not connected (State: {voice_client.ws})")

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
