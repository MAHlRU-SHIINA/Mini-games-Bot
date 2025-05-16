"""
Configuration settings for the Discord Emoji Memory Match Game.
"""

# --- Bot Configuration ---
COMMAND_PREFIX = '!'

# --- Game Configuration ---
EMOJI_BACK = "❓"  # The emoji shown for hidden/unmatched emojis

# Define emoji categories with their corresponding emojis
EMOJI_CATEGORIES = {
    "food": ["🍎", "🍕", "🍔", "🌮", "🍦", "🍰", "🍫", "🥑", "🍓", "🍇", "🍪", "🥕", "🥨", "🥩", "🍜"],
    "animals": ["🐶", "🐱", "🐭", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐸", "🐔", "🦄"],
    "faces": ["😀", "😂", "🥰", "😎", "🤔", "😴", "🥳", "😇", "🤠", "🤡", "😺", "🤖", "👻", "👽", "🎃"],
    "nature": ["🌸", "🌺", "🌻", "🌼", "🌷", "🌹", "🍀", "🌿", "🌴", "🌲", "🍁", "⭐", "🌙", "☀️", "⛅"],
    "objects": ["📱", "💻", "⌚", "📷", "🎮", "🎨", "📚", "✏️", "🎵", "🎸", "⚽", "🎲", "🎭", "🎪", "🎁"],
    "hearts": ["❤️", "🧡", "💛", "💚", "💙", "💜", "🤎", "🖤", "🤍", "💖", "💗", "💓", "💝", "💕", "💞"],
    "travel": ["✈️", "🚗", "🚲", "⛵", "🚁", "🚂", "🎡", "🗽", "🗼", "🏰", "⛩️", "🏖️", "🌋", "🗻", "🌉"],
    "flags": ["🏁", "🚩", "🎌", "🏴", "🏳️", "🏳️‍🌈", "🏴‍☠️", "🇺🇳", "🇬🇧", "🇺🇸", "🇯🇵", "🇨🇦", "🇲🇽", "🇮🇳", "🇧🇷"],
    # New categories
    "sports": ["⚽", "🏀", "🏈", "⚾", "🥎", "🎾", "🏐", "🏉", "🥏", "🎱", "🏓", "🏸", "🏒", "⛳", "🥊"],
    "moon": ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘", "🌙", "🌚", "🌛", "🌜", "🌝", "🌞", "⭐"],
    "fruits": ["🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🫐", "🍈", "🍒", "🍑", "🥭", "🍍", "🥝"],
    "tech": ["📱", "💻", "⌨️", "🖥️", "🖱️", "💾", "💿", "📼", "📟", "📠", "📺", "📻", "🔋", "🔌", "🧮"],
    "weather": ["☀️", "🌤️", "⛅", "🌥️", "☁️", "🌦️", "🌧️", "⛈️", "🌩️", "🌨️", "❄️", "💨", "🌪️", "🌫️", "☔"]
}

# Board dimensions
ROWS = 5
COLUMNS = 5

# Number of pairs (actual value calculated in bot code)
PAIRS = 12  # This is the default, but we'll use ROWS * COLUMNS // 2 in the code

# Time (in seconds) to show non-matching emojis before hiding them
REVEAL_DELAY_SECONDS = 2.0

# Challenge timeout
CHALLENGE_TIMEOUT_SECONDS = 60.0

# Emojis for challenge acceptance/rejection
ACCEPT_EMOJI = "✅"
DECLINE_EMOJI = "❌"

# Time (in seconds) to auto-dismiss ephemeral messages
EPHEMERAL_MESSAGE_DURATION = 2.0

# AFK timeout (in seconds) - 3 minutes
AFK_TIMEOUT_SECONDS = 180.0 