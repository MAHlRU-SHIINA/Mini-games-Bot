"""
UI components for the Discord Rock Paper Scissors Games (ID: 1003).
"""
import discord
import logging
import traceback
import aiohttp
from typing import List, Dict, Optional, Callable

from games.game_1003_rps.game_1003 import RPS_CHOICES, RPS_EMOJIS, ACTION_OPTIONS

logger = logging.getLogger("discord_bot")

class RPSButton(discord.ui.Button):
    """Button for Rock, Paper, or Scissors selection."""
    def __init__(self, choice: str, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=choice.capitalize(),
            emoji=RPS_EMOJIS[choice],
            row=row
        )
        self.choice = choice
    
    async def callback(self, interaction: discord.Interaction):
        try:
            view = self.view
            if hasattr(view, 'on_choice_select'):
                await view.on_choice_select(interaction, self.choice)
        except Exception as e:
            logger.error(f"Error in RPSButton callback: {e}\n{traceback.format_exc()}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
                else:
                    await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
            except:
                # If all else fails, just log it
                logger.error("Failed to send error message to user")


class RPSView(discord.ui.View):
    """View with Rock, Paper, Scissors buttons."""
    def __init__(self, game, player_id: int, on_choice_made: Callable = None):
        super().__init__(timeout=120)  # 2 minute timeout
        self.game = game
        self.player_id = player_id
        self.on_choice_made = on_choice_made
        
        # Add RPS buttons
        for i, choice in enumerate(RPS_CHOICES):
            self.add_item(RPSButton(choice, row=0))
    
    async def on_choice_select(self, interaction: discord.Interaction, choice: str):
        """Handle when a player selects rock, paper, or scissors."""
        try:
            # Verify this is the correct player
            if interaction.user.id != self.player_id:
                await interaction.response.send_message("This is not your choice to make!", ephemeral=True)
                return
                
            # Check if player already made a choice
            if self.game.choices[self.player_id] is not None:
                await interaction.response.send_message("You've already made your choice!", ephemeral=True)
                return
                
            # Record the choice
            self.game.make_choice(self.player_id, choice)
            
            # Disable all buttons
            for child in self.children:
                child.disabled = True
            
            # Update the message to show selection is done
            try:
                await interaction.response.edit_message(
                    content=f"You chose {RPS_EMOJIS[choice]} **{choice.capitalize()}**! Waiting for the other player...",
                    view=self
                )
            except (discord.errors.NotFound, discord.errors.HTTPException, aiohttp.ClientOSError) as e:
                # If interaction expired or network error, send a new message to the channel
                logger.warning(f"Interaction response failed: {str(e)}. Sending fallback message.")
                await self.game.channel.send(
                    f"{interaction.user.mention} chose {RPS_EMOJIS[choice]} **{choice.capitalize()}**!",
                    delete_after=5
                )
            except discord.errors.InteractionResponded:
                # In case the interaction has already been responded to
                try:
                    await interaction.followup.send(
                        content=f"You chose {RPS_EMOJIS[choice]} **{choice.capitalize()}**! Waiting for the other player...",
                        ephemeral=True
                    )
                except:
                    pass
            
            # Call the callback if provided
            if self.on_choice_made:
                try:
                    await self.on_choice_made(interaction, choice)
                except Exception as e:
                    logger.error(f"Error in on_choice_made callback: {e}\n{traceback.format_exc()}")
        
        except Exception as e:
            logger.error(f"Error in on_choice_select: {e}\n{traceback.format_exc()}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred processing your choice. Please try again.", 
                        ephemeral=True
                    )
            except:
                pass
    
    async def on_timeout(self):
        """Handle view timeout."""
        # Make all buttons disabled
        for child in self.children:
            child.disabled = True
        
        # We're not saving message references now, so just log
        logger.info(f"RPSView for player {self.player_id} timed out")


class ActionSelectView(discord.ui.View):
    """View for selecting an action in RPS Action game."""
    def __init__(self, game, player_id: int, on_action_selected: Callable = None):
        super().__init__(timeout=120)  # 2 minute timeout
        self.game = game
        self.player_id = player_id
        self.on_action_selected = on_action_selected
        
        # Add action select dropdown
        self.add_item(ActionSelect(game, player_id))
    
    async def action_selected(self, interaction: discord.Interaction, action: str):
        """Called when an action is selected from the dropdown."""
        try:
            # Disable all items
            for child in self.children:
                child.disabled = True
            
            # Update message
            try:
                await interaction.response.edit_message(
                    content=f"You selected the action: **{action}**! Now choose Rock, Paper, or Scissors to determine if you'll use it.",
                    view=self
                )
            except (discord.errors.NotFound, discord.errors.HTTPException, aiohttp.ClientOSError) as e:
                # If interaction expired or network error, send a new message to the channel
                logger.warning(f"Interaction response failed: {str(e)}. Sending fallback message.")
                await self.game.channel.send(
                    f"{interaction.user.mention} selected their action!",
                    delete_after=5
                )
            except discord.errors.InteractionResponded:
                # In case the interaction has already been responded to
                try:
                    await interaction.followup.send(
                        content=f"You selected the action: **{action}**! Now choose Rock, Paper, or Scissors to determine if you'll use it.",
                        ephemeral=True
                    )
                except:
                    pass
            
            # Call the callback if provided
            if self.on_action_selected:
                try:
                    await self.on_action_selected(interaction, action)
                except Exception as e:
                    logger.error(f"Error in on_action_selected callback: {e}\n{traceback.format_exc()}")
        
        except Exception as e:
            logger.error(f"Error in action_selected: {e}\n{traceback.format_exc()}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred processing your action selection. Please try again.", 
                        ephemeral=True
                    )
            except:
                pass
            
    async def on_timeout(self):
        """Handle view timeout."""
        # Make all components disabled
        for child in self.children:
            child.disabled = True
        
        # We're not saving message references now, so just log
        logger.info(f"ActionSelectView for player {self.player_id} timed out")


class ActionSelect(discord.ui.Select):
    """Dropdown for selecting an action in RPS Action game."""
    def __init__(self, game, player_id: int):
        options = [
            discord.SelectOption(label=action.capitalize(), value=action, description=f"Choose to {action} your opponent")
            for action in ACTION_OPTIONS
        ]
        
        super().__init__(
            placeholder="Choose your action...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.game = game
        self.player_id = player_id
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # Verify this is the correct player
            if interaction.user.id != self.player_id:
                await interaction.response.send_message("This is not your choice to make!", ephemeral=True)
                return
                
            # Get the selected action
            action = self.values[0]
            
            # Record the action in the game
            self.game.set_player_action(self.player_id, action)
            
            # Let the view know an action was selected
            if hasattr(self.view, 'action_selected'):
                await self.view.action_selected(interaction, action)
        except Exception as e:
            logger.error(f"Error in ActionSelect callback: {e}\n{traceback.format_exc()}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
                else:
                    await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
            except:
                # If all else fails, just log it
                logger.error("Failed to send error message to user")


class PlayAgainButton(discord.ui.Button):
    """Button to play again after a game ends."""
    def __init__(self, callback: Callable):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Play Again",
            emoji="🔄"
        )
        self.play_again_callback = callback
    
    async def callback(self, interaction: discord.Interaction):
        """Handle when a player clicks play again."""
        try:
            # Call the provided callback
            if self.play_again_callback:
                await self.play_again_callback(interaction)
        except Exception as e:
            logger.error(f"Error in PlayAgainButton callback: {e}\n{traceback.format_exc()}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
                else:
                    await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
            except:
                # If all else fails, just log it
                logger.error("Failed to send error message to user") 