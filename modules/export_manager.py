# -*- coding: utf-8 -*-
"""
Export manager for handling file exports and overwrite protection.
"""

import tkinter.messagebox as messagebox
from typing import Dict

class ExportManager:
    """Manages export states to prevent duplicates and handle overwrites."""
    
    def __init__(self):
        self.exported_formats: Dict[str, bool] = {
            'excel': False, 
            'csv': False, 
            'json': False
        }

    def check_overwrite(self, format_type: str) -> bool:
        """Check if format was exported and prompt for overwrite."""
        if self.exported_formats.get(format_type, False):
            return messagebox.askyesno(
                "Overwrite Confirmation", 
                f"{format_type.upper()} file already exported. Overwrite?"
            )
        return True

    def mark_exported(self, format_type: str):
        """Mark format as exported."""
        self.exported_formats[format_type] = True

    def reset_exports(self):
        """Reset all export states."""
        for format_type in self.exported_formats:
            self.exported_formats[format_type] = False