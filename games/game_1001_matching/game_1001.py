"""
Game logic for the Discord Emoji Memory Match Game (ID: 1001).
"""
import random
import discord
import asyncio
import logging
import traceback
import time

# Import from new folder structure
from common.config import ROWS, COLUMNS, EMOJI_BACK, REVEAL_DELAY_SECONDS, EMOJI_CATEGORIES
from common.database import database
from common.utils.game_utils import update_database_with_game_results

logger = logging.getLogger("discord_bot")

GAME_ID = "1001" # Define Game ID for database logging

class EmojiCard:
    """Represents a single emoji card in the game."""
    def __init__(self, emoji, position, is_joker=False):
        self.emoji = emoji
        self.position = position  # (row, col) tuple
        self.is_matched = False
        self.is_revealed = False
        self.is_joker = is_joker
    
    def get_display(self, force_reveal=False):
        """Returns the emoji to display based on state."""
        if self.is_matched or self.is_revealed or force_reveal:
            return self.emoji
        else:
            return EMOJI_BACK

class MemoryGame:
    """Main game class that handles the Memory Match game logic and state."""
    def __init__(self, player1, player2, channel, category, rows=None, columns=None):
        self.player1 = player1
        self.player2 = player2
        self.channel = channel
        self.category = category
        # Randomly select the first player
        self.current_player = random.choice([player1, player2])
        self.board = []
        self.selected_this_turn = [] # List of (row, col) for current turn's selections
        self.scores = {player1.id: 0, player2.id: 0}
        self.matched_pairs_count = 0
        self.game_over = False
        self.winner = None
        self.board_message_id = None # To store the ID of the game board message
        self.last_activity_time = time.time() # For AFK tracking

        # Use provided rows/columns, or default from config
        self.rows = rows if rows is not None else ROWS
        self.columns = columns if columns is not None else COLUMNS

        self.num_cards = self.rows * self.columns
        self.include_joker = (self.num_cards % 2 != 0)
        self.pairs_to_find = (self.num_cards - (1 if self.include_joker else 0)) // 2
        
        # Specific rules for 5x5 grid
        self.is_5x5_grid = (self.rows == 5 and self.columns == 5)
        self.is_4x5_grid = (self.rows == 5 and self.columns == 4)
        self.target_score_to_win_4x5 = 6 if self.is_4x5_grid else None
        self.target_score_to_win_5x5 = 7 if self.is_5x5_grid else None

        self._initialize_board()
        logger.info(f"Memory Match game ({self.rows}x{self.columns}) created between {player1.display_name} and {player2.display_name} in category {category}")
    
    def _initialize_board(self):
        """Generates the game board with shuffled emoji pairs."""
        try:
            # Validate the category
            if self.category not in EMOJI_CATEGORIES:
                logger.error(f"Invalid emoji category: {self.category}")
                raise ValueError(f"Invalid category: {self.category}")
            
            available_emojis = EMOJI_CATEGORIES[self.category]
            
            # Ensure we have enough unique emojis
            if len(available_emojis) < self.pairs_to_find:
                logger.error(f"Not enough unique emojis in category '{self.category}' for a {self.rows}x{self.columns} grid needing {self.pairs_to_find} pairs.")
                # Fallback or raise error - for now, this might lead to issues if not handled upstream
                # This should ideally be checked before game creation if possible.
                # For now, let the game proceed, it might repeat emojis if too few.
                pass # Or: raise ValueError("Not enough unique emojis")

            # Take required number of pairs
            emojis_for_game = random.sample(available_emojis, self.pairs_to_find) * 2
            
            # Add joker card if needed
            if self.include_joker:
                joker_emoji = "🃏"
                emojis_for_game.append(joker_emoji)
            
            random.shuffle(emojis_for_game)
            
            # Distribute emojis onto the board
            # The board is a list of lists (rows containing columns)
            self.board = [[None for _ in range(self.columns)] for _ in range(self.rows)]
            temp_emojis = list(emojis_for_game) # Create a mutable copy
            random.shuffle(temp_emojis)
            
            card_idx = 0
            for r in range(self.rows):
                for c in range(self.columns):
                    if card_idx < len(temp_emojis):
                        self.board[r][c] = EmojiCard(temp_emojis[card_idx], (r, c))
                        card_idx += 1
                    else: # Should not happen if num_cards matches len(temp_emojis)
                        self.board[r][c] = None 
            
            logger.info(f"Created board with {self.rows}x{self.columns} grid, {len(emojis_for_game)} emoji pairs, and {('1 joker card' if self.include_joker else 'no joker card')}")
        except Exception as e:
            logger.error(f"Error in _initialize_board: {e}\n{traceback.format_exc()}")
            raise
    
    def get_card(self, row, col):
        """Gets the card at the specified position."""
        try:
            if 0 <= row < self.rows and 0 <= col < self.columns:
                return self.board[row][col]
            logger.warning(f"Attempted to get card at invalid position: ({row},{col})")
            return None
        except Exception as e:
            logger.error(f"Error in get_card at ({row},{col}): {e}")
            return None
    
    def get_board_embed(self, game_status_message=""):
        """Get an embed displaying the current game board."""
        # Create a Discord embed with the current board state
        embed = discord.Embed(
            title=f"Memory Match - {self.category.capitalize()}", 
            color=discord.Color.blue()
        )
        
        # Set the board display
        board_display = self._get_board_display()
        embed.description = board_display
        
        # Add player scores
        score1 = self.scores.get(self.player1.id, 0)
        score2 = self.scores.get(self.player2.id, 0)
        
        embed.add_field(
            name="Scores",
            value=f"{self.player1.display_name}: {score1}\n{self.player2.display_name}: {score2}",
            inline=True
        )
        
        # Add current turn
        embed.add_field(
            name="Current Turn",
            value=f"@{self.current_player.display_name}",
            inline=True
        )
        
        # Add game over message if relevant
        if self.game_over:
            if self.winner:
                result = f"🏆 {self.winner.display_name} wins!"
            else:
                result = "🤝 It's a tie!"
            
            embed.add_field(
                name="Result",
                value=result,
                inline=True
            )
        
        if game_status_message:
            embed.set_footer(text=game_status_message)
        
        return embed
    
    async def update_board(self, status_message=None, reveal_all=False):
        """Updates the board message with the current game state."""
        try:
            embed = self.get_board_embed(status_message)
            
            # If we have a direct message object reference, use it first
            if hasattr(self, 'board_message') and self.board_message:
                try:
                    await self.board_message.edit(embed=embed)
                    logger.debug("Board message updated successfully (using board_message reference)")
                    return
                except Exception as e:
                    logger.error(f"Error updating board_message: {e}")
                    # Fall back to board_message_id method
            
            # If we have a message ID but no direct object, try to fetch and update
            if self.board_message_id:
                try:
                    channel = self.channel
                    message = await channel.fetch_message(self.board_message_id)
                    await message.edit(embed=embed)
                    # Update the direct reference too
                    self.board_message = message
                    logger.debug("Board message updated successfully (using board_message_id)")
                except discord.NotFound:
                    logger.warning("Board message not found, creating new one")
                    message = await self.channel.send(embed=embed)
                    self.board_message_id = message.id
                    self.board_message = message
                except Exception as e:
                    logger.error(f"Error updating board message: {e}\n{traceback.format_exc()}")
                    # Try to send a new message if update fails
                    try:
                        message = await self.channel.send(embed=embed)
                        self.board_message_id = message.id
                        self.board_message = message
                    except Exception as e2:
                        logger.error(f"Failed to create new board message after update error: {e2}")
            else:
                try:
                    message = await self.channel.send(embed=embed)
                    self.board_message_id = message.id
                    self.board_message = message
                    logger.debug("New board message created")
                except Exception as e:
                    logger.error(f"Error creating board message: {e}\n{traceback.format_exc()}")
                    raise
        except Exception as e:
            logger.error(f"Error in update_board: {e}\n{traceback.format_exc()}")
    
    async def make_move(self, row1, col1, row2, col2, player):
        """Process a player's move selecting two cards.
        
        Returns:
            Tuple of (success: bool, message: str, game_ended: bool)
            message can be: "Match", "No Match", "Joker", "Game Over - Win", "Game Over - Tie", or an error message.
        """
        try:
            # Initialize game_just_ended_by_this_move
            game_just_ended_by_this_move = False

            # Validate player's turn
            if player.id != self.current_player.id:
                logger.warning(f"Player {player.display_name} tried to move out of turn")
                return False, "It's not your turn!", False
            
            # Validate card positions
            card1 = self.get_card(row1, col1)
            card2 = self.get_card(row2, col2)
            
            if not card1 or not card2:
                logger.warning(f"Invalid card selection: ({row1},{col1}), ({row2},{col2})")
                return False, "Invalid card selection.", False
            
            if card1.is_matched or card2.is_matched:
                # This check should ideally be caught by UI, but as a safeguard
                return False, "One or both cards already matched.", False
                
            if card1 == card2:
                # This check should ideally be caught by UI
                return False, "You selected the same card twice.", False

            logger.info(f"{player.display_name} evaluating pair: ({row1+1},{col1+1}) and ({row2+1},{col2+1})")
            
            # Cards are assumed to be already revealed by the UI calling this method.
            # No need to set card1.is_revealed or card2.is_revealed here.
            # No need to call self.update_board() here just for revealing.

            result_message_key = ""
            current_move_matched = False

            # Check for Joker card
            if self.include_joker and (card1.emoji == "🃏" or card2.emoji == "🃏"):
                joker_card = card1 if card1.emoji == "🃏" else card2
                other_card = card2 if card1.emoji == "🃏" else card1
                
                joker_card.is_matched = True
                # other_card remains as is, not matched by the joker
                self.scores[player.id] += 1 
                self.matched_pairs_count += 0.5 # Joker counts as half a pair for completion tracking
                
                result_message_key = "Joker"
                current_move_matched = True # Joker find counts as a successful move for turn continuation
                logger.info(f"{player.display_name} found the joker card! Score: {self.scores[player.id]}")
            
            # Check for a normal match
            elif card1.emoji == card2.emoji:
                card1.is_matched = True
                card2.is_matched = True
                self.scores[player.id] += 1
                self.matched_pairs_count += 1
                result_message_key = "Match"
                current_move_matched = True
                logger.info(f"{player.display_name} found a match! Score: {self.scores[player.id]}")
            else:
                # No match
                logger.info(f"{player.display_name} found no match.")
                result_message_key = "No Match"
                
                # Explicitly set the cards to not revealed in the game state
                # This ensures the board will hide them properly even if UI has issues
                card1.is_revealed = False
                card2.is_revealed = False
                
                # Switch turns - explicitly switch here instead of delegating it
                # This ensures it always happens even if there are errors elsewhere
                old_player = self.current_player
                self._switch_turn()
                logger.info(f"Turn explicitly switched from {old_player.display_name} to {self.current_player.display_name}")
                
                self.last_activity_time = time.time()
                game_just_ended_by_this_move = False

            # Check for game end conditions (applies after joker, match, or no match)
            # 5x5 grid win conditions
            if self.is_5x5_grid:
                if self.scores[player.id] >= self.target_score_to_win_5x5:
                    self.winner = player
                    result_message_key = f"Game Over - {player.display_name} wins by reaching {self.target_score_to_win_5x5} pairs!"
                    game_just_ended_by_this_move = True
                elif self.matched_pairs_count >= self.pairs_to_find: # All pairs found
                    # Determine winner based on scores
                    score1 = self.scores[self.player1.id]
                    score2 = self.scores[self.player2.id]
                    if score1 > score2:
                        self.winner = self.player1
                        result_message_key = f"Game Over - {self.player1.display_name} wins!"
                    elif score2 > score1:
                        self.winner = self.player2
                        result_message_key = f"Game Over - {self.player2.display_name} wins!"
                    else: # Tie
                        self.winner = None
                        result_message_key = "Game Over - It's a Tie!"
                    game_just_ended_by_this_move = True
            # 4x5 grid win conditions
            elif self.is_4x5_grid:
                if self.scores[player.id] >= self.target_score_to_win_4x5:
                    self.winner = player
                    result_message_key = f"Game Over - {player.display_name} wins by reaching {self.target_score_to_win_4x5} pairs!"
                    game_just_ended_by_this_move = True
                elif self.matched_pairs_count >= self.pairs_to_find: # All 10 pairs found (or 9.5 with joker)
                    # Recalculate winner based on scores as target wasn't hit directly by this player
                    score1 = self.scores[self.player1.id]
                    score2 = self.scores[self.player2.id]
                    if score1 == 5 and score2 == 5: # Specific 5-5 tie for 4x5
                        result_message_key = "Game Over - It's a 5-5 Tie!"
                        self.winner = None
                    elif score1 > score2:
                        self.winner = self.player1
                        result_message_key = f"Game Over - {self.player1.display_name} wins!"
                    elif score2 > score1:
                        self.winner = self.player2
                        result_message_key = f"Game Over - {self.player2.display_name} wins!"
                    else: # Should be caught by 5-5 tie, but as a fallback for general tie
                        self.winner = None
                        result_message_key = "Game Over - It's a Tie!"
                    game_just_ended_by_this_move = True
            
            # Default win condition for other grid sizes
            elif not game_just_ended_by_this_move and self.matched_pairs_count >= self.pairs_to_find:
                self.winner = self.get_winner() # Determine winner by general score comparison
                if self.winner:
                    result_message_key = f"Game Over - {self.winner.display_name} wins! All pairs found."
                else:
                    result_message_key = "Game Over - All pairs found, it's a Tie!"
                game_just_ended_by_this_move = True

            if game_just_ended_by_this_move:
                self.game_over = True
                final_scores_msg = f"Final Scores: {self.player1.display_name}={self.scores[self.player1.id]}, {self.player2.display_name}={self.scores[self.player2.id]}"
                logger.info(f"Game over! {result_message_key} {final_scores_msg}")
                
                # Update database with game results
                await update_database_with_game_results(
                    game_id=GAME_ID,
                    player1_id=self.player1.id,
                    player2_id=self.player2.id,
                    winner_id=self.winner.id if self.winner else None,
                    score_player1=self.scores[self.player1.id],
                    score_player2=self.scores[self.player2.id],
                    channel_id=self.channel.id
                )
                # The UI layer will handle the final user-facing message and "Play Again" button.
                # This method just signals game end and the outcome.
                # However, let's update the internal board embed to a final state for completeness.
                await self.update_board(status_message=f"{result_message_key} {final_scores_msg}")
                return True, result_message_key, True

            # If game continues and wasn't a match, we already switched turns above
            
            return True, result_message_key, False

        except Exception as e:
            logger.error(f"Error in make_move: {e}\n{traceback.format_exc()}")
            return False, f"An error occurred: {type(e).__name__}", False
    
    def _check_game_over(self):
        """Checks if all pairs have been matched or if a specific win condition (like 4x5 target) was met.
           This method is more of a status check; primary game end logic is in make_move.
        """
        if self.game_over: # If make_move already set it
            return True
            
        # This condition implies all cards are matched if game_over wasn't set by target scores.
        return self.matched_pairs_count >= self.pairs_to_find
    
    def _switch_turn(self):
        """Switches the turn to the other player."""
        self.current_player = self.player2 if self.current_player == self.player1 else self.player1
    
    def get_winner(self):
        """Determine the winner based on scores. Returns winning player object or None for a tie."""
        if self.game_over: # Ensure game is actually over before declaring winner based on final scores
            score1 = self.scores.get(self.player1.id, 0)
            score2 = self.scores.get(self.player2.id, 0)
            
            if score1 > score2:
                return self.player1
            elif score2 > score1:
                return self.player2
            else: # Tie
                return None
        return self.winner # If winner was already set by specific conditions (e.g., 4x5 target score)
    
    def _get_board_display(self):
        """Generates a text representation of the game board."""
        # Simplified display without grid lines
        
        # Start with an empty line for better Discord rendering
        board_str = "\n"
        
        # Header row (column numbers)
        board_str += "     "  # Space for row labels 
        for c in range(self.columns):
            board_str += f"{c+1}   "  # Column numbers with spacing
            
        board_str += "\n\n"  # Extra line for spacing
        
        # Add each row without cell borders
        for r in range(self.rows):
            # Row number
            board_str += f" {r+1}  "
            
            # Add each cell
            for c in range(self.columns):
                card = self.board[r][c]
                # Display card based on its state; only force reveal if game is over
                display = " " if card is None else card.get_display(force_reveal=self.game_over)
                board_str += f"{display}  "  # Emoji with spacing
            
            board_str += "\n"  # End of row
        
        # Return formatted as code block
        return f"```\n{board_str}```" 