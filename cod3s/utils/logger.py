import logging
import sys
from colored import fg, bg, attr


class COD3SLogger:
    """Logger for COD3S framework with colored output support using the colored module."""

    # Color and style definitions using the colored module
    STYLES = {
        "h1": fg("orange_3") + attr("bold"),
        "h2": fg("dodger_blue_2") + attr("bold"),
        "h3": fg("purple_3") + attr("bold"),
        "text": fg("grey_69"),
        "warning": fg("dark_orange") + attr("bold"),
        "alert": fg("red_1") + attr("bold"),
    }

    def __init__(self, name="COD3S", level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        # To avoid logging propagation and repeated messages
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
        """Apply colored style to text and reset after."""
        return f"{self.STYLES[style]}{msg}{attr('reset')}"

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
