import re,cv2,yt_dlp,asyncio,pyttsx3,random,requests,openai,discord,subprocess,os,gc
import numpy as np
from discord.ext import commands
import replicate as rp
from time import sleep
from discord.utils import get
from PIL import Image
import speech_recognition as sr
import tensorflow as tf
import mediapipe as mp
import tensorflow_hub as hub
from bs4 import BeautifulSoup
from moviepy.editor import *
import pandas as pd

# customize these fields
# go to line 548 to set up custom responses to non commands

# unless you customize the speech to text try and make this easily/intuitively interpretable by a speech to text solution. EX: instead of 'Adum' do 'Adam'
bot_name = 'bot'
bot_token  = os.environ['discord_bot']

# right click user and hit 'copy id'
admin_id = 123

# channel to pull shared music from (for radio station)
music_channel = 123

# channel to pull random images from (maybe a channel of only memes?)
random_image_channel = 123

# chat that the bot will send messages in when it's unsure of where else. /rand_image and /rand_chat pull from here too.
main_chat = 123

# if you want to restrict what users can look up add accepted topics to this list.
news_topics = ['tech','stock market','crypto','movies','tv','videogames']
# if you want users to look up anything make the list empty. (news_topics = [])

# FREE news api
# get a key here: https://newsapi.org/
news_key = os.environ['news_api']

# You need an openai pay as you go key to use openai stuff.
openai.api_key = os.environ['openai_key']

# replicat AI API.
# free key here: https://replicate.com/
replicate = rp.Client(api_token = os.environ['replicate'])

# describe what you want the bots personality to be. If unsure you can do something like 'you are a helpful assistant who loves to help people'
personality = f"You are a cheery, funny, and helpful friend. Your name is {bot_name}. When you see the word 'recipe' you give concise and tasty recipes."
chat_history= [{"role": "system", "content": personality}]


# voice lines the radio station host / dj will say when joining the call.
dj_intros = [f"Hello hello, you just tuned into the station with the smoothest beats on air.. I'm your host {bot_name} and without further ado our first song of the night is ",
             "That song really reminds me of the summer of 1988... If you're just tuning in now we've got a good vibe going and up next is ",
             f"You already know what's up.. It's {bot_name} with beats that will blow your mind. Let's get right into it with ",
             # add as many as you like.
             ]

# voice lines the radio station host / dj will say between songs.
dj_bridges = ['coming at you next is',
              'this is a classic you may not have heard before... or maybe you have who knows... stick around for',
              'that was nice but this next one is even better...',
              "See what they did there before the chorus hit? Incredible... This next song has a couple sneaky things like that too..."
              # add as many as you like.
              ]

# voice lines played when introducing recommended songs {} will be formatted as the users name
dj_recomended = ['Alright while that song was playing {} phoned in and asked me to play a little something. I have not heard it before so I gotta say I am pretty excited. Here comes',
                 "{} called in and wanted to change the vibe up a bit so without further a do",
                 "That song was great and {} wanted to keep the ball rolling so he requested I play "
                 # add as many as you like.
                 ]


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
alpaca_memory = list()

playing_music = False
last_clip = ''
last_song = ''
recommended_songs = []
senders = []



try:
    music_list = pd.read_csv('music_dataset.csv',header=0)
except:
    music_list = pd.Series()
    print('no music dataset found. run /scrape_music')

requests_allowed = True

take_requests = False

#####################################################################################################
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~{ COMMANDS }~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
#####################################################################################################


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

# custom help
client.remove_command('help')
@client.command(description='',name='help', brief='Shows a list of commands')
async def help_command(ctx):
    embed = discord.Embed(title=f'General Help', description='This is a massive bot so I grouped help into the following subcategories:', color=0x00ff00)
    embed.add_field(name='🧠 /help_ai',value='Deep AI Commands. image generation, chatbots, image restoration, etc.',inline=False)
    embed.add_field(name='📰 /help_news',value='Interact with news API and webscrape contents.',inline=False)
    embed.add_field(name='📷 /help_image_editing',value='Commands to manipulate images. Resizing, cropping, background removal, etc.',inline=False)
    embed.add_field(name='🎦 /help_video_editing',value='Video editor inside of discord.',inline=False)
    embed.add_field(name='🎶 /help_music',value='Commands to play music. request songs, personal dj, downloading songs, etc.',inline=False)
    embed.add_field(name='❔ /help_misc',value='Miscellaneous commands.',inline=False)
    await ctx.send(embed=embed)


@client.command(description='',name='help_ai', brief='Shows a list of commands')
async def help_ai(ctx):
    embed = discord.Embed(title=f'AI Help', description='If it has a money icon it costs money and you likely need permission to use:', color=0x00ff00)
    for command in client.commands:
        if command.description == 'ai':
            embed.add_field(name='🧠 ' + command.name, value=command.brief, inline=False)
    await ctx.send(embed=embed)

@client.command(description='',name='help_news', brief='Shows a list of commands')
async def help_news(ctx):
    embed = discord.Embed(title=f'News Help', description='/news has a few subcommands, here they are.', color=0x00ff00)
    embed.add_field(name='📰 /news', value='Retrieves and embeds the latest top 3 most popular articles.', inline=False)
    embed.add_field(name='📰 /news explain x y', value='Where `x` is a number from 1 to 3. This will webscrape the url and print the contents of the article.\nWhere `y` is a number from 1-inf representing how many discord paragraphs the bot can return. Leave empty for full article.', inline=False)
    embed.add_field(name='📰 /news more', value='Shows more articles continuing to sort by popularity.', inline=False)
    embed.add_field(name='📰 /news <topic>', value='Retrieves and embeds the latest top 3 most popular articles about a given topic.', inline=False)
    await ctx.send(embed=embed)

@client.command(description='',name='help_image_editing', brief='Shows a list of commands')
async def help_image_editing(ctx):
    embed = discord.Embed(title=f'Image Editor Help', description='Remove Background, resize, crop, etc.', color=0x00ff00)
    for command in client.commands:
        if command.description == 'edit':
            embed.add_field(name=command.name, value=command.brief, inline=False)
    await ctx.send(embed=embed)

@client.command(description='',name='help_video_editing', brief='Shows a list of commands')
async def help_video_editing(ctx):
    embed = discord.Embed(title=f'Video Editor Help', description='/editor has a lot of commands, here they are:', color=0x00ff00)
    embed.add_field(name='🎦 /editor load <link>', value='Loads the video you will be working with.', inline=False)
    embed.add_field(name='🎦 /editor save', value='Saves the output video as the working video.\nThis way you don\'t have to reload the original video over and over if you mess up.', inline=False)
    embed.add_field(name='🎦 /editor stats', value='Send stats of the video, bit rate, size, length, and resolution.', inline=False)
    embed.add_field(name='🎦 /editor fx <method> <factor>', value='A couple ways to manipulate the video.(more being added)\n`/editor fx speed 5` multiplies video speed by 5.\n`/editor fx loop 5` loops the video for 5 seconds.\n`/editor fx loop None 5` loops the video 5 times.', inline=False)
    embed.add_field(name='🎦 /editor top_text "text" <size> <color> <font>', value='Adds top text to video (default is Impact) Font is automatically fit to video width and wrapped.\n`/editor top_text "hello world" 50 red impact.ttf` adds red impact size 50 font to the top of the video,\nsize,color,and font parameter can be left blank, those are the default values.\nTo use other fonts they must be downloaded and placed in the bots working directory.', inline=False)
    embed.add_field(name='🎦 /editor bottom_text "text" <size> <color> <font>', value='Same thing but bottom text.', inline=False)
    embed.add_field(name='🎦 /editor compress <method> <arg1> <arg2>', value='Means for compressing videos.\n`/editor compress b` compression via bitrate reduction. Leaving arg 1 blank will aim for a target size of ~25mb. `/editor compress b 8` will aim for 8 mb.\n`/editor compress r` Lower the resolution. By default it halves it but can be specified through arg 1 and 2.\n`/editor compress r 0.33` will make a resolution one third the original.\n`/editor compress r 1920 1080` resizes to 1920x1080', inline=False)
    embed.add_field(name='🎦 /editor replace_audio <link> <priority>', value='Replaces audio of working video with audio from video you link to.\nLeave empty to remove audio.\nThe priority argument can be passed as `a` or `v`\n`v` will make the duration fit the video, `a` will make the duration fit the audio. Default is `a`.\n', inline=False)
    embed.add_field(name='❗ *NOTE:*', value='Codec is h.264 with medium preset and a crf of 23. Discord doesn\'t support 265 and vp9 and av1 are too slow.\nMore fx will be added. Extreme speeding of the video can occasionally corrupt audio and may prevent you from doing other tasks. Remove the audio using audio_replace to modify further.\nDiscord bots have a max upload of 8mb. If you can not compress it further, ask if an admin can fish it out of the working directory.', inline=False)

    await ctx.send(embed=embed)

@client.command(description='',name='help_music', brief='Shows a list of commands')
async def help_music(ctx):
    embed = discord.Embed(title=f'Music Command Help', description='Play song, start dj station, download songs, etc', color=0x00ff00)
    for command in client.commands:
        if command.description == 'music':
            embed.add_field(name=':musical_note: ' + command.name, value=command.brief, inline=False)
    await ctx.send(embed=embed)

@client.command(description='',name='help_misc', brief='Shows a list of commands')
async def help_music(ctx):
    embed = discord.Embed(title=f'Miscellaneous Command Help', description='Fetch random chats', color=0x00ff00)
    for command in client.commands:
        if command.description == 'misc':
            embed.add_field(name=':frame_photo: '+command.name, value=command.brief, inline=False)
    await ctx.send(embed=embed)

@client.command(description = 'news',brief=':newspaper:\nGet Top Headlines. \nExamples:\n/news = top headlines globally\n/news more = show more articles.\n/news "movies" = show articles about movies/other topic\n/news explain 1 -1 = webscrape content of first article linked, -1 = no char limit, 1 = 2000 char limit, etc.',name='news')
async def news(ctx, arg1 = '', arg2 = '', arg3 = -1):
    await handle_news(ctx,arg1,arg2,arg3)

@client.command(description = 'ai',brief=':moneybag: \nTalk to the bot in voice chat (admin only // costs money!). \nExample:\n/talk = make the bot join the call (speak_when_spoken_to = False!).\n say "goodbye" to make the bot leave and wipe memory.',name='talk')
async def talk(ctx):
    if ctx.message.author.id == admin_id:await handle_voice_channel(ctx.message)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_voice_channel(ctx.message)

@client.command(description = 'ai',brief=':moneybag: \nTalk to the bot in voice chat (admin only // costs money!). \nExample:\n/talk = make the bot join the call (speak_when_spoken_to = True!).\n say "goodbye" to make the bot leave and wipe memory.',name='speak_when_spoken_to')
async def speak_when_spoken_to(ctx):
    if ctx.message.author.id == admin_id:await handle_voice_channel(ctx.message, speak_when_spoken_to=True)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_voice_channel(ctx.message, speak_when_spoken_to=True)

@client.command(description = 'ai',brief=':moneybag: \nTalk to the bot in text chat (admin only // costs money!). \nExample:\n/chat "hey <bot_name> how are you?" = it will send a text response. Type "bye" in message to wipe memory.',name='chat')
async def chat(ctx):
    if ctx.message.author.id == admin_id:await handle_chat(ctx.message)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_chat(ctx.message)

@client.command(description = 'ai',brief=':moneybag: \nStart a dnd adventure (expiremental WIP) (admin only // costs money!). \nExample:\n/adventure I am a monk, where am I = dungeon master dnd response.',name='adventure')
async def adventure(ctx):
    global chat_history
    chat_history = [{"role": "system", "content": f"You an excellent dungeon master who asks players what their next move is after speaking."}]
    if ctx.message.author.id == admin_id:await handle_dm(ctx.message)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_dm(ctx.message)

@client.command(description = 'ai',brief=':moneybag: \nGenerate Image with Openai (admin only // costs money!). \nExample:\n/gen_image a siamese cat = generates and posts a 1024x1024 image of a white cat.',name='gen_image')
async def gen_image(ctx):
    if ctx.message.author.id == admin_id:await handle_generator(ctx.message)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_generator(ctx.message)

@client.command(description = 'ai',brief=':moneybag: \nMake a variation of an image with Openai (admin only // costs money!). \nExample:\n/var_image <link_to_image> = generates and posts a 1024x1024 variation of linked image.',name='var_image')
async def var_image(ctx):
    if ctx.message.author.id == admin_id:await handle_variation(ctx.message)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_variation(ctx.message)

@client.command(description = 'music',brief='Stream a given youtube video to the voice channel (admin only // must be youtube or music.youtube link). \nExample:\n/play <link_to_video> = joins voice channel, streams video, disconnects.',name='play')
async def play(ctx,arg1):
    if ctx.message.author.id == admin_id: await handle_video(ctx.message,arg1)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_video(ctx.message,arg1)

@client.command(description = 'music',brief='Stop the stream of a youtube video to the voice channel. \nExample:\n/skip = skips/ends song',name='skip')
async def skip(ctx):
    # by simply pausing we'll break the while loop and make a new song be chosen and played.
    voice = discord.utils.get(client.voice_clients, guild=ctx.message.guild)
    if voice.is_playing():voice.pause()
    else:print('no audio playing')

@client.command(description = 'music',brief='Stop the dj or music player and make it leave the call. \nExample:\n/stop_music = stop stream and end call.',name='stop_music')
async def stop_music(ctx):
    voice = discord.utils.get(client.voice_clients, guild=ctx.message.guild)
    global playing_music
    try:
        playing_music = False
        await voice.disconnect()
        voice.pause()
    except: print('cant dc')

@client.command(description = 'music',brief='Start the dj/radio station in the current voice channel. \nExample:\n/dj = dj ai joins the call and plays songs from music channel.',name='dj')
async def dj(ctx):
    await handle_radio(ctx.message)

@client.command(description = 'music',brief='Build a dataset of youtube links of music to stream (saved as csv)\nExample:\n`/scrape_music 1000` = scrapes 1000 messages for links in music channel.',name='scrape_music')
async def scrape_music(ctx,arg1=None):
    await handle_scrape_music(ctx.message,arg1)

@client.command(description = 'edit',brief=':cinema: \nRemove the background of a given image (translucent png). \nExample:\n/remove_bg <link_to_image> = sends new image',name='remove_bg')
async def remove_bg(ctx,arg1=None,arg2=None,arg3=None):
    await handle_remove_bg(ctx.message,arg1,arg2,arg3)

@client.command(description = 'edit',brief=':cinema: \nreplace the background of a given image with another image. \nExample:\n/new_bg <link_to_img_foreground> <link_to_img_new_background> = sends new image with new background',name='new_bg')
async def new_bg(ctx,arg1=None,arg2=None,arg3=None,arg4=None):
    await handle_replace_bg(ctx.message,arg1,arg2,arg3,arg4)

@client.command(description = 'ai',brief='Transfer the style of one image onto another. \nExample:\n/style_transfer <link_to_content_img> <link_to_style_img> = sends new image with new style',name='style_transfer')
async def style_transfer(ctx):
    await handle_style_transfer(ctx.message)

@client.command(description = 'misc',brief='Send a random image from a channel. \nExample:\n/rand = sends random image from channel',name='rand')
async def rand(ctx):
    await fetch_chat(ctx.message,type = 1,channel = random_image_channel)

@client.command(description = 'misc',brief='Send a random image from main channel. \nExample:\n/rand = sends random image from main channel',name='rand_image')
async def rand_image(ctx):
    await fetch_chat(ctx.message,type = 1,channel = main_chat)

@client.command(description = 'misc',brief='Send a random chat from main channel. \nExample:\n/rand = sends random chat from main channel',name='rand_chat')
async def rand_image(ctx):
    await fetch_chat(ctx.message,type = 0,channel = main_chat)

@client.command(description = 'ai',brief='Chat with Alpaca LLM\nExample:\n/alpaca how are you doing today? = will tell you how it is doing',name='alpaca')
async def alpaca(ctx):
    await handle_alpaca(ctx.message)

@client.command(description = 'ai',brief='Wipes chatbot memory',name='wipe_memory')
async def wipe_memory(ctx):
    global alpaca_memory
    global chat_history
    global personality
    chat_history=[{"role": "system", "content": personality}]
    alpaca_memory = list()

@client.command(description = 'ai',brief=':moneybag: \n Stable diffusion image generation \nExample:\n/sd "A cow jumping over the moon" = image of a cow jumping over the moon',name='sd')
async def sd(ctx, arg1,arg2 = 0):
    tmp = int(arg2)
    if ctx.message.author.id == admin_id: await handle_sd(ctx.message,arg1,arg2)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_sd(ctx.message,arg1,arg2)

@client.command(description = 'ai',brief=':moneybag: \n Image Restoration \nExample:\n/restore <link_to_old_image> = restored image',name='restore')
async def restore(ctx, arg1):
    if ctx.message.author.id == admin_id: await handle_restore(ctx.message,arg1)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_restore(ctx.message,arg1)

@client.command(description = 'ai',brief=':moneybag: :moneybag: :moneybag: \n Text to Video \nExample:\n/gen_video "a panda eating bamboo" = video of panda eating bamboo',name='gen_video')
async def gen_video(ctx, arg1):
    if ctx.message.author.id == admin_id: await handle_video_gen(ctx.message,arg1)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_video_gen(ctx.message,arg1)

@client.command(description = 'ai',brief=':moneybag: \n Manipulate a headshot \nExample:\n/edit_face <link_to_face> "a face with a bowl cut" = the given face with a bowl cut',name='edit_face')
async def edit_face(ctx, arg1,arg2,arg3=4.1,arg4=0.15):
    if ctx.message.author.id == admin_id: await handle_face_edit(ctx.message,arg1,arg2,arg3,arg4)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_face_edit(ctx.message,arg1,arg2,arg3,arg4)

@client.command(description = 'ai',brief=':moneybag: \n Simulate someones face at a given age or make a gif of them aging \nExample:\n/age_photo <link_to_face> 80 = the given face at age 80 (only send the link to make a gif)',name='age_face')
async def age_face(ctx, arg1,arg2=None):
    if ctx.message.author.id == admin_id: await handle_aging(ctx.message,arg1,arg2)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_aging(ctx.message,arg1,arg2)

@client.command(description = 'ai',brief=':moneybag: :moneybag: \n Provide a doodle and a prompt to generate an image \nExample:\n/doodle <link_to_img> "a photo of an orange cat" = Photo of orange cat mapped to doodle',name='doodle')
async def doodle(ctx, arg1,arg2):
    if ctx.message.author.id == admin_id: await handle_doodle(ctx.message,arg1,arg2)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_doodle(ctx.message,arg1,arg2)

@client.command(description = 'ai',brief=':moneybag: \n Ask questions about an image \nExample:\n/explain <link_to_img_of_CN_tower> "Where is this photo" = "This photo was taken in Toronto"',name='explain')
async def explain(ctx, arg1,arg2):
    if ctx.message.author.id == admin_id: await handle_explanation(ctx.message,arg1,arg2)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_explanation(ctx.message,arg1,arg2)

@client.command(description = 'ai',brief=':moneybag: \n Interp between two images \nExample:\n/interp <link_to_img1> <link_to_img2> = interp animation',name='interp')
async def interp(ctx, arg1,arg2,arg3=2):
    if ctx.message.author.id == admin_id: await handle_interp(ctx.message,arg1,arg2,arg3)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        tmp = await ctx.message.channel.send(f'{admin.mention} React to this message with a 👍 if you want me to execute this command.')
        await tmp.add_reaction("👍")
        def check(reaction, user):
            return user.id == admin_id and str(reaction.emoji) == '👍'
        try:
            reaction, user = await client.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Sorry, the command request has timed out.")
        else:
            await ctx.send("Executing Command...")
            await handle_interp(ctx.message,arg1,arg2,arg3)

@client.command(description = 'editor',brief='moviepy',name='editor')
async def editor(ctx, cmd = None,arg1=None,arg2=None,arg3=None,arg4=None,arg5=30):
    if cmd == None: await help_video_editing(ctx)
    else: await handle_editor(ctx.message,cmd,arg1,arg2,arg3,arg4,arg5)

@client.command(description = 'music',brief='Recommend a song to the dj',name='recommend')
async def recommend(ctx, arg1=None):
    take_requests = requests_allowed
    if take_requests:
        await handle_recommendation(ctx.message,arg1)
    else:
        admin = await commands.MemberConverter().convert(ctx, str(admin_id))
        await ctx.message.channel.send(f'take_requests is set to false. Get an admin ({admin.mention}) to do `/recommend allow`')


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
        url = await extract_youtube_id(arg1)
        if url == None:
            try:
                if 'discordapp' in arg1:
                    response = requests.get(arg1)
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
                        if '.wav' in arg1:
                            with open('cache/audio.wav', 'wb') as f:
                                f.write(response.content)
                            audio = AudioFileClip('cache/audio.wav')
                        elif '.mp3' in arg1:
                            with open('cache/audio.mp3', 'wb') as f:
                                f.write(response.content)
                            audio = AudioFileClip('cache/audio.mp3')
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
                await message.channel.send(f"File size: {round(os.path.getsize('cache/output_vid.mp4') / (1024 * 1024),1)}Mb\nAs a bot my limit is 8Mb, you can reach out to an admin if the file is <25mb and you can't get it lower.")
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
                    await message.channel.send(f"File size: {round(os.path.getsize('cache/output_vid.mp4') / (1024 * 1024),1)}Mb\nAs a bot my limit is 8Mb, you can reach out to an admin if the file is <25mb and you can't get it lower.")
            except Exception as e:
                await message.channel.send(e)
        else: 
            await message.channel.send('no method provided.\nTry: `/editor compress b` to reduce bitrate, a to remove audio, and r to resize')
            return
            
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

async def handle_scrape_music(message,arg1):
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
    music_list.to_csv('music_dataset.csv',index=False)
    await message.channel.send(f'Scraped {len(messages)} songs from music channel and saved to CSV')

async def extract_youtube_id(message):
    if 'https://y' in message or 'https://music.y' in message or 'https://www.y' in message:
        for word in message.split():
            # make sure it's a youtube link
            if 'https://y' in word or 'https://music.y' in word or 'https://www.y' in word:
                url = word
                # regex pattern that keeps me up at night
                #pattern = r'^https?://(?:(?:www|m)\.)?(?:youtube\.com/watch\?v=|youtu\.be/|music\.youtube\.com/watch\?v=)([\w-]+).*?(?=$|&)'
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
        await message.channel.send(f"Don't like how it looks? Try:\n/sd \"prompt\" x\nwhere `x` is a number ranging from 0-{len(models)-1}")
    except Exception as e:
        await message.channel.send(e)

async def handle_alpaca(message):
    global alpaca_memory
    prompt = message.content[8:]
    print(' '.join([line for line in alpaca_memory]) + ' Respond to: '+prompt)

    # coldstart and terminate
    cmd = ['./chat', '-p', ' '.join([line for line in alpaca_memory]) + ' Respond to: '+prompt]
    output = subprocess.check_output(cmd, universal_newlines=True)

    await message.channel.send(output)
    if len(alpaca_memory) > 6:
        alpaca_memory.pop(1)
        alpaca_memory.pop(2)
    if 'bye' in message.content or 'goodbye' in message.content: alpaca_memory = []
    alpaca_memory.append('I said:'+message.content[8:])
    alpaca_memory.append('you said:'+output)

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

    response = requests.get(url2)
    if 'png' in url2:
        with open('cache/style_image.png', 'wb') as f:
            f.write(response.content)
    else:
        with open('cache/style_image.jpg', 'wb') as f:
            f.write(response.content)
        image = Image.open('cache/style_image.jpg')
        image.save('cache/style_image.png')

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

    response = requests.get(url2)
    if 'png' in url2:
        with open('cache/input_background.png', 'wb') as f:
            f.write(response.content)
    else:
        with open('cache/input_background.jpg', 'wb') as f:
            f.write(response.content)
        image = Image.open('cache/input_background.jpg')
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

async def handle_news(ctx,arg1,arg2,arg3):
    global loop
    global news
    if arg1.lower() == 'more':
        if news == []:
            await ctx.message.channel.send('No news has been retrived yet. Please call "/news" or "/news <topic>"')
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
        arg3 = int(arg3)

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
            if arg3 != -1:
                if article_length > (arg3 * 2000): article_length = (arg3 * 2000)
            if article_length > 2000:
                start = 0
                end = 2000
                while start < article_length:
                    await ctx.message.channel.send(article_text[start:end])
                    start += 2000
                    end += 2000
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
            url = ('https://newsapi.org/v2/everything?'
                f'q={prompt}'
                'sortBy=date&'
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
                url = ('https://newsapi.org/v2/everything?'
                    f'q={prompt}'
                    'sortBy=date&'
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
        music = pd.read_csv('music_dataset.csv',header=0)
    except:
        await message.channel.send('No music dataset found. Scraping channel now.')
        await handle_scrape_music(message,None)
        music = pd.read_csv('music_dataset.csv',header=0)

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
    if recommended_songs: # if theres a reco song in queue then use that.
        url = recommended_songs.pop(0)
        name = senders.pop(0)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['formats'][5]['url']
            video_title = info.get('title', None)
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
        

async def handle_rage(message):
    try:
        channel = message.author.voice.channel
        await channel.connect()
        voice_channel = message.guild.voice_client
        voice_channel.play(discord.FFmpegPCMAudio('Recording_2.mp3'))
        while voice_channel.is_playing():
            await asyncio.sleep(1)
        await voice_channel.disconnect()
    except:
        print('author not in voice channel')

async def handle_chat(message):
    prompt = message.content[6:]
    global chat_history
    chat_history.append({"role": "user", "content": f'Respond to this as {bot_name}: "{prompt}"'})
    request = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=chat_history
    )
    chat_history.append({"role": "assistant", "content": request['choices'][0]['message']['content']})
    await message.channel.send(request['choices'][0]['message']['content'])
    if 'bye' in prompt:
        await wipe_memory()

async def handle_dm(message):
    prompt = message.content[10:]
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


async def handle_generator(message):
    prompt = message.content[10:]
    print(prompt)
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

async def handle_variation(message):
    try:
        url = message.content[10:]
        print(url)
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

client.run(bot_token)