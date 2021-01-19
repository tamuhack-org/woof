import discord
from discord.ext import commands

from googleapiclient.discovery import build
from google.oauth2 import service_account

import os
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
client = commands.Bot(command_prefix = '!')

CLIENT_TOKEN = os.environ['ENV_CLIENT_TOKEN']

ORGANIZER_SUPPORT_DISCORD_NAME = os.environ['ENV_ORGANIZER_SUPPORT_DISCORD_NAME']

CHECKIN_CHANNEL_ID = int(os.environ['ENV_CHECKIN_CHANNEL_ID'])
SPONSOR_ID = int(os.environ['ENV_SPONSOR_ID'])
MENTOR_ID = int(os.environ['ENV_MENTOR_ID'])
HACKER_ID = int(os.environ['ENV_HACKER_ID'])

@client.event
async def on_ready():
  print(f'{client.user} is ready.')

@client.command(aliases=['checkin', 'check-in', 'check_in', 'Checkin', 'Check-in', 'Check_in'])
async def _checkin(ctx, email):

  # ignore capitalizations
  email = email.lower()

  # Check the user typed the command in the right channel
  if ctx.channel.id != CHECKIN_CHANNEL_ID:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Howdy {ctx.author.mention}! Please check in using the checkin channel! If you need any help, contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
    await ctx.message.delete()
    return

  sponsor_role = discord.utils.get(ctx.guild.roles, id=SPONSOR_ID)
  mentor_role = discord.utils.get(ctx.guild.roles, id=MENTOR_ID)
  hacker_role = discord.utils.get(ctx.guild.roles, id=HACKER_ID)

  checkin_roles = [sponsor_role, mentor_role, hacker_role]

  # check if user has a role already
  for author_role in ctx.author.roles:
    if author_role in checkin_roles:
      await ctx.author.create_dm()
      await ctx.author.dm_channel.send(f'You have already been checked in, if there was a mistake please message an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')
      return

  # get emails from GSHEETS
  hackers_results = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="hackers!A2:B").execute()
  hackers_emails = list(map(lambda row: row[0].lower(), hackers_results.get('values', [])))

  mentors_results = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="mentors!A2:B").execute()
  mentors_emails = list(map(lambda row: row[0].lower(), mentors_results.get('values', [])))

  sponsors_results = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="sponsors!A2:B").execute()
  sponsors_emails = list(map(lambda row: row[0].lower(), sponsors_results.get('values', [])))

  if email in hackers_emails:
    # 2 for the header row + index starts at 0
    spreadsheetIndex = 2 + hackers_emails.index(email)
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'hackers!B{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[1]]}).execute()

    await ctx.author.add_roles(hacker_role)
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'{ctx.author.mention} you now have {hacker_role} role!')
    return

  elif email in mentors_emails:
    # 2 for the header row + index starts at 0
    spreadsheetIndex = 2 + mentors_emails.index(email)
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'mentors!B{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[1]]}).execute()

    await ctx.author.add_roles(mentor_role)
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'{ctx.author.mention} you now have {mentor_role} role!')
    return

  elif email in sponsors_emails:
    # 2 for the header row + index starts at 0
    spreadsheetIndex = 2 + sponsors_emails.index(email)
    sheet.values().update(spreadsheetId=SPREADSHEET_ID, range=f'sponsors!B{spreadsheetIndex}', valueInputOption="USER_ENTERED", body={'values': [[1]]}).execute()

    await ctx.author.add_roles(sponsor_role)
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'{ctx.author.mention} you now have {sponsor_role} role!')
    return

  else:
    await ctx.author.create_dm()
    await ctx.author.dm_channel.send(f'Email not found, please make sure you are writing the email and command correctly (Ex: !checkin email@example.com). If you need any help, please contact an organizer or {ORGANIZER_SUPPORT_DISCORD_NAME}.')

client.run(CLIENT_TOKEN)