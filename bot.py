import discord
from discord.ext import commands

from googleapiclient.discovery import build
from google.oauth2 import service_account

import os
import datetime
import json
from collections import defaultdict

# load environmment variables
from dotenv import load_dotenv
load_dotenv()

# write the keys.json file for GSHEET credentials
keys = open(os.environ['ENV_GSHEETS_KEY_FILE'], 'w')
keys.write(os.environ['ENV_GSHEETS_SERVICE_ACCOUNT_CREDENTIALS'])
keys.close() 

# Google Sheets initialization
# Follow https://youtu.be/4ssigWmExak to setup a service account to interact with your Google Sheet
# The google sheet has 3 sheets, hackers, mentors, sponsors, and row 1 of each sheet is ['Email', 'Status']
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = service_account.Credentials.from_service_account_file(os.environ['ENV_GSHEETS_KEY_FILE'], scopes=SCOPES)

SPREADSHEET_ID = os.environ['ENV_SPREADSHEET_ID']
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Discord bot, called client, initialization
# Activate developer mode on Discord to get role and channel IDs
# Useful tutorial for setting up the Discord bot: https://www.youtube.com/watch?v=nW8c7vT6Hl4&t=880s&ab_channel=Lucas
# Useful tutorial for hosting the Discord bot on Heroku: https://www.youtube.com/watch?v=BPvg9bndP1U&t=314s&ab_channel=TechWithTim
client = commands.Bot(command_prefix = '!')

CLIENT_TOKEN = os.environ['ENV_CLIENT_TOKEN']

ORGANIZER_SUPPORT_DISCORD_NAME = os.environ['ENV_ORGANIZER_SUPPORT_DISCORD_NAME']

CHECKIN_CHANNEL_ID = int(os.environ['ENV_CHECKIN_CHANNEL_ID'])
HACKER_ID = int(os.environ['ENV_HACKER_ID'])
MENTOR_ID = int(os.environ['ENV_MENTOR_ID'])
SPONSOR_ID = int(os.environ['ENV_SPONSOR_ID'])
GUILD_ID = int(os.environ['ENV_GUILD_ID'])
WAITING_ROOM_CHANNEL_ID = int(os.environ['ENV_WAITING_ROOM_CHANNEL_ID'])
WAITING_ROOM_CHANNEL_LINK = os.environ['ENV_WAITING_ROOM_CHANNEL_LINK']
QUEUE_CHANNEL_ID = int(os.environ['ENV_QUEUE_CHANNEL_ID'])

COMPANIES = os.environ['ENV_COMPANIES'].split(" ")
COMPANIES_VOICE = json.loads(os.environ['ENV_COMPANIES_VOICE'])

curr_queue = defaultdict(list)
ids_in_queue = defaultdict(int)

current_queues_message = ''

#####################################################################
# Basic Discord events
@client.event
async def on_ready():
  global current_queues_message
  print(f'{client.user} is ready.')
  channel = client.get_channel(QUEUE_CHANNEL_ID)
  current_queues_message = await channel.send(get_current_queues_message())
  await recover()

async def update_current_queue_message():
  global current_queues_message
  await current_queues_message.edit(content=get_current_queues_message())

@client.event
async def on_message(message):
  if message.author.id == client.user.id:
    return
  channel = message.channel
  if channel.id == CHECKIN_CHANNEL_ID:
    await message.delete()
  elif channel.id == QUEUE_CHANNEL_ID:

    await message.delete()

  await client.process_commands(message)

@client.event
async def on_command_error(ctx, error):
  if isinstance(error, commands.CommandNotFound):
    print(f'Invalid command, {ctx.invoked_with} used. Message was: {ctx.message}')
#####################################################################

#####################################################################
# Queue commands
@client.command(aliases=['queue'])
async def _queue(ctx, company):

  # Check the user typed the command in the right channel
  if ctx.channel.id != QUEUE_CHANNEL_ID:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Howdy {ctx.author.mention}! Please queue in using the queue channel! If you need any help, contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
    return

  if company not in COMPANIES:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Howdy {ctx.author.mention}! The company, `{company}`, you requested was not found. Please double check the spelling, or ask for help from {ORGANIZER_SUPPORT_DISCORD_NAME}.')
    return
  
  if ctx.author.id in ids_in_queue:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'❌ You are already in queue for `{ids_in_queue[ctx.author.id]}`. You can only be in queue for one company at a time. If you would like to leave the queue, please use the command `!leavequeue` in the `#sponsor-queue` channel.')
    return

  company_queue = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"queue!A2:A").execute()
  company_queue_idx = len(list(map(lambda row: row[0].lower(), company_queue.get('values', [])))) + 2

  current_utc = datetime.datetime.utcnow()

  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'queue!A{company_queue_idx}', valueInputOption="USER_ENTERED", body={'values': [[ctx.author.name + '#' + ctx.author.discriminator]]}).execute()
  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'queue!B{company_queue_idx}', valueInputOption="USER_ENTERED", body={'values': [[str(ctx.author.id)]]}).execute()
  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'queue!C{company_queue_idx}', valueInputOption="USER_ENTERED", body={'values': [[company]]}).execute()
  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'queue!D{company_queue_idx}', valueInputOption="USER_ENTERED", body={'values': [['waiting']]}).execute()
  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'queue!E{company_queue_idx}', valueInputOption="USER_ENTERED", body={'values': [[str(current_utc)]]}).execute()

  curr_queue[company].append([ctx.author.id, company_queue_idx, ctx.author.name + '#' + ctx.author.discriminator])
  ids_in_queue[ctx.author.id] = company

  await ctx.author.create_dm()
  await ctx.author.dm_channel.send(f':white_check_mark: You have successfully joined the queue for `{company}`!\nYour position in line is: `{len(curr_queue[company])}`.\n\nPlease join the waiting room voice channel, where you will automatically be moved when it is your turn.\n**IF YOU ARE NOT IN THE WAITING ROOM VOICE CHANNEL WHEN IT IS YOUR TURN, YOU WILL BE REMOVED FROM THE QUEUE**\n{WAITING_ROOM_CHANNEL_LINK}')

  await update_current_queue_message()
  update_recovery()
  return

# Dequeue commands
@client.command(aliases=['dequeue'])
async def _dequeue(ctx, company):
  if ctx.channel.id != QUEUE_CHANNEL_ID:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Howdy {ctx.author.mention}! Please dequeue using the queue channel! If you need any help, contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
    return

  if company not in COMPANIES:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Howdy {ctx.author.mention}! The company, {company}, you requested was not found. Please double check the spelling, or ask for help from {ORGANIZER_SUPPORT_DISCORD_NAME}.')
    return

  sponsor_role = discord.utils.get(ctx.guild.roles, id=SPONSOR_ID)

  # check user is a sponsor
  flag = True
  for author_role in ctx.author.roles:
    if author_role == sponsor_role:
      flag = False
      break
  if flag:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Only a sponsor can use the `dequeue` command.')
    return

  guild = client.get_guild(GUILD_ID)
  channel = client.get_channel(int(COMPANIES_VOICE[company])) 
  # channel now holds the channel you want to move people into

  if len(curr_queue[company]) == 0:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'The queue for `{company}` is empty. Please check again in a few minutes!')
    return

  member_id, spreadsheet_idx, _ = curr_queue[company][0]
  curr_queue[company].pop(0)
  if member_id in ids_in_queue:
    ids_in_queue.pop(member_id)

  current_utc = datetime.datetime.utcnow()

  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'queue!D{spreadsheet_idx}', valueInputOption="USER_ENTERED", body={'values': [['error']]}).execute()
  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'queue!F{spreadsheet_idx}', valueInputOption="USER_ENTERED", body={'values': [[str(current_utc)]]}).execute()

  member = await guild.fetch_member(member_id)
  await update_current_queue_message()
  update_recovery()

  if member.voice is None or member.voice.channel.id != WAITING_ROOM_CHANNEL_ID:
    await member.create_dm()
    await member.dm_channel.send(f'👋 Howdy! Your turn was called for `{company}`, but you were not in the waiting room and thus have been removed from the queue. Please queue back up if you would still like to meet.\n\nIf you believe this was a mistake, please contact {ORGANIZER_SUPPORT_DISCORD_NAME}.')
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'queue!D{spreadsheet_idx}', valueInputOption="USER_ENTERED", body={'values': [['missing']]}).execute()

    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'❗ The next user was not found in the waiting room and has been removed from the queue. Please dequeue again to get the next person in line.')
  else:
    await member.move_to(channel)
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'queue!D{spreadsheet_idx}', valueInputOption="USER_ENTERED", body={'values': [['seen']]}).execute()
  
  return

# Leave queue command
@client.command(aliases=['leavequeue'])
async def _leavequeue(ctx):
  if ctx.channel.id != QUEUE_CHANNEL_ID:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Howdy {ctx.author.mention}! Please leavequeue using the queue channel! If you need any help, contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
    return

  if ctx.author.id not in ids_in_queue:
    return
  company = ids_in_queue[ctx.author.id]

  flag = True
  pop_idx = -1

  for idx, member_data in enumerate(curr_queue[company]):
    member_id, member_idx, _ = member_data
    if member_id == ctx.author.id:
      flag = False
      pop_idx = idx
      break

  if flag:
    return

  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'queue!D{member_idx}', valueInputOption="USER_ENTERED", body={'values': [['left']]}).execute()
  curr_queue[company].pop(pop_idx)

  if member_id in ids_in_queue:
    ids_in_queue.pop(member_id)

  await ctx.author.create_dm()
  await ctx.author.dm_channel.send(f'👋 You have left the queue for `{company}`.')
  await update_current_queue_message()

  update_recovery()
  return

def get_current_queues_message():
  res = ":wave:  Howdy! Use this channel to join queues for our virtual companies. Here are the following commands you can do:\n\n:computer:**`!queue {company_name}`**\n- Use this to join the queue.\n- You MUST be in the WAITING ROOM voice channel when it is your turn or you will be removed from the queue.\n- You can only be in queue for **1** company at a time.\n- Replace {company name} with the name as seen below. EX: `!queue capitalone` to join Capital One's queue."
  res += "\n\n:computer: **`!leavequeue`**\n- Leave the current queue you are in.\n"
  res += '-----------------------\n**VIRTUAL LINES 🚶**\nHere are the live queue sizes to talk with our virtual sponsors!```'
  for company in COMPANIES:
    res += f'\n{company}: {len(curr_queue[company])}'
  res += '```-----------------------'
  return res

def update_recovery():
  global curr_queue
  global ids_in_queue

  curr_queue_json = json.dumps(curr_queue)
  ids_in_queue_json = json.dumps(ids_in_queue)

  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'recover!A1:A1', valueInputOption="USER_ENTERED", body={'values': [[curr_queue_json]]}).execute()
  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'recover!A2:A2', valueInputOption="USER_ENTERED", body={'values': [[ids_in_queue_json]]}).execute()

async def recover():
  global curr_queue
  global ids_in_queue
  recovery_curr_queue_json = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"recover!A1:A1").execute()
  recovery_curr_queue = json.loads(recovery_curr_queue_json.get('values', [])[0][0])

  for key in recovery_curr_queue:
    curr_queue[key] = recovery_curr_queue[key]

  recovery_ids_in_queue_json = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"recover!A2:A2").execute()
  recovery_ids_in_queue = json.loads(recovery_ids_in_queue_json.get('values', [])[0][0])
  ids_in_queue = defaultdict(int)

  for key in recovery_ids_in_queue:
    ids_in_queue[int(key)] = recovery_ids_in_queue[key]

  await update_current_queue_message()


@client.command(aliases=['recover'])
async def _recover(ctx):
  sponsor_role = discord.utils.get(ctx.guild.roles, id=SPONSOR_ID)

  # check user is a sponsor
  flag = True
  for author_role in ctx.author.roles:
    if author_role == sponsor_role:
      flag = False
      break
  if flag:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Only a sponsor can use the `dequeue` command.')
    return
  
  await recover()

@_queue.error
async def queue_error(ctx, error):
  print(f'queue error [{ctx.author.id}:', error)
  await ctx.author.create_dm()
  await ctx.author.dm_channel.send(f'An error occurred. Please try again or contact {ORGANIZER_SUPPORT_DISCORD_NAME} for help.')
  return

@_dequeue.error
async def dequeue_error(ctx, error):
  print(f'dequeue error [{ctx.author.id}:', error)
  await ctx.author.create_dm()
  await ctx.author.dm_channel.send(f'An error occurred. Please try again or contact {ORGANIZER_SUPPORT_DISCORD_NAME} for help.')
  return

@_leavequeue.error
async def leavequeue_error(ctx, error):
  print(f'leavequeue error [{ctx.author.id}:', error)
  await ctx.author.create_dm()
  await ctx.author.dm_channel.send(f'An error occurred. Please try again or contact {ORGANIZER_SUPPORT_DISCORD_NAME} for help.')
  return

@_recover.error
async def queue_error(ctx, error):
  print(f'recover error [{ctx.author.id}:', error)
  await ctx.author.create_dm()
  await ctx.author.dm_channel.send(f'An error occurred. Please try again or contact {ORGANIZER_SUPPORT_DISCORD_NAME} for help.')
  return
#####################################################################

#####################################################################
# Check-in commands
@client.command(aliases=['checkin', 'check-in', 'check_in', 'Checkin', 'Check-in', 'Check_in'])
async def _checkin(ctx, email):

  # ignore capitalizations
  email = email.lower()

  # Check the user typed the command in the right channel
  if ctx.channel.id != CHECKIN_CHANNEL_ID:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Howdy {ctx.author.mention}! Please check in using the checkin channel! If you need any help, contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
    return

  # sponsor_role = discord.utils.get(ctx.guild.roles, id=SPONSOR_ID)
  hacker_role = discord.utils.get(ctx.guild.roles, id=HACKER_ID)
  mentor_role = discord.utils.get(ctx.guild.roles, id=MENTOR_ID)

  checkin_roles = [hacker_role, mentor_role]
  # checkin_roles = [sponsor_role, mentor_role, hacker_role]

  # check if user has a role already
  for author_role in ctx.author.roles:
    if author_role in checkin_roles:
      await ctx.author.create_dm()
      await ctx.author.dm_channel.send(f'You have already been checked in, if there was a mistake please message an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
      return

  # get emails from GSHEETS
  hackers_results = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="hackers!A2:B").execute()
  hackers_emails = list(map(lambda row: row[0].lower(), hackers_results.get('values', [])))
  
  mentor_results = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="mentors!A2:B").execute()
  mentor_emails = list(map(lambda row: row[0].lower(), mentor_results.get('values', [])))

  current_utc = datetime.datetime.utcnow()

  if email in hackers_emails:
    # 2 for the header row + index starts at 0
    spreadsheetIndex = 2 + hackers_emails.index(email)

    res = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f'hackers!B{spreadsheetIndex}').execute()
    rsvpStatus = res['values'][0][0]

    res = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f'hackers!C{spreadsheetIndex}').execute()
    checkinStatus = res['values'][0][0]

    if int(checkinStatus) == 1:
      await ctx.author.create_dm()
      await ctx.author.dm_channel.send(f'The email you entered has already checked in to Discord. Please contact {ORGANIZER_SUPPORT_DISCORD_NAME} for more help.')
      return

    if rsvpStatus == 'yes':
      sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'hackers!C{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[1]]}).execute()
      sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'hackers!D{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[ctx.author.name + '#' + ctx.author.discriminator]]}).execute()
      sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'hackers!E{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[str(ctx.author.id)]]}).execute()
      sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'hackers!F{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[str(current_utc)]]}).execute()

      await ctx.author.add_roles(hacker_role)
      await ctx.author.create_dm()
      await ctx.author.dm_channel.send(f'{ctx.author.mention} you now have the {hacker_role} role!\nWe are happy to have you here at TAMUHack!\n\nPlease read through the 👋│welcome and 📢│th-announcements channels to stay up to date on TAMUHack information.\nWe hope you enjoy the event and best of luck!')
      return
    else:
      await ctx.author.create_dm()
      await ctx.author.dm_channel.send(f'👋 Howdy, {ctx.author.mention}!\n\nWe have you in our system, but you have not RSVP\'d yet. Please do so in our application portal, and then try again. \nNote: It can take up to 24 hours after you RSVP for you to be able to check-in. Please try again soon, and we look forward to seeing you at TAMUHack!\n\nIf you are still unable to check-in 24 hours later, please contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
      return
  #mentor email check
  elif email in mentor_emails:
    # 2 for the header row + index starts at 0
    spreadsheetIndex = 2 + mentor_emails.index(email)
    
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'mentors!C{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[1]]}).execute()
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'mentors!D{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[ctx.author.name + '#' + ctx.author.discriminator]]}).execute()
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'mentors!E{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[str(ctx.author.id)]]}).execute()
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'mentors!F{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[str(current_utc)]]}).execute()

    await ctx.author.add_roles(mentor_role)
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'{ctx.author.mention} you now have the {mentor_role} role!\nWe are happy to have you here at TAMUHack!\n\nPlease read through the 👋│welcome and 📢│th-announcements channels to stay up to date on TAMUHack information.\nWe hope you enjoy the event and best of luck!')
    return

  #ERROR not found    
  else:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Email not found, please make sure you are writing the email and command correctly (Ex: !checkin email@example.com), and that you have RSVP\'d online. If you need any help, please contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')

@_checkin.error
async def checkin_error(ctx, error):
  print(f'checkin error [{ctx.author.id}]:', error)
  if isinstance(error, commands.MissingRequiredArgument):
    if ctx.channel.id != CHECKIN_CHANNEL_ID:
      await ctx.author.create_dm()
      await ctx.message.delete()
      await ctx.author.dm_channel.send(f'Howdy {ctx.author.mention}! Please check in using the checkin channel! If you need any help, contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
  
    else:
      await ctx.author.create_dm()
      await ctx.author.dm_channel.send(f'Email not found, please make sure you are writing the email and command correctly (Ex: !checkin email@example.com). If you need any help, please contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
  
  else:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'An error has occurred. Please contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
  
#####################################################################

client.run(CLIENT_TOKEN)