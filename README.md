# Discord Game Bot

A Discord bot that supports multiple games with a modular architecture.

## Games

- **Memory Match (ID: 1001)** - Match pairs of emojis to win!
- **Tic Tac Toe (ID: 1002)** - Classic X and O game

## Features

- Modular architecture with support for multiple games
- Leaderboard system with pagination
- Player statistics tracking
- AFK detection
- Game end confirmation
- Interactive UI with buttons

## File Structure

```
├── bot.py                    # Main bot file
├── requirements.txt          # Dependencies
├── common/                   # Shared functionality
│   ├── commands/             # Common commands
│   │   ├── help.py           # Help command
│   │   └── leaderboard.py    # Leaderboard commands
│   ├── config/               # Configuration
│   │   ├── __init__.py       # Config initialization
│   │   └── game_config.py    # Game settings
│   ├── database/             # Database functionality
│   │   ├── __init__.py       # Database initialization
│   │   └── database.py       # Database operations
│   └── utils/                # Utility functions
│       └── game_utils.py     # Game utilities
├── games/                    # Game modules
│   ├── game_1001_matching/   # Memory Match Game
│   │   ├── commands_1001.py  # Game commands
│   │   ├── game_1001.py      # Game logic
│   │   └── ui_1001.py        # UI components
│   └── game_1002_tictactoe/  # Tic Tac Toe Game
│       ├── commands_1002.py  # Game commands
│       ├── game_1002.py      # Game logic
│       └── ui_1002.py        # UI components
└── utils/                    # General utilities
    └── card.py               # Card class
```

## Commands

### Memory Match Game
- `/matching_game @user [category]` - Challenge a user to a Memory Match game
- `/accept` - Accept a Memory Match challenge
- `/decline` - Decline a Memory Match challenge
- `/end_game` - End a Memory Match game

### Tic Tac Toe Game
- `/tic-tac-toe @user` - Challenge a user to a Tic Tac Toe game
- `/ttt_accept` - Accept a Tic Tac Toe challenge
- `/ttt_decline` - Decline a Tic Tac Toe challenge
- `/ttt_end` - End a Tic Tac Toe game

### General Commands
- `/leaderboard [scope] [game]` - Show the game leaderboard
- `/stats [game] [@user]` - Show your or another user's game statistics
- `/help` - Show information about available games
- `/sync` - Sync slash commands with Discord (owner only)

## Adding New Games

To add a new game:

1. Choose a unique 4-digit ID (e.g., 1003)
2. Create a new folder under `games/` named `game_XXXX_gamename`
3. Add your game to the `GAME_IDS` dictionary in `common/commands/leaderboard.py`
4. Add your game help info to `common/commands/help.py`
5. Create game files:
   - `commands_XXXX.py` - Game commands
   - `game_XXXX.py` - Game logic
   - `ui_XXXX.py` - UI components
6. Import and register your game in `bot.py`

## Requirements

- Python 3.8+
- discord.py 2.0+
- See requirements.txt for all dependencies
