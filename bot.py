"""
Discord Game Bot with support for multiple games.
"""
import os
import asyncio
import discord
import logging
import traceback
import sys
import time
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Custom log formatter that safely handles emojis
class SafeFormatter(logging.Formatter):
    def format(self, record):
        try:
            return super().format(record)
        except UnicodeEncodeError:
            record.msg = str(record.msg).encode('utf-8', 'replace').decode('utf-8')
            if hasattr(record, 'args') and record.args:
                record.args = tuple(
                    str(arg).encode('utf-8', 'replace').decode('utf-8') 
                    if isinstance(arg, str) else arg 
                    for arg in record.args
                )
            return super().format(record)

# Import from common modules
from common.config import (
    COMMAND_PREFIX, AFK_TIMEOUT_SECONDS, 
    ACCEPT_EMOJI, DECLINE_EMOJI
)
from common.database import database
from common.utils.game_utils import active_games
from common.commands.leaderboard import setup_leaderboard_commands, GAME_IDS
from common.commands.help import setup_help_command

# Import game modules
# Memory Match Game (ID: 1001)
from games.game_1001_matching.commands_1001 import (
    setup_challenge_command, end_game_internal,
    end_game_confirmations, pending_challenges
)

# Tic Tac Toe Game (ID: 1002)
from games.game_1002_tictactoe.commands_1002 import (
    setup_tictactoe_command, end_ttt_game_internal,
    end_ttt_confirmations, pending_ttt_challenges
)

# Rock Paper Scissors Game (ID: 1003)
from games.game_1003_rps.commands_1003 import (
    setup_rps_command, pending_rps_challenges
)

# Setup logging
file_handler = logging.FileHandler("discord_bot.log", encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)

# Apply the safe formatter to both handlers
formatter = SafeFormatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.ERROR,  # Only show errors by default, can be changed to INFO
    format='%(asctime)s [%(levelname)s] %(message)s', # This format is overridden by handlers
    handlers=[
        file_handler,
        console_handler
    ]
)
logger = logging.getLogger("discord_bot")

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Setup intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

# Create bot
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

# Error handler
@bot.event
async def on_error(event, *args, **kwargs):
    error_type, error_value, error_traceback = sys.exc_info()
    
    error_msg = f"Error in {event}: {error_type.__name__}: {error_value}\n"
    error_msg += "".join(traceback.format_tb(error_traceback))
    
    logger.error(error_msg)
    
    # If this is during command execution, try to notify the user
    if event == "on_command_error" and args:
        ctx = args[0]
        try:
            await ctx.send(f"An error occurred: {error_type.__name__}. Check logs for details.", delete_after=5.0)
        except:
            pass

@bot.event
async def on_command_error(ctx, error):
    error_msg = f"Command '{ctx.command}' error for {ctx.author} in {ctx.channel.name}: {error}"
    logger.error(error_msg)
    
    # Send a message to the user
    try:
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(f"Error executing command: {error.original.__class__.__name__}. Check logs for details.", delete_after=5.0)
        else:
            await ctx.send(f"Command error: {error.__class__.__name__}. Check logs for details.", delete_after=5.0)
    except:
        pass

@bot.event
async def on_ready():
    """When the bot is ready."""
    # Initialize database
    database["init_db"]()
    
    # Start background tasks
    bot.loop.create_task(check_afk_games())
    
    # Log bot info
    app_info = await bot.application_info()
    logger.info(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"Owner: {app_info.owner}")
    logger.info(f"Discord.py version: {discord.__version__}")
    
    # Set bot status
    game_names = list(GAME_IDS.values())
    status_text = f"{game_names[0]} & {game_names[1]}"
    await bot.change_presence(activity=discord.Game(name=status_text))
    
    print(f"{bot.user.name} is ready!")

async def check_afk_games():
    """Background task to check for AFK players and end inactive games."""
    while not bot.is_closed():
        try:
            current_time = time.time()
            
            # Check Memory Match Games (ID: 1001)
            game_id = "1001"
            channels_to_check = list(active_games[game_id].keys()) if game_id in active_games else []
            for channel_id in channels_to_check:
                game = active_games[game_id].get(channel_id)
                if not game:
                    continue
                
                # Check if the game has been inactive for too long
                if current_time - game.last_activity_time > AFK_TIMEOUT_SECONDS:
                    # Get the channel
                    channel = bot.get_channel(channel_id)
                    if not channel:
                        # Channel no longer exists, remove the game
                        if channel_id in active_games[game_id]:
                            del active_games[game_id][channel_id]
                        continue
                    
                    # End the game due to AFK
                    await end_game_internal(
                        channel, 
                        game, 
                        None, 
                        f"Game ended due to inactivity (no moves for {int(AFK_TIMEOUT_SECONDS/60)} minutes)."
                    )
            
            # Check Tic Tac Toe Games (ID: 1002)
            game_id = "1002"
            channels_to_check = list(active_games[game_id].keys()) if game_id in active_games else []
            for channel_id in channels_to_check:
                game = active_games[game_id].get(channel_id)
                if not game:
                    continue
                
                # Check if the game has been inactive for too long
                if current_time - game.last_activity_time > AFK_TIMEOUT_SECONDS:
                    # Get the channel
                    channel = bot.get_channel(channel_id)
                    if not channel:
                        # Channel no longer exists, remove the game
                        if channel_id in active_games[game_id]:
                            del active_games[game_id][channel_id]
                        continue
                    
                    # End the game due to AFK
                    await end_ttt_game_internal(
                        channel, 
                        game, 
                        None, 
                        f"Game ended due to inactivity (no moves for {int(AFK_TIMEOUT_SECONDS/60)} minutes)."
                    )
            
            # Check Rock Paper Scissors Games (ID: 1003)
            game_id = "1003"
            channels_to_check = list(active_games[game_id].keys()) if game_id in active_games else []
            for channel_id in channels_to_check:
                game = active_games[game_id].get(channel_id)
                if not game:
                    continue
                
                # Check if the game has been inactive for too long
                if current_time - game.last_activity_time > AFK_TIMEOUT_SECONDS:
                    # Get the channel
                    channel = bot.get_channel(channel_id)
                    if not channel:
                        # Channel no longer exists, remove the game
                        if channel_id in active_games[game_id]:
                            del active_games[game_id][channel_id]
                        continue
                    
                    # End the game due to AFK by removing it from active games
                    # No need for special handling as RPS games are stateless between rounds
                    if channel_id in active_games[game_id]:
                        del active_games[game_id][channel_id]
                        await channel.send(f"Rock Paper Scissors game ended due to inactivity (no moves for {int(AFK_TIMEOUT_SECONDS/60)} minutes).")
            
            # Sleep for a while before checking again (every 10 seconds)
            await asyncio.sleep(10)
        
        except Exception as e:
            logger.error(f"Error in AFK checker: {e}")
            await asyncio.sleep(30)  # Sleep longer on error

@bot.event
async def on_raw_reaction_add(payload):
    """Handle reactions for game challenges and confirmations."""
    try:
        # Ignore bot's own reactions
        if payload.user_id == bot.user.id:
            return
        
        # Get the channel
        channel = bot.get_channel(payload.channel_id)
        if not channel:
            return
        
        # Get the message
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.errors.NotFound, discord.errors.Forbidden):
            return
            
        # Ignore if the message is not from the bot
        if message.author.id != bot.user.id:
            return
            
        # Get the emoji as a string
        emoji = str(payload.emoji)
        
        # Get the user who reacted
        user = None # Initialize user
        try:
            guild = bot.get_guild(payload.guild_id)
            if not guild:
                logger.warning(f"Reaction payload from unknown guild_id: {payload.guild_id}, channel_id: {payload.channel_id}")
                return
            
            # Try to get member from cache first, then fetch if not found or if member object is incomplete
            user = guild.get_member(payload.user_id)
            if not user:
                logger.info(f"Member {payload.user_id} not in cache for guild {guild.id}, attempting to fetch.")
                user = await guild.fetch_member(payload.user_id)
            
            if not user: # Should be redundant if fetch_member raises NotFound, but as a safeguard
                logger.warning(f"Could not obtain member object for {payload.user_id} in guild {guild.id} after fetch attempt.")
                return

        except discord.errors.NotFound:
            logger.warning(f"Member {payload.user_id} not found in guild {guild.id} via fetch_member. They might have left.")
            return
        except discord.errors.Forbidden:
            logger.error(f"Bot lacks permissions to fetch member {payload.user_id} in guild {guild.id}.")
            return
        except discord.errors.HTTPException as e:
            logger.error(f"HTTP error fetching member {payload.user_id} in guild {guild.id}: {e.status} {e.text}")
            return
        except Exception as e:
            logger.error(f"Unexpected error fetching member {payload.user_id} in guild {guild.id}: {type(e).__name__} - {e}")
            logger.error(traceback.format_exc())
            return
            
        # Check for Memory Match challenge acceptance/rejection
        # pending_challenges: (target_user_id, channel_id) -> (challenger, channel, category, message_id, rows, cols)
        for key, challenge_tuple in list(pending_challenges.items()):
            target_id, ch_id = key
            
            # Unpack only the first 4 values we need, ignoring the rest
            challenger, channel, message_id, category = challenge_tuple[:4]
            
            if message_id == payload.message_id and payload.user_id == target_id:
                # This is a reaction to a challenge message
                
                if emoji == ACCEPT_EMOJI:
                    # Challenge accepted - create a new Context to call the accept command
                    ctx = await bot.get_context(message)
                    ctx.author = user
                    await bot.get_command("matching_accept").invoke(ctx)
                    return
                    
                elif emoji == DECLINE_EMOJI:
                    # Challenge declined - create a new Context to call the decline command
                    ctx = await bot.get_context(message)
                    ctx.author = user
                    await bot.get_command("matching_decline").invoke(ctx)
                    return
        
        # Check for Tic Tac Toe challenge acceptance/rejection
        for key, (challenger, ch, msg_id) in list(pending_ttt_challenges.items()):
            target_id, ch_id = key
            
            if msg_id == payload.message_id and payload.user_id == target_id:
                # This is a reaction to a Tic Tac Toe challenge message
                
                if emoji == ACCEPT_EMOJI:
                    # Challenge accepted - create a new Context to call the accept command
                    ctx = await bot.get_context(message)
                    ctx.author = user
                    await bot.get_command("ttt_accept").invoke(ctx)
                    return
                    
                elif emoji == DECLINE_EMOJI:
                    # Challenge declined - create a new Context to call the decline command
                    ctx = await bot.get_context(message)
                    ctx.author = user
                    await bot.get_command("ttt_decline").invoke(ctx)
                    return
        
        # Check for Rock Paper Scissors challenge acceptance/rejection
        for key, (challenger, ch, msg_id, game_type) in list(pending_rps_challenges.items()):
            target_id, ch_id = key
            
            if msg_id == payload.message_id and payload.user_id == target_id:
                # This is a reaction to a Rock Paper Scissors challenge message
                
                if emoji == ACCEPT_EMOJI:
                    # Challenge accepted - create a new Context to call the accept command
                    ctx = await bot.get_context(message)
                    ctx.author = user
                    await bot.get_command("rps_accept").invoke(ctx)
                    return
                    
                elif emoji == DECLINE_EMOJI:
                    # Challenge declined - create a new Context to call the decline command
                    ctx = await bot.get_context(message)
                    ctx.author = user
                    await bot.get_command("rps_decline").invoke(ctx)
                    return
        
        # Check for Memory Match end game confirmations
        for confirmation_id, info in list(end_game_confirmations.items()):
            if info["message_id"] == payload.message_id and payload.user_id == info["opponent_id"]:
                # This is a reaction to an end game confirmation message
                
                if emoji == ACCEPT_EMOJI:
                    # End game confirmed
                    channel_id = info["channel_id"]
                    
                    # Check if the game still exists
                    if "1001" in active_games and channel_id in active_games["1001"]:
                        game = active_games["1001"][channel_id]
                        
                        # End the game
                        await end_game_internal(
                            channel,
                            game,
                            info["requester"],
                            "Game ended by mutual agreement."
                        )
                    
                    # Delete the confirmation message
                    try:
                        await message.delete()
                    except:
                        pass
                    
                    # Remove the confirmation
                    del end_game_confirmations[confirmation_id]
                    return
                    
                elif emoji == DECLINE_EMOJI:
                    # End game rejected
                    # Update the embed
                    embed = discord.Embed(
                        title="End Game Rejected",
                        description=f"{info['opponent'].mention} wants to continue playing.",
                        color=discord.Color.red()
                    )
                    
                    # Edit the message
                    try:
                        await message.edit(embed=embed)
                        await message.clear_reactions()
                    except:
                        pass
                    
                    # Remove the confirmation
                    del end_game_confirmations[confirmation_id]
                    return
        
        # Check for Tic Tac Toe end game confirmations
        for confirmation_id, info in list(end_ttt_confirmations.items()):
            if info["message_id"] == payload.message_id and payload.user_id == info["opponent_id"]:
                # This is a reaction to an end game confirmation message
                
                if emoji == ACCEPT_EMOJI:
                    # End game confirmed
                    channel_id = info["channel_id"]
                    
                    # Check if the game still exists
                    if "1002" in active_games and channel_id in active_games["1002"]:
                        game = active_games["1002"][channel_id]
                        
                        # End the game
                        await end_ttt_game_internal(
                            channel,
                            game,
                            info["requester"],
                            "Game ended by mutual agreement."
                        )
                    
                    # Delete the confirmation message
                    try:
                        await message.delete()
                    except:
                        pass
                    
                    # Remove the confirmation
                    del end_ttt_confirmations[confirmation_id]
                    return
                    
                elif emoji == DECLINE_EMOJI:
                    # End game rejected
                    # Update the embed
                    embed = discord.Embed(
                        title="End Game Rejected",
                        description=f"{info['opponent'].mention} wants to continue playing.",
                        color=discord.Color.red()
                    )
                    
                    # Edit the message
                    try:
                        await message.edit(embed=embed)
                        await message.clear_reactions()
                    except:
                        pass
                    
                    # Remove the confirmation
                    del end_ttt_confirmations[confirmation_id]
                    return
                
    except Exception as e:
        logger.error(f"Error handling reaction: {e}\n{traceback.format_exc()}")

@bot.command(name="sync", description="Sync slash commands with Discord")
@commands.is_owner()
async def sync(ctx):
    """Sync slash commands with Discord."""
    try:
        logger.info("Syncing slash commands...")
        await bot.tree.sync()
        response = await ctx.send("Slash commands synced successfully!", delete_after=1.0)
        await ctx.message.delete(delay=1.0)
        logger.info("Slash commands synced successfully")
    except Exception as e:
        logger.error(f"Error syncing slash commands: {e}")
        await ctx.send(f"Error syncing slash commands: {e}", delete_after=1.0)

async def setup_all_games():
    """Set up all game modules."""
    # Register the common commands
    leaderboard_commands = await setup_leaderboard_commands(bot)
    help_commands = await setup_help_command(bot)
    
    # Set up matching game commands (ID: 1001)
    await setup_challenge_command(bot)
    
    # Set up tic tac toe commands (ID: 1002)
    await setup_tictactoe_command(bot)
    
    # Set up Rock Paper Scissors commands (ID: 1003)
    await setup_rps_command(bot)
    
    logger.info(f"Registered commands: {', '.join(list(leaderboard_commands.keys()) + list(help_commands.keys()))}")

# Run the bot
async def main():
    """Main entry point."""
    try:
        # Initialize active_games dictionary
        for game_id in GAME_IDS:
            active_games[game_id] = {}
        
        # Setup all games
        await setup_all_games()
        
        # Start the bot
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot shutdown initiated via keyboard interrupt")
        await bot.close()
    finally:
        logger.info("Bot has been shutdown")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shutdown initiated by user (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        print(f"Unhandled error: {e}") 