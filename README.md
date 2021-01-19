# TAMUhack Discord Bot
This bot is used in the TAMUhack community server to checkin hackers, mentors, and sponsors to the event.

It was heavily inspired by the ShellHacks Discord bot from UPE @ FIU. Special shoutout to them!

## Example .env file
```
ENV_GSHEETS_KEY_FILE="./keys.json"
ENV_GSHEETS_SERVICE_ACCOUNT_CREDENTIALS={"type": "service_account", "project_id": "", "private_key_id": "", "private_key": "", "client_email": "", "client_id": "", "auth_uri": "", "token_uri": "", "auth_provider_x509_cert_url": "", "client_x509_cert_url": "" }

ENV_SPREADSHEET_ID=spreadsheet_id

ENV_CLIENT_TOKEN=discord_token
ENV_ORGANIZER_SUPPORT_DISCORD_NAME=Support#1111

ENV_CHECKIN_CHANNEL_ID=checkin_channel
ENV_SPONSOR_ID=sponsor_role
ENV_MENTOR_ID=mentor_role
ENV_HACKER_ID=hacker_role

```