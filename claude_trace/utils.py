"""
Utility functions for Claude Code local tracing.
"""

import re
from datetime import datetime
from typing import Optional


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse an ISO 8601 timestamp string to datetime.
    
    Handles various formats:
    - 2025-02-04T10:30:00Z
    - 2025-02-04T10:30:00.123Z
    - 2025-02-04T10:30:00.123456Z
    
    Args:
        timestamp_str: ISO 8601 timestamp string
        
    Returns:
        datetime object
    """
    if not timestamp_str:
        return datetime.now()
    
    # Remove trailing Z and replace with +00:00 for parsing
    ts = timestamp_str.rstrip('Z')
    
    # Try different formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",  # With microseconds
        "%Y-%m-%dT%H:%M:%S",     # Without microseconds
        "%Y-%m-%d %H:%M:%S.%f",  # Space separator with microseconds
        "%Y-%m-%d %H:%M:%S",     # Space separator without microseconds
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    
    # Fallback: try to extract just the date/time parts
    match = re.match(r'(\d{4})-(\d{2})-(\d{2})T?(\d{2}):(\d{2}):(\d{2})', timestamp_str)
    if match:
        return datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            int(match.group(4)),
            int(match.group(5)),
            int(match.group(6))
        )
    
    # Last resort: return current time
    return datetime.now()


def format_duration(ms: Optional[int]) -> str:
    """
    Format a duration in milliseconds to a human-readable string.
    
    Args:
        ms: Duration in milliseconds
        
    Returns:
        Formatted string (e.g., "2.3s", "150ms", "1m 30s")
    """
    if ms is None:
        return "N/A"
    
    if ms < 1000:
        return f"{ms}ms"
    
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    if minutes < 60:
        return f"{minutes}m {remaining_seconds:.1f}s"
    
    hours = int(minutes // 60)
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes}m {remaining_seconds:.0f}s"


def format_tokens(count: int) -> str:
    """
    Format a token count with thousands separators.
    
    Args:
        count: Token count
        
    Returns:
        Formatted string (e.g., "1,234")
    """
    return f"{count:,}"


def format_percentage(value: float) -> str:
    """
    Format a percentage value.
    
    Args:
        value: Percentage value (0-100)
        
    Returns:
        Formatted string (e.g., "42.5%")
    """
    return f"{value:.1f}%"


def format_bytes(size: int) -> str:
    """
    Format a byte size to human-readable string.
    
    Args:
        size: Size in bytes
        
    Returns:
        Formatted string (e.g., "2.4KB", "1.5MB")
    """
    if size < 1024:
        return f"{size}B"
    
    size_kb = size / 1024.0
    if size_kb < 1024:
        return f"{size_kb:.1f}KB"
    
    size_mb = size_kb / 1024.0
    if size_mb < 1024:
        return f"{size_mb:.1f}MB"
    
    size_gb = size_mb / 1024.0
    return f"{size_gb:.2f}GB"


def truncate_string(s: str, max_length: int = 80, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.
    
    Args:
        s: String to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated string
    """
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def clean_model_name(model: str) -> str:
    """
    Clean up a model name by removing date suffixes.
    
    Args:
        model: Full model name (e.g., "claude-sonnet-4-5-20250929")
        
    Returns:
        Cleaned model name (e.g., "claude-sonnet-4-5")
    """
    if not model:
        return "unknown"
    
    # Remove date suffix (YYYYMMDD pattern at the end)
    cleaned = re.sub(r'-\d{8}$', '', model)
    return cleaned


def generate_id() -> str:
    """
    Generate a unique ID.
    
    Returns:
        UUID-like string
    """
    import uuid
    return str(uuid.uuid4())


def safe_json_loads(s: str) -> Optional[dict]:
    """
    Safely parse a JSON string, returning None on error.
    
    Args:
        s: JSON string
        
    Returns:
        Parsed dictionary or None
    """
    import json
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


def get_nested(data: dict, *keys, default=None):
    """
    Safely get a nested value from a dictionary.
    
    Args:
        data: Dictionary to search
        *keys: Keys to traverse
        default: Default value if not found
        
    Returns:
        Value at the nested path or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
        if current is None:
            return default
    return current
