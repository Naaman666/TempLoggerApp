# -*- coding: utf-8 -*-
"""
Helper functions and utilities for Temperature Logger.
"""

import tkinter as tk
from tkinter import ttk
import json
import uuid
import os
import time
from typing import Dict, Any
from w1thermsensor import SensorNotReadyError
from functools import wraps

def sanitize_filename(name: str) -> str:
    """Sanitize filename by keeping only alphanumeric and allowed characters."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()

def generate_short_uuid() -> str:
    """Generate a 6-character UUID."""
    return str(uuid.uuid4())[:6]

def get_next_counter() -> int:
    """Get and increment the session counter."""
    try:
        with open("config/counter.json", "r") as f:
            data = json.load(f)
        counter = data.get("session_counter", 0) + 1
        with open("config/counter.json", "w") as f:
            json.dump({"session_counter": counter}, f)
        return counter
    except Exception as e:
        print(f"Counter error: {e}")
        return 1

def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open("config/config.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Config load error: {e}")
        return get_default_config()

def get_default_config() -> Dict[str, Any]:
    """Return default configuration."""
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
    """Decorator for retrying a function on specific exceptions."""
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
    """Ensure required directories exist."""
    os.makedirs(config["measurement_folder"], exist_ok=True)
    os.makedirs(config["config_folder"], exist_ok=True)
    os.makedirs("config", exist_ok=True)

def format_duration(seconds: float) -> str:
    """Format duration as hours, minutes, seconds."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:3d}h {minutes:2d}m {secs:2d}s"
