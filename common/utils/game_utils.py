"""
Utility functions shared between different games.
"""
import discord
import logging
import asyncio
import time
import uuid

logger = logging.getLogger("discord_bot")

# Active games tracking - dictionary of dictionaries: {game_id: {channel_id: game_instance}}
active_games = {}

async def check_afk(bot, game_id, channel_id, game, end_game_func, afk_timeout):
    """
    Check if a game is AFK and end it if necessary.
    
    Args:
        bot: The Discord bot instance
        game_id: The unique game identifier
        channel_id: The channel ID where the game is taking place
        game: The game instance
        end_game_func: Function to call to end the game
        afk_timeout: Timeout in seconds
    
    Returns:
        bool: True if game was ended due to AFK, False otherwise
    """
    try:
        current_time = time.time()
        
        # Check if the game has been inactive for too long
        if current_time - game.last_activity_time > afk_timeout:
            # Get the channel
            channel = bot.get_channel(channel_id)
            if not channel:
                # Channel no longer exists, remove the game
                if game_id in active_games and channel_id in active_games[game_id]:
                    del active_games[game_id][channel_id]
                return True
            
            # End the game due to AFK
            await end_game_func(
                channel, 
                game, 
                None, 
                f"Game ended due to inactivity (no moves for {int(afk_timeout/60)} minutes)."
            )
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error in AFK check: {e}")
        return False

async def handle_challenge_expiration(challenge_key, timeout_seconds):
    """
    Handle the expiration of a game challenge.
    
    Args:
        challenge_key: Key for this challenge in the challenge dictionary
        timeout_seconds: Time in seconds to wait before expiring
    """
    # Import here to avoid circular imports
    from games.game_1001_matching.commands_1001 import pending_challenges
    from games.game_1002_tictactoe.commands_1002 import pending_ttt_challenges
    from games.game_1003_rps.commands_1003 import pending_rps_challenges
    
    try:
        # Wait for the timeout
        await asyncio.sleep(timeout_seconds)
        
        # Check if this was a memory match challenge
        if challenge_key in pending_challenges:
            # Remove it
            del pending_challenges[challenge_key]
            logger.info(f"Challenge {challenge_key} expired and was removed")
            
        # Check if this was a tic tac toe challenge    
        elif challenge_key in pending_ttt_challenges:
            # Remove it
            del pending_ttt_challenges[challenge_key]
            logger.info(f"TTT Challenge {challenge_key} expired and was removed")
            
        # Check if this was a Rock Paper Scissors challenge
        elif challenge_key in pending_rps_challenges:
            # Remove it
            del pending_rps_challenges[challenge_key]
            logger.info(f"RPS Challenge {challenge_key} expired and was removed")
            
    except Exception as e:
        logger.error(f"Error in handle_challenge_expiration: {e}")

def generate_confirmation_id():
    """Generate a unique confirmation ID."""
    return str(uuid.uuid4())

async def handle_confirmation_expiration(confirmation_id, timeout_seconds):
    """
    Handle the expiration of an end game confirmation.
    
    Args:
        confirmation_id: ID for this confirmation
        timeout_seconds: Time in seconds to wait before expiring
    """
    # Import here to avoid circular imports
    from games.game_1001_matching.commands_1001 import end_game_confirmations
    from games.game_1002_tictactoe.commands_1002 import end_ttt_confirmations
    
    try:
        # Wait for the timeout
        await asyncio.sleep(timeout_seconds)
        
        # Check if this was a memory match game confirmation
        if confirmation_id in end_game_confirmations:
            # Remove it
            del end_game_confirmations[confirmation_id]
            logger.info(f"End game confirmation {confirmation_id} expired and was removed")
            
        # Check if this was a tic tac toe game confirmation
        elif confirmation_id in end_ttt_confirmations:
            # Remove it
            del end_ttt_confirmations[confirmation_id]
            logger.info(f"TTT End game confirmation {confirmation_id} expired and was removed")
            
    except Exception as e:
        logger.error(f"Error in handle_confirmation_expiration: {e}")

async def update_database_with_game_results(**kwargs):
    """
    Update the database with game results.
    
    Args:
        This function accepts the following parameters in two formats:
        
        Format 1:
        channel: Discord channel where the game happened
        winner: Winner user (or None for a tie)
        loser: Loser user (or player2 in case of a tie)
        game_id: Game identifier
        
        Format 2:
        game_id: Game identifier
        player1_id: ID of player 1
        player2_id: ID of player 2
        winner_id: ID of the winner (or None for a tie)
        score_player1: Score of player 1
        score_player2: Score of player 2
        channel_id: ID of the channel where the game happened
    """
    from common.database import database
    
    try:
        # Check which format is being used
        if 'channel' in kwargs and 'winner' in kwargs and 'loser' in kwargs:
            # Format 1
            channel = kwargs['channel']
            winner = kwargs['winner']
            loser = kwargs['loser']
            game_id = kwargs['game_id']
            
            if not hasattr(channel, 'guild') or not channel.guild:
                logger.error(f"Channel {channel.id} has no guild attribute or guild is None")
                return
                
            server_id = channel.guild.id
            
            if winner:
                # Update winner stats
                database['update_player_stats'](
                    winner.id,
                    winner.display_name,
                    server_id,
                    True,
                    game_id
                )
                
                # Update loser stats
                database['update_player_stats'](
                    loser.id,
                    loser.display_name,
                    server_id,
                    False,
                    game_id
                )
            else:
                # It's a tie, both players get a loss
                database['update_player_stats'](
                    loser.id,
                    loser.display_name,
                    server_id,
                    False,
                    game_id
                )
        
        elif 'player1_id' in kwargs and 'player2_id' in kwargs:
            # Format 2 - Just log for now since we don't have easy access to server_id
            game_id = kwargs['game_id']
            player1_id = kwargs['player1_id']
            player2_id = kwargs['player2_id']
            winner_id = kwargs.get('winner_id')
            score_player1 = kwargs.get('score_player1', 0)
            score_player2 = kwargs.get('score_player2', 0)
            
            logger.info(
                f"Game results: game_id={game_id}, "
                f"player1_id={player1_id} (score: {score_player1}), "
                f"player2_id={player2_id} (score: {score_player2}), "
                f"winner_id={winner_id if winner_id else 'Tie'}"
            )
            
            # We won't update the database in this format for now
            # since we don't have the server_id and display_names easily
        
        else:
            logger.error(f"Invalid parameter format for update_database_with_game_results: {kwargs}")
    
    except Exception as e:
        logger.error(f"Error updating database with game results: {e}") 