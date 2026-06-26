# news-relay

Free, zero-server finance news flow into Discord. Runs entirely on **GitHub
Actions** (a free cloud cron), so nothing runs on your machine. It reads a set
of free RSS feeds, dedupes them, and posts new items into the right Discord
channel via webhooks.

No API keys required for the base version. Everything below is free.

---

## What you need (all free)

- A GitHub account
- A Discord server where you can create channels (you're the admin)
- ~5–10 minutes

---

## Setup

### 1. Create the Discord channels + webhooks

In your server, make the channels you want, e.g. `#macro`, `#equities`,
`#pe-ma`, `#crypto`, `#filings`.

For **each** channel: **Edit Channel → Integrations → Webhooks → New Webhook
→ Copy Webhook URL**. You'll paste these into GitHub in step 3.

> A webhook URL is a secret — anyone with it can post to your channel. Keep it
> only in GitHub Secrets (below). Don't commit it, and don't paste it into chat.

### 2. Put this code in a GitHub repo

Create a new repo and add these files (drag-drop in the GitHub web UI is fine):

```
relay.py
config.yaml
requirements.txt
state/seen_ids.json        <- contains just: {}
.github/workflows/relay.yml
```

**Make the repo public** if you can — public repos get *unlimited* free Actions
minutes, and your secrets stay private regardless. If you keep it private,
change the cron in `relay.yml` to hourly (`"0 * * * *"`) to stay under the
2,000 free minutes/month.

### 3. Add your webhook URLs as Secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**.
Create one per channel, names matching `config.yaml`:

| Secret name                | Value                          |
|----------------------------|--------------------------------|
| `DISCORD_WEBHOOK_MACRO`    | the #macro webhook URL         |
| `DISCORD_WEBHOOK_EQUITIES` | the #equities webhook URL      |
| `DISCORD_WEBHOOK_PEMA`     | the #pe-ma webhook URL         |
| `DISCORD_WEBHOOK_CRYPTO`   | the #crypto webhook URL        |
| `DISCORD_WEBHOOK_FILINGS`  | the #filings webhook URL       |

(Only add the ones you're using. A feed whose webhook secret is missing is
skipped, not an error.)

### 4. Edit one line in config.yaml

Set `user_agent:` to include your real email. SEC EDGAR and some feeds reject
requests without a contact.

### 5. Run it

Repo → **Actions** tab → enable workflows if prompted → click **news-relay** →
**Run workflow**.

The **first run seeds quietly** — it records what's currently in each feed and
posts nothing, so you don't get blasted with 40 backlog messages. From the
next run on, only genuinely new items post. After that it runs on its own every
30 minutes.

---

## Day-to-day

- **Add a source:** add a block to `config.yaml`. Any RSS/Atom URL works.
- **Track a ticker or topic:** clone a Google News block and edit the `q=`
  query, e.g. `q=NVDA+when:1d`. These feeds never break, so they're the
  reliable backbone.
- **Filter noise:** add `include:` / `exclude:` keyword lists to any feed.
- **Quiet a channel:** lower `max_items_per_run`.

A couple of the non-Google feed URLs can drift over time. If a channel goes
silent, open that feed URL in a browser — if it 404s, swap it for a Google
News query on the same topic.

---

## Gotchas (all minor)

- Scheduled Actions are best-effort and can lag 5–15 min under GitHub load.
  Fine for news; not for trading-speed alerts.
- GitHub auto-pauses schedules after 60 days of **repo** inactivity. This relay
  commits its state file every run, which counts as activity — so it keeps
  itself alive.
- The dedup state lives in `state/seen_ids.json`, committed back automatically.
  Don't delete it or the next run re-seeds.

---

## Later upgrades (when you want them)

- **Tickers / earnings / sentiment:** add a Finnhub free key (60 calls/min) and
  a second feed function. Drop me the word and I'll write it.
- **AI daily brief:** route the day's items through the Claude API to dedupe,
  tag, and summarize into one `#daily-brief` post instead of a raw firehose.
  This is the single biggest quality jump and it's a small addition.
- **FinTwit:** X is the one piece that resists free automation. Use Readybot
  (2 accounts free) alongside this, posting into a `#fintwit` channel.
