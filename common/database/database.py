"""
Database module for the Discord Game Bot.
Manages leaderboard data using SQLite.
"""
import sqlite3
import os
import logging

logger = logging.getLogger("discord_bot")

# Database file
DB_FILE = "game_stats.db"

# Ensure the database exists and has the necessary tables
def init_db():
    """Initialize the database and create tables if they don't exist."""
    try:
        # Check if database file exists
        db_exists = os.path.exists(DB_FILE)
        
        # Connect to database (creates it if it doesn't exist)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS leaderboard (
            user_id INTEGER,
            username TEXT NOT NULL,
            server_id INTEGER,
            game_id TEXT NOT NULL,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, server_id, game_id)
        )
        ''')
        
        conn.commit()
        
        # Log result
        if db_exists:
            logger.info("Connected to existing database")
        else:
            logger.info("Created new database")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def update_player_stats(user_id, username, server_id, is_win, game_id="1001"):
    """
    Update a player's stats in the database.
    
    Args:
        user_id: Discord user ID
        username: Player's display name
        server_id: Discord server ID
        is_win: True if player won, False if lost
        game_id: Game identifier (default: "1001" for Memory Match)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get current stats
        cursor.execute(
            "SELECT wins, losses FROM leaderboard WHERE user_id = ? AND server_id = ? AND game_id = ?", 
            (user_id, server_id, game_id)
        )
        result = cursor.fetchone()
        
        if result:
            # Update existing record
            wins, losses = result
            if is_win:
                wins += 1
            else:
                losses += 1
                
            cursor.execute(
                "UPDATE leaderboard SET wins = ?, losses = ?, username = ? WHERE user_id = ? AND server_id = ? AND game_id = ?",
                (wins, losses, username, user_id, server_id, game_id)
            )
        else:
            # Insert new record
            wins = 1 if is_win else 0
            losses = 0 if is_win else 1
            
            cursor.execute(
                "INSERT INTO leaderboard (user_id, username, server_id, game_id, wins, losses) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, server_id, game_id, wins, losses)
            )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated stats for player {username} (ID: {user_id}) in server {server_id} for game {game_id}: {'Win' if is_win else 'Loss'}")
        
    except Exception as e:
        logger.error(f"Error updating player stats: {e}")

def get_player_stats(user_id, game_id=None):
    """
    Get a player's stats from the database.
    
    Args:
        user_id: Discord user ID
        game_id: Game identifier or None for all games
        
    Returns:
        Tuple of (wins, losses, total_games, win_rate)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        if game_id:
            # Get stats for specific game
            cursor.execute(
                "SELECT SUM(wins), SUM(losses) FROM leaderboard WHERE user_id = ? AND game_id = ?",
                (user_id, game_id)
            )
        else:
            # Get combined stats for all games
            cursor.execute(
                "SELECT SUM(wins), SUM(losses) FROM leaderboard WHERE user_id = ?",
                (user_id,)
            )
            
        result = cursor.fetchone()
        conn.close()
        
        if result and (result[0] is not None or result[1] is not None):
            wins = result[0] or 0
            losses = result[1] or 0
            total_games = wins + losses
            win_rate = f"{(wins / total_games * 100) if total_games > 0 else 0:.1f}%"
            
            return wins, losses, total_games, win_rate
        else:
            return 0, 0, 0, "0.0%"
        
    except Exception as e:
        logger.error(f"Error getting player stats: {e}")
        return 0, 0, 0, "0.0%"

def get_player_game_stats(user_id, game_id=None):
    """
    Get a player's stats for each game.
    
    Args:
        user_id: Discord user ID
        game_id: Game identifier or None for all games
        
    Returns:
        List of tuples (game_name, wins, losses, win_rate, games_played)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Game ID to name mapping
        game_names = {
            "1001": "Memory Match",
            "1002": "Tic Tac Toe"
        }
        
        if game_id:
            # Get stats for specific game
            cursor.execute(
                "SELECT game_id, SUM(wins), SUM(losses) FROM leaderboard WHERE user_id = ? AND game_id = ? GROUP BY game_id",
                (user_id, game_id)
            )
        else:
            # Get stats for all games
            cursor.execute(
                "SELECT game_id, SUM(wins), SUM(losses) FROM leaderboard WHERE user_id = ? GROUP BY game_id",
                (user_id,)
            )
            
        results = cursor.fetchall()
        conn.close()
        
        stats = []
        for game_id, wins, losses in results:
            wins = wins or 0
            losses = losses or 0
            total_games = wins + losses
            win_rate = f"{(wins / total_games * 100) if total_games > 0 else 0:.1f}%"
            game_name = game_names.get(game_id, f"Game {game_id}")
            
            stats.append((game_name, wins, losses, win_rate, total_games))
            
        return stats
        
    except Exception as e:
        logger.error(f"Error getting player game stats: {e}")
        return []

def get_server_leaderboard(server_id, limit=10, offset=0):
    """
    Get the server leaderboard.
    
    Args:
        server_id: Discord server ID
        limit: Maximum number of entries to return
        offset: Starting offset for pagination
        
    Returns:
        List of tuples (username, game_name, wins, losses, win_rate)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Game ID to name mapping
        game_names = {
            "1001": "Memory Match",
            "1002": "Tic Tac Toe"
        }
        
        # Get all-time stats for each player in the server, for all games
        cursor.execute('''
        SELECT username, game_id, wins, losses 
        FROM leaderboard 
        WHERE server_id = ? 
        ORDER BY wins DESC, losses ASC
        LIMIT ? OFFSET ?
        ''', (server_id, limit, offset))
        
        results = cursor.fetchall()
        conn.close()
        
        leaderboard = []
        for username, game_id, wins, losses in results:
            total_games = wins + losses
            win_rate = f"{(wins / total_games * 100) if total_games > 0 else 0:.1f}%"
            game_name = game_names.get(game_id, f"Game {game_id}")
            
            leaderboard.append((username, game_name, wins, losses, win_rate))
            
        return leaderboard
        
    except Exception as e:
        logger.error(f"Error getting server leaderboard: {e}")
        return []

def get_server_game_leaderboard(server_id, game_id, limit=10, offset=0):
    """
    Get the server leaderboard for a specific game.
    
    Args:
        server_id: Discord server ID
        game_id: Game identifier
        limit: Maximum number of entries to return
        offset: Starting offset for pagination
        
    Returns:
        List of tuples (username, wins, losses, win_rate)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get all-time stats for each player in the server, for the specific game
        cursor.execute('''
        SELECT username, wins, losses 
        FROM leaderboard 
        WHERE server_id = ? AND game_id = ?
        ORDER BY wins DESC, losses ASC
        LIMIT ? OFFSET ?
        ''', (server_id, game_id, limit, offset))
        
        results = cursor.fetchall()
        conn.close()
        
        leaderboard = []
        for username, wins, losses in results:
            total_games = wins + losses
            win_rate = f"{(wins / total_games * 100) if total_games > 0 else 0:.1f}%"
            
            leaderboard.append((username, wins, losses, win_rate))
            
        return leaderboard
        
    except Exception as e:
        logger.error(f"Error getting server game leaderboard: {e}")
        return []

def get_global_leaderboard(limit=10, offset=0):
    """
    Get the global leaderboard.
    
    Args:
        limit: Maximum number of entries to return
        offset: Starting offset for pagination
        
    Returns:
        List of tuples (username, game_name, wins, losses, win_rate)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Game ID to name mapping
        game_names = {
            "1001": "Memory Match",
            "1002": "Tic Tac Toe"
        }
        
        # Get all-time stats for each player across all servers and games
        cursor.execute('''
        SELECT username, game_id, SUM(wins) as total_wins, SUM(losses) as total_losses 
        FROM leaderboard 
        GROUP BY user_id, game_id
        ORDER BY total_wins DESC, total_losses ASC
        LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        results = cursor.fetchall()
        conn.close()
        
        leaderboard = []
        for username, game_id, wins, losses in results:
            total_games = wins + losses
            win_rate = f"{(wins / total_games * 100) if total_games > 0 else 0:.1f}%"
            game_name = game_names.get(game_id, f"Game {game_id}")
            
            leaderboard.append((username, game_name, wins, losses, win_rate))
            
        return leaderboard
        
    except Exception as e:
        logger.error(f"Error getting global leaderboard: {e}")
        return []

def get_global_game_leaderboard(game_id, limit=10, offset=0):
    """
    Get the global leaderboard for a specific game.
    
    Args:
        game_id: Game identifier
        limit: Maximum number of entries to return
        offset: Starting offset for pagination
        
    Returns:
        List of tuples (username, wins, losses, win_rate)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get all-time stats for each player across all servers for the specific game
        cursor.execute('''
        SELECT username, SUM(wins) as total_wins, SUM(losses) as total_losses 
        FROM leaderboard 
        WHERE game_id = ?
        GROUP BY user_id
        ORDER BY total_wins DESC, total_losses ASC
        LIMIT ? OFFSET ?
        ''', (game_id, limit, offset))
        
        results = cursor.fetchall()
        conn.close()
        
        leaderboard = []
        for username, wins, losses in results:
            total_games = wins + losses
            win_rate = f"{(wins / total_games * 100) if total_games > 0 else 0:.1f}%"
            
            leaderboard.append((username, wins, losses, win_rate))
            
        return leaderboard
        
    except Exception as e:
        logger.error(f"Error getting global game leaderboard: {e}")
        return []

def search_player(search_term, scope="server", server_id=None, game_id=None):
    """
    Search for a player in the leaderboard.
    
    Args:
        search_term: Player username to search for
        scope: "server" or "global"
        server_id: Discord server ID (required if scope is "server")
        game_id: Game identifier (optional)
        
    Returns:
        List of tuples (username, game_name, wins, losses, win_rate)
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Game ID to name mapping
        game_names = {
            "1001": "Memory Match",
            "1002": "Tic Tac Toe"
        }
        
        params = [f"%{search_term}%"]
        query = """
        SELECT username, game_id, SUM(wins) as total_wins, SUM(losses) as total_losses 
        FROM leaderboard 
        WHERE username LIKE ?
        """
        
        if scope == "server" and server_id:
            query += " AND server_id = ?"
            params.append(server_id)
            
        if game_id:
            query += " AND game_id = ?"
            params.append(game_id)
            
        query += " GROUP BY username, game_id ORDER BY total_wins DESC, total_losses ASC LIMIT 10"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        search_results = []
        for username, game_id, wins, losses in results:
            total_games = wins + losses
            win_rate = f"{(wins / total_games * 100) if total_games > 0 else 0:.1f}%"
            game_name = game_names.get(game_id, f"Game {game_id}")
            
            search_results.append((username, game_name, wins, losses, win_rate))
            
        return search_results
        
    except Exception as e:
        logger.error(f"Error searching for player: {e}")
        return []

def get_server_leaderboard_count(server_id):
    """Get the total number of entries in the server leaderboard."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) FROM leaderboard WHERE server_id = ?", 
            (server_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
        
    except Exception as e:
        logger.error(f"Error getting server leaderboard count: {e}")
        return 0

def get_server_game_leaderboard_count(server_id, game_id):
    """Get the total number of entries in the server leaderboard for a specific game."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) FROM leaderboard WHERE server_id = ? AND game_id = ?", 
            (server_id, game_id)
        )
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
        
    except Exception as e:
        logger.error(f"Error getting server game leaderboard count: {e}")
        return 0

def get_global_leaderboard_count():
    """Get the total number of unique player-game combinations in the global leaderboard."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM (SELECT DISTINCT user_id, game_id FROM leaderboard)")
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
        
    except Exception as e:
        logger.error(f"Error getting global leaderboard count: {e}")
        return 0

def get_global_game_leaderboard_count(game_id):
    """Get the total number of entries in the global leaderboard for a specific game."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(DISTINCT user_id) FROM leaderboard WHERE game_id = ?", 
            (game_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
        
    except Exception as e:
        logger.error(f"Error getting global game leaderboard count: {e}")
        return 0

# Create a singleton database instance
database = {
    'init_db': init_db,
    'update_player_stats': update_player_stats,
    'get_global_leaderboard': get_global_leaderboard,
    'get_server_leaderboard': get_server_leaderboard,
    'get_player_stats': get_player_stats,
    'get_player_game_stats': get_player_game_stats,
    'get_server_game_leaderboard': get_server_game_leaderboard,
    'get_global_game_leaderboard': get_global_game_leaderboard,
    'search_player': search_player,
    'get_server_leaderboard_count': get_server_leaderboard_count,
    'get_server_game_leaderboard_count': get_server_game_leaderboard_count,
    'get_global_leaderboard_count': get_global_leaderboard_count,
    'get_global_game_leaderboard_count': get_global_game_leaderboard_count
} 