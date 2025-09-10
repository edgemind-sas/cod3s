import logging
import sys
from colored import fg, bg, attr


class COD3SLogger:
    """
    Logger for COD3S framework with colored output support using the colored module.

    This logger provides custom logging levels (INFO1, INFO2, INFO3) in addition to
    standard Python logging levels, with colored output for better readability.

    Custom Levels:
        - INFO3 (21): Detailed messages (lowest priority)
        - INFO2 (23): Intermediate messages
        - INFO1 (25): Important messages (highest priority)
        - Standard levels: DEBUG (10), INFO (20), WARNING (30), ERROR (40), CRITICAL (50)

    Examples:
        Basic usage with default settings:

        >>> logger = COD3SLogger("MyApp")
        >>> logger.info("Standard info message")
        >>> logger.info1("Important information")
        >>> logger.info2("Intermediate information")
        >>> logger.info3("Detailed information")

        Control verbosity with custom levels:

        >>> # Show only INFO1 and above (hides INFO2, INFO3, and standard INFO)
        >>> logger = COD3SLogger("MyApp", level=COD3SLogger.INFO1_LEVEL)
        >>> logger.info3("This won't be displayed")
        >>> logger.info2("This won't be displayed")
        >>> logger.info1("This will be displayed")
        >>> logger.warning("This will be displayed")

        >>> # Show INFO2 and above (hides only INFO3)
        >>> logger = COD3SLogger("MyApp", level=COD3SLogger.INFO2_LEVEL)
        >>> logger.info3("This won't be displayed")
        >>> logger.info2("This will be displayed")
        >>> logger.info1("This will be displayed")

        >>> # Show all messages including detailed INFO3
        >>> logger = COD3SLogger("MyApp", level=COD3SLogger.INFO3_LEVEL)
        >>> logger.info3("This will be displayed")
        >>> logger.info2("This will be displayed")
        >>> logger.info1("This will be displayed")

        Custom formatter usage:

        >>> logger = COD3SLogger("MyApp")
        >>> # Change to a simpler format
        >>> logger.update_formatter("%(levelname)s: %(message)s")
        >>> logger.info1("Simple format message")

        >>> # Change to a more detailed format
        >>> logger.update_formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        >>> logger.info2("Detailed format message")

        >>> # Reset to default format
        >>> logger.update_formatter()
        >>> logger.info("Back to default format")

        Different verbosity scenarios:

        >>> # For production: only warnings and errors
        >>> prod_logger = COD3SLogger("Production", level=logging.WARNING)

        >>> # For development: show all info levels
        >>> dev_logger = COD3SLogger("Development", level=COD3SLogger.INFO3_LEVEL)

        >>> # For debugging: show everything
        >>> debug_logger = COD3SLogger("Debug", level=logging.DEBUG)

        Using level_name parameter:

        >>> # Using string level names instead of numeric constants
        >>> logger = COD3SLogger("MyApp", level_name="INFO1")
        >>> logger.info3("This won't be displayed")
        >>> logger.info1("This will be displayed")

        >>> # Case insensitive level names
        >>> logger = COD3SLogger("MyApp", level_name="info2")
        >>> logger.info3("This won't be displayed")
        >>> logger.info2("This will be displayed")

        >>> # Standard level names also work
        >>> logger = COD3SLogger("MyApp", level_name="DEBUG")
        >>> logger.debug("This will be displayed")
    """

    # Niveaux de logging personnalisés
    INFO1_LEVEL = 25  # Entre INFO (20) et WARNING (30)
    INFO2_LEVEL = 23  # Entre INFO (20) et INFO1 (25)
    INFO3_LEVEL = 21  # Entre INFO (20) et INFO2 (23)

    # Color and style definitions using the colored module
    STYLES = {
        "h1": fg("orange_3") + attr("bold"),
        "h2": fg("dodger_blue_2") + attr("bold"),
        "h3": fg("purple_3") + attr("bold"),
        "text": fg("grey_69"),
        "warning": fg("dark_orange") + attr("bold"),
        "alert": fg("red_1") + attr("bold"),
        "error": fg("red_1") + attr("bold"),
    }

    def __init__(self, name="COD3S", level=logging.INFO, level_name=None):
        # Ajouter les niveaux personnalisés au module logging
        logging.addLevelName(self.INFO1_LEVEL, "INFO1")
        logging.addLevelName(self.INFO2_LEVEL, "INFO2")
        logging.addLevelName(self.INFO3_LEVEL, "INFO3")
        
        # Si level_name est fourni, convertir en niveau numérique
        if level_name is not None:
            level = self._get_level_from_name(level_name)
            self.level_name = level_name.upper()
        else:
            # Déterminer le nom du niveau à partir du niveau numérique
            self.level_name = self._get_name_from_level(level)
        
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

    def _get_level_from_name(self, level_name):
        """
        Convert a level name string to its corresponding numeric level.

        Args:
            level_name (str): Level name like "DEBUG", "INFO", "INFO1", "INFO2", "INFO3", "WARNING", "ERROR", "CRITICAL"

        Returns:
            int: Numeric level value

        Raises:
            ValueError: If the level name is not recognized
        """
        level_mapping = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "INFO3": self.INFO3_LEVEL,
            "INFO2": self.INFO2_LEVEL,
            "INFO1": self.INFO1_LEVEL,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        level_name_upper = level_name.upper()
        if level_name_upper not in level_mapping:
            available_levels = ", ".join(level_mapping.keys())
            raise ValueError(
                f"Unknown level name '{level_name}'. Available levels: {available_levels}"
            )

        return level_mapping[level_name_upper]

    def _get_name_from_level(self, level):
        """
        Convert a numeric level to its corresponding level name.
        
        Args:
            level (int): Numeric level value
            
        Returns:
            str: Level name string
        """
        level_mapping = {
            logging.DEBUG: "DEBUG",
            logging.INFO: "INFO",
            self.INFO3_LEVEL: "INFO3",
            self.INFO2_LEVEL: "INFO2",
            self.INFO1_LEVEL: "INFO1",
            logging.WARNING: "WARNING",
            logging.ERROR: "ERROR",
            logging.CRITICAL: "CRITICAL",
        }
        
        return level_mapping.get(level, "UNKNOWN")

    def update_formatter(self, format_string=None):
        """
        Update the logger formatter with a new format string.

        Args:
            format_string (str, optional): New format string for the logger.
                If None, uses the default format.
        """
        if format_string is None:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # Create new formatter
        new_formatter = logging.Formatter(format_string)

        # Update all handlers with the new formatter
        for handler in self.logger.handlers:
            handler.setFormatter(new_formatter)

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
        self.logger.log(self.INFO1_LEVEL, styled_msg)

    def info2(self, msg):
        styled_msg = self._style_text(msg, "h2")
        self.logger.log(self.INFO2_LEVEL, styled_msg)

    def info3(self, msg):
        styled_msg = self._style_text(msg, "h3")
        self.logger.log(self.INFO3_LEVEL, styled_msg)

    def warning(self, msg):
        styled_msg = self._style_text(msg, "warning")
        self.logger.warning(styled_msg)

    def error(self, msg):
        styled_msg = self._style_text(msg, "error")
        self.logger.error(styled_msg)

    def critical(self, msg):
        styled_msg = self._style_text(msg, "alert")
        self.logger.critical(styled_msg)
