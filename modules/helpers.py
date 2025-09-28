# -*- coding: utf-8 -*-
"""
Helper functions for Temperature Logger.
"""

import tkinter as tk
from tkinter import ttk
import json
import uuid
import os
import time
from typing import Dict, Any, List
from w1thermsensor import SensorNotReadyError
from functools import wraps

def sanitize_filename(name: str) -> str:
    """Sanitize filename."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()

def generate_short_uuid() -> str:
    """Generate short UUID."""
    return str(uuid.uuid4())[:6]

def get_next_counter() -> int:
    """Get next counter."""
    try:
        with open("config/counter.json", "r") as f:
            data = json.load(f)
        counter = data.get("session_counter", 0) + 1
        with open("config/counter.json", "w") as f:
            json.dump({"session_counter": counter}, f)
        return counter
    except Exception:
        return 1

def load_config() -> Dict[str, Any]:
    """Load config."""
    try:
        with open("config/config.json", "r") as f:
            return json.load(f)
    except Exception:
        return get_default_config()

def get_default_config() -> Dict[str, Any]:
    """Default config."""
    return {
        "default_log_interval": 10,
        "default_view_interval": 3,
        "default_start_threshold": 22.0,
        "default_stop_threshold": 30.0,
        "max_log_lines": 500,
        "measurement_folder": "TestResults",
        "config_folder": "SensorConfigs"
    }

def retry(max_attempts: int = 5, delay: float = 0.1):
    """Retry decorator."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except SensorNotReadyError:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

def ensure_directories(config: Dict[str, Any]):
    """Ensure dirs."""
    os.makedirs(config["measurement_folder"], exist_ok=True)
    os.makedirs(config["config_folder"], exist_ok=True)
    os.makedirs("config", exist_ok=True)

def format_duration(seconds: float) -> str:
    """Format duration."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:3d}h {minutes:2d}m {secs:2d}s"

# New for conditions
def sanitize_sensor_list(sensors: List[str], available_ids: List[str]) -> List[str]:
    """Sanitize and validate sensor list."""
    return [sid for sid in sensors if sid in available_ids]

def evaluate_operator(temp: Optional[float], thresh: float, op: str) -> bool:
    """Evaluate temp op thresh."""
    if temp is None:
        return False
    if op == '>': return temp > thresh
    if op == '<': return temp < thresh
    if op == '>=': return temp >= thresh
    if op == '<=': return temp <= thresh
    if op == '=': return abs(temp - thresh) < 0.1  # Tolerance for float eq
    return False
