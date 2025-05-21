import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import sys
from datetime import datetime
import os
import time
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import random
import aiohttp
import asyncio

# Load environment variables
load_dotenv()

# Initialize bot with command prefix '!'
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def validate_letterboxd_url(url):
    """
    Validate if the provided URL is a valid Letterboxd watchlist URL.
    
    Args:
        url (str): The URL to validate
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"
    
    # Check if URL starts with @ symbol and remove it if present
    if url.startswith('@'):
        url = url[1:]
    
    try:
        parsed_url = urlparse(url)
        
        # Check if it's a valid URL
        if not all([parsed_url.scheme, parsed_url.netloc]):
            return False, "Invalid URL format"
        
        # Check if it's a letterboxd.com domain
        if not parsed_url.netloc.endswith('letterboxd.com'):
            return False, "URL must be from letterboxd.com"
        
        # Check if it's a watchlist URL
        if not '/watchlist/' in parsed_url.path:
            return False, "URL must be a watchlist page"
        
        # Extract username from path
        username = parsed_url.path.split('/')[1]
        if not username:
            return False, "Username not found in URL"
        
        return True, username
        
    except Exception as e:
        return False, f"Error validating URL: {str(e)}"

def get_watchlist_url(username):
    """
    Construct a Letterboxd watchlist URL from a username.
    
    Args:
        username (str): The Letterboxd username
        
    Returns:
        str: The complete watchlist URL
    """
    return f"https://letterboxd.com/{username}/watchlist/"

async def scrape_watchlist(url):
    """
    Scrape the watchlist from the provided Letterboxd URL.
    
    Args:
        url (str): The Letterboxd watchlist URL
        
    Returns:
        list: List of movies in the watchlist
    """
    # Remove @ symbol if present
    if url.startswith('@'):
        url = url[1:]
    
    try:
        movies = []
        page = 1
        async with aiohttp.ClientSession() as session:
            while True:
                # Construct page URL
                page_url = f"{url}page/{page}/" if page > 1 else url
                # print(f"Scraping page {page}...")
                
                async with session.get(page_url) as response:
                    response.raise_for_status()
                    html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find all movie posters which contain the movie information
                movie_elements = soup.find_all('div', class_='film-poster')
                
                # If no movies found on this page, we've reached the end
                if not movie_elements:
                    break
                    
                for movie in movie_elements:
                    # Get the movie title from the img alt attribute
                    title_element = movie.find('img')
                    if title_element and title_element.get('alt'):
                        movies.append(title_element['alt'])
                
                # Check if there's a next page
                next_page = soup.find('a', class_='next')
                if not next_page:
                    break
                
                # Add delay between requests to avoid rate limiting
                # print("Waiting 15 seconds before next request...")
                await asyncio.sleep(15)
                page += 1
        
        return movies
        
    except Exception as e:
        # print(f"Error fetching the page: {str(e)}")
        return []

async def find_common_movies(*usernames):
    """
    Find movies that are common between multiple users' watchlists.
    
    Args:
        *usernames: Variable number of Letterboxd usernames (2-4)
        
    Returns:
        list: List of common movies
    """
    if not 2 <= len(usernames) <= 4:
        raise ValueError("Number of usernames must be between 2 and 4")
    
    # Get watchlists for all users
    movie_sets = []
    for username in usernames:
        url = get_watchlist_url(username)
        movies = set(await scrape_watchlist(url))
        movie_sets.append(movies)
    
    # Find intersection of all sets
    common_movies = set.intersection(*movie_sets)
    return sorted(list(common_movies))

def pick_random_movie(movie_list):
    """
    Pick a random movie from the provided list.
    
    Args:
        movie_list (list): List of movies to choose from
        
    Returns:
        str: Randomly selected movie title
    """
    if not movie_list:
        return None
    return random.choice(movie_list)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        # Set bot status
        await bot.change_presence(activity=discord.Game(name="Try using /random_movie!"))
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="watchlist_overlap", description="Compare watchlists between 2-4 users")
async def watchlist_overlap(
    interaction: discord.Interaction,
    username1: str,
    username2: str,
    username3: str = None,
    username4: str = None
):
    """
    Compare watchlists between 2-4 users and find common movies.
    
    Args:
        interaction: Discord interaction
        username1: First user's Letterboxd username
        username2: Second user's Letterboxd username
        username3: Third user's Letterboxd username (optional)
        username4: Fourth user's Letterboxd username (optional)
    """
    # Defer the response since this might take a while
    await interaction.response.defer()
    
    try:
        # Filter out None values and get common movies
        usernames = [u for u in [username1, username2, username3, username4] if u is not None]
        common_movies = await find_common_movies(*usernames)
        
        if not common_movies:
            await interaction.followup.send("No common movies found between these users.")
            return
            
        # Create message chunks to avoid Discord's message length limit
        message_chunks = []
        current_chunk = f"Common movies between {', '.join(usernames)}:\n\n"
        
        for movie in common_movies:
            if len(current_chunk) + len(movie) + 3 > 1900:  # Discord's limit is 2000
                message_chunks.append(current_chunk)
                current_chunk = ""
            current_chunk += f"- {movie}\n"
            
        if current_chunk:
            message_chunks.append(current_chunk)
            
        # Send results
        for chunk in message_chunks:
            await interaction.followup.send(chunk)
            
        await interaction.followup.send(f"Found {len(common_movies)} common movies in total!")
        
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}")

@bot.tree.command(name="random_movie", description="Pick a random movie from common watchlist between 2-4 users")
async def random_movie(
    interaction: discord.Interaction,
    username1: str,
    username2: str,
    username3: str = None,
    username4: str = None
):
    """
    Pick a random movie from the common watchlist of 2-4 users.
    
    Args:
        interaction: Discord interaction
        username1: First user's Letterboxd username
        username2: Second user's Letterboxd username
        username3: Third user's Letterboxd username (optional)
        username4: Fourth user's Letterboxd username (optional)
    """
    # Defer the response since this might take a while
    await interaction.response.defer()
    
    try:
        # Filter out None values and get common movies
        usernames = [u for u in [username1, username2, username3, username4] if u is not None]
        common_movies = await find_common_movies(*usernames)
        
        if not common_movies:
            await interaction.followup.send("No common movies found between these users.")
            return
        
        random_movie = pick_random_movie(common_movies)
        await interaction.followup.send(
            f"🎬 Random movie pick for {', '.join(usernames)}:\n**{random_movie}**"
        )
        
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}")

def main():
    # Get token from environment variable
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN not found in environment variables")
        sys.exit(1)
        
    # Run the bot
    bot.run(token)

if __name__ == "__main__":
    main() 