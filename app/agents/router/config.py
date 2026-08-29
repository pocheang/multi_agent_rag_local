"""Router module configuration."""

import os
from typing import Final

# Confidence calibration
ENABLE_CALIBRATION: Final[bool] = os.getenv("ENABLE_CALIBRATION", "false").lower() == "true"

# Web route control
ENABLE_WEB_ROUTE_DOWNGRADE: Final[bool] = os.getenv("ENABLE_WEB_ROUTE_DOWNGRADE", "false").lower() == "true"
