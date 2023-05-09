import re,cv2,yt_dlp,asyncio,pyttsx3,random,requests,openai,discord,os,gc,html,ast,time
import numpy as np
from discord.ext import commands
from discord import app_commands
import replicate as rp
from PIL import Image, ImageDraw, ImageFont
import speech_recognition as sr
import tensorflow as tf
import mediapipe as mp
import tensorflow_hub as hub
from bs4 import BeautifulSoup
from moviepy.editor import *
import pandas as pd
from faceRecognitionModule import FaceDetector
from pedalboard import Pedalboard, Reverb, Distortion
from pedalboard.io import AudioFile
from textblob import TextBlob
import matplotlib.pyplot as plt
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from scipy.signal import savgol_filter
from prophet import Prophet
from pandas_datareader import data as pdr
import yfinance as yf

yf.pdr_override()

# customize these fields

# unless you customize the speech to text try and make this easily/intuitively interpretable by a speech to text solution. EX: instead of 'Adum' do 'Adam'
bot_name = 'Bob'
bot_token  = os.environ['discord_bot']
currency_name = 'Dollars'

# right click server name (top left) and click copy id
server_id = 123

# right click user and hit 'copy id'
admin_id = 123

# channel to pull shared music from (for radio station)
music_channel = 123
random_image_channel = 123
main_chat = 123

# if you want to restrict what users can look up add accepted topics to this list.
news_topics = ['tech','stock market','crypto','movies','tv','videogames']
# if you want users to look up anything make the list emp'y. (news_topics = [])

# FREE news api
# get a key here: https://newsapi.org/
news_key = os.environ['news_api']

# You need an openai pay as you go key to use openai stuff.
openai.api_key = os.environ['openai_key']

# spotify API info
spotify_client_id = os.environ['spotify_client']
spotify_secret = os.environ['spotify_secret']

# Steam API for /random_game
steam_api = os.environ['steam_api']
steam_acc_id = 123

# replicat AI API.
# free key here: https://replicate.com/
replicate = rp.Client(api_token = os.environ['replicate'])

# describe what you want the bots personality to be. If unsure you can do something like 'you are a helpful assistant who loves to help people'
personality = f"You are a happy and helpful assistant. Your name is {bot_name}."
chat_history= [{"role": "system", "content": personality}]


# voice lines the radio station host / dj will say when joining the call.
dj_intros = ['Hi I am a dj this is a voice line I\'m saying to welcome you to the stream.',
             'Wow look at that another opening line to say. Feel free to customize these and add your own.',
             'Just another default stream initilization message floating on by don\'t mind me. Get your admin to change me and add more.'
             ]
# voice lines the radio station host / dj will say between songs.
dj_bridges = ['Hi I am a dj this is a voice line.',
              'Wasn\'t that last song great? Up Next we have',
              'I\'m craving homemade chicken cordon bleu. Wonderful stuff. Customize these or add your own.'
              ]
# voice lines played when introducing recommended songs {} will be formatted as the users name
dj_recomended = ['This is a song that {} recommended. Thanks {}',
                 "{} called in and wanted to change the vibe up a bit so without further a do",
                 "Here's a little something brought to us by {}"]

#####################################################################################################
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~{ INITIALIZATION }~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
#####################################################################################################

# init lightweight mediapipe solution for removing / swapping backgrounds of photos. (this is so light there's no need to control its ram usage)
mp_selfie_segmentation = mp.solutions.selfie_segmentation
selfie_segmentation = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

# set intents all because I'm lazy and it's only going on my private server of close friends.
intents = discord.Intents.all()
client = commands.Bot(command_prefix='/',intents=intents)

news = dict()
loop = 0
clip = None

with open('cache/spotify_token.txt', 'r') as f:
    spotify_token = f.read()

# init our tts, set speed and voice,
engine = pyttsx3.init()
engine.setProperty('rate', 200)
engine.setProperty('voice', 'english-us')

# Youtube streaming settings (feel free to mess with these but after a lot of trouble shooting I found this works well)
# We use the url at the 5th index of info['urls']. You can try print and use different ones.                               [Change Volume]
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn -filter:a "volume=0.35"'}
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

playing_music = False
last_clip = ''
last_song = ''
recommended_songs = []
current_song_title=''
current_song_link=''
senders = []

all_fish = pd.read_csv('server_datasets/fish_data.csv',index_col=0)

try:
    music_list = pd.read_csv('server_datasets/music_dataset.csv',header=0)
except:
    music_list = pd.Series()
    print('no music dataset found. run /scrape_music')

try:
    user_stats = pd.read_csv('server_datasets/user_stats.csv',header=0,index_col=0)
except:
    user_stats = pd.DataFrame()
    print('no user stats found. run create_database()')


requests_allowed = True

take_requests = False

messages = []

#####################################################################################################
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~{ COMMANDS }~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
#####################################################################################################


@client.event
async def on_ready():
    try:
        synced = await client.tree.sync()
        print(f'synced {len(synced)} commands')
    except Exception as e:
        print(e)
    global user_stats
    print('We have logged in as {0.user}'.format(client))
    channel = client.get_channel(main_chat)
    if not os.path.isfile('fishing_levels/Server Lake/lake_map.jpg'):
        tmp = await channel.send('Building Server Lake...')
        await handle_new_lake(tmp,'Server Lake')
    if not os.path.isfile('server_datasets/user_stats.csv'):
        #tmp = await channel.send('Building user database...')
        user_stats = await create_user_stats()
    if not os.path.isfile('server_datasets/music_dataset.csv'):
        tmp = await channel.send('Scraping music channel...')
        await handle_scrape_music(tmp)

client.remove_command('help')

@client.tree.command(name="help_news",description="Explanation on how to use /news.")
async def help_news(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    embed = discord.Embed(title=f'News Help', description='/news has a few subcommands, here they are.', color=0x00ff00)
    embed.add_field(name='📰 /news', value='Retrieves and embeds the latest top 3 most popular articles.', inline=False)
    embed.add_field(name='📰 /news explain x', value='Where `x` is a number from 1 to 3. This will webscrape the url and print the contents of the article.', inline=False)
    embed.add_field(name='📰 /news more', value='Shows more articles continuing to sort by popularity.', inline=False)
    embed.add_field(name='📰 /news <topic>', value='Retrieves and embeds the latest top 3 most popular articles about a given topic.', inline=False)

    await ctx.send(embed=embed)

@client.tree.command(name="help_video_editing",description="Explanation on how to use /editor.")
async def help_video_editing(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    embed = discord.Embed(title=f'Video Editor Help', description='/editor has a lot of commands, here they are:', color=0x00ff00)
    embed.add_field(name='🎦 /editor load <link>', value='Loads the video you will be working with.', inline=False)
    embed.add_field(name='🎦 /editor save', value='Saves the output video as the working video.\nThis way you don\'t have to reload the original video over and over if you mess up.', inline=False)
    embed.add_field(name='🎦 /editor stats', value='Send stats of the video, bit rate, size, length, and resolution.', inline=False)
    embed.add_field(name='🎦 /editor fx <method> <factor>', value='A couple ways to manipulate the video.(more being added)\n`/editor fx speed 5` multiplies video speed by 5.\n`/editor fx loop 5` loops the video for 5 seconds.\n`/editor fx loop None 5` loops the video 5 times.', inline=False)
    embed.add_field(name='🎦 /editor top_text "text" <size> <color> <font>', value='Adds top text to video (default is Impact) Font is automatically fit to video width and wrapped.\n`/editor top_text "hello world" 50 red impact.ttf` adds red impact size 50 font to the top of the video,\nsize,color,and font parameter can be left blank, those are the default values.\nTo use other fonts they must be downloaded and placed in the bots working directory.', inline=False)
    embed.add_field(name='🎦 /editor bottom_text "text" <size> <color> <font>', value='Same thing but bottom text.', inline=False)
    embed.add_field(name='🎦 /editor clip <start_time> <end_time>', value='Clips working video. \n`/editor clip 0 10` takes the first 10 seconds.', inline=False)
    embed.add_field(name='🎦 /editor compress <method> <arg1> <arg2>', value='Means for compressing videos.\n`/editor compress b` compression via bitrate reduction. Leaving arg 1 blank will aim for a target size of ~25mb. `/editor compress b 8` will aim for 8 mb.\n`/editor compress r` Lower the resolution. By default it halves it but can be specified through arg 1 and 2.\n`/editor compress r 0.33` will make a resolution one third the original.\n`/editor compress r 1920 1080` resizes to 1920x1080', inline=False)
    embed.add_field(name='🎦 /editor replace_audio <link> <priority>', value='Replaces audio of working video with audio from video you link to.\nLeave empty to remove audio.\nThe priority argument can be passed as `a` or `v`\n`v` will make the duration fit the video, `a` will make the duration fit the audio. Default is `a`.\n', inline=False)
    embed.add_field(name='❗ *NOTE:*', value='Codec is h.264 with medium preset and a crf of 23. Discord doesn\'t support 265 and vp9 and av1 are too slow.\nMore fx will be added. Extreme speeding of the video can occasionally corrupt audio and may prevent you from doing other tasks. Remove the audio using audio_replace to modify further.\nDiscord bots have a max upload of 8mb. If you can not compress it further, ask if an admin can fish it out of the working directory.', inline=False)

    await ctx.send(embed=embed)

@client.tree.command(name="news",description="Leave arguments blank for top headlines.")
@app_commands.describe(sub_cmd = "<topic>/more/explain")
@app_commands.describe(article_cmd = "1-3")
async def news(interaction:discord.Interaction, sub_cmd:str = '', article_cmd:int = 1):
    ctx = await commands.Context.from_interaction(interaction)
    await handle_news(ctx,sub_cmd,article_cmd)

@client.tree.command(name="talk",description="Talk to chatGPT in voice chat!")
@app_commands.describe(speak_when_spoken_to = "If 'yes' then it will only answer you when it hears its name.")
async def speak_when_spoken_to(interaction:discord.Interaction, speak_when_spoken_to:str = ''):
    if speak_when_spoken_to.lower() == 'yes': swst = True
    else:swst=False
    ctx = await commands.Context.from_interaction(interaction)
    if ctx.message.author.id == admin_id:
        async with ctx.typing():
            await handle_voice_channel(ctx.message, speak_when_spoken_to=swst)
    else:
        async with ctx.typing():
            permission = await get_permission(ctx)
            if permission:
                await handle_voice_channel(ctx.message, speak_when_spoken_to=swst)

@client.tree.command(name="chat",description="Chat with ChatGPT. Type 'bye' in message to wipe memory (or /wipe_memory)")
@app_commands.describe(message = "What do you want to say?")
async def chat(interaction:discord.Interaction, message:str):
    ctx = await commands.Context.from_interaction(interaction)
    if ctx.message.author.id == admin_id:
        async with ctx.typing():
            await handle_chat(ctx.message,message)
    else:
        async with ctx.typing():
            permission = await get_permission(ctx)
            if permission:
                await handle_chat(ctx.message, message)

@client.tree.command(name="adventure",description="Start a dnd adventure (expiremental WIP) ")
@app_commands.describe(message = "What do you want to say?")
async def adventure(interaction:discord.Interaction,message:str):
    ctx = await commands.Context.from_interaction(interaction)
    global chat_history
    chat_history = [{"role": "system", "content": f"You an excellent dungeon master who asks players what their next move is after speaking."}]
    if ctx.message.author.id == admin_id:
        async with ctx.typing():
            await handle_dm(ctx.message,message)
    else:
        async with ctx.typing():
            permission = await get_permission(ctx)
            if permission:
                await handle_dm(ctx.message,message)

@client.tree.command(name="gen_image",description="Generate image with OpenAI ")
@app_commands.describe(prompt = "Describe the image")
async def gen_image(interaction:discord.Interaction,prompt:str):
    ctx = await commands.Context.from_interaction(interaction)
    
    if ctx.message.author.id == admin_id:
        async with ctx.typing():
            await handle_generator(ctx.message,prompt)
    else:
        async with ctx.typing():
            permission = await get_permission(ctx)
            if permission:
                await handle_generator(ctx.message,prompt)

@client.tree.command(name="var_image",description="Generate a variation of an image with OpenAI (squeezed 1:1 ratio)")
@app_commands.describe(img = "Paste a link to the image")
async def var_image(interaction:discord.Interaction,img:str):
    ctx = await commands.Context.from_interaction(interaction)
    if ctx.message.author.id == admin_id:
        async with ctx.typing():
            await handle_variation(ctx.message,img)
    else:
        async with ctx.typing():
            permission = await get_permission(ctx)
            if permission:
                await handle_variation(ctx.message,img)

@client.tree.command(name="play",description="Stream a given youtube video to the voice channel (must be youtube or music.youtube link)")
@app_commands.describe(url = "Paste a youtube link")
async def play(interaction:discord.Interaction,url:str):
    ctx = await commands.Context.from_interaction(interaction)
    if ctx.message.author.id == admin_id: 
        async with ctx.typing():
            await handle_video(ctx.message,url)
    else:
        async with ctx.typing():
            permission = await get_permission(ctx)
            if permission:
                await handle_video(ctx.message,url)

@client.tree.command(name="skip",description="Skip the stream of a youtube video to the voice channel.")
async def skip(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    # by simply pausing we'll break the while loop and make a new song be chosen and played.
    voice = discord.utils.get(client.voice_clients, guild=ctx.message.guild)
    if voice.is_playing():voice.pause()
    else:print('no audio playing')

@client.tree.command(name="stop_music",description="Stops the bot from streaming in the voice channel.")
async def stop_music(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    voice = discord.utils.get(client.voice_clients, guild=ctx.message.guild)
    global playing_music
    try:
        playing_music = False
        voice.pause()
        await voice.disconnect()
        
    except: print('cant dc')

@client.tree.command(name="dj",description="Start the dj/radio station in the current voice channel.")
async def dj(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    await handle_radio(ctx.message)

@client.tree.command(name="scrape_music",description="Build a dataset of youtube links of music to stream (saved as csv)")
@app_commands.describe(amount = "How many messages to check (leave empty for all).")
async def scrape_music(interaction:discord.Interaction,amount:int=None):
    ctx = await commands.Context.from_interaction(interaction)
    await handle_scrape_music(ctx.message,amount)

@client.tree.command(name="remove_bg",description="Remove the background of a given image.")
@app_commands.describe(url = "How many messages to check (leave empty for all).")
@app_commands.describe(sensitivity = "model sensitivity (0.0-1.0) default = 0.6.")
@app_commands.describe(passes = "How many times to remove background noise, default = 1.")
async def remove_bg(interaction:discord.Interaction,url:str,sensitivity:float=None,passes:int=None):
    ctx = await commands.Context.from_interaction(interaction)
    await handle_remove_bg(ctx.message,url,sensitivity,passes)

@client.tree.command(name="new_bg",description="Replace the background of a given image with another image.")
@app_commands.describe(foreground_url = "How many messages to check (leave empty for all).")
@app_commands.describe(background_url = "How many messages to check (leave empty for all).")
@app_commands.describe(sensitivity = "model sensitivity (0.0-1.0) default = 0.6.")
@app_commands.describe(passes = "How many times to remove background noise, default = 1.")
async def new_bg(interaction:discord.Interaction,foreground_url:str,background_url:str,sensitivity:float=None,passes:int=None):
    ctx = await commands.Context.from_interaction(interaction)
    await handle_replace_bg(ctx.message,foreground_url,background_url,sensitivity,passes)

@client.tree.command(name="style_transfer",description="Transfer the style of one image onto another.")
@app_commands.describe(content_img = "The image to keep.")
@app_commands.describe(style_img = "The image with the desired style.")
async def style_transfer(interaction:discord.Interaction,content_img:str,style_img:str):
    ctx = await commands.Context.from_interaction(interaction)
    await handle_style_transfer(ctx.message,content_img,style_img)

@client.tree.command(name="rand",description="Send a random image from a channel.")
async def rand(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    await fetch_chat(ctx.message,type = 1,channel = random_image_channel)

@client.tree.command(name="rand_image",description="Send a random image from main channel.")
async def rand_image(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    await fetch_chat(ctx.message,type = 1,channel = main_chat)

@client.tree.command(name="rand_chat",description="Send a random chat from main channel.")
async def rand_chat(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    await fetch_chat(ctx.message,type = 0,channel = main_chat)

@client.tree.command(name="wipe_memory",description="Wipes chatbot memory.")
async def wipe_memory(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    global chat_history
    global personality
    chat_history=[{"role": "system", "content": personality}]

@client.tree.command(name="stable_diff",description="Stable diffusion image generation.")
@app_commands.describe(prompt = "Describe your image.")
@app_commands.describe(model = "0 or 1 // which stable diffusion model to use.")
async def sd(interaction:discord.Interaction, prompt:str,model:int = 0):
    ctx = await commands.Context.from_interaction(interaction)
    if ctx.message.author.id == admin_id:
        async with ctx.typing():
            await handle_sd(ctx.message,prompt,model)
    else:
        async with ctx.typing():
            permission = await get_permission(ctx)
            if permission:
                await handle_sd(ctx.message,prompt,model)

@client.tree.command(name="restore",description="Face restoration.")
@app_commands.describe(url = "Link to your image.")
async def restore(interaction:discord.Interaction, url:str):
    ctx = await commands.Context.from_interaction(interaction)
    if ctx.message.author.id == admin_id: 
        async with ctx.typing():
            await handle_restore(ctx.message,url)
    else:
        async with ctx.typing():
            permission = await get_permission(ctx)
            if permission:
                await handle_restore(ctx.message,url)

@client.tree.command(name="gen_video",description="Text to Video.")
@app_commands.describe(prompt = "What video do you want to create?.")
async def gen_video(interaction:discord.Interaction, prompt:str):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        if ctx.message.author.id == admin_id: await handle_video_gen(ctx.message,prompt)
        else:
            permission = await get_permission(ctx)
            if permission:
                await handle_video_gen(ctx.message,prompt)

@client.tree.command(name="edit_face",description="Make changes to a headshot of someone.")
@app_commands.describe(url = "Link to the face to edit.")
@app_commands.describe(prompt = "What do you want to change? try: 'a face with a bowl cut'.")
@app_commands.describe(manipulation_strength = "-10 - 10")
@app_commands.describe(disentanglement_threshold = "0.08 - 0.3")
async def edit_face(interaction:discord.Interaction, url:str,prompt:str,manipulation_strength:float=4.1,disentanglement_threshold:float=0.15):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        if ctx.message.author.id == admin_id: await handle_face_edit(ctx.message,url,prompt,manipulation_strength,disentanglement_threshold)
        else:
            permission = await get_permission(ctx)
            if permission:
                await handle_face_edit(ctx.message,url,prompt,manipulation_strength,disentanglement_threshold)

@client.tree.command(name="age_face",description="Simulate someones face at a given age or make a gif of them aging.")
@app_commands.describe(url = "Link to the face to age.")
@app_commands.describe(age = "The target age (ignore to make a gif).")
async def age_face(interaction:discord.Interaction, url:str,age:int):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        if ctx.message.author.id == admin_id: await handle_aging(ctx.message,url,age)
        else:
            permission = await get_permission(ctx)
            if permission:
                await handle_aging(ctx.message,url,age)

@client.tree.command(name="doodle",description="Provide a doodle and a prompt to generate an image.")
@app_commands.describe(url = "Link to your doodle.")
@app_commands.describe(prompt = "How do you imagine your doodle?")
async def doodle(interaction:discord.Interaction, url:str,prompt:str):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        if ctx.message.author.id == admin_id: await handle_doodle(ctx.message,url,prompt)
        else:
            permission = await get_permission(ctx)
            if permission:
                await handle_doodle(ctx.message,url,prompt)

@client.tree.command(name="explain",description="Ask questions about an image.")
@app_commands.describe(url = "Link to image.")
@app_commands.describe(question = "The question you have about the image.")
async def explain(interaction:discord.Interaction, url:str,question:str):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        if ctx.message.author.id == admin_id: await handle_explanation(ctx.message,url,question)
        else:
            permission = await get_permission(ctx)
            if permission:
                await handle_explanation(ctx.message,url,question)

@client.tree.command(name="interp",description="Interp between two images.")
@app_commands.describe(url1 = "Link to starting image.")
@app_commands.describe(url2 = "Link to ending image.")
@app_commands.describe(steps = "How Many Steps to take. 1 - 7 (default is 4)")
async def interp(interaction:discord.Interaction, url1:str,url2:str,steps:int=4):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        if ctx.message.author.id == admin_id: await handle_interp(ctx.message,url1,url2,steps)
        else:
            permission = await get_permission(ctx)
            if permission:
                await handle_interp(ctx.message,url1,url2,steps)

@client.tree.command(name="editor",description="video editor using moviepy and pedalboard.")
@app_commands.describe(subcommand = "load, fx, clip, replace_audio, reverb, distortion, top_text, bottom_text, stats, compress. leave empty for help")
@app_commands.describe(arg1 = "Argument relative to chosen subcommand")
@app_commands.describe(arg2 = "Argument relative to chosen subcommand")
@app_commands.describe(arg3 = "Argument relative to chosen subcommand")
@app_commands.describe(arg4 = "Argument relative to chosen subcommand")
@app_commands.describe(arg5 = "Argument relative to chosen subcommand")
async def editor(interaction:discord.Interaction, subcommand:str = None,arg1:str=None,arg2:str=None,arg3:str=None,arg4:str=None,arg5:int=30):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        if subcommand == None: await help_video_editing(ctx)
        else: await handle_editor(ctx.message,subcommand,arg1,arg2,arg3,arg4,arg5)

@client.tree.command(name="recommend",description="Recommend a song to the dj.")
@app_commands.describe(url = "must be youtube or youtube music link.")
async def recommend(interaction:discord.Interaction, url:str=None):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        take_requests = requests_allowed
        if take_requests:
            await handle_recommendation(ctx.message,url)
        else:
            admin = await commands.MemberConverter().convert(ctx, str(admin_id))
            await ctx.message.channel.send(f'take_requests is set to false. Get an admin ({admin.mention}) to do `/recommend allow`')

@client.tree.command(name="start_trivia",description="Begins a trivia competition.")
@app_commands.describe(rounds = "1-50, default is 5")
@app_commands.describe(difficulty = "Easy, Medium, Hard. Ignore for a mix of all.")
async def trivia(interaction:discord.Interaction, rounds:int = 5, difficulty:str=None):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_trivia(ctx.message,rounds,difficulty)

@client.tree.command(name="extract_face",description="Crops photo around the face in the photo.")
@app_commands.describe(url = "Link to your photo.")
@app_commands.describe(pad = "How much to pad the photo by. (EX: pad=5 will pad the photo by 1/5 the width of the original photo.)")
async def get_face(interaction:discord.Interaction, url:str, pad:int=0):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await extract_face(ctx.message,url,pad)

@client.tree.command(name="start_run",description="Begins a monster chase game.")
@app_commands.describe(rounds = "How many rounds (default is 5).")
async def start_run(interaction:discord.Interaction, rounds:int = 5):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_run(ctx.message,rounds)

@client.tree.command(name="create_database",description="Creates a database for user stats (to store how much fake money they have etc.).")
async def create_db(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        global user_stats
        if ctx.message.author.id == admin_id: user_stats = await create_user_stats()

@client.tree.command(name="stats",description="Checks your stats (how much fake money you have etc.).")
async def get_user_stats(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await check_user_stats(ctx.message)

@client.tree.command(name="flip",description="Challenge another user to a coin flip wager.")
@app_commands.describe(challenged_user = "@ a user to challenge.")
@app_commands.describe(wager = "How much do you want to bet?")
async def coin_flip(interaction:discord.Interaction, challenged_user:str,wager:int):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_coin_flip(ctx.message,challenged_user,wager)

@client.tree.command(name="similiar_songs",description="Gets similiar songs to a given song.")
@app_commands.describe(song = "Enter the title and artist of the song.")
async def similiar_songs(interaction:discord.Interaction, song:str):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_similiar_songs(ctx.message,song)

@client.tree.command(name="similiar_artists",description="Gets similiar artists to a given artist.")
@app_commands.describe(artist = "Enter the artist.")
async def similiar_artists(interaction:discord.Interaction,artist:str):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_similiar_artists(ctx.message,artist)

@client.tree.command(name="random_game",description="Gets 3 random games from your Steam library.")
async def random_game(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_random_game(ctx.message)

@client.tree.command(name="get_sales",description="Gets 3 top steam games on sale.")
async def get_sales(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_get_sales(ctx.message)

@client.tree.command(name="cast",description="Cast your fishing rod.")
async def cast(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_cast(ctx.message)

@client.tree.command(name="new_lake",description="Generates a new server lake.")
async def new_lake(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        if ctx.message.author.id == admin_id:
            await handle_new_lake(ctx.message,"Server Lake")

@client.tree.command(name="move_tile",description="Move to another spot on the current lake.")
async def move_tile(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_move_tile(ctx.message)

@client.tree.command(name="find_secret_spot",description="Creates your own fishing spot. Call /secret_spot to travel there.")
async def secret_fishing_spot(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_secret_fishing_spot(ctx.message)

@client.tree.command(name="travel_secret_spot",description="Move to your own fishing spot.")
async def secret_spot(interaction:discord.Interaction):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_secret_spot(ctx.message)

@client.tree.command(name="shrink",description="Shrinks the image to a given size.")
@app_commands.describe(url = "Link to the image.")
@app_commands.describe(max_pixel_dim = "Enter the max height or width in pixels.")
async def shrink(interaction:discord.Interaction,url:str,max_pixel_dim:int=1000):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        if(max_pixel_dim > 4000):
            ctx.send(f"Requested max dim is too large ({max_pixel_dim})\nPlease Request a smaller max dimension.")
            return
        response = requests.get(url)
        if 'png' in url:
            with open('cache/shrink.png', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/shrink.jpg', 'wb') as f:
                f.write(response.content)
            image = Image.open('cache/shrink.jpg')
            image.save('cache/shrink.png')
        img = Image.open('cache/shrink.png')
        img = await handle_shrink(img,max_pixel_dim)
        img.save('cache/shrink.png')
        await ctx.message.channel.send(file=discord.File('cache/shrink.png'))

@client.tree.command(name="sharpen",description="Good first step for restoring old photos.")
@app_commands.describe(url = "Link to the image.")
async def sharpen(interaction:discord.Interaction,url:str):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_sharpen(ctx.message,url)

@client.tree.command(name="color",description="Colors photos.")
@app_commands.describe(url = "Link to the image.")
async def color(interaction:discord.Interaction,url:str):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_color(ctx.message,url)

@client.tree.command(name="restore_2",description="Alternate face restoration model.")
@app_commands.describe(url = "Link to the image.")
async def restore_2(interaction:discord.Interaction,url:str):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_restore_2(ctx.message,url)

@client.tree.command(name="current_song",description="Sends the current song the DJ is playing.")
async def current_song(interaction:discord.Interaction,url:str):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_current_song(ctx.message)

@client.tree.command(name="analyze",description="Get NLP stats of a given user.")
@app_commands.describe(user = "@ the user to analyze.")
@app_commands.describe(window_size = "Window size for rolling average. Default is 7")
async def analyze(interaction:discord.Interaction,user:str,window_size:int=7):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_analyze(ctx,window_size)

@client.tree.command(name="download_chat",description="Download messages for NLP analysis.")
@app_commands.describe(limit = "Number of messages to download. Default is 5000")
async def download_chat(interaction:discord.Interaction, limit:int=5000):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_download_chat(ctx,limit)

@client.tree.command(name="sentiment",description="The chat\'s sentiment towards a given topic.")
@app_commands.describe(topic = "Topic to filter and analyze for.")
async def sentiment(interaction:discord.Interaction, topic:str):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_sentiment_topic(ctx.message,topic)

@client.tree.command(name="asset_rundown",description="Provides a rundown for a given asset and a history line plot with rolling average.")
@app_commands.describe(asset = "Ticker symbol. EX: GOOGL, BTC-USD, AMZN")
@app_commands.describe(period = 'History length for plot. ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")')
@app_commands.describe(window = "Window for rolling average. Default is 10")
async def stock_rundown(interaction:discord.Interaction, asset:str, period:str='3mo', window:int=10):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_stock_rundown(ctx.message,asset, period, window)

@client.tree.command(name="forecast_asset",description="Forecast the price of an asset.")
@app_commands.describe(asset = "Ticker symbol. EX: GOOGL, BTC-USD, AMZN")
@app_commands.describe(future = 'How long to forecast into the future. Default is 30')
@app_commands.describe(history_timeframe = 'How much history to harvest. Default is 3y')
@app_commands.describe(changepoint_prior_scale = 'Trend flexibility. Small values grant a rigid trend. Default is 0.05')
@app_commands.describe(seasonality_prior_scale = 'Regularization strngth. Lower values allow more variability in seasonal. Default is 10')
@app_commands.describe(n_changepoints = 'Potential changepoints to consider. Higher values allow for more trend flexibility. Default is 25')
@app_commands.describe(daily_seasonality = 'Whether daily seasonality should be true or false. (Leave false for now).')
@app_commands.describe(start_at = '0.0 - 1.0 what percent of the history to start the plot at.')
async def forecast_stock(interaction:discord.Interaction, asset:str, future:int=30, history_timeframe:str='3y', changepoint_prior_scale:float=0.05, seasonality_prior_scale:int=10, n_changepoints:int=25, daily_seasonality:bool=False,start_at:float=0.0):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_forecast_stock(ctx.message,asset,future,history_timeframe,changepoint_prior_scale,seasonality_prior_scale,n_changepoints,daily_seasonality,start_at)

@client.tree.command(name="forecast_asset_test",description="Forecast the price of an asset and test it on it's current state.")
@app_commands.describe(asset = "Ticker symbol. EX: GOOGL, BTC-USD, AMZN")
@app_commands.describe(history_timeframe = 'How much history to harvest. Default is 3y')
@app_commands.describe(changepoint_prior_scale = 'Trend flexibility. Small values grant a rigid trend. Default is 0.05')
@app_commands.describe(seasonality_prior_scale = 'Regularization strngth. Lower values allow more variability in seasonal components. Default is 10')
@app_commands.describe(n_changepoints = 'Potential changepoints. Higher values allow for more trend flexibility. Default is 25')
@app_commands.describe(daily_seasonality = 'Whether daily seasonality should be true or false. (Leave false for now).')
@app_commands.describe(start_at = '0.0 - 1.0 what percent of the history to start the plot at.')
async def forecast_stock_test(interaction:discord.Interaction, asset:str, history_timeframe:str='3y', changepoint_prior_scale:float=0.05, seasonality_prior_scale:int=10, n_changepoints:int=25, daily_seasonality:bool=False,start_at:float=0.0):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_forecast_stock_test(ctx.message,asset,history_timeframe,changepoint_prior_scale,seasonality_prior_scale,n_changepoints,daily_seasonality,start_at)

@client.tree.command(name="gen_music",description="Text to music.")
@app_commands.describe(prompt_a = "Describe what you want. EX: Soulful blues guitar solo.")
@app_commands.describe(prompt_b = "Describe Genre/vibe. EX: 90's jazz.")
@app_commands.describe(steps = "How long (in steps). Default is 50.")
async def gen_music(interaction:discord.Interaction,prompt_a:str,steps:int=50,prompt_b:str=None):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_gen_music(ctx.message,prompt_a,steps,prompt_b)

@client.tree.command(name="buy",description="Tries to fake buy fake shares of a real asset. EX: /buy AMZN 30")
@app_commands.describe(ticker = "Ticker of the asset you want. EX: AMZN, BTC-USD, BMO.TO")
@app_commands.describe(amount = "How much money you want to spend (can be left blank for all).")
async def buy(interaction:discord.Interaction,ticker:str,amount:int=None):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_buy(ctx.message,ticker,amount)

@client.tree.command(name="sell",description="Tries to fake sell fake shares of a real asset. EX: /sell AMZN 30")
@app_commands.describe(ticker = "Ticker of the asset you want to sell. EX: AMZN, BTC-USD, BMO.TO")
@app_commands.describe(amount = "How many shares you want to sell (can be left blank for all).")
async def sell(interaction:discord.Interaction,ticker:str,amount:int=None):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_sell(ctx.message,ticker,amount)

@client.tree.command(name="sell_short",description="Tries to fake sell fake short positions of a real asset. EX: /sell_short AMZN 30")
@app_commands.describe(ticker = "Ticker of the asset you want to sell. EX: AMZN, BTC-USD, BMO.TO")
@app_commands.describe(amount = "How many shares you want to sell (can be left blank for all).")
async def sell_short(interaction:discord.Interaction,ticker:str,amount:int=None):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_sell_short(ctx.message,ticker,amount)

@client.tree.command(name="buy_short",description="Tries to fake buy fake short positions of a real asset. EX: /buy_short AMZN 30")
@app_commands.describe(ticker = "Ticker of the asset you want to buy. EX: AMZN, BTC-USD, BMO.TO")
@app_commands.describe(amount = "How muhc money to spend (can be left blank for all).")
async def buy_short(interaction:discord.Interaction,ticker:str,amount:int=None):
    ctx = await commands.Context.from_interaction(interaction)
    async with ctx.typing():
        await handle_buy_short(ctx.message,ticker,amount)

@client.event
async def on_message(message):
    # prevent bot from talking to itself
    if message.author == client.user:
        return
    # process commands
    await client.process_commands(message)
    # you can set up custom responses to content in messages here like this

    #if str(message.author.id) == '<user_id>': await message.channel.send('send something')
    
    #if 'keyword' in message.content: await message.channel.send('send something')


#####################################################################################################
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~{ FUNCTIONS }~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
#####################################################################################################

async def handle_forecast_stock_test(message,tag,timeframe,cps,sps,nc,ds,start_at):
    df = pdr.get_data_yahoo(tag,period=timeframe)
    df = df[['Close']]
    df.index = pd.to_datetime(df.index)
    df.columns = ['y']
    df.reset_index(inplace=True)
    df = df.rename(columns={'Date': 'ds', 'y': 'y'})

    train_size = int(len(df) * 0.8)
    test_size = int(len(df) * 0.3)
    plot_offset = int(len(df) * start_at)

    train_df = df[:train_size]

    model = Prophet(daily_seasonality=ds,changepoint_prior_scale=cps,seasonality_prior_scale=sps,n_changepoints=nc)
    model.fit(train_df)

    future = model.make_future_dataframe(periods=test_size,freq='D', include_history=True)
    forecast = model.predict(future)

    fig, ax = plt.subplots()
    ax.plot(df['ds'][plot_offset:], df['y'][plot_offset:], label='Actual')
    ax.plot(forecast['ds'][plot_offset:train_size], forecast['yhat'][plot_offset:train_size], label='Fitted')
    ax.plot(forecast['ds'][train_size:len(df)], forecast['yhat'][train_size:len(df)], label='Predicted')
    ax.legend()

    ax.set_title(f'{tag} Closing Price Forecast')
    ax.set_xlabel('Date')
    ax.set_ylabel('Closing Price')
    plt.xticks(rotation = 45)
    plt.tight_layout()
    plt.grid()
    plt.savefig("cache/forecast_crypto_test.png")
    plt.close()
    await message.channel.send(file=discord.File('cache/forecast_crypto_test.png'))

async def handle_sell_short(message,keyword,amount):
    keyword = keyword.upper()
    col_name = keyword+'_short'
    price_name = 'ignore_'+keyword+'_short'
    try:
        user_stats[col_name]
    except:
        await message.channel.send(f'{col_name} is not owned by anyone on the server.')
        return
    available = float(user_stats.loc[message.author.id,col_name])
    if amount == None: amount = available
    amount = float(amount)
    if amount > available or amount < 0: amount = available

    
    try:
        info = yf.Ticker(keyword).info
        try:crypto_price = float(info['currentPrice'])
        except:crypto_price = float(info['regularMarketOpen'])
        revenue = amount * float(user_stats.loc[message.author.id,price_name])

        profit_loss = amount * (crypto_price - float(user_stats.loc[message.author.id,price_name]))

        net = revenue + profit_loss

        tmp = await message.channel.send(f"Sell {amount} of your {available} {col_name} for ${int(net)}?\n(1 {keyword} = ~${round(crypto_price,3)})")
        await tmp.add_reaction('✅')

        def check_emoji(reaction, user):
            return str(reaction.emoji) == '✅' and user.id == message.author.id
        
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=60, check=check_emoji)
            if float(user_stats.loc[message.author.id,col_name]) >= amount:
                user_stats.loc[message.author.id,col_name] -= amount
                user_stats.loc[message.author.id,price_name] = 0
                user_stats.loc[message.author.id,'money'] += int(net)

                await tmp.edit(content=f"Sold {amount} {col_name} for ${int(net)}!\nYou have {user_stats.loc[message.author.id,'money']} {currency_name} now and ~{round(user_stats.loc[message.author.id,col_name],3)} {col_name}.")
                await tmp.clear_reactions()
            else:
                await tmp.edit(content=f"Nice try.")
                await tmp.clear_reactions()

        except asyncio.TimeoutError:
            await tmp.edit(content="Cancelled Transaction.")
            await tmp.clear_reactions()
            return
        
    except:
        await message.channel.send("Error Completing Request:\nLikely too many requests have been made recently. (5 per minute max)")
    user_stats.to_csv('server_datasets/user_stats.csv')

async def handle_buy_short(message,keyword,amount):
    keyword = keyword.upper()
    col_name = keyword+'_short'
    price_name = 'ignore_'+keyword+'_short'
    try:
        user_stats.loc[message.author.id,price_name]
        await message.channel.send("You can only hold one short position per asset")
        return
    except:pass

    money = float(user_stats.loc[message.author.id,'money'])
    if amount == None: amount = money
    amount = float(amount)
    if amount > money: amount = money
    if money < 1:
        await message.channel.send(f"You have no {currency_name}...")
        return
    
    try:
        info = yf.Ticker(keyword).info
        try:crypto_price = float(info['currentPrice'])
        except:crypto_price = float(info['regularMarketOpen'])
        
        tmp = await message.channel.send(f"Buy ${amount} {currency_name} worth of {col_name} at ${crypto_price}?\n(~{round(amount/crypto_price,3)} {keyword})")
        await tmp.add_reaction('✅')

        def check_emoji(reaction, user):
            return str(reaction.emoji) == '✅' and user.id == message.author.id
        
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=60, check=check_emoji)
            if user_stats.loc[message.author.id,'money'] >= amount:
                user_stats.loc[message.author.id,'money'] -= amount
                
                try:user_stats[col_name]
                except:user_stats[col_name]=0.0
                user_stats.loc[message.author.id, col_name] += amount / crypto_price
                user_stats.loc[message.author.id, price_name] = crypto_price

                await tmp.edit(content=f"Bought ${amount} {currency_name} worth of {col_name} at ${crypto_price}!\nYou have {user_stats.loc[message.author.id,'money']} {currency_name} remaining.")
                await tmp.clear_reactions()
            else:
                await tmp.edit(content=f"Nice try.")
                await tmp.clear_reactions()

        except asyncio.TimeoutError:
            await tmp.edit(content="Cancelled Transaction.")
            await tmp.clear_reactions()
            return
        
    except:
        await message.channel.send("Error Completing Request:\nEither the stock/crypto is not recognized or too many requests have been made recently.")
    user_stats.to_csv('server_datasets/user_stats.csv')

async def handle_sell(message,keyword,amount):
    keyword = keyword.upper()
    try:
        user_stats[keyword]
    except:
        await message.channel.send(f'{keyword} is not owned by anyone on the server.')
        return
    available = float(user_stats.loc[message.author.id,keyword])
    if amount == None: amount = available
    amount = float(amount)
    if amount > available or amount < 0: amount = available

    
    try:
        info = yf.Ticker(keyword).info
        try:crypto_price = float(info['currentPrice'])
        except:crypto_price = float(info['regularMarketOpen'])

        tmp = await message.channel.send(f"Sell {amount} of your {available} {keyword} for ${int(amount*crypto_price)}?\n(1 {keyword} = ~${round(crypto_price,3)})")
        await tmp.add_reaction('✅')

        def check_emoji(reaction, user):
            return str(reaction.emoji) == '✅' and user.id == message.author.id
        
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=60, check=check_emoji)
            if float(user_stats.loc[message.author.id,keyword]) >= amount:
                user_stats.loc[message.author.id,keyword] -= amount
                user_stats.loc[message.author.id,'money'] += int(amount*crypto_price)

                await tmp.edit(content=f"Sold {amount} {keyword} for ${int(amount*crypto_price)}!\nYou have {user_stats.loc[message.author.id,'money']} {currency_name} now and ~{round(user_stats.loc[message.author.id,keyword],3)} {keyword}.")
                await tmp.clear_reactions()
            else:
                await tmp.edit(content=f"Nice try.")
                await tmp.clear_reactions()

        except asyncio.TimeoutError:
            await tmp.edit(content="Cancelled Transaction.")
            await tmp.clear_reactions()
            return
        
    except:
        await message.channel.send("Error Completing Request:\nLikely too many requests have been made recently.")
    user_stats.to_csv('server_datasets/user_stats.csv')

async def handle_buy(message,keyword,amount):
    keyword = keyword.upper()
    money = float(user_stats.loc[message.author.id,'money'])
    if amount == None: amount = money
    amount = float(amount)
    if amount > money: amount = money
    if money < 1:
        await message.channel.send(f"You have no {currency_name}...")
        return
    
    try:
        info = yf.Ticker(keyword).info
        try:crypto_price = float(info['currentPrice'])
        except:crypto_price = float(info['regularMarketOpen'])

        tmp = await message.channel.send(f"Buy ${amount} {currency_name} worth of {keyword} at ${crypto_price}?\n(~{round(amount/crypto_price,3)} {keyword})")
        await tmp.add_reaction('✅')

        def check_emoji(reaction, user):
            return str(reaction.emoji) == '✅' and user.id == message.author.id
        
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=60, check=check_emoji)
            if user_stats.loc[message.author.id,'money'] >= amount:
                user_stats.loc[message.author.id,'money'] -= amount

                try:user_stats[keyword]
                except:user_stats[keyword]=0.0
                user_stats.loc[message.author.id, keyword] += amount / crypto_price

                await tmp.edit(content=f"Bought ${amount} {currency_name} worth of {keyword} at ${crypto_price}!\nYou have {user_stats.loc[message.author.id,'money']} {currency_name} remaining.")
                await tmp.clear_reactions()
            else:
                await tmp.edit(content=f"Nice try.")
                await tmp.clear_reactions()

        except asyncio.TimeoutError:
            await tmp.edit(content="Cancelled Transaction.")
            await tmp.clear_reactions()
            return
        
    except:
        await message.channel.send("Error Completing Request:\nEither the stock/crypto is not recognized or too many requests have been made recently.")
    user_stats.to_csv('server_datasets/user_stats.csv')



async def handle_gen_music(message,desc,steps,interp):
    steps = int(steps)
    try:
        if interp != None:
            output = replicate.run(
                "riffusion/riffusion:8cf61ea6c56afd61d8f5b9ffd14d7c216c0a93844ce2d82ac1c9ecc9c7f24e05",
                input={"prompt_a": desc,
                       "prompt_b": interp,
                       "num_inference_steps":steps}
            )
        else:
            output = replicate.run(
                "riffusion/riffusion:8cf61ea6c56afd61d8f5b9ffd14d7c216c0a93844ce2d82ac1c9ecc9c7f24e05",
                input={"prompt_a": desc,
                       "num_inference_steps":steps}
            )
        
        print(output)
        try:
            response = requests.get(output['audio'])
            with open('cache/gen_music.mp3', 'wb') as f:
                f.write(response.content)

            await message.channel.send(file=discord.File('cache/gen_music.mp3'))
        except Exception as e: 
            await message.channel.send(e)
            await message.channel.send(output)
    except Exception as e:
        await message.channel.send(e)

async def handle_forecast_stock(message,tag,length,timeframe,cps,sps,nc,ds,start_at):
    length=int(length)
    df = pdr.get_data_yahoo(tag,period=timeframe)
    df = df[['Close']]
    df.index = pd.to_datetime(df.index)
    df.columns = ['y']
    df.reset_index(inplace=True)
    df = df.rename(columns={'Date': 'ds', 'y': 'y'})

    model = Prophet(daily_seasonality=ds,changepoint_prior_scale=cps,seasonality_prior_scale=sps,n_changepoints=nc)
    model.fit(df)

    future = model.make_future_dataframe(periods=length, freq='D', include_history=True)
    forecast = model.predict(future)

    plot_split = int(len(df) * 0.8)
    plot_offset = int(len(df) * start_at)

    fig, ax = plt.subplots()
    ax.plot(df['ds'][plot_offset:], df['y'][plot_offset:], label='Actual')
    ax.plot(forecast['ds'][plot_offset:len(df)], forecast['yhat'][plot_offset:len(df)], label='Fitted')
    ax.plot(forecast['ds'][len(df):], forecast['yhat'][len(df):], label='Predicted')
    ax.legend()
    ax.set_title(f'{tag} Closing Price Forecast')
    ax.set_xlabel('Date')
    ax.set_ylabel('Closing Price')
    plt.xticks(rotation = 45)
    plt.tight_layout()
    plt.grid()
    plt.savefig("cache/forecast_crypto.png")
    plt.close()
    await message.channel.send(file=discord.File('cache/forecast_crypto.png'))

async def handle_stock_rundown(message, tag, period, window):
    window = int(window)

    data = pdr.get_data_yahoo(tag, period=period,interval='1h')
    ma = data['Close'].rolling(window=window,step = window // 4).mean()

    data['Close'].plot()
    plt.plot(ma.index, ma, label='Moving Average')
    plt.title(f'{period} {tag} chart')
    plt.tight_layout()
    plt.grid()
    plt.xticks(rotation = 45)
    plt.savefig('cache/timeseries_stock.png')
    plt.close()


    tick = yf.Ticker(tag)

    info = defaultdict(lambda: 0,tick.info)

    stock_news = tick.news

    colors = {"none":0x000000, "strong_buy":0x00FFFF, "buy":0x00FF00, "hold":0xFFFF00, "sell":0xFF9900,"strong_sell":0xFF0000}
    try: additionalDesc = f", Industry: {info['industry']}, Sector: {info['sector']}"
    except: additionalDesc = ''

    embed = discord.Embed(title=f"***Rundown For {info['shortName']}***",description=f"Current Price: ${info['currentPrice']} {info['currency']}{additionalDesc}",color=colors[info['recommendationKey']])

    try:analysis = f"Of the {info['numberOfAnalystOpinions']} opinions, the consensus is **'{info['recommendationKey']}'** with an average score of **{info['recommendationMean']}**.\n**Target High:** {info['targetHighPrice']}\n**Target Low:** {info['targetLowPrice']}\n**Target Mean:** {info['targetMeanPrice']}\n"
    except Exception as e: 
        analysis = "It looks like there aren't enough opinions on this stock.\n"
        print(e)
    embed.add_field(name="🕵️🕵️🕵️\n***Analysts:***",value=analysis,inline=False)

    try: stats = f"{tag} had a **52 week low** of {info['fiftyTwoWeekLow']} and a **high** of {info['fiftyTwoWeekHigh']}.\n**Price To Sales (Trailing 12 Months):** {info['priceToSalesTrailing12Months']}\n**Enterprise Value:** {format(int(info['enterpriseValue']),',')}\n**Trailing Annual Dividend Yield:** {info['trailingAnnualDividendYield']}\n**Profit Margin:** %{float(info['profitMargins'])*100}\n**Price To Book:** {info['priceToBook']} (Book Value: {info['bookValue']})\n**Trailing EPS:** {info['trailingEps']}, **Forward EPS:** {info['forwardEps']}\n**Peg Ratio:** {info['pegRatio']}\n**Trailing PE:** {info['trailingPE']}, **Forward PE:** {info['forwardPE']}\n**Average Volume (10 Days):** {format(int(info['averageVolume10days']),',')}\n"
    except Exception as e: 
        stats = "Error retrieving stats.\n"
        print(e)
    embed.add_field(name="📊📊📊\n***Stats:***",value=stats,inline=False)

    try: shares = f"**Float Shares:** {format(int(info['floatShares']),',')}\n**Outstanding Shares:** {format(int(info['sharesOutstanding']),',')}\n**float to outstanding share ratio:** {round((int(info['floatShares'])+1)/(int(info['sharesOutstanding'])+1),3)}\n**Shares Short:** {format(int(info['sharesShort']),',')} (%{float(info['sharesPercentSharesOut'])*100})\n**Short Last Month:** {format(int(info['sharesShortPriorMonth']),',')}\n**% Held By Insiders:** %{float(info['heldPercentInsiders'])*100}\n**% Held By Institutions:** %{float(info['heldPercentInstitutions'])*100}\n"
    except Exception as e:
        shares = "Error retrieving shares.\n"
        print(e)
    embed.add_field(name="📜📜📜\n***Shares:***",value=shares,inline=False)

    try: News = f"**Top Headlines**: \n[{stock_news[0]['title']}]({stock_news[0]['link']})\n[{stock_news[1]['title']}]({stock_news[1]['link']})\n[{stock_news[2]['title']}]({stock_news[2]['link']})"
    except: News = "Unable to fetch news."
    embed.add_field(name="📰📰📰\n***News:***",value=News,inline=False)


    tmp = await message.channel.send(embed=embed)
    await tmp.add_reaction('🧠')
    await message.channel.send(file=discord.File('cache/timeseries_stock.png'))
    def check_emoji(reaction, user):
        return str(reaction.emoji) == '🧠' and user.id == message.author.id
    try:
        
        reaction, user = await client.wait_for('reaction_add', timeout=60, check=check_emoji)
        await tmp.clear_reactions()
        tmp_news = f"{stock_news[0]['title']}\n{stock_news[1]['title']}\n{stock_news[2]['title']}"
        prompt = "In less than 2000 characters, does this stock seem overvalued or undervalued? Summarize this info and provide insights:\n" + stats.replace('*', '') + shares.replace('*', '') + "\nTop Headlines:\n" + tmp_news.replace('*', '')
        print(prompt)
        completion = openai.ChatCompletion.create(
            model = "gpt-3.5-turbo",
            temperature = 0.8,
            max_tokens = 2000,
            messages = [
            {"role": "system", "content": "You are a financial advisor who is excellent at interpretting stock data and loves giving their input. (a value of '0' means the data is not available)"},
            {"role": "user", "content":prompt}
            ]
        )

        await tmp.reply(completion.choices[0].message.content)
        
    except asyncio.TimeoutError:
        await tmp.clear_reactions()
    
    del tick,info,data,ma


async def handle_sentiment_topic(message, keyword):
    global messages
    if len(messages) < 1:
        return

    keyword_messages = [message for message in messages if keyword.lower() in " " + message.content.lower()]

    sentiments = [TextBlob(message.content).sentiment.polarity for message in keyword_messages]
    avg_sentiment = sum(sentiments) / len(sentiments)

    user_counts = defaultdict(int)
    for message in keyword_messages:
        user_counts[message.author.name] += 1
    top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    min_sentiment_message = min(keyword_messages, key=lambda message: TextBlob(message.content).sentiment.polarity)
    max_sentiment_message = max(keyword_messages, key=lambda message: TextBlob(message.content).sentiment.polarity)

    embed = discord.Embed(title=f"Global Sentiment on {keyword}", description=f"{len(keyword_messages)}/{len(messages)} messages are about {keyword}.")
    embed.add_field(name=f"Average Sentiment:", value=f'{round(avg_sentiment, 4)}', inline=False)
    embed.add_field(name=f"Highest Sentiment Message ({max_sentiment_message.author.display_name}):", value=f'{max_sentiment_message.content}', inline=False)
    embed.add_field(name=f"Lowest Sentiment Message ({min_sentiment_message.author.display_name}):", value=f'{min_sentiment_message.content}', inline=False)
    embed.add_field(name=f"Users Who Mention {keyword} the Most:", value='\n\n'.join(f'{user}: {count}' for user, count in top_users), inline=False)

    await message.channel.send(embed=embed)

async def handle_download_chat(ctx, limit):
    limit = int(limit)
    await ctx.message.channel.send(f"Loading {limit} messages into memory\nThis will take approximately {limit//70} seconds")

    start_time = time.monotonic()
    global messages
    async for message in ctx.channel.history(limit=limit):
        messages.append(message)
    end_time = time.monotonic()
    elapsed_time = end_time - start_time

    await ctx.message.channel.send(f"{limit} messages have been loaded into memory in {elapsed_time:.2f} seconds")

async def handle_analyze(ctx,window_size):
    window_size = int(window_size)
    user = client.get_user(ctx.message.mentions[0].id)
    if user is None:
        await ctx.send(f"Can't Find User.")
        return
    global messages
    if len(messages) < 1:
        await ctx.send("Please call `/download_chat` first.")
        return
    
    user_messages = []
    for message in messages:
        if message.author == user:
            user_messages.append(message)

    percentage = round(len(user_messages) / len(messages) * 100, 2)

    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_counts = Counter(message.created_at.weekday() for message in user_messages)
    weekday_data = [weekday_counts[i] for i in range(7)]
    fig, ax = plt.subplots()
    ax.bar(weekdays, weekday_data)
    ax.set_ylabel('Number of Messages')
    ax.set_xlabel('Day of the Week')
    ax.set_title(f"{user.display_name}'s Activity by Day of the Week")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig('cache/weekday_activity.png')
    plt.close()

    noun_counts = Counter(word.lower() for message in user_messages for word, tag in TextBlob(message.content).tags if tag.startswith('NN') and not re.search("[^a-zA-Z]", word) and 'https' not in word)
    top_nouns = noun_counts.most_common(10)

    sentiment_scores = []
    for message in user_messages:
        sentiment_scores.append(TextBlob(message.content).sentiment.polarity)

    if sentiment_scores:
        sorted_messages = sorted(user_messages, key=lambda message: TextBlob(message.content).sentiment.polarity, reverse=True)
        top_messages = sorted_messages[:3]
        bottom_messages = sorted_messages[-3:]
        average_sentiment = np.mean(sentiment_scores)
        weekday_sentiment = defaultdict(list)
        for message in user_messages:
            weekday = message.created_at.weekday()
            sentiment = TextBlob(message.content).sentiment.polarity
            weekday_sentiment[weekday].append(sentiment)
        average_weekday_sentiment = {}
        for weekday, sentiments in weekday_sentiment.items():
            average_weekday_sentiment[weekdays[weekday]] = np.mean(sentiments)

        weekdays_ordered = pd.Categorical(average_weekday_sentiment.keys(), categories=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], ordered=True)

        sorted_weekdays = [weekday for weekday, sentiment in sorted(average_weekday_sentiment.items(), key=lambda x: weekdays.index(x[0]))]
        sorted_sentiments = [average_weekday_sentiment[day] for day in sorted_weekdays]
        fig, ax = plt.subplots()
        ax.bar(sorted_weekdays, sorted_sentiments)
        ax.set_ylabel('Sentiment Score')
        ax.set_xlabel('Day of the Week')
        ax.set_title(f"{user.name}'s Sentiment by Day of the Week")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig('cache/weekday_sentiment.png')
        plt.close()
    else:
        top_messages = None
        bottom_messages = None
        average_sentiment = None
        average_weekday_sentiment = None

    daily_counts = defaultdict(int)
    for message in user_messages:
        date = message.created_at.date()
        daily_counts[date] += 1

    dates = sorted(daily_counts.keys())
    counts = [daily_counts[date] for date in dates]

    fig, ax = plt.subplots()
    ax.plot(dates, counts)
    n = len(dates) // 15
    if n == 0: n = 1
    xticks = [date.strftime('%m/%d') for date in dates[::n]]
    ax.set_xticks(dates[::n])
    ax.set_xticklabels(xticks)
    ax.set_xlabel('Date')
    ax.set_ylabel('Number of Messages')
    ax.set_title('Daily Message Count')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    smoothed_counts = savgol_filter(counts, window_size, 3)
    ax.plot(dates, smoothed_counts, color='red')
    
    plt.savefig('cache/messages_over_time.png')
    plt.close()


    avg_sentiments = {}
    for message in user_messages:
        date = message.created_at.date()
        if date in avg_sentiments:
            avg_sentiments[date].append(TextBlob(message.content).sentiment.polarity)
        else:
            avg_sentiments[date] = [TextBlob(message.content).sentiment.polarity]
    avg_sentiments = {date: np.mean(sentiments) for date, sentiments in avg_sentiments.items()}

    fig, ax = plt.subplots()
    ax.plot(list(avg_sentiments.keys()), list(avg_sentiments.values()))
    n = len(avg_sentiments.keys()) // 15
    if n == 0: n = 1
    xticks = [date.strftime('%m/%d') for date in list(avg_sentiments.keys())[::n]]
    ax.set_xticks(list(avg_sentiments.keys())[::n])
    ax.set_xticklabels(xticks)
    ax.set_title('Average Sentiment per Day')
    ax.set_xlabel('Date')
    ax.set_ylabel('Average Sentiment')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    smoothed_sentiments = savgol_filter(list(avg_sentiments.values()), window_size, 3)
    ax.plot(list(avg_sentiments.keys()), smoothed_sentiments, color='red')
    
    plt.savefig('cache/sentiment_over_time.png')
    plt.close()

    embed = discord.Embed(title=f'{user.display_name}\'s behaviour:',description=f'{user.display_name} is responsible for {len(user_messages)} messages, or {percentage}% of the last {len(messages)}.',color=0x00ff00)
    embed.add_field(name=f"Top 10 Words Used:",value='\n'.join(f"{noun.capitalize()} ({count} times)" for noun, count in top_nouns),inline=False)
    embed.add_field(name=f"Top 3 Most Positive Messages:",value='\n\n'.join(str(i+1) + ": " + word.content for i, word in enumerate(top_messages)),inline=False)
    embed.add_field(name=f"Top 3 Most Negative Messages:",value='\n\n'.join(str(i+1) + ": " + word.content for i, word in enumerate(bottom_messages)),inline=False)
    embed.add_field(name=f"Average Sentiment:",value=f"{round(average_sentiment,4)}",inline=False)

    await message.channel.send(embed=embed)
    await message.channel.send(file=discord.File('cache/weekday_activity.png'))
    await message.channel.send(file=discord.File('cache/weekday_sentiment.png'))
    await message.channel.send(file=discord.File('cache/messages_over_time.png'))
    await message.channel.send(file=discord.File('cache/sentiment_over_time.png'))

async def handle_current_song(message):
    if current_song_link != '':
        await message.channel.send(current_song_link)
    else:
        await message.channel.send('No current song.')
        return

async def handle_restore_2(message,link):
    try:
        response = requests.get(link)
        if 'png' in link:
            with open('cache/restore_2.png', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/restore_2.jpg', 'wb') as f:
                f.write(response.content)
                image = Image.open('cache/restore_2.jpg')
                image.save('cache/restore_2.png')
        image = Image.open('cache/restore_2.png')
        image = await handle_shrink(image)
        image.save('cache/restore_2.png')
        output = replicate.run(
            "tencentarc/vqfr:f9085ea5bf9c8f2d7e5c64564234ab41b5bcd8cd61a58b59a3dde5cbb487721a",
            input={"image": open("cache/restore_2.png", "rb")}
        )
        
        print(output)
        try:
            for i,img in enumerate(output):
                response = requests.get(img['image'])
                with open(f'cache/restore_2_{i}.png', 'wb') as f:
                    f.write(response.content)
                await message.channel.send(file=discord.File(f'cache/restore_2_{i}.png'))
        except Exception as e: 
            await message.channel.send(e)
            await message.channel.send(output)
    except Exception as e:
        await message.channel.send(e)

async def handle_color(message,link):
    try:
        response = requests.get(link)
        if 'png' in link:
            with open('cache/color.png', 'wb') as f:
                f.write(response.content)
                image = Image.open('cache/color.png')
                image = image.convert('RGB')
                image.save('cache/color.jpg')
        else:
            with open('cache/color.jpg', 'wb') as f:
                f.write(response.content)
                
        image = Image.open('cache/color.jpg')
        image = await handle_shrink(image)
        image.save('cache/color.png')
        output = replicate.run(
            "cjwbw/bigcolor:9451bfbf652b21a9bccc741e5c7046540faa5586cfa3aa45abc7dbb46151a4f7",
            input={"image": open("cache/color.jpg", "rb")}
        )
        
        print(output)
        try:
            for i,img in enumerate(output):
                response = requests.get(img['image'])
                with open(f'cache/color{i}.png', 'wb') as f:
                    f.write(response.content)
                await message.channel.send(file=discord.File(f'cache/color{i}.png'))
        except Exception as e: 
            await message.channel.send(e)
            await message.channel.send(output)
    except Exception as e:
        await message.channel.send(e)

async def handle_sharpen(message,link):
    try:
        response = requests.get(link)
        if 'png' in link:
            with open('cache/sharpen.png', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/sharpen.jpg', 'wb') as f:
                f.write(response.content)
                image = Image.open('cache/sharpen.jpg')
                image.save('cache/sharpen.png')
        image = Image.open('cache/sharpen.png')
        image = await handle_shrink(image)
        image.save('cache/sharpen.png')

        output = replicate.run(
            "microsoft/bringing-old-photos-back-to-life:c75db81db6cbd809d93cc3b7e7a088a351a3349c9fa02b6d393e35e0d51ba799",
            input={"image": open("cache/sharpen.png", "rb")}
        )
        response = requests.get(output)
        print(output)
        with open('cache/sharpened.png', 'wb') as f:
            f.write(response.content)
        try:
            await message.channel.send(file=discord.File('cache/sharpened.png'))
        except Exception as e: 
            await message.channel.send(e)
            await message.channel.send(output)
    except Exception as e:
        await message.channel.send(e)

async def handle_shrink(img,max_dim = 1000):
    w = img.size[0]
    h = img.size[1]
    if w > max_dim or h > max_dim:
        pass
    else:
        return img
    if w > h:
        shrink_percent = max_dim / w
        h *= shrink_percent
        img = img.resize((int(max_dim),int(h)),Image.Resampling.LANCZOS)
    else:
        shrink_percent = max_dim / h
        w *= shrink_percent
        img = img.resize((int(w),int(max_dim)),Image.Resampling.LANCZOS)
    return img
    

async def handle_secret_spot(message):
    if os.path.isfile(f'fishing_levels/@{message.author.display_name} Lake/lake_data.csv'):
        user_stats.loc[message.author.id,'lake'] = f'@{message.author.display_name} Lake'
        user_stats.to_csv('server_datasets/user_stats.csv')
        await message.channel.send('You are now in your secret fishing spot.')
    else:
        await message.channel.send('No secret spot found. Call `/secret_fishing_spot`')

async def handle_secret_fishing_spot(message):
    await handle_new_lake(message,f'@{message.author.display_name} Lake')

async def handle_move_tile(message):
    int_to_alpha = {0:"A",
                    1:"B",
                    2:"C"}
    emoji_to_int = {'🇦':0,
                    '🇧':1,
                    '🇨':2,
                    '1️⃣':0,
                    '2️⃣':1,
                    '3️⃣':2}
    
    try: pos = ast.literal_eval(user_stats.loc[message.author.id,'fishing_pos'])
    except: pos = user_stats.loc[message.author.id,'fishing_pos']
    tmp = await message.channel.send(content=f'**You are in tile {int_to_alpha[pos[0]]}{pos[1]+1}**',file=discord.File('fishing_levels/'+user_stats.loc[message.author.id,'lake']+'/lake_map.jpg'))
    await tmp.add_reaction('🇦')
    await tmp.add_reaction('🇧')
    await tmp.add_reaction('🇨')

    accepted_responses = ['🇦','🇧','🇨']
    def check_emoji(reaction, user):
        return str(reaction.emoji) in accepted_responses and user.id == message.author.id
    try:
        reaction, user = await client.wait_for('reaction_add', timeout=60, check=check_emoji)
        column = emoji_to_int[str(reaction.emoji)]
    except asyncio.TimeoutError:
        await tmp.edit(content="Staying Where You Are")
        await tmp.clear_reactions()
        return
    await tmp.add_reaction('1️⃣')
    await tmp.add_reaction('2️⃣')
    await tmp.add_reaction('3️⃣')
    accepted_responses = ['1️⃣','2️⃣','3️⃣']
    def check_emoji(reaction, user):
        return str(reaction.emoji) in accepted_responses and user.id == message.author.id
    try:
        reaction, user = await client.wait_for('reaction_add', timeout=60, check=check_emoji)
        row = emoji_to_int[str(reaction.emoji)]
    except asyncio.TimeoutError:
        await tmp.edit(content="Staying Where You Are")
        await tmp.clear_reactions()
        return
    
    pos = [column,row]
    print(pos)
    user_stats.loc[message.author.id,'fishing_pos'] = f'[{column},{row}]'
    user_stats.to_csv('server_datasets/user_stats.csv')

    await tmp.edit(content=f"Moved to {int_to_alpha[pos[0]]}{pos[1]+1}")
    await tmp.clear_reactions()

async def handle_new_lake(message,arg1):
    image_size = (512, 512)
    square_size = 512

    im = Image.open('fishing_levels/water_bg.jpg')

    draw = ImageDraw.Draw(im)

    square_position = (
        (image_size[0] - square_size) // 2,
        (image_size[1] - square_size) // 2,
        (image_size[0] + square_size) // 2,
        (image_size[1] + square_size) // 2,
    )

    draw.rectangle(square_position, fill=None, outline="black", width=1)

    num_ellipses = 125

    border_width = 10

    x_range = (
        square_position[0] + border_width,
        square_position[2] - border_width,
    )
    y_range = (
        square_position[1] + border_width,
        square_position[3] - border_width,
    )

    # Draw
    for i in range(num_ellipses):
        while True:
            edge = random.randint(0, 3)
            if edge == 0:
                center_x = random.randint(x_range[0], x_range[1])
                center_y = y_range[0]
            elif edge == 1:
                center_x = random.randint(x_range[0], x_range[1])
                center_y = y_range[1]
            elif edge == 2:
                center_x = x_range[0]
                center_y = random.randint(y_range[0], y_range[1])
            else:
                center_x = x_range[1]
                center_y = random.randint(y_range[0], y_range[1])
            if (
                abs(center_x - square_position[0]) >= border_width
                and abs(center_x - square_position[2]) >= border_width
                and abs(center_y - square_position[1]) >= border_width
                and abs(center_y - square_position[3]) >= border_width
            ):
                break
        radius_x = random.randint(10, 50)
        radius_y = random.randint(10, 50)

        draw.ellipse(
            (
                center_x - radius_x,
                center_y - radius_y,
                center_x + radius_x,
                center_y + radius_y,
            ),
            fill= (211, 184, 140),
            outline=None,
            width=0,
        )
    square_size = 512 // 3
    for i in range(3):
        for j in range(3):
            square_position = (
                i * square_size,
                j * square_size,
                (i + 1) * square_size,
                (j + 1) * square_size
            )
            
            draw.rectangle(square_position, fill=None, outline="black", width=1)
            
            label_position = (square_position[0] + 10, square_position[1] + 10)
            draw.text(label_position, f'{chr(97+i).upper()}{3-j}', fill="white",font=ImageFont.truetype("arial.ttf", 25),stroke_width=2,stroke_fill='black')
    os.makedirs(os.path.dirname('fishing_levels/'+arg1+'/'), exist_ok=True)
    im.save('fishing_levels/'+arg1+'/lake_map.jpg')
    
    lake_data = []
    for i in range(3):
        for y in range(3):
            tmp_fish = []
            for j in range(len(all_fish.name)):
                for k in range(int(all_fish.loc[j,'proba']*100)):
                    tmp_fish.append(all_fish.loc[j,'name'])
            random.shuffle(tmp_fish)
            num_fish = random.randint(1,len(all_fish.name))
            lake_data.append({'x':i,'y':y,'fish':list(set(tmp_fish[:num_fish])),'bite_chance':random.uniform(0.6,0.9)})
    lake_data = pd.DataFrame(lake_data)
    lake_data.to_csv('fishing_levels/'+arg1+'/lake_data.csv')
    await message.channel.send(file=discord.File('fishing_levels/'+arg1+'/lake_map.jpg'))

async def handle_cast(message):
    init_msg = await message.channel.send('You cast your line into the water...')
    tries = 0
    lake_vars = pd.read_csv('fishing_levels/'+user_stats.loc[message.author.id,'lake']+'/lake_data.csv',index_col=0)
    user_loc = user_stats.loc[message.author.id,'fishing_pos']
    try:
        user_loc = ast.literal_eval(user_loc)
    except Exception as e:
        print(e)
    bite_chance = lake_vars[(lake_vars['x'] == int(user_loc[0])) & (lake_vars['y'] == int(user_loc[1]))].bite_chance
    print('bite chance:',bite_chance)

    while True:
        tries += 1
        if tries > 15:
            await init_msg.edit(content='No bites...\nMaybe try somewhere else?')
            return
        ran = random.random()
        if (ran > bite_chance).any():
            break
        await asyncio.sleep(1)
    await init_msg.add_reaction('❗')
    def check(reaction, user):
        return str(reaction.emoji) == '❗' and user.id == message.author.id
    try:
        reaction, user = await client.wait_for('reaction_add', timeout=1, check=check)
    except asyncio.TimeoutError:
        await init_msg.edit(content="You didn't react fast enough and the fish got away...\n(Hit ❗ faster when it pops up)")
        await init_msg.clear_reactions()
        return
    else:
        await init_msg.edit(content='You hooked the fish!\nGet ready...')
        await init_msg.clear_reactions()
        await asyncio.sleep(1)
        fish_pos = np.array([0,2])
        move_dict = {"⬅️":np.array([0,-1]),
                     "⬇️":np.array([1,0]),
                     "➡️":np.array([0,1]),
                     "💤":np.array([0,0])}
        
        fish_move_dict = {0:np.array([0,-1]),
                          1:np.array([0,1]),
                          2:np.array([0,0]),
                          3:np.array([0,0])}
        await init_msg.edit(content='🌊 🌊 🐠 🌊 🌊\n🌊 🌊 🌊 🌊 🌊\n🌊 🌊 🌊 🌊 🌊\n🌊 🌊 🌊 🌊 🌊\n🌊 🌊 🌊 🌊 🌊\n🌊 🌊 🌊 🌊 🌊\n               🙂')
        await init_msg.add_reaction("⬅️")
        await init_msg.add_reaction("⬇️")
        await init_msg.add_reaction("➡️")
        await init_msg.add_reaction("💤")
        def check_move(reaction, user):
            return str(reaction.emoji) in move_dict.keys() and user.id == message.author.id
        icons = ['🌊','🐠','💢']

        random_move = 0
        while True:
            await init_msg.add_reaction('🟢')
            try:
                reaction, user = await client.wait_for('reaction_add', timeout=2, check=check_move)
                move = move_dict[str(reaction.emoji)]
                await reaction.remove(user)
            except asyncio.TimeoutError:
                move = np.array([-1,0])
            await init_msg.remove_reaction('🟢',client.user)
            if random_move == 3: # if angry
                if move[0] == 0 and move[1] == 0:
                    pass
                else:
                    await init_msg.edit(content='The fish broke off!')
                    await init_msg.clear_reactions()
                    return
            else:
                fish_pos += move

            # move fish
            world = ''
            for i in range(6):
                # blank row
                if fish_pos[0] != i:
                    world += '🌊 🌊 🌊 🌊 🌊\n'
                else:
                    for x in range(5):
                        if fish_pos[1] == x: world += icons[1] + ' '
                        else: world += icons[0] + ' '
                    world += '\n'
            if fish_pos[0] > 5:
                world += '               🎣'
                break
            else:
                world += '               🙂'
            await init_msg.edit(content=world)

            await asyncio.sleep(1)

            random_move = random.randint(0,3)
            fish_pos += fish_move_dict[random_move]

            world = ''
            for i in range(6):
                # blank row
                if fish_pos[0] != i:
                    world += '🌊 🌊 🌊 🌊 🌊\n'
                else:
                    for x in range(5):
                        if fish_pos[1] == x:
                            if random_move == 3: world += icons[2] + ' '
                            else: world += icons[1] + ' '
                        else: world += icons[0] + ' '
                    world += '\n'
            world += '               🙂'
            await init_msg.edit(content=world)
            if fish_pos[0] < 0 or fish_pos[1] < 0 or fish_pos[1] > 4:
                await asyncio.sleep(1)
                await init_msg.edit(content='The fish got away!')
                await init_msg.clear_reactions()
                return
        # caught the fish
        await init_msg.edit(content=world)
        await asyncio.sleep(2)
        fish = lake_vars[(lake_vars['x'] == int(user_loc[0])) & (lake_vars['y'] == int(user_loc[1]))].fish

        fish = fish.values[0]

        fish = ast.literal_eval(fish)

        tmp_fish = []
        fish_in_tile = all_fish[all_fish['name'].isin(fish)]
        fish_in_tile = fish_in_tile.reset_index(drop=True)
        for j in range(len(fish_in_tile)):
            for _ in range(int(fish_in_tile.loc[j,'proba']*100)):
                tmp_fish.append(fish_in_tile.loc[j,'name'])
        random.shuffle(tmp_fish)


        mult = random.uniform(0.5,2)
        fish_stats = all_fish[all_fish['name'] == tmp_fish[0]]
        fish_stats = fish_stats.to_dict('records')[0]

        await init_msg.edit(content=f'You caught a {fish_stats["name"]}!\nIt\'s {round(fish_stats["size"] * mult,2)} Inches long and {round(fish_stats["weight"] * mult,2)} pounds.\n It\'s worth {round(fish_stats["value"] * mult)} {currency_name}.')
        user_stats.loc[message.author.id,'money'] += round(fish_stats["value"] * mult)
        user_stats.loc[message.author.id,'fish_caught'] += 1
        try: species = ast.literal_eval(user_stats.loc[message.author.id,'species_caught'].strip("'"))
        except: species = user_stats.loc[message.author.id,'species_caught']

        species.append(fish_stats['name'])
        species = list(set(species))
        user_stats.loc[message.author.id,'species_caught'] = "['"+"','".join([s for s in species])+"']"
        if float(fish_stats['size']) > float(user_stats.loc[message.author.id,'longest_catch']): user_stats.loc[message.author.id,'longest_catch'] = round(mult * fish_stats['size'],2)
        if float(fish_stats['weight']) > float(user_stats.loc[message.author.id,'heaviest_catch']): user_stats.loc[message.author.id,'heaviest_catch'] = round(mult * fish_stats['weight'],2)

        user_stats.to_csv('server_datasets/user_stats.csv')
        await init_msg.clear_reactions()



        

async def handle_get_sales(message):
    url = f"https://store.steampowered.com/api/featuredcategories?key={steam_api}&cc=CA"

    response = requests.get(url)
    #print(response.json())
    data = response.json()["specials"]['items']
    #print(data)

    #games_sorted = sorted(data, key=lambda x: x["discount_percent"], reverse=True)

    for i in range(3):
        game = data[i]
        name = game["name"]
        discount = game["discount_percent"]
        final_price = game["final_price"]/100
        original_price = game["original_price"]/100
        url = game['small_capsule_image']
        embed = discord.Embed(title=f'{name} is {discount}% off',description=f'It is now available for ${final_price} CAD\n(The original price was ${original_price} CAD)')
        embed.set_image(url=url)
        await message.channel.send(embed=embed)

async def handle_random_game(message):
    try:
        response = requests.get('https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/',
                            params={'key': steam_api, 'steamid': steam_acc_id, 'include_appinfo': 1, 'include_played_free_games': 1})
        owned_games = response.json()['response']['games']
        possible_games = [game for game in owned_games if game['playtime_forever'] > 30]
        random.shuffle(possible_games)
        embed = discord.Embed(title='3 Games You Could Play')
        for i in range(3):
            embed.add_field(name=possible_games[i]['name'],value=f"Playtime: {round(possible_games[i]['playtime_forever']/60,1)} hours.",inline=False)
        await message.channel.send(embed=embed)
    except Exception as e:
        await message.channel.send(e)

async def handle_similiar_songs(message,arg1):
    global spotify_token
    if arg1 == None:
        await message.channel.send('You need to provide a song to search for. EX: `/similiar_songs "Deacon Blues"`')
        return
    headers = {'Authorization': f'Bearer {spotify_token}'}
    response = requests.get('https://api.spotify.com/v1/search', 
                        headers=headers,
                        params={'q': arg1, 'type': 'track', 'limit': 1})
    if response.status_code == 401:
        url = "https://accounts.spotify.com/api/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        data = {
            "grant_type": "client_credentials",
            "client_id": spotify_client_id,
            "client_secret": spotify_secret,
        }

        response = requests.post(url, headers=headers, data=data)
        spotify_token = response.json()["access_token"]
        with open('cache/spotify_token.txt','w') as f:
            f.write(spotify_token)

        headers = {'Authorization': f'Bearer {spotify_token}'}
        response = requests.get('https://api.spotify.com/v1/search', 
                        headers=headers,
                        params={'q': arg1, 'type': 'track', 'limit': 1})
        if response.status_code == 401:
            await message.channel.send('api issue, please inform admin')
            return
    track_id = response.json()['tracks']['items'][0]['id']
    response = requests.get(f'https://api.spotify.com/v1/recommendations?limit=10&seed_tracks={track_id}',
                        headers=headers)
    
    recommended_tracks = response.json()['tracks']
    embed = discord.Embed(title=f'Similiar Tracks to {arg1}')
    for track in recommended_tracks:
        embed.add_field(name=track['name'], value = track['artists'][0]['name'],inline=False)
    await message.channel.send(embed=embed)

async def handle_similiar_artists(message,arg1):
    global spotify_token
    if arg1 == None:
        await message.channel.send('You need to provide an artist to search for. EX: `/similiar_artists "Lou Rawls"`')
        return
    headers = {'Authorization': f'Bearer {spotify_token}'}
    response = requests.get('https://api.spotify.com/v1/search', 
                        headers=headers,
                        params={'q': arg1, 'type': 'artist', 'limit': 1})
    if response.status_code == 401:
        url = "https://accounts.spotify.com/api/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        data = {
            "grant_type": "client_credentials",
            "client_id": spotify_client_id,
            "client_secret": spotify_secret,
        }

        response = requests.post(url, headers=headers, data=data)
        spotify_token = response.json()["access_token"]
        with open('cache/spotify_token.txt','w') as f:
            f.write(spotify_token)

        headers = {'Authorization': f'Bearer {spotify_token}'}
        response = requests.get('https://api.spotify.com/v1/search', 
                        headers=headers,
                        params={'q': arg1, 'type': 'artist', 'limit': 1})
        if response.status_code == 401:
            await message.channel.send('api issue, please inform admin')
            return
    artist_id = response.json()['artists']['items'][0]['id']
    response = requests.get(f'https://api.spotify.com/v1/recommendations?limit=10&seed_artists={artist_id}',
                        headers=headers)
    recommended_artists = response.json()['tracks']
    embed = discord.Embed(title=f'Similiar Artists to {arg1}',description='\n'.join([artist['artists'][0]['name'] for artist in recommended_artists]))
    await message.channel.send(embed=embed)
    
        

async def handle_coin_flip(message,other_user,wager):
    wager = int(wager)
    global user_stats
    if user_stats.loc[message.mentions[0].id,'money'] < wager:
        await message.channel.send(f'{message.mentions[0].mention} does not have enough {currency_name}.\nThey have {user_stats.loc[message.mentions[0].id,"money"]} {currency_name}')
    if user_stats.loc[message.author.id,'money'] < wager:
        await message.channel.send(f'{message.author.mention} does not have enough {currency_name}.\nThey have {user_stats.loc[message.author.id,"money"]} {currency_name}')
    print(message.mentions)
    await message.add_reaction("✅")
    await message.channel.send('Press the green checkmark to accept the challenge.')
    def check(reaction, user):
        return str(reaction.emoji) == '✅' and user.id == message.mentions[0].id
    try:
        reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await message.channel.send("No one pressed ✅\nCancelling the game.")
        return
    if random.random() > 0.5:
        await message.channel.send(f'{message.author.mention} won {wager*2} {currency_name}!')
        user_stats.loc[user.id,'money'] -= wager
        user_stats.loc[message.author.id,'money'] += wager
        user_stats.to_csv('server_datasets/user_stats.csv')
    else:
        await message.channel.send(f'{message.mentions[0].mention} won {wager*2} {currency_name}!')
        user_stats.loc[user.id,'money'] += wager
        user_stats.loc[message.author.id,'money'] -= wager
        user_stats.to_csv('server_datasets/user_stats.csv')
    

async def check_user_stats(message):
    global user_stats
    embed = discord.Embed(title=f'Server Stats for {message.author.display_name}:')
    stats_dict = user_stats.loc[message.author.id].to_dict()
    embed.add_field(name=f'Bank Account',value=f'{stats_dict["money"]} {currency_name}',inline=False)
    embed.add_field(name=f'Fish Caught',value=f'{stats_dict["fish_caught"]}',inline=False)
    embed.add_field(name=f'Number of Species Caught',value=f'''{len(ast.literal_eval(stats_dict["species_caught"].strip("'")))}''',inline=False)
    embed.add_field(name=f'Longest Fish Caught',value=f'{stats_dict["longest_catch"]} inches',inline=False)
    embed.add_field(name=f'Heaviest Fish Caught',value=f'{stats_dict["heaviest_catch"]} pounds',inline=False)
    for asset in user_stats.columns:
        if asset not in ["money", "lake", "fish_caught", "fishing_pos", "species_caught", "longest_catch", "heaviest_catch"] and 'ignore' not in asset:
            value = round(float(stats_dict[asset]),3)
            if value > 0:
                embed.add_field(name=f'{asset}', value=f'~{value}', inline=True)
    await message.channel.send(embed=embed)

async def create_user_stats():
    users = dict()
    # change this if bot is on multiple servers
    for user in client.guilds[0].members:
        if user != client.user:
            users[user.id] = {'money':10000,'fishing_pos':[0,0],'lake':'Server Lake','fish_caught':0,'species_caught':[],'longest_catch':0,'heaviest_catch':0}
    df = pd.DataFrame.from_dict(users,orient='index')
    df.to_csv('server_datasets/user_stats.csv')
    return df

async def handle_run(message,runs=5):
    tmp = await message.channel.send(f'Starting a monster run!\nReact with 🙋‍♂️ to join the game.\nYou have 30 seconds to confirm players and start by pressing ✅')
    await tmp.add_reaction("🙋‍♂️")
    await tmp.add_reaction("✅")
    def check(reaction, user):
        return str(reaction.emoji) == '✅'
    try:
        reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await message.channel.send("No one pressed ✅\nCancelling the game.")
        return
    users = []
    failed_users = []
    tmp = await message.channel.fetch_message(tmp.id)
    for reaction in tmp.reactions:
        if str(reaction.emoji) == "🙋‍♂️":
            async for user in reaction.users():
                if user not in users and not user.bot:
                    users.append(user)
    print(len(users))
    if len(users):
        await message.channel.send(f"Starting Game with {len(users)} player(s).\n\nYou will have 5 seconds to decide to run right, left, or straight, good luck.")
    else:
        await message.channel.send('No players joined the game. Cancelling. Press 🙋‍♂️ when prompted to join the game next time.')
        return
    current_run = 0
    answer_dict = {"⬅️":0,"⬆️":1,"➡️":2}
    while current_run < runs and len(users):
        embed = discord.Embed(title=f'{runs - current_run} turns left. Go right, left, or straight')
        tmp = await message.channel.send(embed=embed)
        await tmp.add_reaction("⬅️")
        await tmp.add_reaction("⬆️")
        await tmp.add_reaction("➡️")
        await asyncio.sleep(5)
        tmp = await message.channel.fetch_message(tmp.id)
        answered = []
        answer = random.randint(0,2)
        for reaction in tmp.reactions:
            if reaction.emoji in answer_dict.keys():
                async for user in reaction.users():
                    if user != client.user and user not in answered and user in users:
                        if answer_dict[reaction.emoji] == answer:
                            print(answer)
                            print('hit ' + user.display_name)
                            users.remove(user)
                            failed_users.append(user)
                        print(answer)
                        print('pass')
                        answered.append(user)
        for user in users:
            if user not in answered:
                failed_users.append(user)
                users.remove(user)
        if len(failed_users):
            user_mentions = ' '.join([user.mention for user in failed_users])
            embed = discord.Embed(title='Players that got eaten by the monster:', description=user_mentions, color=0xFF0000)
            failed_users.clear()

        else:
            embed = discord.Embed(title='No one got eaten by the monster!', color=0x00ff00)
        await message.channel.send(embed=embed)
        await asyncio.sleep(3)
        current_run += 1
    if len(users):
            user_mentions = ' '.join([user.mention for user in users])
            embed = discord.Embed(title='Players that escaped the monster:', description=user_mentions, color=0x00ff00)
            embed.add_field(name='Reward:', value=f'50 {currency_name}')
            for user in users:
                user_stats.loc[user.id,'money'] += 50
            user_stats.to_csv('server_datasets/user_stats.csv')
            failed_users.clear()
    else:
        embed = discord.Embed(title='No one survived the monster..', color=0xFF0000)
    await message.channel.send(embed=embed)


async def extract_face(message,link = None,pad_size=0):
    if pad_size < 0: pad_size = 0
    detector = FaceDetector(detectionCon=0.6)
    if link == None:
        await message.channel.send('Please provide a link to the image containing a face to extract. `/extract_face <link.png>`')
        return
    response = requests.get(link)
    if 'png' in link:
        with open('cache/face.png', 'wb') as f:
            f.write(response.content)
        image = Image.open('cache/face.png')
        image = image.convert('RGB')
        image.save('cache/face.jpg')
    else:
        with open('cache/face.jpg', 'wb') as f:
            f.write(response.content)
        image = Image.open('cache/face.jpg')
        #image.save('cache/face.png')

    image = Image.open('cache/face.jpg')

    im, bbox = detector.findFaces(np.array(image),draw=False)

    if len(bbox) > 0: # if face was detected
        print('hit')
        # get crop coords
        x, y, w, h = bbox[0][0]

        # pad them
        if pad_size == 0: pad = 0
        else: pad = np.min([image.size[0],image.size[1]]) // pad_size
        
        x1, y1, = x+w, y+h
        x -= pad
        y -= pad
        x1 += pad
        y1 += pad
            
        # do some ugly padding management to avoid overshoot
        if x < 0: x = 0
        if y < 0: y = 0
        if x > image.size[0]: x = image.size[0]
        if y > image.size[1]: y = image.size[1]
        if x1 > image.size[0]: x1 = image.size[0]
        if y1 > image.size[1]: y1 = image.size[1]
        if x1 < 0: x1 = 0
        if y1 < 0: y1 = 0
            
        # simple crop
        im = im[y:y1,x:x1]

        # anti alias scale to desired ratio
        im = Image.fromarray(im)
            
        im.save(f"cache/extracted_face.png")
        await message.channel.send(file=discord.File('cache/extracted_face.png'))
    else:
        await message.channel.send('Face not Detected.')

async def handle_trivia(message,rounds, difficulty = None):
    url = f'https://opentdb.com/api.php?amount={rounds}'
    if difficulty != None: url += f'&difficulty={difficulty}'
    try:
        questions = requests.get(url).json()
    except Exception as e:
        await message.channel.send(e)
        await message.channel.send('Error retreiving trivia questions. Did you call the command correctly? Example: `/start_trivia 3 easy`')
    tmp = await message.channel.send(f'Retrieved {rounds} questions!\nReact with 🙋‍♂️ to join the game.\nYou have 30 seconds to confirm players and start by pressing ✅')
    await tmp.add_reaction("🙋‍♂️")
    await tmp.add_reaction("✅")
    def check(reaction, user):
        return str(reaction.emoji) == '✅'
    try:
        reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await message.channel.send("No one pressed ✅\nCancelling the game.s")
        return
    users = []
    score = dict()
    tmp = await message.channel.fetch_message(tmp.id)
    for reaction in tmp.reactions:
        if str(reaction.emoji) == "🙋‍♂️":
            async for user in reaction.users():
                if user not in users and not user.bot:
                    users.append(user)
                    score[user] = 0
    print(len(users))
    if len(users):
        await message.channel.send(f"Starting Game with {len(users)} player(s).\n\nYou will have 10 seconds to answer each question, good luck.")
    else:
        await message.channel.send('No players joined the game. Cancelling. Press 🙋‍♂️ when prompted to join the game next time.')
        return
    current_question = 0
    type_translator = {'boolean':'True or False','multiple':'Multiple Choice'}
        
    while current_question < len(questions['results']):
        embed = discord.Embed(title='Get ready for the next question!')
        embed.add_field(name='Category',value=questions["results"][current_question]["category"],inline=False)
        embed.add_field(name='Difficulty',value=questions["results"][current_question]["difficulty"],inline=False)
        embed.add_field(name='Type',value=type_translator[questions["results"][current_question]["type"]],inline=False)

        await message.channel.send(embed=embed)
        await asyncio.sleep(5)
        correct_answer = html.unescape(questions["results"][current_question]['correct_answer'])
        incorrect_answers = html.unescape(questions["results"][current_question]['incorrect_answers'])
        answers = incorrect_answers
        answers.append(correct_answer)
        random.shuffle(answers)
        if questions["results"][current_question]["type"] == 'multiple':
            embed = discord.Embed(title=f'Question:\n\n{html.unescape(questions["results"][current_question]["question"])}',description=f'**Possible Answers:**\n1️⃣ {html.unescape(answers[0])}\n2️⃣ {html.unescape(answers[1])}\n3️⃣ {html.unescape(answers[2])}\n4️⃣ {html.unescape(answers[3])}', color=0x00ff00)
            tmp = await message.channel.send(embed=embed)
            await tmp.add_reaction("1️⃣")
            await tmp.add_reaction("2️⃣")
            await tmp.add_reaction("3️⃣")
            await tmp.add_reaction("4️⃣")
            answer_dict = {'1️⃣':answers[0],'2️⃣':answers[1],'3️⃣':answers[2],'4️⃣':answers[3]}
        else:
            embed = discord.Embed(title=f'Question:\n\n{html.unescape(questions["results"][current_question]["question"])}',description=f'Possible Answers:\n1️⃣ {html.unescape(answers[0])}\n2️⃣ {html.unescape(answers[1])}', color=0x00ff00)
            tmp = await message.channel.send(embed=embed)
            await tmp.add_reaction("1️⃣")
            await tmp.add_reaction("2️⃣")
            answer_dict = {'1️⃣':answers[0],'2️⃣':answers[1]}
        await asyncio.sleep(10)
        tmp = await message.channel.fetch_message(tmp.id)
        answered = []
        for reaction in tmp.reactions:
            if reaction.emoji in answer_dict.keys():
                async for user in reaction.users():
                    if user != client.user and user not in answered and user in users:
                        if answer_dict[reaction.emoji] == correct_answer:
                            score[user] += 1
                        answered.append(user)
        current_question+=1
        highest_score = max(score.values())
        winners = [key for key, value in score.items() if value == highest_score]
        if len(winners) == 1:
            tmp = await message.channel.send(f'**The correct answer was:**\n\n\n*"{correct_answer}"*\n\n\n{winners[0].mention} is in the lead with {highest_score} points!')
        else:
            tmp = await message.channel.send(f'**The correct answer was:**\n\n\n*"{correct_answer}"*\n\n\nThere are {len(winners)} people tied for the lead with {highest_score} points!')

        await tmp.add_reaction("⏭️")
        def check_next(reaction, user):
            return str(reaction.emoji) == '⏭️'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check_next)
        except:
            pass

    embed = discord.Embed(title='Final Scores!')
    for user in score.keys():
        embed.add_field(name=user.display_name,value=score[user],inline=False)
    await message.channel.send(embed=embed)


    

async def handle_recommendation(message,arg1):
    global recommended_songs
    global take_requests
    global senders
    if arg1.lower() == 'allow':
        take_requests = True
        await message.channel.send('Requests are now being taken for this listening session. (to make this permanent change requests_allowed to True in the bot script)')
    if arg1.lower() == 'forbid':
        take_requests = False
        await message.channel.send('Requests are no longer being taken for this listening session. (to make this permanent change requests_allowed to False in the bot script)\nDo `/recommend clear` to clear recommendations')
    if arg1.lower() =='clear':
        
        recommended_songs = []
        senders = []
        await message.channel.send('Cleared recommendation queue.')
        return

    url = await extract_youtube_id(arg1)
    if url == None:
        await message.channel.send('link is not a youtube video')
        print(message.author.name)
        return
    else:
        recommended_songs.append(url)
        senders.append(message.author.display_name)
        await message.add_reaction('✅')

async def handle_editor(message,cmd,arg1=None,arg2=None,arg3=None, arg4=None,fps=30):
    if arg1 == 'None':arg1=None
    if arg2 == 'None':arg2=None
    if arg3 == 'None':arg3=None
    if arg4 == 'None':arg4=None

    if cmd == 'load':
        await message.channel.send('downloading...')
        if arg1 == None:
            await message.channel.send('no link provided.\nTry: `/editor load <link_to_video>`')
            return
        try: del loaded_video
        except: pass
        gc.collect()
        url = await extract_youtube_id(arg1)
        if url == None:
            try:
                if 'discordapp' in arg1:
                    response = requests.get(arg1)
                    if os.path.isfile('cache/loaded_vid.mp4'):
                        os.remove('cache/loaded_vid.mp4')
                    with open('cache/loaded_vid'+arg1[arg1.rfind('.'):], 'wb') as f:
                        f.write(response.content)
                    if arg1[arg1.rfind('.'):] != '.mp4':
                        video_clip = VideoFileClip('cache/loaded_vid'+arg1[arg1.rfind('.'):])
                        video_clip.write_videofile('cache/loaded_vid.mp4', fps=fps,codec='libx264')
                    await message.add_reaction('✅')
            except:
                await message.channel.send("Given argument is not a youtube link or a link to an video on discord")
                return
        else:
            options = {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "outtmpl": 'cache/loaded_vid.mp4',
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
            } 
            if arg2: options['start_time'] = float(arg2)
            if arg3: options['start_time'] = float(arg3)
            if os.path.isfile('cache/loaded_vid.mp4'):
                os.remove('cache/loaded_vid.mp4')
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
            await message.add_reaction('✅')

    try:
        loaded_video = VideoFileClip('cache/loaded_vid.mp4')
    except:
        await message.channel.send('No video loaded, call `/editor load <link_to_video>`')
        return

    if cmd == 'replace_audio':
        if arg1 == None:
            try:
                await message.channel.send('No url to audio to replace provided, removing audio')
                loaded_video = loaded_video.without_audio()
                loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
                try:
                    await message.channel.send(file=discord.File('cache/output_vid.mp4'))
                except Exception as e:
                    await message.channel.send(f"File size: {round(os.path.getsize('cache/output_vid.mp4') / (1024 * 1024),1)}Mb\nAs a bot my limit is 25MB, try compressing.")
            except Exception as e:
                await message.channel.send(e)
            return
        try:
            if os.path.isfile('cache/audio.mp3'):
                    os.remove('cache/audio.mp3')
            url = await extract_youtube_id(arg1)
            if url == None:
                try:
                    if 'discordapp' in arg1:
                        response = requests.get(arg1)
                        with open('cache/audio', 'wb') as f:
                            f.write(response.content)
                        audio = AudioFileClip('cache/audio')
                except:
                    await message.channel.send("Given argument is not a youtube link or a link to an mp3/wav")
                    return
            else:
                options = {
                "format": "bestaudio/best",
                "outtmpl": 'cache/audio.mp3',
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                }
                if os.path.isfile('cache/audio.mp3'):
                    os.remove('cache/audio.mp3')
                with yt_dlp.YoutubeDL(options) as ydl:
                    ydl.download([url])
                audio = AudioFileClip('cache/audio.mp3')
            if arg2 == 'a': loaded_video = loaded_video.subclip(0,audio.duration)
            if arg2 == 'v': audio = audio.subclip(0, loaded_video.duration)
            loaded_video = loaded_video.set_audio(audio)
            if os.path.isfile('cache/output_vid.mp4'):
                os.remove('cache/output_vid.mp4')
            loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
            await message.channel.send(file=discord.File('cache/output_vid.mp4'))
        except Exception as e:
            await message.channel.send(e)

    elif cmd == 'stats':
        duration = loaded_video.duration
        size = loaded_video.size
        bitrate = int(os.path.getsize('cache/loaded_vid.mp4') / (duration * 170))
        filesize = os.path.getsize('cache/loaded_vid.mp4') / (1024 * 1024)

        await message.channel.send(f"Duration: {duration:.2f} seconds\nSize: {size[0]}x{size[1]} pixels\nBitrate: ~{bitrate} kbps\nFilesize: {filesize:.2f} MB")
    
    elif cmd == 'compress':
        if arg1 == None:
            arg1 = 'b'
            await message.channel.send('No method provided, Executing biterate reduction')
            if arg2 == None:
                arg2 = 25
                await message.channel.send('No target size provided, aiming for 25mb')

        if arg1 == 'b':
            arg2 = int(arg2)
            bitrate = ((arg2 * 8 * 1024) / loaded_video.duration) * 0.75
            loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264',bitrate=str(int(bitrate))+'k')
            try:
                await message.channel.send(file=discord.File('cache/output_vid.mp4'))
            except Exception as e:
                await message.channel.send(f"File size: {round(os.path.getsize('cache/output_vid.mp4') / (1024 * 1024),1)}Mb\nAs a bot my limit is 25Mb, you can reach out to an admin if the file is <25mb and you can't get it lower.")
        elif arg1 == 'r':
            try:
                if arg2 == None and arg3 == None:
                    await message.channel.send('No resizing arguments provided. Shrinking by 0.5')
                    arg2 = loaded_video.size[0] // 2
                    arg3 = loaded_video.size[1] // 2
                    loaded_video = loaded_video.resize((arg2,arg3))
                    loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
                elif arg3 == None:
                    await message.channel.send(f'Resizing by {arg2}')
                    arg3 = int(loaded_video.size[1] * float(arg2))
                    arg2 = int(loaded_video.size[0] * float(arg2))
                    loaded_video = loaded_video.resize((arg2,arg3))
                    loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
                else:
                    loaded_video = loaded_video.resize((arg2,arg3))
                    loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
                try:
                    await message.channel.send(file=discord.File('cache/output_vid.mp4'))
                except Exception as e:
                    await message.channel.send(f"File size: {round(os.path.getsize('cache/output_vid.mp4') / (1024 * 1024),1)}Mb\nAs a bot my limit is 25Mb, you can reach out to an admin if the file is <25mb and you can't get it lower.")
            except Exception as e:
                await message.channel.send(e)
        else: 
            await message.channel.send('no method provided.\nTry: `/editor compress b` to reduce bitrate, a to remove audio, and r to resize')
            return
    elif cmd =='reverb':
        if arg1 == None:arg1 = 0.25
        if arg2 == None:arg2 = 0.5
        if arg3 == None: arg3 = 0.33
        board = Pedalboard([Reverb(room_size=float(arg1),wet_level=float(arg3),dry_level=float(arg2))])
        audio = loaded_video.audio
        audio.write_audiofile('cache/input_audio.wav')
        with AudioFile('cache/input_audio.wav') as f:
            with AudioFile('cache/output_audio.wav','w',f.samplerate,f.num_channels) as o:
                while f.tell() < f.frames:
                    chunk = f.read(int(f.samplerate))
                    
                    # Run the audio through our pedalboard:
                    effected = board(chunk, f.samplerate, reset=False)
                    
                    # Write the output to our output file:
                    o.write(effected)

        try:
            await message.channel.send(file=discord.File(f'cache/output_audio.wav'))
        except Exception as e:
            await message.channel.send(e)
    elif cmd =='distortion':
        if arg1 == None:arg1 = 25
        board = Pedalboard([Distortion(drive_db = float(arg1))])
        audio = loaded_video.audio
        audio.write_audiofile('cache/input_audio.wav')
        with AudioFile('cache/input_audio.wav') as f:
            with AudioFile('cache/output_audio.wav','w',f.samplerate,f.num_channels) as o:
                while f.tell() < f.frames:
                    chunk = f.read(int(f.samplerate))
                    
                    # Run the audio through our pedalboard:
                    effected = board(chunk, f.samplerate, reset=False)
                    
                    # Write the output to our output file:
                    o.write(effected)

        try:
            await message.channel.send(file=discord.File(f'cache/output_audio.wav'))
        except Exception as e:
            await message.channel.send(e)
            
    elif cmd == 'fx':
        if arg1 == 'speed': 
            if arg2 == None:
                await message.channel.send('No factor to multiply speed by set.\nTry:`/editor fx speed 2` to increase speed by 2x')
                return
            loaded_video = loaded_video.speedx(factor=float(arg2))
            if os.path.isfile('cache/output_vid.mp4'):
                os.remove('cache/output_vid.mp4')
            await asyncio.sleep(1)
            loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
            await message.channel.send(file=discord.File('cache/output_vid.mp4'))
        elif arg1 == 'loop':
            if arg2 == None and arg3 == None:
                await message.channel.send('No duration or number of loops set.\nTry:`/editor fx loop 5` for a 5 second loop or `/editor fx loop None 5` to loop the video 5 times')
                return
            if arg1: loaded_video = loaded_video.loop(duration = float(arg2))
            elif arg2: loaded_video = loaded_video.loop(n = int(arg3))
            if os.path.isfile('cache/output_vid.mp4'):
                os.remove('cache/output_vid.mp4')
            await asyncio.sleep(1)
            loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
            await message.channel.send(file=discord.File('cache/output_vid.mp4'))

    elif cmd == 'top_text':
        if arg1 == None:
            await message.channel.send('What text do you want to add?\nTry:`/editor top_text "my text"`')
            return
        if arg2 == None: arg2=50
        if arg3 == None: arg3 = 'white'
        if arg4 == None:
            try:
                arg4 = 'fonts/impact.ttf'
            except:
                arg4 = 'Arial'
        elif 'fonts' not in 'arg4': arg4 = 'fonts/'+arg4
        
        text = TextClip(arg1,fontsize=float(arg2),color=arg3,font=arg4,method='caption',stroke_color='black',size=(loaded_video.size[0],None)).set_duration(loaded_video.duration)
        text = text.set_pos(('center','top'))
        loaded_video = CompositeVideoClip([loaded_video, text])

        if os.path.isfile('cache/output_vid.mp4'):
            os.remove('cache/output_vid.mp4')
        await asyncio.sleep(1)
        loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
        await message.channel.send(file=discord.File('cache/output_vid.mp4'))
    
    elif cmd == 'bottom_text':
        if arg1 == None:
            await message.channel.send('What text do you want to add?\nTry:`/editor top_text "my text"`')
            return
        if arg2 == None: arg2=50
        if arg3 == None: arg3 = 'white'
        if arg4 == None: arg4 = 'impact.ttf'
        
        text = TextClip(arg1,fontsize=float(arg2),color=arg3,font=arg4,method='caption',stroke_color='black',size=(loaded_video.size[0],None)).set_duration(loaded_video.duration)
        text = text.set_pos(('center','bottom'))
        loaded_video = CompositeVideoClip([loaded_video, text])

        if os.path.isfile('cache/output_vid.mp4'):
            os.remove('cache/output_vid.mp4')
        await asyncio.sleep(1)
        loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
        await message.channel.send(file=discord.File('cache/output_vid.mp4'))

    elif cmd == 'save':
        try:
            if loaded_video is not None:
                loaded_video.close()
                del loaded_video
            gc.collect()
            if os.path.isfile('cache/loaded_vid.mp4'):
                os.remove('cache/loaded_vid.mp4')
            await asyncio.sleep(0.5)
            os.rename('cache/output_vid.mp4','cache/loaded_vid.mp4')
            await message.add_reaction('✅')
        except Exception as e:
            await message.channel.send(e)
            return
        
    elif cmd == 'concat':
        if arg1 == None:
            await message.channel.send('You need to provide the link to the video you want to concatenate to the loaded video.')
            return
        try:
            url = await extract_youtube_id(arg1)
            if url == None:
                try:
                    if 'discordapp' in arg1:
                        response = requests.get(arg1)
                        with open('cache/concat_vid'+arg1[arg1.rfind('.'):], 'wb') as f:
                            f.write(response.content)
                        if arg1[arg1.rfind('.'):] != '.mp4':
                            video_clip = VideoFileClip('cache/concat_vid'+arg1[arg1.rfind('.'):])
                            video_clip.write_videofile('cache/concat_vid.mp4', fps=fps,codec='libx264')
                except:
                    await message.channel.send("Given argument is not a youtube link or a link to an video on discord")
                    return
            else:
                options = {
                    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "outtmpl": 'cache/concat_vid.mp4',
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                } 
                if arg2: options['start_time'] = float(arg2)
                if arg3: options['start_time'] = float(arg3)
                if os.path.isfile('cache/concat_vid.mp4'):
                    os.remove('cache/concat_vid.mp4')
                with yt_dlp.YoutubeDL(options) as ydl:
                    ydl.download([url])
            
            clip2 = VideoFileClip('cache/concat_vid.mp4')
            w,h = clip2.size
            w2,h2 = loaded_video.size
            if w != w2 or h != h2:
                await message.channel.send('resizing video 2 to fit video 1. Aspect ratio may be lost.')
                clip2=clip2.resize((w2,h2))
            output = concatenate_videoclips([loaded_video,clip2])
            if os.path.isfile('cache/output_vid.mp4'):
                os.remove('cache/output_vid.mp4')
            await asyncio.sleep(1)
            output.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
            await message.channel.send(file=discord.File('cache/output_vid.mp4'))
        except Exception as e:
            await message.channel.send(e)

    elif cmd == 'clip':
        if arg1 == None: arg1 = 0
        if arg2 == None:
            await message.channel.send('must provide a time to cut the video at. Example: `/editor clip 0 10` clips the first 10 seconds.')
            return
        loaded_video = loaded_video.subclip(float(arg1),float(arg2))
        if os.path.isfile('cache/output_vid.mp4'):
                os.remove('cache/output_vid.mp4')
        await asyncio.sleep(1)
        loaded_video.write_videofile('cache/output_vid.mp4', fps=fps,codec='libx264')
        await message.channel.send(file=discord.File('cache/output_vid.mp4'))



async def handle_scrape_music(message,arg1=None):
    channel = client.get_channel(music_channel)
    messages = []
    await message.channel.send('Scraping, filtering, and cleaning ALL messages. This may take a while. Keep your eye on the console for updates...')
    current_message = 0
    async for message in channel.history(limit=arg1):#change limit to something if this takes forever as .history is not efficient
        url = await extract_youtube_id(message.content)
        if url != None: messages.append(url)

        print(f'Done message {current_message}/{arg1}', end='\r')
        current_message += 1

    music_list = pd.Series(messages)
    music_list.to_csv('server_datasets/music_dataset.csv',index=False)
    await message.channel.send(f'Scraped {len(messages)} songs from music channel and saved to CSV')

async def extract_youtube_id(message):
    if 'https://y' in message or 'https://music.y' in message or 'https://www.y' in message:
        for word in message.split():
            # make sure it's a youtube link
            if 'https://y' in word or 'https://music.y' in word or 'https://www.y' in word:
                url = word

                pattern = r'^https?://(?:www\.|m\.)?(?:youtube\.com/watch\?v=|youtu\.be/|music\.youtube\.com/watch\?v=)([\w-]+)'

                # this extracts the video id so we don't download entire playlists or other nonsense
                url = re.match(pattern, url)
                try:
                    url= url.group(1)
                    url = 'https://www.youtube.com/watch?v='+url
                    return url
                except Exception as e:
                    print(e)
                    print(word)
                    print(url)
                    return None
    else: return None
        
    

async def handle_interp(message,link1,link2,interp_times=2):
    try:
        interp_times = int(interp_times)
        if link1 == None or link2 == None:
            await message.channel.send('Must provide links to images. Example:\n`/interp <link1> <link2> <interp_times>`')
            return
        
        response = requests.get(link1)
        if 'png' in link1:
            with open('cache/interp1.png', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/interp1.jpg', 'wb') as f:
                f.write(response.content)
                image1 = Image.open('cache/interp1.jpg')
                image1.save('cache/interp1.png')
            

        response = requests.get(link2)
        if 'png' in link2:
            with open('cache/interp2.png', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/interp2.jpg', 'wb') as f:
                f.write(response.content)
                image2 = Image.open('cache/interp2.jpg')
                image2.save('cache/interp2.png')
        
        image1 = Image.open('cache/interp1.png')
        image2 = Image.open('cache/interp2.png')

        image1 = await handle_shrink(image1)
        image2 = await handle_shrink(image2)

        w1,h1 = image1.size
        w2,h2 = image2.size
        if h1 != h2 or w1 != w2:
            if (w1 / h1) != (w2/h2):
                m = 'WARNING: Aspect ratios are different, img2 will be squeezed to fit img1...'
            else:
                m = 'Resizing img2 to fit img1...'
            await message.channel.send(m)
            image2 = image2.resize((w1,h1))

        image1.save('cache/interp1.png')
        image2.save('cache/interp2.png')

        output = replicate.run(
            "google-research/frame-interpolation:4f88a16a13673a8b589c18866e540556170a5bcb2ccdc12de556e800e9456d3d",
            input={"frame1": open("cache/interp1.png", "rb"),
                "frame2": open("cache/interp2.png","rb"),
                "times_to_interpolate":interp_times}
        )
        response = requests.get(output)
        print(output)
        with open('cache/interp_vid.mp4', 'wb') as f:
            f.write(response.content)
            await message.channel.send(file=discord.File('cache/interp_vid.mp4'))
    except Exception as e:
        await message.channel.send(e)

async def handle_explanation(message,link,question):
    if link == None or question == None:
        await message.channel.send('Must provide link to your black and white doodle and a question. Example:\n`/explain <link> "question"')
        return
    try:
        response = requests.get(link)
        if 'png' in link:
            with open('cache/question.png', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/question.jpg', 'wb') as f:
                f.write(response.content)
            image = Image.open('cache/question.jpg')
            image.save('cache/question.png')
        image = Image.open('cache/question.png')
        image = await handle_shrink(image)
        image.save('cache/question.png')

        output = replicate.run(
                "salesforce/blip:2e1dddc8621f72155f24cf2e0adbde548458d3cab9f00c0139eea840d0ac4746",
                input={"image": open("cache/question.png", "rb"),
                    "task":"visual_question_answering",
                    "question":question}
            )
        await message.channel.send(output)
    except Exception as e:
        await message.channel.send(e)

async def handle_doodle(message,link,prompt):
    try:
        if link == None or prompt == None:
            await message.channel.send('Must provide link to your black and white doodle and a prompt. Example:\n`/doodle <link> "prompt"')
            return
        response = requests.get(link)
        if 'png' in link:
            with open('cache/doodle.png', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/doodle.jpg', 'wb') as f:
                f.write(response.content)
            image = Image.open('cache/doodle.jpg')
            image.save('cache/doodle.png')
        output = replicate.run(
            "jagilley/controlnet-scribble:435061a1b5a4c1e26740464bf786efdfa9cb3a3ac488595a2de23e143fdb0117",
            input={"image": open("cache/doodle.png", "rb"),
                "prompt":prompt}
        )
        image = Image.open('cache/doodle.png')
        image = await handle_shrink(image)
        image.save('cache/doodle.png')

        response = requests.get(output[1])
        with open('cache/doodle.png', 'wb') as f:
            f.write(response.content)
        print(output)
        await message.channel.send(file=discord.File('cache/doodle.png'))
    except Exception as e:
        await message.channel.send(e)

async def handle_aging(message,link,age=None):
    if age == None:
        age = 'default'
    if link == None:
        await message.channel.send('You must link an image of someones face.\nExample: `/age_face <link>`')
        return
    try:
        response = requests.get(link)
        if 'png' in link:
            with open('cache/face_to_edit.png', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/face_to_edit.jpg', 'wb') as f:
                f.write(response.content)
            image = Image.open('cache/face_to_edit.jpg')
            image.save('cache/face_to_edit.png')
        image = Image.open('cache/face_to_edit.png')
        image = await handle_shrink(image)
        image.save('cache/face_to_edit.png')

        output = replicate.run(
            "yuval-alaluf/sam:9222a21c181b707209ef12b5e0d7e94c994b58f01c7b2fec075d2e892362f13c",
            input={"image": open("cache/face_to_edit.png", "rb"),
                "target_age":age}
        )
        response = requests.get(output)
        if age == 'default':
            with open('cache/edited_face.gif', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/edited_face.png', 'wb') as f:
                f.write(response.content)
        print(output)
        if age == 'default': await message.channel.send(file=discord.File('cache/edited_face.gif'))
        else: await message.channel.send(file=discord.File('cache/edited_face.png'))
    except Exception as e:
        await message.channel.send(e)
    

async def handle_face_edit(message,link,prompt,manipulation_strength=4.1,disentanglement_threshold=0.15):
    if disentanglement_threshold < 0.08:
        disentanglement_threshold = 0.08
        await message.channel.send('Minimum disentanglement threshold is 0.08, setting to 0.08')
    elif disentanglement_threshold > 0.3:
        disentanglement_threshold = 0.3
        await message.channel.send('Maximum disentanglement threshold is 0.3, setting to 0.3')

    if manipulation_strength > 10.0:
        manipulation_strength = 10
        await message.channel.send('Maximum manipulation strength is 10, setting to 10')
    elif manipulation_strength < -10.0:
        manipulation_strength = -10
        await message.channel.send('Minimum manipulation strength is -10, setting to -10')
    
    if link == None or prompt == None:
        await message.channel.send('You need to enter a link to the image you want to manipulate and a prompt of how you want to manipulate it.\nExample:\n/edit_face <link> "a face with a bowl cut"')
        return
    
    try:
        response = requests.get(link)
        if 'png' in link:
            with open('cache/face_to_edit.png', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/face_to_edit.jpg', 'wb') as f:
                f.write(response.content)
            image = Image.open('cache/face_to_edit.jpg')
            image.save('cache/face_to_edit.png')

        image = Image.open('cache/face_to_edit.png')
        image = await handle_shrink(image)
        image.save('cache/face_to_edit.png')

        output = replicate.run(
            "orpatashnik/styleclip:7af9a66f36f97fee2fece7dcc927551a951f0022cbdd23747b9212f23fc17021",
            input={"input": open("cache/face_to_edit.png", "rb"),
                "target":prompt,
                "manipulation_strength":float(manipulation_strength),
                "disentanglement_threshold":float(disentanglement_threshold)}
        )
        response = requests.get(output)
        with open('cache/edited_face.jpg', 'wb') as f:
            f.write(response.content)
        print(output)
        await message.channel.send(file=discord.File('cache/edited_face.jpg'))
        await message.channel.send("Output didn't look how you expected?\nMake sure your prompt starts with 'a face with'\nTry changing the manipulation strength and disentanglement threshold.\n`/edit_face <link> \"prompt\" float(manipulation) float(entanglement)")
    except Exception as e:
        await message.channel.send(e)

async def handle_video_gen(message,prompt):
    if prompt == None:
        await message.channel.send('Please enter a prompt\nExample:\n`/gen_video "a panda eating bamboo on a rock"')
        return
    try:
        output = replicate.run(
            "cjwbw/damo-text-to-video:1e205ea73084bd17a0a3b43396e49ba0d6bc2e754e9283b2df49fad2dcf95755",
            input={"prompt": prompt}
        )
        response = requests.get(output)
        with open('cache/generated_video.mp4', 'wb') as f:
            f.write(response.content)
        print(output)
        await message.channel.send(file=discord.File('cache/generated_video.mp4'))
    except Exception as e:
        await message.channel.send(e)

async def handle_restore(message,prompt = None):
    if prompt == None:
        await message.channel.send('You need to provide an image to restore.\nExample:\n\t`/restore <link_to_img>`')
    try:
        response = requests.get(prompt)
        if 'png' in prompt:
            with open('cache/old_img.png', 'wb') as f:
                f.write(response.content)
        else:
            with open('cache/old_img.jpg', 'wb') as f:
                f.write(response.content)
            image = Image.open('cache/old_img.jpg')
            image.save('cache/old_img.png')

        image = Image.open('cache/old_img.png')
        image = await handle_shrink(image)
        image.save('cache/old_img.png')
            
        output = replicate.run(
        "tencentarc/gfpgan:9283608cc6b7be6b65a8e44983db012355fde4132009bf99d976b2f0896856a3",
        input={"img": open("cache/old_img.png", "rb")}
        )

        response = requests.get(output)
        with open('cache/restored_img.png', 'wb') as f:
            f.write(response.content)
        await message.channel.send(file=discord.File('cache/restored_img.png'))
    except Exception as e:
        await message.channel.send(e)

    print(output)

async def handle_sd(message,prompt = None, model=0):
    # add any other stable diffusion models you want to use here.
    models = ["stability-ai/stable-diffusion:db21e45d3f7023abc2a46ee38a23973f6dce16bb082a930b0c49861f96d1e5bf",
              "ai-forever/kandinsky-2:65a15f6e3c538ee4adf5142411455308926714f7d3f5c940d9f7bc519e0e5c1a"]
    if model > len(models) or model < 0:
        model = 0
        await message.channel.send(f'model selection argument not valid. Using default model.\nSyntax is\n`/sd "prompt" x` where x is an integer ranging from 0-{len(models)}')

    if prompt == None:
        await message.channel.send('You need to provide a prompt.\nExample:\n\t`/sd "a cow jumping over the moon"`')
    try:
        output = replicate.run(
        models[model],
        input={"prompt": prompt}
        )
        if model == 0: response = requests.get(output[0])
        else: response = requests.get(output)
        try:
            with open('cache/sd.png', 'wb') as f:
                f.write(response.content)
            await message.channel.send(file=discord.File('cache/sd.png'))
        except Exception as e:
            await message.channel.send(e)
            await message.channel.send(output)
    except Exception as e:
        await message.channel.send(e)

async def handle_style_transfer(message):
    max_size = 8000000 
    params = message.content.split()
    
    try:
        url1 = params[1]
        url2 = params[2]
    except:
        await message.channel.send('poor request format. It should be URL1(main photo), URL2(new background)')
        return
    
    response = requests.get(url1)
    if 'png' in url1:
        with open('cache/content_image.png', 'wb') as f:
            f.write(response.content)
    else:
        with open('cache/content_image.jpg', 'wb') as f:
            f.write(response.content)
        image = Image.open('cache/content_image.jpg')
        image.save('cache/content_image.png')

    image = Image.open('cache/content_image.png')
    image = await handle_shrink(image)
    image.save('cache/content_image.png')

    response = requests.get(url2)
    if 'png' in url2:
        with open('cache/style_image.png', 'wb') as f:
            f.write(response.content)
    else:
        with open('cache/style_image.jpg', 'wb') as f:
            f.write(response.content)
        image = Image.open('cache/style_image.jpg')
        image.save('cache/style_image.png')

    image = Image.open('cache/style_image.jpg')
    image = await handle_shrink(image)
    image.save('cache/style_image.jpg')

    content_image = Image.open('cache/content_image.png')
    content_image = content_image.convert('RGB')
    max_dim = 512
    size = tuple((int(np.ceil(max_dim * d / max(content_image.size))) for d in content_image.size))
    content_image = content_image.resize(size, Image.Resampling.LANCZOS)
    content_image = np.array(content_image).astype('float32') / 255.0
    content_image = np.expand_dims(content_image, axis=0)

    style_image = Image.open('cache/style_image.png')
    style_image = style_image.convert('RGB')
    max_dim = 512
    size = tuple((int(np.ceil(max_dim * d / max(style_image.size))) for d in style_image.size))
    style_image = style_image.resize(size, Image.Resampling.LANCZOS)
    style_image = np.array(style_image).astype('float32') / 255.0
    style_image = np.expand_dims(style_image, axis=0)

    #Light style transfer model
    st_model = hub.load('https://tfhub.dev/google/magenta/arbitrary-image-stylization-v1-256/2')
    
    stylized_image = st_model(tf.constant(content_image), tf.constant(style_image))[0]
    stylized_image = stylized_image*255
    stylized_image = np.array(stylized_image, dtype=np.uint8)
    if np.ndim(stylized_image)>3:
        assert stylized_image.shape[0] == 1
    stylized_image = stylized_image[0]
    stylized_image = Image.fromarray(stylized_image)

    stylized_image.save('cache/output_image.png')

    while os.path.getsize('cache/output_image.png') > max_size:
        new_size = tuple(int(x*0.9) for x in stylized_image.size)
        stylized_image = stylized_image.resize(new_size, Image.Resampling.LANCZOS)
        stylized_image.save('cache/output_image.png')

    await message.channel.send(file=discord.File('cache/output_image.png'))

    del st_model
    gc.collect()

async def handle_replace_bg(message,url1,url2,sensitivity,passes):
    if sensitivity == None: sensitivity = 0.6
    if passes == None: passes = 1
    if url1 == None or url2 == None:
        await message.channel.send('poor request format. It should be URL1(main photo), URL2(new background), sensitivity, passes. Example: "@remove_background URL1, URL2, 0.6 1')
    response = requests.get(url1)
    if 'png' in url1:
        with open('cache/input_image.png', 'wb') as f:
            f.write(response.content)
    else:
        with open('cache/input_image.jpg', 'wb') as f:
            f.write(response.content)
        image = Image.open('cache/input_image.jpg')
        image.save('cache/input_image.png')

    image = Image.open('cache/input_image.png')
    image = await handle_shrink(image)
    image.save('cache/input_image.png')

    response = requests.get(url2)
    if 'png' in url2:
        with open('cache/input_background.png', 'wb') as f:
            f.write(response.content)
    else:
        with open('cache/input_background.jpg', 'wb') as f:
            f.write(response.content)
        image = Image.open('cache/input_background.jpg')
        image.save('cache/input_background.png')

    image = Image.open('cache/input_background.png')
    image = await handle_shrink(image)
    image.save('cache/input_background.png')
    
    max_size = 8000000 

    image = Image.open('cache/input_image.png')
    bg_image = cv2.imread('cache/input_background.png')

    while os.path.getsize('cache/input_image.png') > max_size:
        new_size = tuple(int(x*0.9) for x in image.size)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        image.save('cache/input_image.png')

    image = cv2.imread('cache/input_image.png')

    for _ in range(int(passes)):
        height, width, channel = image.shape
        results = selfie_segmentation.process(image)
        

        mask = results.segmentation_mask
        condition = np.stack(
            (mask,) * 3, axis=-1) > float(sensitivity)
        bg_image = cv2.resize(bg_image, (width, height))

        output_image = np.where(condition, image, bg_image)

        cv2.imwrite('cache/input_image.png', output_image)

    image = Image.open('cache/input_image.png')

    while os.path.getsize('cache/input_image.png') > max_size:
        new_size = tuple(int(x*0.9) for x in image.size)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        image.save('cache/input_image.png')

    await message.channel.send(file=discord.File('cache/input_image.png'))

async def handle_remove_bg(message,url=None,sensitivity=None,passes=None):
    if sensitivity == None: sensitivity = 0.6
    if passes == None: passes = 1
    if url == None:
        await message.channel.send('No url included. It should be URL, sensititivy, passes. Example: "@remove_background URL 0.6 1')
        return
    response = requests.get(url)
    if 'png' in url:
        with open('cache/input_image.png', 'wb') as f:
            f.write(response.content)
    else:
        with open('cache/input_image.jpg', 'wb') as f:
            f.write(response.content)
        image = Image.open('cache/input_image.jpg')
        image.save('cache/input_image.png')

    image = Image.open('cache/input_image.png')
    image = await handle_shrink(image)
    image.save('cache/input_image.png')
    
    max_size = 8000000 

    image = Image.open('cache/input_image.png')
    bg_image = cv2.imread('cache/blank.png')

    while os.path.getsize('cache/input_image.png') > max_size:
        new_size = tuple(int(x*0.9) for x in image.size)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        image.save('cache/input_image.png')

    image = cv2.imread('cache/input_image.png')

    for _ in range(int(passes)):
        height, width, channel = image.shape
        results = selfie_segmentation.process(image)
        

        mask = results.segmentation_mask
        condition = np.stack(
            (results.segmentation_mask,) * 3, axis=-1) > float(sensitivity)
        bg_image = cv2.resize(bg_image, (width, height))

        output_image = np.zeros((height, width, 4), dtype=np.uint8)
        output_image[:, :, :3] = np.where(condition, image, bg_image)
        output_image[:, :, 3] = (condition[:, :, 0] * 255).astype(np.uint8)

        cv2.imwrite('cache/input_image.png', output_image)

    image = Image.open('cache/input_image.png')

    while os.path.getsize('cache/input_image.png') > max_size:
        new_size = tuple(int(x*0.9) for x in image.size)
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    image.save('cache/input_image.png')

    await message.channel.send(file=discord.File('cache/input_image.png'))

async def handle_news(ctx,arg1,arg2):
    global loop
    global news
    if arg1.lower() == 'more':
        if news == []:
            await ctx.channel.send('No news has been retrived yet. Please call "/news" or "/news <topic>"')
            return
        loop += 3
        if loop >= len(news['articles']):
            await ctx.message.channel.send('**That\'s all the news**')
        else:
            for i in range(3):
                embed = discord.Embed(title=news['articles'][i + loop]['title'], url=news['articles'][i + loop]['url'])
                if news['articles'][i]['urlToImage'] != None:
                    embed.set_image(url=news['articles'][i + loop]['urlToImage'])
                else: embed.set_image(url='https://media.istockphoto.com/id/1369150014/vector/breaking-news-with-world-map-background-vector.jpg?s=612x612&w=0&k=20&c=9pR2-nDBhb7cOvvZU_VdgkMmPJXrBQ4rB1AkTXxRIKM=')
                if news['articles'][i]['description'] != None:
                    embed.description = news['articles'][i + loop]['description']
                else: embed.description = f'No description, try calling /news explain {i+1} or clicking the hyperlink...'
                await ctx.message.channel.send(embed=embed)
            
    elif arg1.lower() == 'explain':
        if news == []:
            await ctx.message.channel.send('No news has been retrived yet. Please call "/news" or "/news <topic>"')
            return
        if arg2 == '': arg2 = 1
        arg2 = int(arg2) - 1

        url = news['articles'][arg2 + loop]['url']
        print('making request')
        response = requests.get(url)
        print(response)
        print('scraping...')
        soup = BeautifulSoup(response.content, 'html.parser')
        if soup != None:
            paragraphs = soup.find_all('p')
            article_text = ' '.join([p.get_text() for p in paragraphs])
            print('done')
            article_length = len(article_text)
            if article_length > 2000:
                print('hi')
                start = 0
                end = 2000
                while start < article_length:
                    tmp = await ctx.message.channel.send(article_text[start:end])
                    await tmp.add_reaction('⬇️')
                    start += 2000
                    end += 2000
                    def check(reaction, user):
                        return str(reaction.emoji) == '⬇️'
                    try:
                        reaction, user = await client.wait_for('reaction_add', timeout=180, check=check)
                    except asyncio.TimeoutError:
                        await tmp.clear_reactions()
                        break
                    if end > article_length:
                        end = article_length
            else:
                await ctx.message.channel.send(article_text)
        else: await ctx.message.channel.send(f'Sorry there was an issue webscraping this article. Please inspect HTML elements {news["articles"][arg2 + loop]["url"]}')

    elif arg1 != '':
        # setup admin gate to search for specific topics
        if ctx.message.author.id == admin_id:
            loop = 0
            prompt = arg1+'&'

            now = datetime.now()
            two_days_ago = now - timedelta(days=2)
            formatted_date = two_days_ago.strftime("from=%Y-%m-%d&")

            url = ('https://newsapi.org/v2/everything?'
                f'q={prompt}'
                f'from={formatted_date}'
                'sortBy=popularity&'
                'pageSize=30&'
                f'apiKey={news_key}')
            news = requests.get(url).json()
            for i in range(3):
                embed = discord.Embed(title=news['articles'][i + loop]['title'], url=news['articles'][i + loop]['url'])
                if news['articles'][i]['urlToImage'] != None:
                    embed.set_image(url=news['articles'][i + loop]['urlToImage'])
                else: embed.set_image(url='https://media.istockphoto.com/id/1369150014/vector/breaking-news-with-world-map-background-vector.jpg?s=612x612&w=0&k=20&c=9pR2-nDBhb7cOvvZU_VdgkMmPJXrBQ4rB1AkTXxRIKM=')
                if news['articles'][i]['description'] != None:
                    embed.description = news['articles'][i + loop]['description']
                else: embed.description = f'No description, try calling /news explain {i+1} or clicking the hyperlink...'
                await ctx.message.channel.send(embed=embed)
        else:
            if arg1.lower() in news_topics or len(news_topics) == 0:
                loop = 0
                prompt = arg1+'&'
                now = datetime.now()
                two_days_ago = now - timedelta(days=2)
                formatted_date = two_days_ago.strftime("from=%Y-%m-%d&")

                url = ('https://newsapi.org/v2/everything?'
                f'q={prompt}'
                f'from={formatted_date}'
                'sortBy=popularity&'
                'pageSize=30&'
                f'apiKey={news_key}')

                news = requests.get(url).json()
                for i in range(3):
                    embed = discord.Embed(title=news['articles'][i + loop]['title'], url=news['articles'][i + loop]['url'])
                    if news['articles'][i]['urlToImage'] != None:
                        embed.set_image(url=news['articles'][i + loop]['urlToImage'])
                    else: embed.set_image(url='https://media.istockphoto.com/id/1369150014/vector/breaking-news-with-world-map-background-vector.jpg?s=612x612&w=0&k=20&c=9pR2-nDBhb7cOvvZU_VdgkMmPJXrBQ4rB1AkTXxRIKM=')
                    if news['articles'][i]['description'] != None:
                        embed.description = news['articles'][i + loop]['description']
                    else: embed.description = f'No description, try calling /news explain {i+1} or clicking the hyperlink...'
                    await ctx.message.channel.send(embed=embed)
            else:
                await ctx.message.channel.send(f'please choose from one of the following topics or recommend a new one: {news_topics}')
    elif arg1 == '':
        loop = 0
        url = ('https://newsapi.org/v2/top-headlines?'
            'language=en&'
            'pageSize=30&'
            f'apiKey={news_key}')
        news = requests.get(url).json()
        for i in range(3):
            embed = discord.Embed(title=news['articles'][i + loop]['title'], url=news['articles'][i + loop]['url'])
            if news['articles'][i]['urlToImage'] != None:
                embed.set_image(url=news['articles'][i + loop]['urlToImage'])
            else: embed.set_image(url='https://media.istockphoto.com/id/1369150014/vector/breaking-news-with-world-map-background-vector.jpg?s=612x612&w=0&k=20&c=9pR2-nDBhb7cOvvZU_VdgkMmPJXrBQ4rB1AkTXxRIKM=')
            if news['articles'][i]['description'] != None:
                embed.description = news['articles'][i + loop]['description']
            else: embed.description = f'No description, try calling /news explain {i+1} or clicking the hyperlink...'
            await ctx.message.channel.send(embed=embed)

async def handle_radio(message):
    global take_requests
    take_requests = requests_allowed
    # join channel message sender is in
    req = take_requests
    try:
        vchannel = message.author.voice.channel
        await vchannel.connect()
        voice_channel = message.guild.voice_client
    except:
        await message.channel.send('Please join a voice channel first')
        return

    # get songs
    try:
        music = pd.read_csv('server_datasets/music_dataset.csv',header=0)
    except:
        await message.channel.send('No music dataset found. Scraping channel now.')
        await handle_scrape_music(message,None)
        music = pd.read_csv('server_datasets/music_dataset.csv',header=0)

    # select, process, and stream random song
    stream_url, music = await handle_dj(music,dj_intros)

    # play the dj radiostation intro
    voice_channel.play(discord.FFmpegPCMAudio('cache/tts_audio.mp3'))
    while voice_channel.is_playing():
        await asyncio.sleep(1)
    
    # play first song
    voice_channel.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS))
    while voice_channel.is_playing():
        await asyncio.sleep(1)

    # enter loop
    playing_music = True
    while playing_music:
        # same thing but we pass dj_bridges instead of dj_intros
        stream_url, music = await handle_dj(music,dj_bridges)

        voice_channel.play(discord.FFmpegPCMAudio('cache/tts_audio.mp3'))
        while voice_channel.is_playing():
            await asyncio.sleep(1)

        voice_channel.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS))
        while voice_channel.is_playing():
            await asyncio.sleep(1)

async def handle_dj(music,dj_clips):
    audio_url = ''
    video_title = ''
    current_clip = ''
    global last_clip
    global last_song
    global recommended_songs
    global senders
    global current_song_link
    global current_song_title

    if recommended_songs: # if theres a reco song in queue then use that.
        url = recommended_songs.pop(0)
        name = senders.pop(0)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['formats'][5]['url']
            video_title = info.get('title', None)
            current_song_title = video_title
            current_song_link = url
            duration = info.get('duration')
        # make sure he isn't repeating himself
        current_clip = random.choice(dj_recomended).format(name,'my friend')
        while current_clip == last_clip:
            current_clip = random.choice(dj_recomended).format(name,'my friend')

        # update last used clips and songs
        last_clip = current_clip

        # generate tts and return
        engine.save_to_file(current_clip + ' ' + video_title, 'cache/tts_audio.mp3')
        engine.runAndWait()
    else:
        find_url = True
        while find_url:
            # try random url and pop it so it's only played once.
            index = random.randint(0, len(music) - 1)
            print(len(music)-1)
            url = music.iloc[index, 0]
            music.drop(index=index, inplace=True)
            music = music.reset_index(drop=True)
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    # I've found the 5th index to be best. You can change this if you like
                    audio_url = info['formats'][5]['url']
                    video_title = info.get('title', None)
                    duration = info.get('duration')
                    current_song_title = video_title
                    current_song_link = url
                # if video is 10 minutes+ we don't use it
                if duration > 600:
                    pass
                else:
                    find_url = False
            except:
                print('error with video, trying another')

        # make sure he isn't repeating himself
        current_clip = random.choice(dj_clips)
        while current_clip == last_clip:
            current_clip = random.choice(dj_clips)

        # update last used clips and songs
        last_clip = current_clip

        # generate tts and return
        engine.save_to_file(current_clip + ' ' + video_title, 'cache/tts_audio.mp3')
        engine.runAndWait()
    
    return audio_url, music

async def handle_video(message,link):
    url = await extract_youtube_id(link)
    if url == None:
        await message.channel.send('Link is not recognized as a youtube video. If you believe this is an error, show link to admin\nsyntax: `/play <link>`')
        return
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        audio_url = info['formats'][5]['url']
        # [I use this for exploring different formats]
        #for i, format in enumerate(info['formats']):
        #    print(f"{i}: {format['format_id']} - {format['ext']} - {format['acodec']} - {format['vcodec']} - {format['height']}p")
    #print(audio_url)
    
    channel = message.author.voice.channel
    await channel.connect()
    voice_channel = message.guild.voice_client
    voice_channel.play(discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS))
    while voice_channel.is_playing():
        await asyncio.sleep(1)
    await voice_channel.disconnect()

async def fetch_chat(message,type,channel):
    channel = client.get_channel(channel)
    messages = []
    async for message in channel.history(limit=1000):
        messages.append(message)
    channel = client.get_channel(main_chat)
    while True:
        random_message = random.choice(messages)
        if type==1:
            if random_message.attachments:
                attachment_url = random_message.attachments[0].url
                await channel.send(attachment_url)
                break
        elif type==0:
            if random_message.content:
                await channel.send(random_message.content)
                break
            elif random_message.attachments:
                attachment_url = random_message.attachments[0].url
                await channel.send(attachment_url)
                break

async def handle_chat(message,msg):
    global chat_history
    chat_history.append({"role": "user", "content": f'Respond to this as {bot_name}: "{msg}"'})
    async with openai.AsyncClient() as client:
        request = await openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=chat_history
        )
    chat_history.append({"role": "assistant", "content": request['choices'][0]['message']['content']})
    await message.channel.send(request['choices'][0]['message']['content'])
    if 'bye' in msg:
        await wipe_memory()

async def handle_dm(message, prompt):
    global chat_history
    chat_history.append({"role": "user", "content": f'Respond to this as a dungeon master: "{prompt}"'})
    request = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=chat_history
    )
    chat_history.append({"role": "assistant", "content": request['choices'][0]['message']['content']})
    await message.channel.send(request['choices'][0]['message']['content'])
    if 'bye' in prompt:
        await wipe_memory()


async def handle_generator(message,prompt):
    response = openai.Image.create(
    prompt=prompt,
    n=1,
    size="1024x1024"
    )
    image_url = response['data'][0]['url']
    response = requests.get(image_url)
    with open('cache/image.png', 'wb') as f:
        f.write(response.content)
    await message.channel.send(file=discord.File('cache/image.png'))

async def handle_variation(message,url):
    try:
        response = requests.get(url)
        if url[-2] == 'n':
            with open('cache/image.png', 'wb') as f:
                f.write(response.content)
            image = Image.open('cache/image.png')
            w,h=image.size
            await message.channel.send('squeezing image to 1:1 ratio...')
            image = image.resize((1024,1024))
            image.save('cache/image.png')
        else:
            with open('cache/image.jpg', 'wb') as f:
                f.write(response.content)
            image = Image.open('cache/image.jpg')
            w,h=image.size
            await message.channel.send('squeezing image to 1:1 ratio...')
            image = image.resize((1024,1024))
            image.save('cache/image.png')
        await message.channel.send('creating variation...')
        response = openai.Image.create_variation(
        image=open('cache/image.png', "rb"),
        n=1,
        size="1024x1024"
        )
        image_url = response['data'][0]['url']
        response = requests.get(image_url)
        with open('cache/image.png', 'wb') as f:
            f.write(response.content)
        await message.channel.send(file=discord.File('cache/image.png'))
    except Exception as e:
        await message.channel.send(e)
    await message.channel.send('done')

async def handle_voice_channel(message, speak_when_spoken_to = False):
    channel = message.author.voice.channel
    await channel.connect()
    voice_channel = message.guild.voice_client
    listen = True
    r = sr.Recognizer()
    loop = True
    ch=[{"role": "system", "content": personality}]
    while loop:
        try:
            if listen:
                with sr.Microphone() as source:
                    audio = r.listen(source, timeout=7, phrase_time_limit=7)
                try:
                    text = r.recognize_google(audio)
                    print(f'Text: {text}')
                    if speak_when_spoken_to:
                        if bot_name.lower() in text.lower():
                            listen = False
                            print('speaking')
                        await asyncio.sleep(1)
                    else:
                        listen = False
                        print('speaking')
                except sr.UnknownValueError:
                    print("Sorry, I couldn't understand what was said.")
                    await asyncio.sleep(1)
                except sr.RequestError:
                    print("Sorry, my speech recognition service is unavailable at the moment.")
                except:
                    await asyncio.sleep(1)
            else:
                try:
                    if len(ch) > 6: ch.pop(1)
                    ch.append({"role": "user", "content": f'Respond to this as {bot_name}: "{text}"'})
                    request = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=ch
                    )
                    engine.save_to_file(request['choices'][0]['message']['content'], 'cache/tts_audio.mp3')
                    engine.runAndWait()
                    if len(ch) > 6: ch.pop(1)
                    ch.append({"role": "assistant", "content": request['choices'][0]['message']['content']})
                    voice_channel.play(discord.FFmpegPCMAudio('cache/tts_audio.mp3'))
                    while voice_channel.is_playing():
                        await asyncio.sleep(1)
                    if 'goodbye' in text:
                        await voice_channel.disconnect()
                        print(ch)
                        break
                    else:
                        listen = True
                        print('listening')
                except Exception as e:
                    print(e)
        except Exception as e:
            print(e)
            asyncio.sleep(1)

async def get_permission(ctx):
    admin = await commands.MemberConverter().convert(ctx, str(admin_id))
    tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
    await tmp.add_reaction("👍")
    def check(reaction, user):
        return user.id == admin_id and str(reaction.emoji) == '👍'
    try:
        reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("Sorry, the command request has timed out.")
        await tmp.delete()
        return False
    else:
        await tmp.delete()
        return True

client.load_extension("src.testcog")
client.run(bot_token)