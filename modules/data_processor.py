# -*- coding: utf-8 -*-
"""
Data processor for handling data logging, storage, and export.
"""
import tkinter as tk
from tkinter import ttk
import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import threading
import atexit
from datetime import datetime
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .temp_logger_core import TempLoggerApp  # Adjust if needed

from .helpers import get_next_counter, generate_short_uuid, sanitize_filename, format_duration

class DataProcessor:
    """Handles data logging, limiting, and exporting."""
    
    def __init__(self, app: 'TempLoggerApp'):
        self.app = app
        self.data: List[List] = []
        self.lock = threading.Lock()
        self.current_session_folder = None
        self.session_counter = None
        self.session_uuid = None
        self.session_start_time = None
        self.session_end_time = None
        self.temp_session_folder = None
        # Register cleanup
        atexit.register(self.finalize_session_folder)

    def create_session_folder(self) -> str:
        """Create a temporary session folder, final name set at stop."""
        if self.session_counter is None:
            self.session_counter = get_next_counter()
            self.session_uuid = generate_short_uuid()
            self.session_start_time = datetime.now()
        
        timestamp = self.session_start_time.strftime("%Y-%m-%d|%H:%M:%S")
        base_name = sanitize_filename(self.app.measurement_name.get())
        
        # Temporary folder name (will be renamed at stop)
        folder_name = f"{base_name}-[AT:{self.session_counter}]-[START:{timestamp}]-[UUID:{self.session_uuid}]"
        folder_path = os.path.join(self.app.measurement_folder, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        self.temp_session_folder = folder_path
        self.current_session_folder = folder_path
        return folder_path

    def finalize_session_folder(self):
        """Rename folder with end timestamp."""
        if not self.session_end_time and self.session_start_time:
            self.session_end_time = datetime.now()
            
        start_timestamp = self.session_start_time.strftime("%Y-%m-%d|%H:%M:%S")
        end_timestamp = self.session_end_time.strftime("%Y-%m-%d|%H:%M:%S") if self.session_end_time else start_timestamp
        base_name = sanitize_filename(self.app.measurement_name.get())
        
        final_folder_name = f"{base_name}-[AT:{self.session_counter}]-[START:{start_timestamp}]-[END:{end_timestamp}]-[UUID:{self.session_uuid}]"
        final_folder_path = os.path.join(self.app.measurement_folder, final_folder_name)
        
        if self.temp_session_folder and os.path.exists(self.temp_session_folder):
            os.rename(self.temp_session_folder, final_folder_path)
            self.current_session_folder = final_folder_path

    def get_session_filename(self, base_name: str, extension: str) -> str:
        """Generate filename for current session."""
        if not self.current_session_folder:
            self.create_session_folder()
        
        start_timestamp = self.session_start_time.strftime("%Y-%m-%d|%H:%M:%S")
        end_timestamp = self.session_end_time.strftime("%Y-%m-%d|%H:%M:%S") if self.session_end_time else start_timestamp
        
        base_name = sanitize_filename(base_name)
        filename = f"{base_name}-[AT:{self.session_counter}]-[START:{start_timestamp}]-[END:{end_timestamp}]-[UUID:{self.session_uuid}].{extension}"
        return os.path.join(self.current_session_folder, filename)

    def reset_session(self):
        """Reset session data for new measurement."""
        self.session_counter = None
        self.session_uuid = None
        self.session_start_time = None
        self.session_end_time = None
        self.current_session_folder = None
        self.temp_session_folder = None
        with self.lock:
            self.data.clear()
        self.app.export_manager.reset_exports()

    def limit_log_lines(self):
        """Limit the number of lines in the log display."""
        # Not needed for Treeview
        pass

    def save_data(self, format_type: str, plot_formats: List[str] = None):
        """Save data to file in the specified format."""
        if not self.data:
            self.app.error_handler("Warning", "No data to export!")
            return
        
        try:
            if format_type == 'excel':
                if self.app.export_manager.check_overwrite('excel'):
                    filename = self.get_session_filename("temp_chart", "xlsx")
                    self._save_excel_with_chart(filename)
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
                plot_formats = plot_formats or ['png', 'pdf']
                filename_base = self.get_session_filename("temp_plot", "")
                for fmt in plot_formats:
                    if fmt == 'png':
                        filename = filename_base + 'png'
                        self.app.export_manager.mark_exported('plot')
                        self._save_plots(filename, None, fmt='png')
                    elif fmt == 'pdf':
                        filename = filename_base + 'pdf'
                        self.app.export_manager.mark_exported('plot')
                        self._save_plots(None, filename, fmt='pdf')
                        
            else:
                return
                
            if format_type != 'plot':
                self.app.log_to_display(f"Data exported to {filename}\n")
                
        except Exception as e:
            self.app.error_handler("Error", f"Export failed: {str(e)}")

    def _save_excel_with_chart(self, filename: str):
        """Save Excel file with embedded chart."""
        df = pd.DataFrame(self.data, columns=self.app.data_columns)
        
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Data', index=False)
            
            workbook = writer.book
            worksheet = writer.sheets['Data']
            
            # Create chart
            chart = workbook.add_chart({'type': 'line'})
            
            # Add series for each temperature column
            for i, col in enumerate(self.app.data_columns[3:], 3):  # Skip Type, Seconds, Timestamp
                chart.add_series({
                    'name': col,
                    'categories': ['Data', 1, 1, len(df), 1],  # Seconds column
                    'values': ['Data', 1, i, len(df), i],
                })
            
            chart.set_title({'name': 'Temperature Measurements'})
            chart.set_x_axis({'name': 'Time (seconds)'})
            chart.set_y_axis({'name': 'Temperature (°C)'})
            
            worksheet.insert_chart('F2', chart)

    def _save_plots(self, filename_png: str = None, filename_pdf: str = None, fmt: str = 'png'):
        """Save plots as PNG and/or PDF."""
        df = pd.DataFrame(self.data, columns=self.app.data_columns)
        plt.figure(figsize=(10, 6))
        for col in self.app.data_columns[3:]:  # Skip Type, Seconds, Timestamp
            if col in df.columns:
                valid_data = df.dropna(subset=[col])
                if not valid_data.empty:
                    plt.plot(valid_data['Seconds'], valid_data[col], label=col)
        
        plt.xlabel("Seconds")
        plt.ylabel("Temperature (°C)")
        plt.title("Temperature Logs")
        plt.legend()
        plt.grid(True)
        if filename_png:
            plt.savefig(filename_png, format='png')
        if filename_pdf:
            plt.savefig(filename_pdf, format='pdf')
        plt.close()
