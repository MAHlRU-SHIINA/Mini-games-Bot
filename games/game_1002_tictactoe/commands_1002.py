"""
Command handlers for the Tic Tac Toe Game (ID: 1002).
"""
import asyncio
import discord
import logging
import uuid
import time
from discord import app_commands
from discord.ext import commands

from common.config import (
    CHALLENGE_TIMEOUT_SECONDS, 
    ACCEPT_EMOJI, DECLINE_EMOJI, EPHEMERAL_MESSAGE_DURATION
)
from common.database import database
from common.utils.game_utils import (
    active_games, handle_challenge_expiration, 
    generate_confirmation_id, handle_confirmation_expiration,
    update_database_with_game_results
)
from games.game_1002_tictactoe.game_1002 import TicTacToeGame
from games.game_1002_tictactoe.ui_1002 import TicTacToeView

logger = logging.getLogger("discord_bot")

# Game-specific storage
GAME_ID = "1002"  # Unique identifier for Tic Tac Toe Game
pending_ttt_challenges = {}  # (target_user_id, channel_id) -> (challenger, channel, message_id)
end_ttt_confirmations = {}  # uuid -> {channel_id, requester, opponent, message_id, opponent_id}

async def setup_tictactoe_command(bot):
    """Set up the Tic Tac Toe challenge command."""
    @bot.hybrid_command(
        name="tictactoe", 
        description="Challenge another player to a Tic Tac Toe game"
    )
    @app_commands.describe(
        user="The user to challenge"
    )
    async def challenge(ctx, user: discord.Member):
        """Challenge another user to a Tic Tac Toe game."""
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
            if (user.id, ctx.channel.id) in pending_ttt_challenges:
                await ctx.send(f"{user.mention} already has a pending challenge in this channel.")
                return
                
            # Create the challenge embed
            embed = discord.Embed(
                title="⚔️ Tic Tac Toe Challenge! ⚔️",
                description=f"💥 {ctx.author.mention} dares {user.mention} to a game of Tic Tac Toe! 💥",
                color=discord.Color.orange()
            )
            embed.add_field(name="⏳ Timeout", value=f"{int(CHALLENGE_TIMEOUT_SECONDS)} seconds", inline=True)
            embed.add_field(
                name="📝 Instructions", 
                value=f"React with {ACCEPT_EMOJI} to accept or {DECLINE_EMOJI} to decline below.",
                inline=False
            )
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            embed.set_footer(text=f"May the best strategist win! | Game ID: {GAME_ID}")
            
            # Send the challenge message
            challenge_msg = await ctx.send(embed=embed)
            
            # Add reaction options
            await challenge_msg.add_reaction(ACCEPT_EMOJI)
            await challenge_msg.add_reaction(DECLINE_EMOJI)
            
            # Store the challenge
            pending_ttt_challenges[(user.id, ctx.channel.id)] = (ctx.author, ctx.channel, challenge_msg.id)
            
            # Set up challenge expiration
            asyncio.create_task(handle_challenge_expiration((user.id, ctx.channel.id), CHALLENGE_TIMEOUT_SECONDS))
        
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            await ctx.send("Error creating challenge. Please try again.")

    @bot.hybrid_command(name="ttt_accept", description="Accept a pending Tic Tac Toe challenge")
    async def accept_ttt(ctx):
        """Accept a pending Tic Tac Toe challenge."""
        try:
            # Check if there's a pending challenge for this user in this channel
            if (ctx.author.id, ctx.channel.id) not in pending_ttt_challenges:
                await ctx.send("You don't have any pending Tic Tac Toe challenges in this channel.")
                return
            
            # Check if there's already an active game in this channel
            if ctx.channel.id in active_games.get(GAME_ID, {}):
                await ctx.send("There's already an active game in this channel. Finish or end that game first.")
                
                # Remove the pending challenge
                del pending_ttt_challenges[(ctx.author.id, ctx.channel.id)]
                return
                
            # Get the challenge details
            challenger, channel, message_id = pending_ttt_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Remove the challenge from pending
            del pending_ttt_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Create the game
            game = TicTacToeGame(challenger, ctx.author, ctx.channel)
            
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
            view = TicTacToeView(game)
            
            # Send initial game state
            await ctx.send(f"Tic Tac Toe Game started: {challenger.mention} vs {ctx.author.mention}")
            board_msg = await ctx.send(embed=game.get_board_embed(), view=view)
            game.board_message = board_msg
            game.board_message_id = board_msg.id
            
            logger.info(f"Tic Tac Toe game started in channel {ctx.channel.id}: {challenger.display_name} vs {ctx.author.display_name}")
            
        except Exception as e:
            logger.error(f"Error accepting challenge: {e}")
            await ctx.send("Error starting game. Please try again.")

    @bot.hybrid_command(name="ttt_decline", description="Decline a pending Tic Tac Toe challenge")
    async def decline_ttt(ctx):
        """Decline a pending Tic Tac Toe challenge."""
        try:
            # Check if there's a pending challenge for this user in this channel
            if (ctx.author.id, ctx.channel.id) not in pending_ttt_challenges:
                await ctx.send("You don't have any pending Tic Tac Toe challenges in this channel.")
                return
                
            # Get the challenge details
            challenger, channel, message_id = pending_ttt_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Remove the challenge from pending
            del pending_ttt_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Create the decline embed
            embed = discord.Embed(
                title="Challenge Declined",
                description=f"{ctx.author.mention} has declined {challenger.mention}'s Tic Tac Toe challenge.",
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
                
            logger.info(f"Tic Tac Toe challenge declined in channel {ctx.channel.id}: {challenger.display_name} -> {ctx.author.display_name}")
            
        except Exception as e:
            logger.error(f"Error declining challenge: {e}")
            await ctx.send("Error declining challenge. Please try again.")

    @bot.hybrid_command(name="ttt_end", description="End the current Tic Tac Toe game in this channel")
    async def end_ttt_game(ctx):
        """End the current Tic Tac Toe game in this channel."""
        try:
            # Check if there's an active game in this channel
            if ctx.channel.id not in active_games.get(GAME_ID, {}):
                await ctx.send("There's no active Tic Tac Toe game in this channel.")
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
                description=f"{ctx.author.mention} wants to end the current Tic Tac Toe game.",
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
            end_ttt_confirmations[confirmation_id] = {
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

    # Register the Tic Tac Toe commands with the bot
    return {
        "tictactoe": challenge,
        "ttt_accept": accept_ttt,
        "ttt_decline": decline_ttt,
        "ttt_end": end_ttt_game
    }

async def end_ttt_game_internal(channel, game, ended_by, reason="Game ended."):
    """End a Tic Tac Toe game and clean up resources.
    
    Args:
        channel: Discord channel where the game is taking place
        game: The TicTacToeGame instance
        ended_by: The user who ended the game
        reason: The reason the game ended
    """
    try:
        # Check if game exists and isn't already over
        if channel.id not in active_games.get(GAME_ID, {}) or game.game_over:
            return
        
        # Mark the game as over
        game.game_over = True
        
        # Get the final game state
        winner = game.get_winner()
        
        # Update the database with game results
        if winner:
            # Update winner stats
            await update_database_with_game_results(
                channel=channel,
                winner=winner,
                loser=game.player1 if winner.id == game.player2.id else game.player2,
                game_id=GAME_ID
            )
        else:
            # It's a tie, both players get a loss
            await update_database_with_game_results(
                channel=channel,
                winner=None,
                loser=game.player2,
                game_id=GAME_ID
            )
        
        # Create game end embed
        embed = discord.Embed(
            title="Tic Tac Toe Game Ended",
            description=f"Game between {game.player1.mention} and {game.player2.mention} has ended.",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Reason", 
            value=f"• {reason}",
            inline=True
        )
        
        if winner:
            embed.add_field(
                name="Result",
                value=f"• 🏆 {winner.mention} wins!"
            )
        else:
            embed.add_field(
                name="Result",
                value=f"• 🤝 It's a draw!"
            )
        
        if ended_by:
            embed.set_footer(text=f"Game ended by {ended_by.display_name}")
        
        # Send the game end message
        await channel.send(embed=embed)
        
        # Update the game board to show final state
        try:
            view = TicTacToeView(game)
            await game.update_board("Game Over!")
            # Update the view
            await game.board_message.edit(view=view)
        except:
            pass
        
        # Remove the game from active games
        del active_games[GAME_ID][channel.id]
        
        logger.info(f"Tic Tac Toe game ended in channel {channel.id}: {reason}")
        
    except Exception as e:
        logger.error(f"Error ending Tic Tac Toe game: {e}")
        # Try to remove the game from active games
        try:
            if GAME_ID in active_games and channel.id in active_games[GAME_ID]:
                del active_games[GAME_ID][channel.id]
        except:
            pass 