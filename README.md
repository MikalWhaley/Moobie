# Letterboxd Watchlist Bot

A Discord bot that helps users find common movies in their Letterboxd watchlists and randomly select movies to watch.

## Features

- Compare watchlists between 2-4 users
- Find common movies across multiple watchlists
- Randomly select a movie from the common watchlist
- Async operations for better performance
- Rate limiting protection

## Commands

- `/watchlist_overlap` - Compare watchlists between 2-4 users
- `/random_movie` - Pick a random movie from common watchlist between 2-4 users

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your Discord bot token:
```
DISCORD_TOKEN=your_token_here
```

3. Run the bot:
```bash
python main.py
```

## Usage

1. `/watchlist_overlap username1:user1 username2:user2 [username3:user3] [username4:user4]`
   - Shows all movies that appear in all specified users' watchlists

2. `/random_movie username1:user1 username2:user2 [username3:user3] [username4:user4]`
   - Picks one random movie from the common watchlist

## Note

The bot includes a 15-second delay between requests to respect Letterboxd's rate limits. 