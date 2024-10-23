from __future__ import annotations

import base64
import re
import zlib


def mask_pattern(text: str, pattern: str) -> str:
    return re.sub(pattern, lambda match: "*" * len(match.group()), text)


def mask_card_number(text: str) -> str:
    return mask_pattern(text, r'(?<=CardNumber=")\d+(?=\d{4}")')


def mask_series_code(text: str) -> str:
    return mask_pattern(text, r'(?<=SeriesCode=")\d+(?=")')


def compress_and_encode(text: str | bytes) -> str:
    text_bytes = text if isinstance(text, bytes) else text.encode()
    return base64.b64encode(zlib.compress(text_bytes)).decode()
