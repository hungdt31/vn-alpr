"""VN-ALPR: Vietnamese license plate recognition."""

from alpr.postprocess.plate_format import normalize, parse_plate
from alpr.types import Detection, PlateEvent, PlateResult, PlateText

__all__ = ["Detection", "PlateEvent", "PlateResult", "PlateText", "normalize", "parse_plate"]
__version__ = "0.1.0"
