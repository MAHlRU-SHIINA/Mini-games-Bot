"""
Command handlers for the Rock Paper Scissors Games (ID: 1003).
"""
import asyncio
import discord
import logging
import uuid
import time
from discord import app_commands
from discord.ext import commands
import aiohttp
import traceback

from common.config import (
    CHALLENGE_TIMEOUT_SECONDS,
    ACCEPT_EMOJI, DECLINE_EMOJI, EPHEMERAL_MESSAGE_DURATION
)
from common.database import database
from common.utils.game_utils import (
    active_games, handle_challenge_expiration,
    generate_confirmation_id, handle_confirmation_expiration
)
from games.game_1003_rps.game_1003 import BasicRPSGame, ActionRPSGame, RPS_EMOJIS
from games.game_1003_rps.ui_1003 import RPSView, ActionSelectView, PlayAgainButton

logger = logging.getLogger("discord_bot")

# Game-specific storage
GAME_ID = "1003"  # Unique identifier for RPS Games
BASIC_GAME_TYPE = "basic"  # Regular RPS
ACTION_GAME_TYPE = "action"  # RPS with actions

# Track challenges
pending_rps_challenges = {}  # (target_user_id, channel_id) -> (challenger, channel, message_id, game_type)

async def setup_rps_commands(bot):
    """Set up both RPS game commands."""
    
    #---------- Basic RPS Command ----------#
    @bot.hybrid_command(
        name="rps",
        description="Challenge another player to Rock Paper Scissors"
    )
    @app_commands.describe(
        user="The user to challenge"
    )
    async def rps_challenge(ctx, user: discord.Member):
        """Challenge another user to a basic Rock Paper Scissors game."""
        await create_challenge(ctx, user, BASIC_GAME_TYPE)
        
    #---------- Action RPS Command ----------#
    @bot.hybrid_command(
        name="rps_action",
        description="Challenge another player to Rock Paper Scissors Action"
    )
    @app_commands.describe(
        user="The user to challenge"
    )
    async def rps_action_challenge(ctx, user: discord.Member):
        """Challenge another user to a Rock Paper Scissors Action game."""
        await create_challenge(ctx, user, ACTION_GAME_TYPE)
    
    #---------- Shared Command Functions ----------#
    async def create_challenge(ctx, user, game_type):
        """Create a challenge for either RPS game type."""
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
                await ctx.send("There's already an active game in this channel. Finish that game first.")
                return
                
            # Check if there's already a pending challenge to this user in this channel
            if (user.id, ctx.channel.id) in pending_rps_challenges:
                await ctx.send(f"{user.mention} already has a pending challenge in this channel.")
                return
            
            # Format game type for display
            display_game_type = "Rock Paper Scissors" if game_type == BASIC_GAME_TYPE else "Rock Paper Scissors Action"
                
            # Create the challenge embed
            embed = discord.Embed(
                title=f"🎮 {display_game_type} Challenge! 🎮",
                description=f"💥 {ctx.author.mention} challenges {user.mention} to a game of {display_game_type}! 💥",
                color=discord.Color.orange()
            )
            embed.add_field(name="⏳ Timeout", value=f"{int(CHALLENGE_TIMEOUT_SECONDS)} seconds", inline=True)
            embed.add_field(
                name="📝 Instructions", 
                value=f"React with {ACCEPT_EMOJI} to accept or {DECLINE_EMOJI} to decline below.",
                inline=False
            )
            
            # Add game type specific description
            if game_type == ACTION_GAME_TYPE:
                embed.add_field(
                    name="🎯 Game Rules", 
                    value="Both players will choose an action and play Rock Paper Scissors. The winner gets to perform their action on the loser!",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎯 Game Rules", 
                    value=f"Choose {RPS_EMOJIS['rock']} Rock, {RPS_EMOJIS['paper']} Paper, or {RPS_EMOJIS['scissors']} Scissors to beat your opponent!",
                    inline=False
                )
                
            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            embed.set_footer(text=f"Let the games begin! | Game ID: {GAME_ID}")
            
            # Send the challenge message
            challenge_msg = await ctx.send(embed=embed)
            
            # Add reaction options
            await challenge_msg.add_reaction(ACCEPT_EMOJI)
            await challenge_msg.add_reaction(DECLINE_EMOJI)
            
            # Store the challenge
            pending_rps_challenges[(user.id, ctx.channel.id)] = (ctx.author, ctx.channel, challenge_msg.id, game_type)
            
            # Set up challenge expiration
            asyncio.create_task(handle_challenge_expiration(
                (user.id, ctx.channel.id), 
                CHALLENGE_TIMEOUT_SECONDS
            ))
        
        except Exception as e:
            logger.error(f"Error creating RPS challenge: {e}")
            await ctx.send("Error creating challenge. Please try again.")
    
    @bot.hybrid_command(
        name="rps_accept", 
        description="Accept a pending Rock Paper Scissors challenge"
    )
    async def accept_rps(ctx):
        """Accept a pending RPS challenge."""
        try:
            # Check if there's a pending challenge for this user in this channel
            if (ctx.author.id, ctx.channel.id) not in pending_rps_challenges:
                await ctx.send("You don't have any pending Rock Paper Scissors challenges in this channel.")
                return
            
            # Check if there's already an active game in this channel
            if ctx.channel.id in active_games.get(GAME_ID, {}):
                await ctx.send("There's already an active game in this channel. Finish that game first.")
                
                # Remove the pending challenge
                del pending_rps_challenges[(ctx.author.id, ctx.channel.id)]
                return
                
            # Get the challenge details
            challenger, channel, message_id, game_type = pending_rps_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Remove the challenge from pending
            del pending_rps_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Try to delete the challenge message
            try:
                challenge_msg = await ctx.channel.fetch_message(message_id)
                await challenge_msg.delete()
            except (discord.errors.NotFound, discord.errors.Forbidden):
                # Message might have been deleted or we lack permissions
                pass
                
            # Start the appropriate game
            if game_type == BASIC_GAME_TYPE:
                await start_basic_rps(ctx.channel, challenger, ctx.author)
            else:
                await start_action_rps(ctx.channel, challenger, ctx.author)
            
        except Exception as e:
            logger.error(f"Error accepting RPS challenge: {e}")
            await ctx.send("Error starting game. Please try again.")

    @bot.hybrid_command(
        name="rps_decline", 
        description="Decline a pending Rock Paper Scissors challenge"
    )
    async def decline_rps(ctx):
        """Decline a pending RPS challenge."""
        try:
            # Check if there's a pending challenge for this user in this channel
            if (ctx.author.id, ctx.channel.id) not in pending_rps_challenges:
                await ctx.send("You don't have any pending Rock Paper Scissors challenges in this channel.")
                return
                
            # Get the challenge details
            challenger, channel, message_id, game_type = pending_rps_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Remove the challenge from pending
            del pending_rps_challenges[(ctx.author.id, ctx.channel.id)]
            
            # Create the decline embed
            embed = discord.Embed(
                title="Challenge Declined",
                description=f"{ctx.author.mention} has declined {challenger.mention}'s Rock Paper Scissors challenge.",
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
                
            logger.info(f"RPS challenge declined in channel {ctx.channel.id}: {challenger.display_name} -> {ctx.author.display_name}")
            
        except Exception as e:
            logger.error(f"Error declining RPS challenge: {e}")
            await ctx.send("Error declining challenge. Please try again.")
    
    # Handle reactions to challenges
    @bot.event
    async def on_reaction_add(reaction, user):
        try:
            # Ignore bot's own reactions
            if user.bot:
                return
                
            message = reaction.message
            channel = message.channel
            emoji = str(reaction.emoji)
            
            # Check pending challenges
            for (target_id, channel_id), (challenger, challenge_channel, message_id, game_type) in list(pending_rps_challenges.items()):
                if message.id == message_id and user.id == target_id:
                    if channel_id != channel.id:
                        continue
                        
                    # Check if accepting or declining
                    if emoji == ACCEPT_EMOJI:
                        # Remove from pending challenges
                        if (target_id, channel_id) in pending_rps_challenges:
                            del pending_rps_challenges[(target_id, channel_id)]
                            
                        # Delete challenge message
                        try:
                            await message.delete()
                        except discord.errors.NotFound:
                            pass
                            
                        # Start appropriate game type
                        if game_type == BASIC_GAME_TYPE:
                            await start_basic_rps(channel, challenger, user)
                        else:
                            await start_action_rps(channel, challenger, user)
                        
                        return
                        
                    elif emoji == DECLINE_EMOJI:
                        # Remove the challenge 
                        if (target_id, channel_id) in pending_rps_challenges:
                            del pending_rps_challenges[(target_id, channel_id)]
                        
                        # Create decline embed
                        embed = discord.Embed(
                            title="Challenge Declined",
                            description=f"{user.mention} has declined {challenger.mention}'s Rock Paper Scissors challenge.",
                            color=discord.Color.red()
                        )
                        
                        # Edit message
                        try:
                            await message.edit(embed=embed)
                            await message.clear_reactions()
                        except discord.errors.NotFound:
                            pass
                            
                        logger.info(f"RPS challenge declined in channel {channel.id}: {challenger.display_name} -> {user.display_name}")
                        return
                        
        except Exception as e:
            logger.error(f"Error handling RPS reaction: {e}")
    
    # Register all RPS commands with the bot
    return {
        "rps": rps_challenge,
        "rps_action": rps_action_challenge,
        "rps_accept": accept_rps,
        "rps_decline": decline_rps
    }

#---------- Game Starter Functions ----------#

async def start_basic_rps(channel, player1, player2):
    """Start a basic Rock Paper Scissors game."""
    # Create the game instance
    game = BasicRPSGame(player1, player2, channel)
    
    # Store in active games
    if GAME_ID not in active_games:
        active_games[GAME_ID] = {}
    active_games[GAME_ID][channel.id] = game
    
    # Send game start message
    start_message = await channel.send(f"🎮 Rock Paper Scissors started: {player1.mention} vs {player2.mention}")
    
    # Send private prompts to both players using buttons on a public message
    view = StartRPSView(game)
    choice_message = await channel.send(
        f"**{player1.mention}** and **{player2.mention}**, click the button below to make your choice!",
        view=view
    )
    
    # Store the message ID for later deletion
    game.choice_message = choice_message
    
    logger.info(f"Basic RPS game started in channel {channel.id}: {player1.display_name} vs {player2.display_name}")

async def start_action_rps(channel, player1, player2):
    """Start a Rock Paper Scissors Action game."""
    # Create the game instance
    game = ActionRPSGame(player1, player2, channel)
    
    # Store in active games
    if GAME_ID not in active_games:
        active_games[GAME_ID] = {}
    active_games[GAME_ID][channel.id] = game
    
    # Send game start message
    game.start_message = await channel.send(f"🎮 Rock Paper Scissors Action started: {player1.mention} vs {player2.mention}")
    
    # First send action selection messages to both players using buttons on a public message
    view = StartActionRPSView(game)
    action_message = await channel.send(
        f"**{player1.mention}** and **{player2.mention}**, click the button below to choose your action!",
        view=view
    )
    
    # Store the message ID for later deletion
    game.action_message = action_message
    
    logger.info(f"Action RPS game started in channel {channel.id}: {player1.display_name} vs {player2.display_name}")

# Add these new view classes to handle interaction-based prompts

class StartRPSView(discord.ui.View):
    """View with buttons for players to start their turns."""
    def __init__(self, game):
        super().__init__(timeout=180)  # 3 minute timeout
        self.game = game
        
    @discord.ui.button(label="Make Your Choice", style=discord.ButtonStyle.primary)
    async def choose_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button that players click to make their choice."""
        try:
            # Check if this is one of the players
            if interaction.user.id not in [self.game.player1.id, self.game.player2.id]:
                await interaction.response.send_message("You are not part of this game!", ephemeral=True)
                return
                
            # Check if they've already made a choice
            if self.game.choices[interaction.user.id] is not None:
                await interaction.response.send_message("You've already made your choice!", ephemeral=True)
                return
                
            # Create the RPS view for this player
            async def on_choice_made(choice_interaction, choice):
                # Check if both players have now chosen
                if self.game.is_complete():
                    # Delete the choice message if both players have made their choices
                    if hasattr(self.game, 'choice_message') and self.game.choice_message:
                        try:
                            await self.game.choice_message.delete()
                            self.game.choice_message = None
                        except:
                            logger.warning("Failed to delete choice message")
                    
                    # Delete the action message in action RPS game
                    if isinstance(self.game, ActionRPSGame) and hasattr(self.game, 'rps_message') and self.game.rps_message:
                        try:
                            await self.game.rps_message.delete()
                            self.game.rps_message = None
                        except:
                            logger.warning("Failed to delete RPS message")
                            
                    # Process the result, determining which type of game this is
                    if isinstance(self.game, ActionRPSGame):
                        await process_action_rps_result(self.game)
                    else:
                        await process_basic_rps_result(self.game)
                
            view = RPSView(self.game, interaction.user.id, on_choice_made)
            
            # Send as ephemeral response to the interaction
            try:
                await interaction.response.send_message(
                    f"Choose Rock, Paper, or Scissors:", 
                    view=view, 
                    ephemeral=True
                )
            except (discord.errors.NotFound, discord.errors.HTTPException, aiohttp.ClientOSError) as e:
                # If interaction expired or network error, send a new message to the channel
                logger.warning(f"Interaction response failed: {str(e)}. Sending fallback message.")
                player = interaction.user
                await interaction.channel.send(
                    f"{player.mention}, your interaction expired. Please click the button again to make your choice.",
                    delete_after=10
                )
        except Exception as e:
            logger.error(f"Error in RPS choose_button: {e}\n{traceback.format_exc()}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred. Please try again.", 
                        ephemeral=True
                    )
            except:
                pass

class StartActionRPSView(discord.ui.View):
    """View with buttons for players to start their action selection."""
    def __init__(self, game):
        super().__init__(timeout=180)  # 3 minute timeout
        self.game = game
        
    @discord.ui.button(label="Choose Your Action", style=discord.ButtonStyle.primary)
    async def action_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button that players click to choose their action."""
        try:
            # Check if this is one of the players
            if interaction.user.id not in [self.game.player1.id, self.game.player2.id]:
                await interaction.response.send_message("You are not part of this game!", ephemeral=True)
                return
                
            # Check if they've already selected an action
            if self.game.actions[interaction.user.id] is not None:
                await interaction.response.send_message("You've already selected an action!", ephemeral=True)
                return
                
            # Create the action selection view for this player
            async def on_action_selected(action_interaction, action):
                # Check if both players have selected their actions
                if self.game.are_actions_selected():
                    # Delete the previous action message since both have chosen
                    if hasattr(self.game, 'action_message') and self.game.action_message:
                        try:
                            await self.game.action_message.delete()
                            self.game.action_message = None
                        except:
                            logger.warning("Failed to delete action message")
                    
                    # Send RPS choice buttons to both players
                    view = StartRPSView(self.game)
                    rps_message = await interaction.channel.send(
                        f"Both players have selected their actions! **{self.game.player1.mention}** and **{self.game.player2.mention}**, click the button below to make your Rock, Paper, Scissors choice!",
                        view=view
                    )
                    
                    # Store the message for later deletion
                    self.game.rps_message = rps_message
            
            view = ActionSelectView(self.game, interaction.user.id, on_action_selected)
            
            # Send as ephemeral response to the interaction
            try:
                await interaction.response.send_message(
                    f"Choose what action you want to perform if you win:", 
                    view=view, 
                    ephemeral=True
                )
            except (discord.errors.NotFound, discord.errors.HTTPException, aiohttp.ClientOSError) as e:
                # If interaction expired or network error, send a new message to the channel
                logger.warning(f"Interaction response failed: {str(e)}. Sending fallback message.")
                player = interaction.user
                await interaction.channel.send(
                    f"{player.mention}, your interaction expired. Please click the button again to choose your action.",
                    delete_after=10
                )
        except Exception as e:
            logger.error(f"Error in RPS action_button: {e}\n{traceback.format_exc()}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred. Please try again.", 
                        ephemeral=True
                    )
            except:
                pass

#---------- Game Resolution Functions ----------#

async def process_basic_rps_result(game):
    """Process and display results for a basic RPS game."""
    # Get the result
    result = game.determine_result()
    
    # Create embed for result
    embed = discord.Embed(
        title="Rock Paper Scissors Result",
        description=result["message"],
        color=discord.Color.blue()
    )
    
    # Add player choices
    embed.add_field(
        name=f"{game.player1.display_name}'s Choice",
        value=f"{result['player1']['emoji']} {result['player1']['choice'].capitalize()}",
        inline=True
    )
    
    embed.add_field(
        name=f"{game.player2.display_name}'s Choice",
        value=f"{result['player2']['emoji']} {result['player2']['choice'].capitalize()}",
        inline=True
    )
    
    # Create view with play again button
    view = discord.ui.View()
    
    async def play_again_callback(interaction):
        # Check if user is one of the players
        if interaction.user.id not in [game.player1.id, game.player2.id]:
            await interaction.response.send_message(
                "Only the original players can start a new game.",
                ephemeral=True
            )
            return
            
        # Reset the game
        game.reset()
        
        # Remove from active games to avoid conflicts
        if game.channel.id in active_games.get(GAME_ID, {}):
            del active_games[GAME_ID][game.channel.id]
            
        # Try to delete the old result message
        if hasattr(game, 'result_message') and game.result_message:
            try:
                await game.result_message.delete()
            except:
                pass
                
        # Start a new game
        await start_basic_rps(game.channel, game.player1, game.player2)
        
        # Disable the button
        for child in view.children:
            child.disabled = True
        await interaction.message.edit(view=view)
    
    # Add play again button
    view.add_item(PlayAgainButton(play_again_callback))
    
    # Delete any remaining game messages
    for msg_attr in ['choice_message', 'start_message']:
        if hasattr(game, msg_attr) and getattr(game, msg_attr):
            try:
                await getattr(game, msg_attr).delete()
                setattr(game, msg_attr, None)
            except:
                pass
    
    # Send the result message
    game.result_message = await game.channel.send(embed=embed, view=view)
    
    # Remove from active games
    if game.channel.id in active_games.get(GAME_ID, {}):
        del active_games[GAME_ID][game.channel.id]
    
    logger.info(f"Basic RPS game ended in channel {game.channel.id}")

async def process_action_rps_result(game):
    """Process and display results for an action RPS game."""
    # Get the result
    result = game.determine_action_result()
    
    # Create embed for initial result
    embed = discord.Embed(
        title="Rock Paper Scissors Action Result",
        description=result["message"],
        color=discord.Color.blue()
    )
    
    # Add player choices
    embed.add_field(
        name=f"{game.player1.display_name}'s Choice",
        value=f"{result['player1']['emoji']} {result['player1']['choice'].capitalize()}",
        inline=True
    )
    
    embed.add_field(
        name=f"{game.player2.display_name}'s Choice",
        value=f"{result['player2']['emoji']} {result['player2']['choice'].capitalize()}",
        inline=True
    )
    
    # Delete any remaining game messages to avoid clutter
    for msg_attr in ['choice_message', 'action_message', 'rps_message', 'start_message']:
        if hasattr(game, msg_attr) and getattr(game, msg_attr):
            try:
                await getattr(game, msg_attr).delete()
                setattr(game, msg_attr, None)
            except:
                pass
    
    # Send the initial result message
    game.result_message = await game.channel.send(embed=embed)
    
    # If there's a winner, fetch and display the action GIF
    if game.winner and result.get("action"):
        # Get the action and participants
        action = result["action"]
        actor = result["actor"]
        target = result["target"]
        
        # Get a random GIF for this action
        gif_url = await game.fetch_gif(action)
        
        # Format the action message
        action_text = f"**{actor.display_name}** {action}s **{target.display_name}**!"
        
        # Create the action embed
        action_embed = discord.Embed(
            title="Action Result",
            description=action_text,
            color=discord.Color.gold()
        )
        
        # Add the GIF if found
        if gif_url:
            action_embed.set_image(url=gif_url)
        
        # Create view with play again button
        view = discord.ui.View()
        
        async def play_again_callback(interaction):
            # Check if user is one of the players
            if interaction.user.id not in [game.player1.id, game.player2.id]:
                await interaction.response.send_message(
                    "Only the original players can start a new game.",
                    ephemeral=True
                )
                return
                
            # Reset the game
            game.reset()
            
            # Remove from active games to avoid conflicts
            if game.channel.id in active_games.get(GAME_ID, {}):
                del active_games[GAME_ID][game.channel.id]
            
            # Try to delete the old result messages
            if hasattr(game, 'result_message') and game.result_message:
                try:
                    await game.result_message.delete()
                except:
                    pass
                    
            # Start a new game
            await start_action_rps(game.channel, game.player1, game.player2)
            
            # Disable the button
            for child in view.children:
                child.disabled = True
            await interaction.message.edit(view=view)
        
        # Add play again button
        view.add_item(PlayAgainButton(play_again_callback))
        
        # Send the action result with Play Again button
        await game.channel.send(embed=action_embed, view=view)
    else:
        # No winner, just a tie - add Play Again button to the embed
        view = discord.ui.View()
        
        async def play_again_callback(interaction):
            # Check if user is one of the players
            if interaction.user.id not in [game.player1.id, game.player2.id]:
                await interaction.response.send_message(
                    "Only the original players can start a new game.",
                    ephemeral=True
                )
                return
                
            # Reset the game
            game.reset()
            
            # Remove from active games to avoid conflicts
            if game.channel.id in active_games.get(GAME_ID, {}):
                del active_games[GAME_ID][game.channel.id]
                
            # Try to delete the old result message
            if hasattr(game, 'result_message') and game.result_message:
                try:
                    await game.result_message.delete()
                except:
                    pass
                    
            # Start a new game
            await start_action_rps(game.channel, game.player1, game.player2)
            
            # Disable the button
            for child in view.children:
                child.disabled = True
            await interaction.message.edit(view=view)
        
        # Add play again button
        view.add_item(PlayAgainButton(play_again_callback))
        
        # Add the Play Again button to the message
        await game.channel.send("It's a tie! No action performed.", view=view)
    
    # Remove from active games
    if game.channel.id in active_games.get(GAME_ID, {}):
        del active_games[GAME_ID][game.channel.id]
    
    logger.info(f"Action RPS game ended in channel {game.channel.id}")

# Setup function for bot.py
async def setup_rps_command(bot):
    """Setup function to maintain compatibility with bot.py imports."""
    return await setup_rps_commands(bot) 