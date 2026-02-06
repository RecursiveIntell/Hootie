from pathlib import Path

# ── Color Palette ──
# Background layers
BG_DARKEST = "#0D1117"      # Window background
BG_DARK = "#161B22"          # Panel background
BG_MID = "#1C2128"           # Card / elevated surface
BG_LIGHT = "#21262D"         # Hover / selected background
BG_LIGHTER = "#30363D"       # Borders, dividers

# Text
TEXT_PRIMARY = "#E6EDF3"
TEXT_SECONDARY = "#8B949E"
TEXT_MUTED = "#6E7681"
TEXT_LINK = "#58A6FF"

# Accent colors
ACCENT_BLUE = "#58A6FF"
ACCENT_GREEN = "#3FB950"
ACCENT_YELLOW = "#D29922"
ACCENT_RED = "#F85149"
ACCENT_PURPLE = "#BC8CFF"
ACCENT_ORANGE = "#F0883E"

# Group color palette
GROUP_COLORS = [
    "#5E81AC",  # Nord blue
    "#A3BE8C",  # Nord green
    "#EBCB8B",  # Nord yellow
    "#BF616A",  # Nord red
    "#B48EAD",  # Nord purple
    "#D08770",  # Nord orange
    "#88C0D0",  # Nord frost
    "#81A1C1",  # Nord light blue
    "#8FBCBB",  # Nord teal
]

# Functional colors
SUCCESS = ACCENT_GREEN
WARNING = ACCENT_YELLOW
ERROR = ACCENT_RED
INFO = ACCENT_BLUE

# Gauge colors
GAUGE_GREEN = "#238636"
GAUGE_YELLOW = "#9E6A03"
GAUGE_RED = "#DA3633"

# ── Typography ──
FONT_FAMILY = "'Segoe UI', 'SF Pro Display', 'Helvetica Neue', 'Noto Sans', sans-serif"
FONT_MONO = "'JetBrains Mono', 'Cascadia Code', 'Fira Code', 'Consolas', monospace"
FONT_SIZE_SM = 11
FONT_SIZE_MD = 13
FONT_SIZE_LG = 16
FONT_SIZE_XL = 20
FONT_SIZE_XXL = 28

# ── Spacing ──
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24
SPACING_XXL = 32

# ── Border Radius ──
RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8
RADIUS_XL = 12


def get_stylesheet_path() -> str:
    return str(Path(__file__).parent.parent / "resources" / "styles" / "dark.qss")


def apply_theme(app):
    """Apply the dark theme to the QApplication."""
    from PyQt6.QtGui import QFont, QPalette, QColor
    from PyQt6.QtCore import Qt

    # Set application font
    font = QFont()
    font.setPointSize(FONT_SIZE_MD)
    app.setFont(font)

    # Load and apply QSS
    qss_path = get_stylesheet_path()
    try:
        with open(qss_path, "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        pass  # Fallback to no stylesheet

    # Set palette for native dialogs
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_DARKEST))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_DARK))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_MID))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_MID))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_BLUE))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Link, QColor(TEXT_LINK))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_MUTED))
    app.setPalette(palette)
