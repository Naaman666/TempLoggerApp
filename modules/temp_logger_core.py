# -*- coding: utf-8 -*-
"""
Temperature Logger Core Application Class.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import os
import json
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional, Any
# Hozzáadva a glob a mappa kereséséhez
import glob

if TYPE_CHECKING:
    from .gui_builder import GUIBuilder
    from .sensor_manager import SensorManager
    from .data_processor import DataProcessor
    from .export_manager import ExportManager

from .helpers import load_config, ensure_directories, format_duration

class TempLoggerApp:
    """Main application class."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = load_config()
        ensure_directories(self.config)
        
        self.default_log_interval = self.config["default_log_interval"]
        self.default_view_interval = self.config["default_view_interval"]
        self.max_log_lines = self.config["max_log_lines"]
        self.measurement_folder = self.config["measurement_folder"]
        self.config_folder = self.config["config_folder"]
        
        self.running_event = threading.Event()
        self.log_file = None
        self.view_timer = None
        self.log_thread: Optional[threading.Thread] = None
        self.measure_start_time = None
        self.session_start_time = None
        self.data_columns = []
        self.lock = threading.Lock()
        self.loaded_config = None
        
        # Tkinter variables
        self.measurement_name = tk.StringVar(value="Test_Measurement")
        self.log_interval = tk.IntVar(value=self.default_log_interval)
        self.view_interval = tk.IntVar(value=self.default_view_interval)
        self.generate_output_var = tk.BooleanVar(value=True)

        self.duration_enabled = tk.BooleanVar(value=False)
        self.duration_days = tk.StringVar(value="0")
        self.duration_hours = tk.StringVar(value="0")
        self.duration_minutes = tk.StringVar(value="0")
        
        self.temp_start_enabled = tk.BooleanVar(value=False)
        self.temp_stop_enabled = tk.BooleanVar(value=False)
        self.start_conditions: List[Dict[str, Any]] = []
        self.stop_conditions: List[Dict[str, Any]] = []

        # Module initialization (Import inside to avoid circular dependency issues)
        from .sensor_manager import SensorManager
        from .data_processor import DataProcessor
        from .gui_builder import GUIBuilder
        from .export_manager import ExportManager
        
        self.data_processor = DataProcessor(self)
        self.sensor_manager = SensorManager(self)
        self.export_manager = ExportManager()
        self.gui = GUIBuilder(root, self)
        
        self.load_configuration()
        self.sensor_manager.init_sensors()

    def update_loop(self):
        """Timer for refreshing the GUI with live data."""
        if self.running_event.is_set():
            # Run the live data update function
            self.data_processor.update_live_data()
            
            # Check for duration stop condition
            if self.duration_enabled.get():
                duration_seconds = self.data_processor.get_total_duration_seconds()
                if duration_seconds is not None:
                    elapsed = time.time() - self.measure_start_time
                    if elapsed >= duration_seconds:
                        self.log_to_display("STOP CONDITION: Fixed duration reached.\\n")
                        self.stop_logging()
                        return # Exit the loop immediately
            
            # Check for temperature stop condition
            if self.temp_stop_enabled.get():
                if self.data_processor.check_conditions(self.stop_conditions):
                    self.log_to_display("STOP CONDITION: Temperature condition met.\\n")
                    self.stop_logging()
                    return # Exit the loop immediately


        # Schedule the next run
        view_interval = self.view_interval.get()
        if view_interval < 1: view_interval = 1 # Minimum 1 second for GUI refresh
        self.view_timer = self.root.after(view_interval * 1000, self.update_loop)

    def start_logging(self):
        """Start the measurement and logging thread."""
        if self.running_event.is_set():
            self.log_to_display("Logging is already running.\\n")
            return
        
        # Check start conditions if enabled
        if self.temp_start_enabled.get():
            self.log_to_display("Waiting for START condition...\\n")
            self.gui.update_start_stop_buttons(True) # Set to Running state
            # A view_timer fogja futtatni az update_loop-ot, ami ellenőrzi a feltételeket
            self.measure_start_time = time.time() # Mérés indítási idő rögzítése
            self.log_thread = threading.Thread(target=self._wait_for_start)
            self.log_thread.daemon = True
            self.log_thread.start()
        else:
            self._start_measurement_thread()

    def _wait_for_start(self):
        """Wait loop for temperature start condition."""
        while not self.running_event.is_set():
            if self.data_processor.check_conditions(self.start_conditions):
                self.root.after(0, self._start_measurement_thread)
                return
            
            # Wait for 1 second before checking again
            time.sleep(1)

    def _start_measurement_thread(self):
        """Internal method to truly start logging after conditions are met or immediately."""
        if self.running_event.is_set():
            return
            
        try:
            self.data_processor.initialize_session()
            self.running_event.set()
            self.measure_start_time = time.time()
            self.session_start_time = datetime.now()
            
            self.log_to_display(f"LOGGING STARTED at {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}\\n")
            
            # Start the main logging thread
            self.log_thread = threading.Thread(target=self.data_processor.log_data_worker)
            self.log_thread.daemon = True
            self.log_thread.start()
            
            # Update GUI buttons (This call also happens in start_logging, but ensures correct state)
            self.gui.update_start_stop_buttons(True)
            self.log_to_display(f"Measurement folder: {self.data_processor.current_session_folder}\\n")

        except Exception as e:
            self.error_handler("Start Error", f"Failed to start logging: {str(e)}")
            self.running_event.clear()
            self.gui.update_start_stop_buttons(False)

    def stop_logging(self):
        """Stop the measurement and start export process."""
        if not self.running_event.is_set():
            if self.log_thread and self.log_thread.is_alive():
                # Esetleg a _wait_for_start van még futásban
                self.running_event.set() 
                self.log_thread.join(timeout=1)
                self.log_thread = None
            self.log_to_display("Logging is already stopped or failed to start.\\n")
            self.gui.update_start_stop_buttons(False)
            return

        self.running_event.clear()
        self.gui.update_start_stop_buttons(False)
        self.log_to_display("LOGGING STOPPED. Preparing export...\\n")

        # Kill the logging thread first
        if self.log_thread:
            self.log_thread.join(timeout=5)
            self.log_thread = None

        # Start export in a separate thread to prevent GUI freeze
        export_thread = threading.Thread(target=self._run_export_process)
        export_thread.daemon = True
        export_thread.start()
        
    def _run_export_process(self):
        """Internal method to manage export thread and GUI updates."""
        try:
            # 1. Show progress bar and change cursor
            self.root.after(0, self.gui.show_export_progress)
            
            # 2. Finalize log file and set end time
            self.data_processor.finalize_session()
            
            # 3. Export data if enabled
            if self.generate_output_var.get():
                self.root.after(0, lambda: self.gui.update_progress(10))
                self.data_processor.export_data(self.root, self.gui.update_progress)

            # 4. Hide progress bar and restore cursor
            self.root.after(0, self.gui.hide_export_progress)
            self.log_to_display("Export complete.\\n")
            
            # 5. Open folder automatically (optional)
            # self.root.after(0, self.open_last_measurement_folder)

        except Exception as e:
            self.root.after(0, self.gui.hide_export_progress)
            self.error_handler("Export Error", f"Export failed: {str(e)}")

    def open_last_measurement_folder(self):
        """
        Opens the folder of the most recently finished measurement session 
        (the one with the highest AT:x number).
        """
        # JAVÍTÁS: Mappa keresési logika a legmagasabb AT:x sorszám alapján
        try:
            # Mintázat a mérésmappa nevére (pl. 231026_145000_AT:12_MyTest)
            search_pattern = os.path.join(self.measurement_folder, '*_AT:*')
            
            # Megkeressük az összes mappát, ami illeszkedik a mintázatra
            folders = glob.glob(search_pattern)
            
            if not folders:
                self.log_to_display("No measurement folders found with the AT:X pattern in the measurement directory.\\n")
                return

            # Elemzés a sorszám alapján
            last_folder = None
            max_counter = -1
            
            for folder_path in folders:
                folder_name = os.path.basename(folder_path)
                # Keresünk AT:X mintát, ahol X egy szám
                parts = folder_name.split('_')
                counter_part = next((part for part in parts if part.startswith('AT:')), None)
                
                if counter_part:
                    try:
                        counter = int(counter_part.split(':')[-1])
                        if counter > max_counter:
                            max_counter = counter
                            last_folder = folder_path
                    except ValueError:
                        # Ha az AT:X rossz formátumú, kihagyjuk
                        continue

            if last_folder and os.path.isdir(last_folder):
                os.startfile(last_folder) if os.name == 'nt' else os.system(f'xdg-open "{last_folder}"')
                self.log_to_display(f"Opened last measurement folder: {os.path.basename(last_folder)}\\n")
            else:
                self.log_to_display("Could not determine the latest measurement folder.\\n")

        except Exception as e:
            self.error_handler("Folder Error", f"Failed to open last measurement folder: {str(e)}")
            
    def log_to_display(self, message: str):
        """Log message to the application's message box."""
        self.root.after(0, lambda: self._update_log_messages(message))

    def _update_log_messages(self, message: str):
        """Thread-safe update of the scrolled text widget."""
        log_widget = self.gui.app.log_messages
        log_widget.config(state=tk.NORMAL)
        log_widget.insert(tk.END, message)
        
        # Limit the number of lines
        line_count = int(log_widget.index('end-1c').split('.')[0])
        if line_count > self.max_log_lines:
            log_widget.delete('1.0', f'{line_count - self.max_log_lines}.0')
            
        log_widget.see(tk.END)
        log_widget.config(state=tk.DISABLED)

    def load_configuration(self):
        """Load configuration from JSON and apply settings."""
        try:
            self.loaded_config = load_config()
            
            self.measurement_name.set(self.loaded_config.get("default_name", "Test_Measurement"))
            self.log_interval.set(self.loaded_config.get("default_log_interval", self.default_log_interval))
            self.view_interval.set(self.loaded_config.get("default_view_interval", self.default_view_interval))
            
            self.duration_enabled.set(self.loaded_config.get("duration_enabled", False))
            
            duration_s = self.loaded_config.get("fixed_duration_seconds", 0)
            self.duration_days.set(str(duration_s // 86400))
            self.duration_hours.set(str((duration_s % 86400) // 3600))
            self.duration_minutes.set(str((duration_s % 3600) // 60))
            
            self.temp_start_enabled.set(self.loaded_config.get("temp_start_enabled", False))
            self.temp_stop_enabled.set(self.loaded_config.get("temp_stop_enabled", False))
            
            self.start_conditions = self.loaded_config.get("start_conditions", [])
            self.stop_conditions = self.loaded_config.get("stop_conditions", [])

            # Legacy threshold conversion (if conditions are empty but thresholds exist)
            if not self.start_conditions and self.loaded_config.get("start_threshold") is not None:
                self._convert_legacy_thresholds(self.loaded_config)

            # GUI condition row creation (must be called after loading)
            try:
                self.gui.load_conditions_to_rows(self.start_conditions, 'start')
                self.gui.load_conditions_to_rows(self.stop_conditions, 'stop')
            except AttributeError:
                self.log_to_display("Warning: GUI conditions load method not available.\\n")
            
            self.gui.populate_condition_checkboxes()
            
        except Exception as e:
            self.error_handler("Error", f"Loading configuration failed: {str(e)}")

    def _convert_legacy_thresholds(self, loaded_config: Dict):
        """Convert old single threshold settings to the new conditions format."""
        all_sensors = self.sensor_manager.sensor_ids
        start_thresh = loaded_config.get("start_threshold", 25.0)
        stop_thresh = loaded_config.get("stop_threshold", 30.0)
        
        if not all_sensors:
            self.log_to_display("No sensors found to apply legacy conditions.\\n")
            return
        
        self.start_conditions = [{
            'sensors': all_sensors,
            'operator': '>',
            'threshold': start_thresh,
            'logic': None
        }]
        
        self.stop_conditions = [{
            'sensors': all_sensors,
            'operator': '<=',
            'threshold': stop_thresh,
            'logic': None
        }]
        
        self.log_to_display("Legacy thresholds converted to conditions.\\n")

    def on_closing(self):
        """Handle application shutdown."""
        self.stop_logging()
        self.root.destroy()

    def error_handler(self, title: str, message: str):
        """Handle errors with messagebox."""
        messagebox.showerror(title, message)
