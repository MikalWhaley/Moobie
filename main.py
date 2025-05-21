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

async def find_common_movies(username1, username2):
    """
    Find movies that are common between two users' watchlists.
    
    Args:
        username1 (str): First user's Letterboxd username
        username2 (str): Second user's Letterboxd username
        
    Returns:
        list: List of common movies
    """
    # print(f"Getting watchlist for {username1}...")
    url1 = get_watchlist_url(username1)
    movies1 = set(await scrape_watchlist(url1))
    
    # print(f"\nGetting watchlist for {username2}...")
    url2 = get_watchlist_url(username2)
    movies2 = set(await scrape_watchlist(url2))
    
    common_movies = sorted(list(movies1.intersection(movies2)))
    
    # # Create logs directory if it doesn't exist
    # if not os.path.exists('logs'):
    #     os.makedirs('logs')
        
    # # Create timestamped log file
    # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # log_filename = f'logs/common_movies_{timestamp}.txt'
    
    # # Write common movies to log file
    # with open(log_filename, 'w', encoding='utf-8') as f:
    #     f.write(f"Common movies between {username1} and {username2}\n")
    #     f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    #     f.write("-" * 50 + "\n")
    #     for movie in common_movies:
    #         f.write(f"{movie}\n")
    
    # print(f"\nResults have been saved to: {log_filename}")
    return common_movies

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
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="watchlist_overlap", description="Compare two Letterboxd users' watchlists and find common movies")
async def watchlist_overlap(interaction: discord.Interaction, username1: str, username2: str):
    """
    Compare two Letterboxd users' watchlists and find common movies.
    
    Args:
        interaction: Discord interaction
        username1: First user's Letterboxd username
        username2: Second user's Letterboxd username
    """
    # Defer the response since this might take a while
    await interaction.response.defer()
    
    try:
        common_movies = await find_common_movies(username1, username2)
        
        if not common_movies:
            await interaction.followup.send("No common movies found between these users.")
            return
            
        # Create message chunks to avoid Discord's message length limit
        message_chunks = []
        current_chunk = f"Common movies between {username1} and {username2}:\n\n"
        
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

@bot.tree.command(name="random_movie", description="Pick a random movie from the common watchlist of two users")
async def random_movie(interaction: discord.Interaction, username1: str, username2: str):
    """
    Pick a random movie from the common watchlist of two users.
    
    Args:
        interaction: Discord interaction
        username1: First user's Letterboxd username
        username2: Second user's Letterboxd username
    """
    # Defer the response since this might take a while
    await interaction.response.defer()
    
    try:
        common_movies = await find_common_movies(username1, username2)
        
        if not common_movies:
            await interaction.followup.send("No common movies found between these users.")
            return
        
        random_movie = pick_random_movie(common_movies)
        await interaction.followup.send(f"🎬 Random movie pick: **{random_movie}**")
        
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