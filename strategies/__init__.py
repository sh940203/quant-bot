from .ma_cross import MACrossInstitutional
from .momentum import Momentum
from .rsi_reversion import RsiReversion
from .breakout import Breakout
from .foreign_streak import ForeignStreak
from .composite import TrendChip

REGISTRY = {
    "ma_cross": MACrossInstitutional,
    "momentum": Momentum,
    "rsi_reversion": RsiReversion,
    "breakout": Breakout,
    "foreign_streak": ForeignStreak,
    "trend_chip": TrendChip,
}
