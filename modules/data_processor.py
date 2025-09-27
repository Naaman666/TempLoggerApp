# -*- coding: utf-8 -*-
"""
Data processor for handling data logging, storage, and export.
"""

import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import threading
from datetime import datetime
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .temp_logger_app import TempLoggerApp

from .helpers import get_next_counter, generate_short_uuid, sanitize_filename

class DataProcessor:
    """Handles data logging, limiting, and exporting."""
    
    def __init__(self, app: 'TempLoggerApp'):
        self.app = app
        self.data: List[List] = []
        self.lock = threading.Lock()
        self.current_session_folder = None

    def create_session_folder(self) -> str:
        """Create a new session folder with proper naming."""
        counter = get_next_counter()
        timestamp = datetime.now().strftime("%Y-%m-%d|%H:%M:%S")
        short_uuid = generate_short_uuid()
        base_name = sanitize_filename(self.app.measurement_name.get())
        
        folder_name = f"{base_name}[AT:{counter:03d}][{timestamp}][UUID:{short_uuid}]"
        folder_path = os.path.join(self.app.measurement_folder, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        self.current_session_folder = folder_path
        return folder_path

    def get_session_filename(self, base_name: str, extension: str) -> str:
        """Generate filename for current session."""
        if not self.current_session_folder:
            self.create_session_folder()
        
        counter = get_next_counter() - 1  # Use current counter
        timestamp = datetime.now().strftime("%Y-%m-%d|%H:%M:%S")
        short_uuid = generate_short_uuid()
        base_name = sanitize_filename(base_name)
        
        filename = f"{base_name}[AT:{counter:03d}][{timestamp}][UUID:{short_uuid}].{extension}"
        return os.path.join(self.current_session_folder, filename)

    def limit_log_lines(self):
        """Limit the number of lines in the log display."""
        if hasattr(self.app, 'log_display') and self.app.log_display:
            content = self.app.log_display.get("1.0", tk.END).splitlines()
            if len(content) > self.app.max_log_lines:
                self.app.log_display.delete("1.0", f"{len(content) - self.app.max_log_lines}.0")

    def save_data(self, format_type: str):
        """Save data to file in the specified format."""
        if not self.data:
            self.app.error_handler("Warning", "No data to export!")
            return
        
        try:
            if format_type == 'excel':
                if self.app.export_manager.check_overwrite('excel'):
                    filename = self.get_session_filename("temp_data", "xlsx")
                    df = pd.DataFrame(self.data, columns=self.app.data_columns)
                    df.to_excel(filename, index=False)
                    self.app.export_manager.mark_exported('excel')
                    
            elif format_type == 'csv':
                if self.app.export_manager.check_overwrite('csv'):
                    filename = self.get_session_filename("temp_data", "csv")
                    df = pd.DataFrame(self.data, columns=self.app.data_columns)
                    df.to_csv(filename, index=False)
                    self.app.export_manager.mark_exported('csv')
                    
            elif format_type == 'json':
                if self.app.export_manager.check_overwrite('json'):
                    filename = self.get_session_filename("temp_data", "json")
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump([dict(zip(self.app.data_columns, row)) for row in self.data], f, indent=2)
                    self.app.export_manager.mark_exported('json')
                    
            elif format_type == 'plot':
                filename_png = self.get_session_filename("temp_plot", "png")
                filename_pdf = self.get_session_filename("temp_plot", "pdf")
                
                plt.figure(figsize=(10, 6))
                for col in self.app.data_columns[3:]:  # Skip Type, Seconds, Timestamp
                    col_data = [row[self.app.data_columns.index(col)] for row in self.data if row[self.app.data_columns.index(col)] is not None]
                    time_data = [row[1] for row in self.data if row[self.app.data_columns.index(col)] is not None]
                    if col_data:
                        plt.plot(time_data, col_data, label=col)
                
                plt.xlabel("Seconds")
                plt.ylabel("Temperature (°C)")
                plt.title("Temperature Logs")
                plt.legend()
                plt.grid(True)
                plt.savefig(filename_png)
                plt.savefig(filename_pdf)
                plt.close()
                
                self.app.log_to_display(f"Plots saved to {filename_png} and {filename_pdf}\n")
            else:
                return
                
            if format_type != 'plot':
                self.app.log_to_display(f"Data exported to {filename}\n")
                
        except Exception as e:
            self.app.error_handler("Error", f"Export failed: {str(e)}")