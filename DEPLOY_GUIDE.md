# Blessing Job Finder — Railway Deployment Guide

## What this does
Runs every 10 minutes and:
- Scrapes 5 UK job sites for care/support worker jobs with visa sponsorship
- Sends new jobs to Telegram and Email
- Auto-applies to matching jobs using Blessing's CV
- Never sends the same job twice

---

## Step 1 — Set up Telegram Bot (to receive job alerts)

1. Open Telegram and search for @BotFather
2. Send /newbot and follow instructions
3. Copy the BOT TOKEN it gives you
4. Search for @userinfobot in Telegram
5. Start it — it will show your CHAT ID
6. Save both values

---

## Step 2 — Set up Gmail App Password (for email alerts)

1. Go to myaccount.google.com
2. Security → 2-Step Verification → turn ON
3. Security → App passwords
4. Create a new app password for "Mail"
5. Copy the 16 character password it gives you

---

## Step 3 — Deploy to Railway

1. Go to railway.app and sign in with GitHub
2. Create New Project → Deploy from GitHub
3. Select your repo
4. Set Root Directory to the folder containing job_scraper/

5. Add these Environment Variables in Railway dashboard:
   TELEGRAM_BOT_TOKEN = [from Step 1]
   TELEGRAM_CHAT_ID   = [from Step 1]
   EMAIL_ADDRESS      = oyewoleblessing61@gmail.com
   EMAIL_PASSWORD     = [app password from Step 2]

6. Railway will detect the Procfile and run:
   python job_scraper/main.py

---

## Step 4 — Verify it is working

Check Railway logs. You should see:
--- Job Scraper Cycle Started at HH:MM:SS ---
Scraping DWP Find a Job...
Scraping NHS Jobs...
...
--- Job Scraper Cycle Finished ---

This repeats every 10 minutes forever.

---

## Files needed in your GitHub repo
- job_scraper/ (entire folder)
- Blessing_Oyewole_Improved_CV_Updated.pdf
- requirements.txt
- Procfile

DO NOT upload .venv folder to GitHub.
Add .venv to .gitignore

---

## Cost
Railway free tier: $5 credit per month
This script is very lightweight — should run 
for weeks on the free tier credits.
