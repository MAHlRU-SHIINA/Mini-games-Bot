"""
Help command for the game bot.
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging

# Import game IDs from leaderboard
from common.commands.leaderboard import GAME_IDS

logger = logging.getLogger("discord_bot")

class HelpView(discord.ui.View):
    def __init__(self, ctx, command_prefix):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.command_prefix = command_prefix
        
    @discord.ui.select(
        placeholder="Select game or category",
        options=[
            discord.SelectOption(label="Overview", value="overview", description="General bot overview", default=True),
            discord.SelectOption(label="Memory Match", value="1001", description="Memory Match Game"),
            discord.SelectOption(label="Tic Tac Toe", value="1002", description="Tic Tac Toe Game"),
            discord.SelectOption(label="General Commands", value="general", description="General commands")
        ]
    )
    async def help_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle selection of help category."""
        selection = select.values[0]
        
        # Create embed based on selection
        if selection == "overview":
            embed = create_overview_embed(self.command_prefix)
        elif selection == "general":
            embed = create_general_commands_embed(self.command_prefix)
        else:
            # Game-specific help
            embed = create_game_help_embed(selection, self.command_prefix)
        
        # Update the message
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """Disable the view when it times out."""
        for item in self.children:
            item.disabled = True
        
        try:
            # Try to update the message with disabled buttons
            message = await self.ctx.fetch_message(self.message.id)
            await message.edit(view=self)
        except:
            pass

def create_overview_embed(command_prefix):
    """Create an overview embed for the bot."""
    embed = discord.Embed(
        title="Game Bot Help",
        description=f"Welcome to the Game Bot! This bot lets you play various games with other server members.",
        color=discord.Color.blue()
    )
    
    # Add bot information
    embed.add_field(
        name="Available Games",
        value=(
            "• **Memory Match** - Match pairs of cards to win\n"
            "• **Tic Tac Toe** - Classic X and O game"
        ),
        inline=False
    )
    
    # Add quick start
    embed.add_field(
        name="Quick Start",
        value=(
            f"Use `{command_prefix}help` and select a game from the dropdown menu for detailed instructions.\n"
            f"Challenge someone with `{command_prefix}matching_game @user` or `{command_prefix}tic-tac-toe @user`"
        ),
        inline=False
    )
    
    # Add general info
    embed.add_field(
        name="Stats & Leaderboards",
        value=(
            f"Check your stats with `{command_prefix}stats`\n"
            f"View leaderboards with `{command_prefix}leaderboard`"
        ),
        inline=False
    )
    
    # Footer
    embed.set_footer(text="Select a specific game or 'General Commands' from the dropdown for more information")
    
    return embed

def create_general_commands_embed(command_prefix):
    """Create an embed for general commands."""
    embed = discord.Embed(
        title="General Commands",
        description="These commands work across all games",
        color=discord.Color.blue()
    )
    
    # Stats and leaderboard
    embed.add_field(
        name="Statistics",
        value=(
            f"`{command_prefix}stats [game] [@user]` - Show your or another user's game statistics\n"
            f"• `game` - (Optional) Filter by specific game\n"
            f"• `user` - (Optional) User to show stats for"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Leaderboard",
        value=(
            f"`{command_prefix}leaderboard [scope] [game]` - Show the game leaderboard\n"
            f"• `scope` - (Optional) 'server' or 'global' (default: server)\n"
            f"• `game` - (Optional) Filter by specific game\n"
            f"• Use the pagination buttons to navigate\n"
            f"• Use 'Search Player' to find a specific player"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Help",
        value=(
            f"`{command_prefix}help` - Show this help menu\n"
            f"• Select a game from the dropdown for specific help"
        ),
        inline=False
    )
    
    return embed

def create_game_help_embed(game_id, command_prefix):
    """Create a help embed for a specific game."""
    game_name = GAME_IDS.get(game_id, "Unknown Game")
    
    embed = discord.Embed(
        title=f"{game_name} Help",
        color=discord.Color.blue()
    )
    
    if game_id == "1001":  # Memory Match
        embed.description = "Match pairs of emojis to win! The player with the most matches wins."
        
        # Add game rules
        embed.add_field(
            name="How to Play",
            value=(
                "1. Challenge another user to start a game\n"
                "2. Take turns selecting two cards\n"
                "3. If the cards match, you get a point and another turn\n"
                "4. If they don't match, it's the other player's turn\n"
                "5. The player with more than half of all possible matches wins!\n"
                "6. Watch out for the joker card - it gives you a point but doesn't match with anything!"
            ),
            inline=False
        )
        
        # Add commands
        embed.add_field(
            name="Commands",
            value=(
                f"`{command_prefix}matching_game @user [category]` - Challenge someone to a Memory Match game\n"
                f"• `category` - (Optional) Choose an emoji category: food, animals, faces, etc.\n"
                f"`{command_prefix}accept` - Accept a Memory Match challenge\n"
                f"`{command_prefix}decline` - Decline a Memory Match challenge\n"
                f"`{command_prefix}end_game` - End the current Memory Match game"
            ),
            inline=False
        )
        
    elif game_id == "1002":  # Tic Tac Toe
        embed.description = "Classic Tic Tac Toe game! Get three in a row to win."
        
        # Add game rules
        embed.add_field(
            name="How to Play",
            value=(
                "1. Challenge another user to start a game\n"
                "2. Players take turns placing their symbol (X or O) on the board\n"
                "3. The first player to get three of their symbols in a row (horizontally, vertically, or diagonally) wins\n"
                "4. If the board fills up with no winner, the game is a draw"
            ),
            inline=False
        )
        
        # Add commands
        embed.add_field(
            name="Commands",
            value=(
                f"`{command_prefix}tic-tac-toe @user` - Challenge someone to a Tic Tac Toe game\n"
                f"`{command_prefix}ttt_accept` - Accept a Tic Tac Toe challenge\n"
                f"`{command_prefix}ttt_decline` - Decline a Tic Tac Toe challenge\n"
                f"`{command_prefix}ttt_end` - End the current Tic Tac Toe game"
            ),
            inline=False
        )
    
    # Add general notes
    embed.add_field(
        name="Notes",
        value=(
            "• Games timeout after inactivity\n"
            "• Both players need to confirm to end a game early\n"
            "• Game stats are tracked for the leaderboard"
        ),
        inline=False
    )
    
    return embed

async def setup_help_command(bot):
    """Set up the help command."""
    
    @bot.hybrid_command(name="help", description="Show information about available games")
    async def help_cmd(ctx):
        """Show help information about the available games."""
        try:
            # Create the view with dropdown
            view = HelpView(ctx, bot.command_prefix)
            
            # Create initial overview embed
            embed = create_overview_embed(bot.command_prefix)
            
            # Send the help message with view
            msg = await ctx.send(embed=embed, view=view)
            
            # Store the message for later reference
            view.message = msg
                
        except Exception as e:
            logger.error(f"Error showing help: {e}")
            await ctx.send("Error showing help. Please try again.")
    
    return {"help": help_cmd} 