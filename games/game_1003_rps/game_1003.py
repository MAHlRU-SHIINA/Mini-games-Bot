"""
Game logic for the Discord Rock Paper Scissors Games (ID: 1003).
"""
import random
import discord
import aiohttp
import logging
import traceback
import time
import os
from typing import Optional, Dict, Tuple, List
from dotenv import load_dotenv

# Import from common folder structure
from common.utils.game_utils import update_database_with_game_results

logger = logging.getLogger("discord_bot")

# Load environment variables
load_dotenv()
TENOR_API_KEY = os.getenv("TENOR_API_KEY", "")

GAME_ID = "1003"  # Define Game ID for database logging

# RPS choices and rules
RPS_CHOICES = ["rock", "paper", "scissors"]
RPS_EMOJIS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
RPS_WINNERS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}  # Key beats Value

# Action options for RPS Action game
ACTION_OPTIONS = [
    "slap", "kiss", "nuke", "laugh", "pat", "hug", 
    "poke", "tickle", "bonk", "punch", "dance with"
]

class BasicRPSGame:
    """Basic Rock Paper Scissors game logic."""
    def __init__(self, player1, player2, channel=None):
        self.player1 = player1
        self.player2 = player2
        self.channel = channel
        self.choices = {player1.id: None, player2.id: None}
        self.game_over = False
        self.winner = None
        self.last_activity_time = time.time()
        
        # Message references for cleanup
        self.start_message = None
        self.choice_message = None
        self.result_message = None
        
    def make_choice(self, player_id, choice):
        """Record a player's choice."""
        if player_id in [self.player1.id, self.player2.id] and choice in RPS_CHOICES:
            self.choices[player_id] = choice
            self.last_activity_time = time.time()
            return True
        return False
    
    def determine_result(self) -> Dict:
        """Determine the winner if both players have chosen."""
        if None in self.choices.values():
            return {"status": "waiting", "message": "Waiting for both players to choose."}
            
        choice1 = self.choices[self.player1.id]
        choice2 = self.choices[self.player2.id]
        
        # Build result object with detailed info
        result = {
            "status": "complete",
            "player1": {"id": self.player1.id, "choice": choice1, "emoji": RPS_EMOJIS[choice1]},
            "player2": {"id": self.player2.id, "choice": choice2, "emoji": RPS_EMOJIS[choice2]},
            "message": "",
            "winner": None
        }
        
        # Determine winner
        if choice1 == choice2:
            result["message"] = f"It's a tie! Both players chose {RPS_EMOJIS[choice1]} {choice1}."
            result["winner"] = None
            self.winner = None
        elif RPS_WINNERS[choice1] == choice2:
            result["message"] = f"{self.player1.mention} wins! {RPS_EMOJIS[choice1]} {choice1} beats {RPS_EMOJIS[choice2]} {choice2}."
            result["winner"] = self.player1
            self.winner = self.player1
        else:
            result["message"] = f"{self.player2.mention} wins! {RPS_EMOJIS[choice2]} {choice2} beats {RPS_EMOJIS[choice1]} {choice1}."
            result["winner"] = self.player2
            self.winner = self.player2
            
        self.game_over = True
        return result
    
    def is_complete(self) -> bool:
        """Check if both players have made their choices."""
        return None not in self.choices.values()
    
    def reset(self):
        """Reset the game for a new round."""
        self.choices = {self.player1.id: None, self.player2.id: None}
        self.game_over = False
        self.winner = None
        self.last_activity_time = time.time()

class ActionRPSGame(BasicRPSGame):
    """Extended RPS game with actions that display GIFs."""
    def __init__(self, player1, player2, channel):
        super().__init__(player1, player2, channel)
        self.actions = {player1.id: None, player2.id: None}
        self.current_state = "WAITING_FOR_ACTIONS"  # Game flow state
        
        # Additional message references for action game
        self.action_message = None
        self.rps_message = None
        
    def set_player_action(self, player_id, action):
        """Set what action the player wants to perform if they win."""
        if player_id in [self.player1.id, self.player2.id] and action in ACTION_OPTIONS:
            self.actions[player_id] = action
            self.last_activity_time = time.time()
            return True
        return False
    
    def are_actions_selected(self) -> bool:
        """Check if both players have selected their actions."""
        return None not in self.actions.values()
    
    def determine_action_result(self) -> Dict:
        """Determine the winner and what action will be performed."""
        # First get the basic RPS result
        result = self.determine_result()
        
        # If it's a tie, no action is performed
        if not self.winner:
            result["action"] = None
            result["action_message"] = "It's a tie! No action performed."
            return result
            
        # Get the winner's action
        winner_id = self.winner.id
        winner_action = self.actions[winner_id]
        
        # Set who performs what on whom
        if winner_id == self.player1.id:
            actor = self.player1
            target = self.player2
        else:
            actor = self.player2
            target = self.player1
            
        result["action"] = winner_action
        result["actor"] = actor
        result["target"] = target
        result["action_message"] = f"{actor.mention} {winner_action}s {target.mention}!"
        
        return result
    
    async def fetch_gif(self, action):
        """Fetch a random GIF for the given action using Tenor API."""
        # Use the test API key from the example
        api_key = "LIVDSRZULELA"  # test API key for v1
        
        try:
            # Add "anime" to the search term
            search_term = f"anime {action}"
            
            # Add random number to search to get different results
            random_limit = 40  # Limit to first 20 results for relevance
            
            async with aiohttp.ClientSession() as session:
                # Use v1 API instead of v2
                url = f"https://g.tenor.com/v1/search?q={search_term}&key={api_key}&limit={random_limit}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])
                        
                        if results:
                            # Pick a random result from the list
                            random_result = random.choice(results)
                            
                            # v1 API has a different structure for media formats
                            media = random_result.get("media", [{}])[0]
                            gif_url = media.get("gif", {}).get("url")
                            
                            # Fallback to other formats if gif is not available
                            if not gif_url:
                                gif_url = media.get("tinygif", {}).get("url")
                                
                            return gif_url
                    else:
                        logger.error(f"Tenor API error: {response.status} - {await response.text()}")
                        
        except Exception as e:
            logger.error(f"Error fetching GIF: {e}\n{traceback.format_exc()}")
            
        return None
        
    def reset(self):
        """Reset the game for a new round."""
        super().reset()
        self.actions = {self.player1.id: None, self.player2.id: None}
        self.current_state = "WAITING_FOR_ACTIONS" 