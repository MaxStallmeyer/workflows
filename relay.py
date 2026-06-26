#!/usr/bin/env python3
"""
news-relay: pull free RSS feeds and push new items to Discord webhooks.

Runs statelessly on GitHub Actions. Dedup state lives in state/seen_ids.json,
which the workflow commits back after each run, so nothing needs to stay on
your machine.

Usage:
    python relay.py            # normal run (posts to Discord)
    python relay.py --dry-run  # print payloads, post nothing (for testing)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
import yaml

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.yaml"
STATE_PATH = ROOT / "state" / "seen_ids.json"

# Some feeds (notably SEC EDGAR) reject requests without a descriptive
# User-Agent that includes a contact. Set USER_AGENT in config.yaml.
DEFAULT_UA = "news-relay/1.0 (set a contact email in config.yaml)"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state, cap=4000):
    # Keep the seen list bounded per feed so the file never grows forever.
    for feed_name, ids in state.items():
        if len(ids) > cap:
            state[feed_name] = ids[-cap:]
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def entry_id(entry):
    # Prefer a stable id; fall back to link, then title.
    return getattr(entry, "id", None) or entry.get("link") or entry.get("title", "")


def passes_filters(entry, feed_cfg):
    text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
    include = [k.lower() for k in feed_cfg.get("include", [])]
    exclude = [k.lower() for k in feed_cfg.get("exclude", [])]
    if include and not any(k in text for k in include):
        return False
    if exclude and any(k in text for k in exclude):
        return False
    return True


def build_embed(entry, feed_cfg):
    summary = entry.get("summary", "")
    # Strip the worst of any HTML and truncate.
    for tag in ("<p>", "</p>", "<br>", "<br/>", "<br />"):
        summary = summary.replace(tag, " ")
    summary = " ".join(summary.split())
    if len(summary) > 300:
        summary = summary[:297] + "..."
    return {
        "title": (entry.get("title", "(no title)"))[:256],
        "url": entry.get("link", ""),
        "description": summary,
        "footer": {"text": feed_cfg["name"]},
        "color": feed_cfg.get("color", 3447003),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def post_to_discord(webhook_url, embed, dry_run):
    payload = {"embeds": [embed]}
    if dry_run:
        print(f"  [dry-run] would POST: {embed['title']}")
        return True
    for attempt in range(4):
        r = requests.post(webhook_url, json=payload, timeout=20)
        if r.status_code == 429:  # rate limited
            wait = r.json().get("retry_after", 1)
            time.sleep(float(wait) + 0.5)
            continue
        if r.status_code in (200, 204):
            return True
        print(f"  ! Discord {r.status_code}: {r.text[:120]}", file=sys.stderr)
        return False
    return False


def run(dry_run=False):
    cfg = load_config()
    ua = cfg.get("user_agent", DEFAULT_UA)
    max_per_feed = cfg.get("max_items_per_run", 6)
    state = load_state()
    posted = 0

    for feed_cfg in cfg["feeds"]:
        name = feed_cfg["name"]
        url = feed_cfg["url"]
        webhook_env = feed_cfg["webhook"]
        webhook_url = os.environ.get(webhook_env)

        if not webhook_url and not dry_run:
            print(f"- {name}: skipped (env var {webhook_env} not set)")
            continue

        parsed = feedparser.parse(url, agent=ua)
        if parsed.bozo and not parsed.entries:
            print(f"- {name}: feed error ({parsed.get('bozo_exception')})", file=sys.stderr)
            continue

        seen = state.get(name, [])
        seen_set = set(seen)
        first_run = name not in state

        new_entries = [e for e in parsed.entries if entry_id(e) not in seen_set]

        # On the very first run for a feed, seed state without posting so you
        # don't get blasted with 40 backlog messages.
        if first_run:
            state[name] = [entry_id(e) for e in parsed.entries]
            print(f"- {name}: seeded {len(parsed.entries)} items (no posts on first run)")
            continue

        # Oldest first, newest last, capped.
        to_post = [e for e in reversed(new_entries) if passes_filters(e, feed_cfg)]
        to_post = to_post[:max_per_feed]

        for e in to_post:
            embed = build_embed(e, feed_cfg)
            if post_to_discord(webhook_url, embed, dry_run):
                posted += 1
                seen.append(entry_id(e))
                if not dry_run:
                    time.sleep(1.2)  # stay under Discord webhook rate limits

        # Record everything we saw this pass (posted or filtered) so we don't
        # re-evaluate them next time.
        for e in new_entries:
            if entry_id(e) not in set(seen):
                seen.append(entry_id(e))
        state[name] = seen
        print(f"- {name}: {len(to_post)} posted")

    save_state(state)
    print(f"\nDone. {posted} item(s) posted.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    run(dry_run=ap.parse_args().dry_run)
