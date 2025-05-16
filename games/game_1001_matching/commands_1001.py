"""
Command handlers for the Memory Match Game (ID: 1001).
"""
import asyncio
import discord
import logging
import uuid
import time
import random
from discord import app_commands
from discord.ext import commands

from common.config import (
    CHALLENGE_TIMEOUT_SECONDS, 
    ACCEPT_EMOJI, DECLINE_EMOJI, EPHEMERAL_MESSAGE_DURATION,
    EMOJI_CATEGORIES
)
from common.database import database
from common.utils.game_utils import (
    active_games, handle_challenge_expiration, 
    generate_confirmation_id, handle_confirmation_expiration
)
from games.game_1001_matching.game_1001 import MemoryGame
from games.game_1001_matching.ui_1001 import GameView

logger = logging.getLogger("discord_bot")

# Game-specific storage
GAME_ID = "1001"  # Unique identifier for Memory Match Game
pending_challenges = {}  # (target_user_id, channel_id) -> (challenger, channel, message_id, category)
end_game_confirmations = {}  # uuid -> {channel_id, requester, opponent, message_id, opponent_id}

# Compatibility aliases for pending_challenges and end_game_confirmations
pending_match_challenges = pending_challenges
end_match_confirmations = end_game_confirmations

async def category_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Provide autocomplete suggestions for emoji categories."""
    categories = list(EMOJI_CATEGORIES.keys())
    return [
        app_commands.Choice(name=cat, value=cat)
        for cat in categories if current.lower() in cat.lower()
    ][:25]  # Discord limits to 25 choices

async def setup_challenge_command(bot):
    """Alias for setup_memory_match_commands to maintain compatibility with bot.py imports."""
    return await setup_memory_match_commands(bot)

async def setup_memory_match_commands(bot):
    """Set up the Memory Match challenge command."""
    @bot.hybrid_command(
        name="matching_game", 
        description="Challenge another player to a Memory Match game"
    )
    @app_commands.describe(
        user="The user to challenge",
        category="The emoji category to use (faces, animals, food, moon, etc.)",
        grid_size="Optional: Set grid size (default: 5x5, mobile-friendly: 4x5)"
    )
    @app_commands.choices(grid_size=[
        app_commands.Choice(name="5x5 (Standard)", value="5x5"),
        app_commands.Choice(name="4x5 (Mobile-friendly)", value="4x5")
    ])
    @app_commands.autocomplete(category=category_autocomplete)
    async def challenge(ctx, user: discord.Member, category: str = None, grid_size: str = "5x5"):
        """Challenge another user to a Memory Match game."""
        try:            
            # Check if challenging self
            if user.id == ctx.author.id:
                await ctx.send("You can't challenge yourself!")
                return
                
            # Check if challenging a bot
            if user.bot:
                await ctx.send("You can't challenge a bot!")
                return
                
            # Check if there's already an active game in this channel
            if ctx.channel.id in active_games.get(GAME_ID, {}):
                await ctx.send("There's already an active game in this channel. Finish or end that game first.")
                return
                
            # Check if there's already a pending challenge to this user in this channel
            if (user.id, ctx.channel.id) in pending_match_challenges:
                await ctx.send(f"{user.mention} already has a pending challenge in this channel.")
                return
                
            # Validate category if provided
            if category and category.lower() not in EMOJI_CATEGORIES:
                available_cats = ", ".join(EMOJI_CATEGORIES.keys())
                await ctx.send(f"Invalid category. Available categories: {available_cats}")
                return
                
            # If no category provided, select random one
            if not category:
                category = random.choice(list(EMOJI_CATEGORIES.keys()))
            
            # Parse grid size
            rows, cols = 5, 5  # Default
            if grid_size == "4x5":
                rows, cols = 5, 4  # 4 columns, 5 rows (mobile-friendly)
                
            # Create the challenge embed
            embed = discord.Embed(
                title="🎮 Memory Match Challenge! 🎮",
                description=f"💥 {ctx.author.mention} challenges {user.mention} to a Memory Match game with {category} emojis! 💥",
                color=discord.Color.orange()
            )
            embed.add_field(name="⏳ Timeout", value=f"{int(CHALLENGE_TIMEOUT_SECONDS)} seconds", inline=True)
            embed.add_field(
                name="📝 Instructions", 
                value=f"React with {ACCEPT_EMOJI} to accept or {DECLINE_EMOJI} to decline below.",
                inline=False
            )
            embed.add_field(
                name="📊 Category", 
                value=f"{category}",
                inline=True
            )
            embed.add_field(
                name="📏 Grid Size", 
                value=f"{cols}x{rows}",
                inline=True
            )
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            embed.set_footer(text=f"Match your memory skills! | Game ID: {GAME_ID}")
            
            # Send the challenge message
            challenge_msg = await ctx.send(embed=embed)
            
            # Add reaction options
            await challenge_msg.add_reaction(ACCEPT_EMOJI)
            await challenge_msg.add_reaction(DECLINE_EMOJI)
            
            # Store the challenge with grid size
            pending_match_challenges[(user.id, ctx.channel.id)] = (ctx.author, ctx.channel, challenge_msg.id, category, rows, cols)
            
            # Set up challenge expiration
            asyncio.create_task(handle_challenge_expiration((user.id, ctx.channel.id), CHALLENGE_TIMEOUT_SECONDS))
        
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            await ctx.send("Error creating challenge. Please try again.")

    @bot.hybrid_command(name="matching_accept", description="Accept a pending Memory Match challenge")
    async def accept_challenge(ctx):
        """Accept a pending Memory Match challenge."""
        try:
            # Check if there's a pending challenge for this user in this channel
            if (ctx.author.id, ctx.channel.id) not in pending_match_challenges:
                await ctx.send("You don't have any pending Memory Match challenges in this channel.")
                return
            
            # Check if there's already an active game in this channel
            if ctx.channel.id in active_games.get(GAME_ID, {}):
                await ctx.send("There's already an active game in this channel. Finish or end that game first.")
                
                # Remove the pending challenge
                del pending_match_challenges[(ctx.author.id, ctx.channel.id)]
                return
                
            # Get the challenge details
            challenger, channel, message_id, category, rows, cols = pending_match_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Remove the challenge from pending
            del pending_match_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Create the game
            game = MemoryGame(challenger, ctx.author, ctx.channel, category, rows, cols)
            
            # Make sure the active_games dictionary is initialized for this game ID
            if GAME_ID not in active_games:
                active_games[GAME_ID] = {}
                
            # Store the game
            active_games[GAME_ID][ctx.channel.id] = game
            
            # Try to delete the challenge message
            try:
                challenge_msg = await ctx.channel.fetch_message(message_id)
                await challenge_msg.delete()
            except (discord.errors.NotFound, discord.errors.Forbidden):
                # Message might have been deleted or we lack permissions
                pass
                
            # Create game view
            view = GameView(game)
            
            # Send initial game state
            grid_size_info = f"{cols}x{rows}" if rows and cols else "standard"
            await ctx.send(f"📝 Memory Match Game started: {challenger.mention} vs {ctx.author.mention} with **{category}** emojis ({grid_size_info} grid)\n🎲 **{game.current_player.mention} will go first!**")
            
            # Send the main game messages (board and buttons separate)
            try:
                board_message, buttons_message = await view.send_initial_messages(ctx.channel)
            except Exception as e:
                logger.error(f"Error sending initial game messages: {e}")
                await ctx.channel.send("Error displaying the game. Please try starting a new game.")
                # Clean up active game if setup failed critically
                if ctx.channel.id in active_games[GAME_ID]:
                    del active_games[GAME_ID][ctx.channel.id]
                return
            
            logger.info(f"Memory Match game started in channel {ctx.channel.id}: {challenger.display_name} vs {ctx.author.display_name} with category {category} and grid size {grid_size_info}")
            
        except Exception as e:
            logger.error(f"Error accepting challenge: {e}")
            await ctx.send("Error starting game. Please try again.")

    @bot.hybrid_command(name="matching_decline", description="Decline a pending Memory Match challenge")
    async def decline_challenge(ctx):
        """Decline a pending Memory Match challenge."""
        try:
            # Check if there's a pending challenge for this user in this channel
            if (ctx.author.id, ctx.channel.id) not in pending_match_challenges:
                await ctx.send("You don't have any pending Memory Match challenges in this channel.")
                return
                
            # Get the challenge details
            challenger, channel, message_id, category, rows, cols = pending_match_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Remove the challenge from pending
            del pending_match_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Create the decline embed
            embed = discord.Embed(
                title="Challenge Declined",
                description=f"{ctx.author.mention} has declined {challenger.mention}'s Memory Match challenge.",
                color=discord.Color.red()
            )
            
            # Try to edit the original challenge message
            try:
                challenge_msg = await ctx.channel.fetch_message(message_id)
                await challenge_msg.edit(embed=embed)
                await challenge_msg.clear_reactions()
            except (discord.errors.NotFound, discord.errors.Forbidden):
                # Message might have been deleted or we lack permissions
                # Send a new message instead
                await ctx.send(embed=embed)
                
            logger.info(f"Memory Match challenge declined in channel {ctx.channel.id}: {challenger.display_name} -> {ctx.author.display_name}")
            
        except Exception as e:
            logger.error(f"Error declining challenge: {e}")
            await ctx.send("Error declining challenge. Please try again.")

    @bot.hybrid_command(name="matching_end", description="End the current Memory Match game in this channel")
    async def end_game(ctx):
        """End the current Memory Match game in this channel."""
        try:
            # Check if there's an active game in this channel
            if ctx.channel.id not in active_games.get(GAME_ID, {}):
                await ctx.send("There's no active Memory Match game in this channel.")
                return
                
            game = active_games[GAME_ID][ctx.channel.id]
            
            # Check if the user is one of the players
            if ctx.author.id != game.player1.id and ctx.author.id != game.player2.id:
                await ctx.send("Only players in the current game can end it.")
                return
            
            # Get the opponent
            opponent = game.player1 if ctx.author.id == game.player2.id else game.player2
            
            # Create a unique ID for this end game request
            confirmation_id = generate_confirmation_id()
            
            # Create the confirmation embed
            embed = discord.Embed(
                title="End Game Confirmation",
                description=f"{ctx.author.mention} wants to end the current Memory Match game.",
                color=discord.Color.gold()
            )
            
            # Add reactions for confirmation
            embed.add_field(
                name="Confirm",
                value=f"{opponent.mention} please react with {ACCEPT_EMOJI} to confirm or {DECLINE_EMOJI} to continue playing."
            )
            
            # Send the confirmation message
            confirmation_msg = await ctx.send(embed=embed)
            
            # Add reaction options
            await confirmation_msg.add_reaction(ACCEPT_EMOJI)
            await confirmation_msg.add_reaction(DECLINE_EMOJI)
            
            # Store the confirmation request
            end_match_confirmations[confirmation_id] = {
                'channel_id': ctx.channel.id,
                'requester': ctx.author,
                'opponent': opponent,
                'message_id': confirmation_msg.id,
                'opponent_id': opponent.id
            }
            
            # Set up confirmation expiration
            asyncio.create_task(handle_confirmation_expiration(confirmation_id, CHALLENGE_TIMEOUT_SECONDS))
            
        except Exception as e:
            logger.error(f"Error processing end game request: {e}")
            await ctx.send("Error processing end game request. Please try again.")

    # React to emojis for accepting/declining challenges
    @bot.event
    async def on_reaction_add(reaction, user):
        try:
            # Ignore bot's own reactions
            if user.bot:
                return
                
            message = reaction.message
            channel = message.channel
            emoji = str(reaction.emoji)
            
            # Check pending match challenges first
            for (target_id, channel_id), (challenger, challenge_channel, message_id, category, rows, cols) in list(pending_match_challenges.items()):
                if message.id == message_id and user.id == target_id:
                    if channel_id != channel.id:
                        continue
                        
                    # Check if accepting or declining
                    if emoji == ACCEPT_EMOJI:
                        # Remove the challenge to prevent duplicate processing
                        if (target_id, channel_id) in pending_match_challenges:
                            del pending_match_challenges[(target_id, channel_id)]
                            
                        # Create the game
                        game = MemoryGame(challenger, user, channel, category, rows, cols)
                        
                        # Make sure the active_games dictionary is initialized for this game ID
                        if GAME_ID not in active_games:
                            active_games[GAME_ID] = {}
                            
                        # Store the game
                        active_games[GAME_ID][channel.id] = game
                        
                        # Try to delete the challenge message
                        try:
                            await message.delete()
                        except discord.errors.NotFound:
                            pass
                            
                        # Create game view
                        view = GameView(game)
                        
                        # Send initial game state
                        grid_size_info = f"{cols}x{rows}" if rows and cols else "standard"
                        await channel.send(f"📝 Memory Match Game started: {challenger.mention} vs {user.mention} with **{category}** emojis ({grid_size_info} grid)\n🎲 **{game.current_player.mention} will go first!**")
                        
                        # Send the main game messages (board and buttons separate)
                        try:
                            board_message, buttons_message = await view.send_initial_messages(channel)
                        except Exception as e:
                            logger.error(f"Error sending initial game messages: {e}")
                            await channel.send("Error displaying the game. Please try starting a new game.")
                            # Clean up active game if setup failed
                            if channel.id in active_games[GAME_ID]:
                                del active_games[GAME_ID][channel.id]
                            return
                        
                        logger.info(f"Memory Match game started in channel {channel.id}: {challenger.display_name} vs {user.display_name} with category {category} and grid size {grid_size_info}")
                        return
                        
                    elif emoji == DECLINE_EMOJI:
                        # Remove the challenge from pending
                        if (target_id, channel_id) in pending_match_challenges:
                            del pending_match_challenges[(target_id, channel_id)]
                        
                        # Create the decline embed
                        embed = discord.Embed(
                            title="Challenge Declined",
                            description=f"{user.mention} has declined {challenger.mention}'s Memory Match challenge.",
                            color=discord.Color.red()
                        )
                        
                        # Edit the original challenge message
                        try:
                            await message.edit(embed=embed)
                            await message.clear_reactions()
                        except discord.errors.NotFound:
                            pass
                            
                        logger.info(f"Memory Match challenge declined in channel {channel.id}: {challenger.display_name} -> {user.display_name}")
                        return
            
            # Check end game confirmations
            for confirmation_id, data in list(end_match_confirmations.items()):
                if message.id == data['message_id'] and user.id == data['opponent_id']:
                    channel_id = data['channel_id']
                    requester = data['requester']
                    
                    if channel.id != channel_id:
                        continue
                    
                    # Check if accepting or declining end request
                    if emoji == ACCEPT_EMOJI:
                        # Check if the game still exists
                        if channel.id in active_games.get(GAME_ID, {}):
                            game = active_games[GAME_ID][channel.id]
                            
                            # Mark the game as over
                            game.game_over = True
                            
                            # Create game end embed
                            embed = discord.Embed(
                                title="Memory Match Game Ended",
                                description=f"Game between {game.player1.mention} and {game.player2.mention} has ended by agreement.",
                                color=discord.Color.gold()
                            )
                            
                            # Add final scores
                            embed.add_field(
                                name="Final Scores", 
                                value=f"{game.player1.display_name}: {game.scores.get(game.player1.id, 0)}\n{game.player2.display_name}: {game.scores.get(game.player2.id, 0)}",
                                inline=True
                            )
                            
                            embed.set_footer(text=f"Game ended by {requester.display_name} with {user.display_name}'s agreement")
                            
                            # Send the game end message
                            await channel.send(embed=embed)
                            
                            # Delete the buttons message if it exists
                            if hasattr(game, 'buttons_message') and game.buttons_message:
                                try:
                                    await game.buttons_message.delete()
                                except:
                                    pass
                            
                            # Update the board to show the final state
                            await game.update_board("Game ended by agreement")
                            
                            # Remove the game from active games
                            del active_games[GAME_ID][channel.id]
                            
                            logger.info(f"Memory Match game ended in channel {channel.id} by agreement")
                            
                        # Remove the confirmation
                        if confirmation_id in end_match_confirmations:
                            del end_match_confirmations[confirmation_id]
                            
                        # Try to delete the confirmation message
                        try:
                            await message.delete()
                        except discord.errors.NotFound:
                            pass
                            
                        return
                        
                    elif emoji == DECLINE_EMOJI:
                        # Create the decline embed
                        embed = discord.Embed(
                            title="End Game Request Declined",
                            description=f"{user.mention} wants to continue playing.",
                            color=discord.Color.green()
                        )
                        
                        # Edit the original confirmation message
                        try:
                            await message.edit(embed=embed)
                            await message.clear_reactions()
                        except discord.errors.NotFound:
                            pass
                            
                        # Remove the confirmation
                        if confirmation_id in end_match_confirmations:
                            del end_match_confirmations[confirmation_id]
                            
                        logger.info(f"End game request declined in channel {channel.id}")
                        return
                        
        except Exception as e:
            logger.error(f"Error handling reaction: {e}")

    # Register the Memory Match commands with the bot
    return {
        "matching_game": challenge,
        "matching_accept": accept_challenge,
        "matching_decline": decline_challenge,
        "matching_end": end_game
    }

async def end_memory_match_game_internal(channel, game, ended_by=None, reason="Game ended."):
    """End a Memory Match game and clean up resources.
    
    Args:
        channel: Discord channel where the game is taking place
        game: The MemoryGame instance
        ended_by: The user who ended the game
        reason: The reason the game ended
    """
    try:
        # Check if game exists and isn't already over
        if channel.id not in active_games.get(GAME_ID, {}) or game.game_over:
            return
        
        # Mark the game as over
        game.game_over = True
        
        # Create game end embed
        embed = discord.Embed(
            title="Memory Match Game Ended",
            description=f"Game between {game.player1.mention} and {game.player2.mention} has ended.",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Reason", 
            value=f"• {reason}",
            inline=True
        )
        
        embed.add_field(
            name="Final Scores", 
            value=f"{game.player1.display_name}: {game.scores.get(game.player1.id, 0)}\n{game.player2.display_name}: {game.scores.get(game.player2.id, 0)}",
            inline=True
        )
        
        if ended_by:
            embed.set_footer(text=f"Game ended by {ended_by.display_name}")
        
        # Send the game end message
        await channel.send(embed=embed)
        
        # Delete the buttons message if it exists
        if hasattr(game, 'buttons_message') and game.buttons_message:
            try:
                await game.buttons_message.delete()
            except:
                pass
        
        # Update the board to show the final state
        await game.update_board("Game Over - Ended manually")
        
        # Remove the game from active games
        del active_games[GAME_ID][channel.id]
        
        logger.info(f"Memory Match game ended in channel {channel.id}: {reason}")
        
    except Exception as e:
        logger.error(f"Error ending Memory Match game: {e}")
        # Try to remove the game from active games
        try:
            if GAME_ID in active_games and channel.id in active_games[GAME_ID]:
                del active_games[GAME_ID][channel.id]
        except:
            pass 

# Alias for end_memory_match_game_internal to match bot.py import
end_game_internal = end_memory_match_game_internal 