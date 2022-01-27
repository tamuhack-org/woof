import discord
from discord.ext import commands

from googleapiclient.discovery import build
from google.oauth2 import service_account

import os
import datetime
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
COMPANIES = ['accenture', 'ford', 'visa', 'statefarm', 'capitalone']

#####################################################################
# Basic Discord events
@client.event
async def on_ready():
  print(f'{client.user} is ready.')

# @client.event
# async def on_message(message):
#   channel = message.channel
#   if channel.id == CHECKIN_CHANNEL_ID:
#     await message.delete()

#   await client.process_commands(message)

@client.event
async def on_command_error(ctx, error):
  if isinstance(error, commands.CommandNotFound):
    print(f'Invalid command, {ctx.invoked_with} used. Message was: {ctx.message}')
#####################################################################

#####################################################################
# Queue commands

@client.command(aliases=['queue'])
async def _queue(ctx, company):
  if company not in COMPANIES:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Howdy {ctx.author.mention}! The company you requested was not found. Please double check the spelling, or ask for help from {ORGANIZER_SUPPORT_DISCORD_NAME}.')
    await ctx.message.delete()
    return
  
  test = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="ford!A2:A").execute()
  test_res = list(map(lambda row: row[0].lower(), test.get('values', [])))

  sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'ford!A{len(test_res) + 2}', valueInputOption="USER_ENTERED", body={'values': [[ctx.author.name + '#' + ctx.author.discriminator]]}).execute()

  return

# Dequeue commands
@client.command(aliases=['dequeue'])
async def _dequeue(ctx, company):
  # TODO: check they have sponsor role
  guild = client.get_guild(123)
  channel = client.get_channel(123) 
  # channel now holds the channel you want to move people into

  member = await guild.fetch_member(123)
  #member now holds the user that you want to move
  await member.move_to(channel)
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
    await ctx.author.dm_channel.send(f'Howdy {ctx.author.mention}!   Please check in using the checkin channel! If you need any help, contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
    await ctx.message.delete()
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

    if rsvpStatus == 'yes':
      sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'hackers!C{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[1]]}).execute()
      sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'hackers!D{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[ctx.author.name + '#' + ctx.author.discriminator]]}).execute()
      sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'hackers!E{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[ctx.author.id]]}).execute()
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
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'mentors!E{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[ctx.author.id]]}).execute()
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'mentors!F{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[str(current_utc)]]}).execute()

    await ctx.author.add_roles(mentor_role)
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'{ctx.author.mention} you now have the {mentor_role} role!\nWe are happy to have you here at TAMUHack!\n\nPlease read through the 👋│welcome and 📢│th-announcements channels to stay up to date on TAMUHack information.\nWe hope you enjoy the event and best of luck!')
    return

  #ERROR not found    
  else:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Email not found, please make sure you are writing the email and command correctly (Ex: !checkin email@example.com). If you need any help, please contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')

@_checkin.error
async def checkin_error(ctx, error):
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