import logging
import sys

COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "orange": "\033[38;5;214m",  # h1
    "blue": "\033[38;5;27m",  # h2
    "purple": "\033[38;5;89m",  # h3
    "light_gray": "\033[38;5;189m",  # text
    "dark_orange": "\033[38;5;172m",  # warning
    "red": "\033[38;5;160m",  # alert
    "green": "\033[38;5;46m",  # repair rate
}

# Style combinations
STYLES = {
    "h1": COLORS["orange"] + COLORS["bold"],
    "h2": COLORS["blue"] + COLORS["bold"],
    "h3": COLORS["purple"] + COLORS["bold"],
    "text": COLORS["light_gray"],
    "warning": COLORS["dark_orange"] + COLORS["bold"],
    "alert": COLORS["red"] + COLORS["bold"],
}


class COD3SLogger:
    """Logger for COD3S framework with colored output support using vanilla Python."""

    def __init__(self, name="COD3S", level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        # To avoid loggin propagation and repeated messages
        self.logger.propagate = False
        # Clear any existing handlers
        if self.logger.handlers:
            self.logger.handlers.clear()

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

        # Add handler to logger
        self.logger.addHandler(console_handler)

    def _style_text(self, msg, style):
        """Apply ANSI style to text and reset after."""
        return f"{STYLES[style]}{msg}{COLORS['reset']}"

    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        styled_msg = self._style_text(msg, "text")
        self.logger.info(styled_msg)

    def info1(self, msg):
        styled_msg = self._style_text(msg, "h1")
        self.logger.info(styled_msg)

    def info2(self, msg):
        styled_msg = self._style_text(msg, "h2")
        self.logger.info(styled_msg)

    def info3(self, msg):
        styled_msg = self._style_text(msg, "h3")
        self.logger.info(styled_msg)

    def warning(self, msg):
        styled_msg = self._style_text(msg, "warning")
        self.logger.warning(styled_msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        styled_msg = self._style_text(msg, "alert")
        self.logger.critical(styled_msg)
