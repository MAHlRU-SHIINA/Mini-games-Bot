"""
Defines the Card class for the Memory Games.
"""
from common.config import EMOJI_CATEGORIES, EMOJI_BACK

class Card:
    """Represents a single card for matching games."""
    def __init__(self, symbol, category=None, position=None, is_joker=False):
        self.symbol = symbol
        self.category = category
        self.position = position  # (row, col) tuple
        self.is_matched = False
        self.is_revealed = False  # If currently revealed in a turn
        self.is_joker = is_joker

    def get_display(self, force_reveal=False):
        """Returns the symbol to display based on state."""
        if self.is_matched or self.is_revealed or force_reveal:
            return self.symbol
        else:
            return EMOJI_BACK  # The hidden symbol

    def __str__(self):
        """String representation."""
        return self.symbol

    def __repr__(self):
        """Developer representation."""
        return f"Card(symbol='{self.symbol}', category='{self.category}', position={self.position})"

    def matches(self, other_card, match_type="exact"):
        """Checks if this card matches another card based on match type."""
        if not isinstance(other_card, Card):
            return False
        if self == other_card:  # Cannot match itself (same object)
            return False

        if match_type == "any":
            # Easy: Match any two cards (just find pairs)
            return True
        elif match_type == "category":
            # Medium: Match cards from same category
            return self.category == other_card.category
        elif match_type == "exact":
            # Hard: Match exact same symbol
            return self.symbol == other_card.symbol
        else:
            return False

    def __eq__(self, other):
        """Checks if two Card objects are the same."""
        if not isinstance(other, Card):
            return NotImplemented
        # Two cards are equal if they have the same symbol and position
        return (self.symbol == other.symbol and 
                self.position == other.position)

    def __hash__(self):
        """Allows cards to be used in sets/dictionaries."""
        return hash((self.symbol, self.position)) 