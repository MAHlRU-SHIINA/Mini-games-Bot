"""
Leaderboard commands for the game bot.
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio

from common.database import database

logger = logging.getLogger("discord_bot")

# Game IDs and names
GAME_IDS = {
    "1001": "Memory Match",
    "1002": "Tic Tac Toe",
    "1003": "Rock Paper Scissors"
}

# Button for pagination
class LeaderboardPagination(discord.ui.View):
    def __init__(self, ctx, scope, game_id=None, page=0, page_size=10):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.scope = scope
        self.game_id = game_id
        self.page = page
        self.page_size = page_size
        self.max_pages = 1  # Will be updated later
        
        # Update buttons state
        self._update_buttons()
    
    def _update_buttons(self):
        # Disable previous button if on first page
        self.previous_button.disabled = (self.page <= 0)
        
        # Disable next button if on last page or not enough data
        self.next_button.disabled = (self.page >= self.max_pages - 1)
        
        # Update the game select menu
        if hasattr(self, 'game_select'):
            self.game_select.options = [
                discord.SelectOption(
                    label=f"{name}",
                    value=game_id,
                    default=(self.game_id == game_id if self.game_id else game_id == "all")
                ) for game_id, name in GAME_IDS.items()
            ]
            # Add "All Games" option
            self.game_select.options.insert(0, discord.SelectOption(
                label="All Games",
                value="all",
                default=(not self.game_id)
            ))
            
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await self.update_leaderboard(interaction)
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_pages - 1:
            self.page += 1
            await self.update_leaderboard(interaction)
    
    @discord.ui.select(
        placeholder="Select a game",
        options=[
            discord.SelectOption(label="All Games", value="all", default=True),
            *[discord.SelectOption(label=name, value=game_id) for game_id, name in GAME_IDS.items()]
        ]
    )
    async def game_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        # Update game_id (or set to None for "all")
        self.game_id = select.values[0] if select.values[0] != "all" else None
        
        # Reset to first page
        self.page = 0
        
        # Update the leaderboard
        await self.update_leaderboard(interaction)
    
    @discord.ui.button(label="Search Player", style=discord.ButtonStyle.success)
    async def search_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Create a modal for searching
        await interaction.response.send_modal(PlayerSearchModal(self))
    
    async def update_leaderboard(self, interaction):
        """Update the leaderboard embed and view."""
        try:
            embed = create_leaderboard_embed(
                self.scope, 
                self.game_id, 
                self.page, 
                self.page_size,
                get_max_pages=True,
                view=self
            )
            
            # Update button states
            self._update_buttons()
            
            # Respond to the interaction
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error updating leaderboard: {e}")
            await interaction.response.send_message(
                "Error updating leaderboard. Please try again.",
                ephemeral=True
            )
    
    async def on_timeout(self):
        """Disable buttons when timeout occurs."""
        for item in self.children:
            item.disabled = True
        
        try:
            # Try to update the message with disabled buttons
            message = await self.ctx.fetch_message(self.message.id)
            await message.edit(view=self)
        except:
            pass

# Modal for player search
class PlayerSearchModal(discord.ui.Modal, title="Search Player"):
    # Text input for player name
    player_name = discord.ui.TextInput(
        label="Player Name",
        placeholder="Enter player name to search",
        required=True,
        max_length=100
    )
    
    def __init__(self, view):
        super().__init__()
        self.parent_view = view
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Search for the player
            search_term = self.player_name.value
            
            # Get player data
            player_data = database["search_player"](
                search_term, 
                self.parent_view.scope, 
                interaction.guild.id if self.parent_view.scope == "server" else None,
                self.parent_view.game_id
            )
            
            if player_data:
                # Create an embed for the player
                embed = create_player_search_embed(player_data, search_term, self.parent_view.scope)
                await interaction.response.edit_message(embed=embed, view=self.parent_view)
            else:
                await interaction.response.send_message(
                    f"No players found matching '{search_term}'.", 
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error searching for player: {e}")
            await interaction.response.send_message(
                "Error searching for player. Please try again.",
                ephemeral=True
            )

def create_player_search_embed(player_data, search_term, scope):
    """Create an embed displaying search results for a player."""
    embed = discord.Embed(
        title=f"Player Search Results for '{search_term}'",
        color=discord.Color.blue()
    )
    
    # Format the results
    result_text = "```\n"
    result_text += f"{'Player':<20}{'Game':<15}{'Wins':<6}{'Losses':<8}{'Win Rate':<8}\n"
    result_text += "-" * 55 + "\n"
    
    for username, game_name, wins, losses, win_rate in player_data:
        result_text += f"{username[:19]:<20}{game_name[:14]:<15}{wins:<6}{losses:<8}{win_rate:<8}\n"
    
    result_text += "```"
    embed.description = result_text
    
    # Add scope information
    embed.set_footer(text=f"Scope: {scope.capitalize()}")
    
    return embed

def create_leaderboard_embed(scope, game_id=None, page=0, page_size=10, get_max_pages=False, view=None):
    """
    Create an embed for the leaderboard.
    
    Args:
        scope: "server" or "global"
        game_id: Game ID to filter by, or None for all games
        page: Page number (0-based)
        page_size: Number of entries per page
        get_max_pages: Whether to calculate and update the max_pages in view
        view: The pagination view to update max_pages
    
    Returns:
        discord.Embed: The formatted leaderboard embed
    """
    try:
        # Calculate offset
        offset = page * page_size
        
        # Get the game name if applicable
        game_name = GAME_IDS.get(game_id, "All Games") if game_id else "All Games"
        
        # Set the title based on scope and game
        if scope == "global":
            title = f"Global Leaderboard: {game_name}"
        else:
            guild_name = view.ctx.guild.name if view else "Server"
            title = f"Server Leaderboard: {guild_name} - {game_name}"
        
        # Get the data from database
        if scope == "global":
            if game_id:
                data = database["get_global_game_leaderboard"](game_id, page_size, offset)
                total = database["get_global_game_leaderboard_count"](game_id) if get_max_pages else 0
            else:
                data = database["get_global_leaderboard"](page_size, offset)
                total = database["get_global_leaderboard_count"]() if get_max_pages else 0
        else:
            server_id = view.ctx.guild.id if view else 0
            if game_id:
                data = database["get_server_game_leaderboard"](server_id, game_id, page_size, offset)
                total = database["get_server_game_leaderboard_count"](server_id, game_id) if get_max_pages else 0
            else:
                data = database["get_server_leaderboard"](server_id, page_size, offset)
                total = database["get_server_leaderboard_count"](server_id) if get_max_pages else 0
        
        # Update max pages if requested
        if get_max_pages and view:
            view.max_pages = max(1, (total + page_size - 1) // page_size)
        
        # Create the embed
        embed = discord.Embed(
            title=title,
            color=discord.Color.blue()
        )
        
        # Format the leaderboard
        if data:
            # Add header
            leaderboard_text = "```\n"
            
            # Adjust headers based on whether we're showing game name
            if not game_id:  # All games
                leaderboard_text += f"{'Rank':<5}{'Player':<20}{'Game':<15}{'Wins':<6}{'Losses':<8}{'Win Rate':<8}\n"
                leaderboard_text += "-" * 65 + "\n"
                
                # Add rows
                for i, (username, game_name, wins, losses, win_rate) in enumerate(data, offset + 1):
                    leaderboard_text += f"{i:<5}{username[:19]:<20}{game_name[:14]:<15}{wins:<6}{losses:<8}{win_rate:<8}\n"
            else:  # Specific game
                leaderboard_text += f"{'Rank':<5}{'Player':<20}{'Wins':<6}{'Losses':<8}{'Win Rate':<8}\n"
                leaderboard_text += "-" * 50 + "\n"
                
                # Add rows
                for i, (username, wins, losses, win_rate) in enumerate(data, offset + 1):
                    leaderboard_text += f"{i:<5}{username[:19]:<20}{wins:<6}{losses:<8}{win_rate:<8}\n"
            
            leaderboard_text += "```"
            embed.description = leaderboard_text
        else:
            embed.description = "No games played yet."
        
        # Add page information
        page_info = f"Page {page+1}/{view.max_pages if view else '?'}"
        embed.set_footer(text=page_info)
        
        return embed
        
    except Exception as e:
        logger.error(f"Error creating leaderboard embed: {e}")
        
        # Return a fallback embed
        embed = discord.Embed(
            title="Error loading leaderboard",
            description="There was an error loading the leaderboard data.",
            color=discord.Color.red()
        )
        return embed

async def setup_leaderboard_commands(bot):
    """Register leaderboard commands."""
    
    @bot.hybrid_command(name="leaderboard", description="Show the game leaderboard with pagination")
    @app_commands.describe(
        scope="Show global or server leaderboard (default: server)",
        game="Specific game to show (default: all games)"
    )
    @app_commands.choices(
        scope=[
            app_commands.Choice(name="Server", value="server"),
            app_commands.Choice(name="Global", value="global")
        ],
        game=[
            app_commands.Choice(name="All Games", value="all"),
            *[app_commands.Choice(name=name, value=game_id) for game_id, name in GAME_IDS.items()]
        ]
    )
    async def leaderboard(ctx, scope: str = "server", game: str = "all"):
        """Show the game leaderboard with pagination."""
        try:
            # Check if the scope is valid
            scope = scope.lower()
            if scope not in ["server", "global"]:
                await ctx.send("Invalid scope. Use 'server' or 'global'.")
                return
            
            # Determine the game ID
            game_id = None if game == "all" else game
            
            # Create the pagination view
            view = LeaderboardPagination(ctx, scope, game_id)
            
            # Create the leaderboard embed
            embed = create_leaderboard_embed(scope, game_id, 0, 10, True, view)
            
            # Send the message with the view
            msg = await ctx.send(embed=embed, view=view)
            
            # Store the message for later reference
            view.message = msg
            
        except Exception as e:
            logger.error(f"Error showing leaderboard: {e}")
            await ctx.send("Error showing leaderboard. Please try again.")
    
    @bot.hybrid_command(name="stats", description="Show your game statistics")
    @app_commands.describe(
        game="Specific game to show stats for (default: all games)",
        user="User to show stats for (default: yourself)"
    )
    @app_commands.choices(
        game=[
            app_commands.Choice(name="All Games", value="all"),
            *[app_commands.Choice(name=name, value=game_id) for game_id, name in GAME_IDS.items()]
        ]
    )
    async def stats(ctx, game: str = "all", user: discord.Member = None):
        """Show a player's game statistics."""
        try:
            # Use the command author if no user specified
            target_user = user or ctx.author
            
            # Determine the game ID
            game_id = None if game == "all" else game
            
            # Get the player's stats
            stats_data = database["get_player_game_stats"](target_user.id, game_id)
            
            # Create the embed
            embed = discord.Embed(
                title=f"Game Stats: {target_user.display_name}",
                color=discord.Color.blue()
            )
            
            if stats_data:
                # Format the stats
                stats_text = "```\n"
                stats_text += f"{'Game':<15}{'Wins':<6}{'Losses':<8}{'Win Rate':<8}{'Played':<8}\n"
                stats_text += "-" * 45 + "\n"
                
                total_wins = 0
                total_losses = 0
                
                for game_name, wins, losses, win_rate, games_played in stats_data:
                    stats_text += f"{game_name[:14]:<15}{wins:<6}{losses:<8}{win_rate:<8}{games_played:<8}\n"
                    total_wins += wins
                    total_losses += losses
                
                # Add totals if showing multiple games
                if len(stats_data) > 1:
                    stats_text += "-" * 45 + "\n"
                    total_games = total_wins + total_losses
                    win_rate = f"{total_wins / total_games * 100:.1f}%" if total_games > 0 else "0.0%"
                    stats_text += f"{'TOTAL':<15}{total_wins:<6}{total_losses:<8}{win_rate:<8}{total_games:<8}\n"
                
                stats_text += "```"
                embed.description = stats_text
            else:
                embed.description = "No games played yet."
            
            # Add user avatar
            embed.set_thumbnail(url=target_user.avatar.url if target_user.avatar else target_user.default_avatar.url)
            
            # Send the embed
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            await ctx.send("Error showing stats. Please try again.")
    
    # Update the database module to include these new functions
    database["get_global_game_leaderboard"] = lambda game_id, limit, offset=0: []
    database["get_server_game_leaderboard"] = lambda server_id, game_id, limit, offset=0: []
    database["get_global_game_leaderboard_count"] = lambda game_id: 0
    database["get_server_game_leaderboard_count"] = lambda server_id, game_id: 0
    database["get_global_leaderboard_count"] = lambda: 0
    database["get_server_leaderboard_count"] = lambda server_id: 0
    database["get_player_game_stats"] = lambda player_id, game_id=None: []
    database["search_player"] = lambda search_term, scope, server_id=None, game_id=None: []
    
    return {"leaderboard": leaderboard, "stats": stats} 