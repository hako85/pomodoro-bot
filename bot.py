import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
import yt_dlp

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# =====================
# 設定ファイル読み込み・保存
# =====================
SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    else:
        default_settings = {
            "focus": 25,
            "break": 5,
            "longbreak": 15,
            "interval": 4,
            "music_url": "",
            "token": "YOURTOKEN"
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(default_settings, f, indent=4)
        return default_settings

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

settings = load_settings()

# =====================
# ユーザーごとの状態管理
# =====================
class PomodoroState:
    def __init__(self):
        self.focus_count = 0
        self.current_task = None
        self.vc = None
        self.music_position = 0
        self.is_running = False
        self.audio_player = None

state = PomodoroState()

# =====================
# タイマー処理
# =====================
async def pomodoro_cycle(ctx):
    state.is_running = True
    while state.is_running:
        await start_focus(ctx)
        if not state.is_running:
            break

        state.focus_count += 1
        if state.focus_count % settings["interval"] == 0:
            await start_break(ctx, long=True)
        else:
            await start_break(ctx, long=False)

async def start_focus(ctx):
    await ctx.send(f"\U0001F525 Focus time開始！ {settings['focus']}分間集中！")
    await join_and_mute(ctx)
    await play_music(ctx, settings["music_url"])
    await asyncio.sleep(settings["focus"] * 60)
    await stop_music()
    await ctx.send("\u23F9 Focus time終了！")

async def start_break(ctx, long=False):
    minutes = settings["longbreak"] if long else settings["break"]
    await ctx.send(f"\U0001F34A Break time {minutes}分開始！")
    await unmute_all()
    await asyncio.sleep(minutes * 60)
    await ctx.send("\u23F9 Break終了！")

# =====================
# VC操作
# =====================
async def join_and_mute(ctx):
    if ctx.author.voice:
        state.vc = await ctx.author.voice.channel.connect()
        for member in ctx.author.voice.channel.members:
            if not member.bot:
                await member.edit(mute=True)

async def unmute_all():
    if state.vc:
        for member in state.vc.channel.members:
            if not member.bot:
                await member.edit(mute=False)

@bot.command()
async def leave(ctx):
    if state.vc:
        await unmute_all()
        await state.vc.disconnect()
        state.vc = None
        await ctx.send("\u274C VCから退出しました")

# =====================
# 音楽再生関連
# =====================
async def play_music(ctx, url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        audio_url = info['url']

    ffmpeg_options = {
        'options': '-vn'
    }

    if state.vc and not state.vc.is_playing():
        source = await discord.FFmpegOpusAudio.from_probe(audio_url, **ffmpeg_options)
        state.vc.play(source)
        state.audio_player = source
        await ctx.send(f"\U0001F3B5 音楽再生開始: {info.get('title', 'Unknown')}\nURL: {url}")

async def stop_music():
    if state.vc and state.vc.is_playing():
        state.vc.stop()
        state.audio_player = None

# =====================
# Botコマンド
# =====================
@bot.command()
async def start(ctx):
    if not state.is_running:
        await ctx.send("\u23F1 タイマーを開始します")
        asyncio.create_task(pomodoro_cycle(ctx))
    else:
        await ctx.send("\u2757 すでにタイマーが動いています")

@bot.command()
async def stop(ctx):
    state.is_running = False
    await stop_music()
    await unmute_all()
    await ctx.send("\u23F9 タイマーを停止しました")

@bot.command()
async def set(ctx, key: str, value):
    if key in ["focus", "break", "longbreak", "interval"]:
        try:
            settings[key] = int(value)
            save_settings(settings)
            await ctx.send(f"\u2705 {key} を {value} に設定しました")
        except ValueError:
            await ctx.send("\u274C 数値を入力してください")
    elif key == "music_url":
        settings[key] = value
        save_settings(settings)
        await ctx.send(f"\u2705 music_url を更新しました")
        if state.is_running:
            await stop_music()
            await play_music(ctx, settings["music_url"])
    else:
        await ctx.send("\u274C 無効なキーです。使用可能なキー: focus, break, longbreak, interval, music_url")

@bot.command()
async def status(ctx):
    status_msg = (
        f"\U0001F4CB **現在の設定**\n"
        f"Focus Time: {settings['focus']}分\n"
        f"Break Time: {settings['break']}分\n"
        f"Long Break Time: {settings['longbreak']}分\n"
        f"Interval: {settings['interval']}回\n"
        f"Music URL: {settings['music_url']}\n"
        f"\n\U0001F552 **現在の状態**\n"
        f"タイマー稼働中: {'はい' if state.is_running else 'いいえ'}\n"
        f"現在のFocus回数: {state.focus_count}"
    )
    await ctx.send(status_msg)

# =====================
# エラー処理
# =====================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("\u274C 不明なコマンドです")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("\u274C コマンドの引数が足りません")
    else:
        await ctx.send(f"\u274C エラーが発生しました: {str(error)}")

# =====================
# 起動
# =====================
TOKEN = settings["token"]

bot.run(TOKEN)
