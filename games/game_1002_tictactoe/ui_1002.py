"""
UI components for the Discord Tic Tac Toe Game (ID: 1002).
"""
import discord
import logging
import traceback
import time

from common.config import EPHEMERAL_MESSAGE_DURATION
from games.game_1002_tictactoe.game_1002 import TicTacToeGame
from common.utils.game_utils import active_games

logger = logging.getLogger("discord_bot")

class PlayAgainButton(discord.ui.Button):
    """Button to start a new Tic Tac Toe game with the same players."""
    def __init__(self, player1, player2):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Play Again",
            emoji="🔄"
        )
        self.player1 = player1
        self.player2 = player2
    
    async def callback(self, interaction):
        try:
            # Only allow the original players to press the button
            if interaction.user.id not in [self.player1.id, self.player2.id]:
                await interaction.response.send_message(
                    "Only the original players can start a new game.",
                    ephemeral=True
                )
                return
            
            # Defer response to give time for processing
            await interaction.response.defer()
            
            # Create a new game with the same players
            challenger = self.player1 if interaction.user.id == self.player2.id else self.player2
            
            # Create the game instance
            game = TicTacToeGame(interaction.user, challenger, interaction.channel)
            
            # Make sure the active_games dictionary is initialized for this game ID
            game_id = "1002"
            if game_id not in active_games:
                active_games[game_id] = {}
                
            # Store the game
            active_games[game_id][interaction.channel.id] = game
            
            # Disable this button to prevent multiple clicks
            self.disabled = True
            await interaction.message.edit(view=self.view)
            
            # Send initial informational message
            await interaction.channel.send(f"🎮 Tic Tac Toe Game started: {interaction.user.mention} vs {challenger.mention}")

            # Create game view
            view = TicTacToeView(game)
            
            # Send the main game message with embed and view
            initial_embed = game.get_board_embed()
            try:
                game_message = await interaction.channel.send(embed=initial_embed, view=view)
                game.board_message = game_message  # For updates
                game.board_message_id = game_message.id  # For embed updates by game logic
            except Exception as e:
                logger.error(f"Error sending initial game message with view: {e}")
                await interaction.channel.send("Error displaying the game. Please try starting a new game.")
                # Clean up active game if setup failed critically
                if game_id in active_games and interaction.channel.id in active_games[game_id]:
                    del active_games[game_id][interaction.channel.id]
                return
            
            logger.info(f"New Tic Tac Toe game started via Play Again in channel {interaction.channel.id}: {interaction.user.display_name} vs {challenger.display_name}")
            
        except Exception as e:
            logger.error(f"Error in PlayAgainButton callback: {e}\n{traceback.format_exc()}")
            await interaction.followup.send(f"Error starting new game: {type(e).__name__}. Please use the /tictactoe command instead.")

class TicTacToeButton(discord.ui.Button):
    """A button for a Tic Tac Toe square."""
    def __init__(self, row, col):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="\u200B",  # Zero-width space as default label
            row=row
        )
        self.row_idx = row
        self.col_idx = col
    
    async def callback(self, interaction):
        view = self.view
        game = view.game # Get game from view
        
        try:
            # Defer immediately. If ephemeral, followup messages will also be ephemeral.
            # If you intend to update the public game message, consider deferring without ephemeral thinking.
            await interaction.response.defer(ephemeral=True) 

            # Ensure this view is still active
            if view.is_finished():
                await interaction.followup.send(
                    "This game interface has expired. Please use a newer one."
                )
                return
            
            # Make sure it's the current player's turn
            if interaction.user.id != game.current_player.id:
                await interaction.followup.send(
                    "It's not your turn!",
                    ephemeral=True # Explicitly set ephemeral
                )
                return
            
            # Make the move - directly pass row and col from button
            success, result = game.make_move(self.row_idx, self.col_idx, interaction.user)
            
            if not success:
                await interaction.followup.send(
                    result
                )
                return
            
            # If move is successful, update the public game message (board and buttons)
            # Ensure game.board_message exists and is the one to edit.
            if game.board_message:
                await view.update_view()  # This should call game.board_message.edit(view=view)
                await game.update_board(result) # Pass the result message to update_board
            else:
                logger.error("game.board_message is not set, cannot update Tic Tac Toe UI after move.")
                await interaction.followup.send("Error updating game display. Board message not found.")

            # Check if the game ended after this move
            if game.game_over:
                # Create play again button and view
                play_again_view = discord.ui.View()
                play_again_view.add_item(PlayAgainButton(game.player1, game.player2))
                
                # Determine game over message based on result
                if "wins" in result:
                    game_over_message = f"🏆 **Game Over!** {game.winner.mention} wins!"
                else: # draw
                    game_over_message = f"🤝 **Game Over!** It's a tie!"
                
                # Send the play again message
                await interaction.channel.send(
                    content=game_over_message,
                    view=play_again_view
                )
                
                # Stop the view since the game is over
                view.stop()

            # No explicit followup needed here if the original message is edited and defer was ephemeral.
            # If defer was not ephemeral, and you want to confirm the interaction, 
            # a followup might be desired, or ensure edit_message handles it.
            
        except discord.errors.NotFound:
            logger.warning(f"Interaction or message not found during TicTacToeButton callback. User: {interaction.user.id}")
            # No response possible if interaction is gone
        except discord.errors.HTTPException as http_err:
            logger.error(f"HTTPException in button callback: {http_err}\n{traceback.format_exc()}")
            # Try to send a followup if interaction not fully dead
            if interaction.response.is_done():
                try:
                    await interaction.followup.send(f"A network error occurred: {http_err.status}. Please try again.", ephemeral=True)
                except:
                    pass # Failed to send followup
            else:
                # This case should ideally not happen if we deferred.
                pass 
        except Exception as e:
            error_msg = f"Error in button callback: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            
            # Generic error followup
            if interaction.response.is_done():
                try:
                    await interaction.followup.send(
                        f"Error processing button: {type(e).__name__}. Please try again.", 
                        ephemeral=True
                    )
                except:
                    pass # Failed to send followup
            else:
                # This case should ideally not happen if we deferred.
                pass

class TicTacToeView(discord.ui.View):
    """View that displays the Tic Tac Toe game buttons."""
    def __init__(self, game):
        super().__init__(timeout=None)  # No timeout
        self.game = game
        
        try:
            # Add buttons for each position
            self._add_buttons()
        except Exception as e:
            error_msg = f"Error creating game view: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
    
    def _add_buttons(self):
        """Add the 3x3 grid of buttons."""
        # Clear any existing buttons
        self.clear_items()
        
        # Add buttons for each position
        for row in range(3):
            for col in range(3):
                button = TicTacToeButton(row, col)
                
                # Set button text based on game state
                cell = self.game.board[row][col]
                if cell is not None:
                    button.label = cell # Cell content is now ❌ or ⭕
                    button.disabled = True
                    # Set button color based on symbol
                    if cell == self.game.symbols[self.game.player1.id]: # Check against player1's symbol (❌)
                        button.style = discord.ButtonStyle.danger
                    elif cell == self.game.symbols[self.game.player2.id]: # Check against player2's symbol (⭕)
                        button.style = discord.ButtonStyle.success
                    else: # Should not happen if cell is not None and symbols are set
                        button.style = discord.ButtonStyle.secondary 
                # If cell is None, label remains "\u200B" (zero-width space)
                # and style remains secondary (default for empty)
                
                self.add_item(button)
        
        # If game is over, disable all buttons
        if self.game.game_over:
            for button in self.children:
                button.disabled = True
    
    async def update_view(self):
        """Update the buttons based on current game state."""
        # Update buttons
        self._add_buttons()
        
        # Update the message with the view
        if self.game.board_message:
            try:
                await self.game.board_message.edit(view=self)
            except Exception as e:
                logger.error(f"Error updating view: {e}") 