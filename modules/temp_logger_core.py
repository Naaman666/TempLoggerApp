# -*- coding: utf-8 -*-
"""
Temperature Logger Core Application Class.
"""

import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import time
import os
import json
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui_builder import GUIBuilder
    from .sensor_manager import SensorManager
    from .data_processor import DataProcessor
    from .export_manager import ExportManager

from .helpers import load_config, ensure_directories

class TempLoggerApp:
    """Main application class."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = load_config()
        ensure_directories(self.config)
        
        # Store config values
        self.default_log_interval = self.config["default_log_interval"]
        self.default_view_interval = self.config["default_view_interval"]
        self.default_start_threshold = self.config["default_start_threshold"]
        self.default_stop_threshold = self.config["default_stop_threshold"]
        self.max_log_lines = self.config["max_log_lines"]
        self.measurement_folder = self.config["measurement_folder"]
        self.config_folder = self.config["config_folder"]
        
        # Initialize components
        self.initialize_components()
        
        # Runtime variables
        self.running_event = threading.Event()
        self.log_file = None
        self.view_timer = None
        self.log_timer = None
        self.measure_start_time = None
        self.measure_duration_sec = None
        self.data_columns = []
        self.lock = threading.Lock()
        self.loaded_config = None

        # Initialize sensors after GUI is ready
        self.root.after(100, self.sensor_manager.init_sensors)

    def initialize_components(self):
        """Initialize all application components."""
        from .gui_builder import GUIBuilder
        from .sensor_manager import SensorManager
        from .data_processor import DataProcessor
        from .export_manager import ExportManager
        
        self.gui = GUIBuilder(self.root, self)
        self.sensor_manager = SensorManager(self)
        self.data_processor = DataProcessor(self)
        self.export_manager = ExportManager()

    def log_to_display(self, message: str):
        """Safely log message to display with thread safety."""
        if hasattr(self, 'log_display') and self.log_display:
            self.log_display.insert(tk.END, message)
            self.log_display.see(tk.END)
            self.data_processor.limit_log_lines()

    def validate_positive_int(self, value: str, field: str) -> bool:
        """Validate that the entry is a positive integer."""
        if not value:
            return True
        try:
            val = int(value)
            if val <= 0:
                raise ValueError
            if field == 'log_interval':
                self.default_log_interval = val
            elif field == 'view_interval':
                self.default_view_interval = val
            return True
        except ValueError:
            return False

    def validate_non_negative_float(self, value: str, field: str) -> bool:
        """Validate that the entry is a non-negative float."""
        if not value:
            return True
        try:
            val = float(value)
            if val < 0:
                raise ValueError
            if field == 'duration':
                self.measure_duration_sec = val * 3600 if val > 0 else None
            return True
        except ValueError:
            return False

    def validate_float(self, value: str, field: str) -> bool:
        """Validate that the entry is a float."""
        if not value:
            return True
        try:
            val = float(value)
            if field == 'start_threshold':
                self.default_start_threshold = val
            elif field == 'stop_threshold':
                if val <= self.default_start_threshold:
                    raise ValueError("Stop threshold must be greater than start threshold")
                self.default_stop_threshold = val
            return True
        except ValueError as e:
            self.error_handler("Error", str(e))
            return False

    def error_handler(self, title: str, message: str):
        """Display an error or warning message."""
        messagebox.showinfo(title, message)

    def toggle_all_sensors(self):
        """Toggle all sensors on/off."""
        self.sensor_manager.toggle_all_sensors()

    def start_logging(self):
        """Start the logging process."""
        if self.running_event.is_set():
            self.error_handler("Warning", "Logging already in progress!")
            return
        
        # Create session folder and clear previous data
        session_folder = self.data_processor.create_session_folder()
        with self.data_processor.lock:
            self.data_processor.data.clear()
        
        self.running_event.set()
        self.gui.start_button.config(state="disabled")
        self.gui.stop_button.config(state="normal")
        self.gui.excel_button.config(state="disabled")
        self.gui.csv_button.config(state="disabled")
        self.gui.json_button.config(state="disabled")

        # Open log file in session folder
        log_filename = self.data_processor.get_session_filename("temp_log", "txt")
        try:
            self.log_file = open(log_filename, "w", encoding='utf-8')
            self.log_to_display(f"Logging started, session folder: {session_folder}\n")
            self.log_to_display(f"Log file: {log_filename}\n")
        except Exception as e:
            self.error_handler("Error", f"Failed to open log file: {str(e)}")
            self.running_event.clear()
            self.gui.start_button.config(state="normal")
            self.gui.stop_button.config(state="disabled")
            return

        # Schedule first timers
        self.schedule_view_update()
        self.schedule_log_update()
        if self.measure_duration_sec is not None:
            self.measure_start_time = time.time()
            self.root.after(1000, self.update_progress, time.time())

    def stop_logging(self):
        """Stop the logging process."""
        self.running_event.clear()
        if self.view_timer:
            self.view_timer.cancel()
        if self.log_timer:
            self.log_timer.cancel()
            
        self.gui.start_button.config(state="normal")
        self.gui.stop_button.config(state="disabled")
        self.gui.excel_button.config(state="normal")
        self.gui.csv_button.config(state="normal")
        self.gui.json_button.config(state="normal")
        
        if self.log_file:
            try:
                self.log_file.close()
            except Exception as e:
                self.error_handler("Error", f"Failed to close log file: {str(e)}")
            self.log_file = None
        
        # Hide progress bar
        self.progress_bar.pack_forget()
        self.progress_label.pack_forget()

        # Generate plots if checkbox is checked and we have data
        if self.generate_output_var.get():
            if self.data_processor.data:
                self.data_processor.save_data('plot')
                self.log_to_display("Plots generated successfully\n")
            else:
                self.log_to_display("No data collected, skipping plot generation\n")

    def schedule_view_update(self):
        if self.running_event.is_set():
            self.view_timer = threading.Timer(int(self.view_interval.get()), self.view_update)
            self.view_timer.start()

    def schedule_log_update(self):
        if self.running_event.is_set():
            self.log_timer = threading.Timer(int(self.log_interval.get()), self.log_update)
            self.log_timer.start()

    def view_update(self):
        """Update GUI view and collect data."""
        if not self.running_event.is_set():
            return
            
        current_time = time.time()
        seconds = int(current_time)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with self.lock:
            temps_dict = self.sensor_manager.read_sensors()
        temps_list = [temps_dict[sid] for sid in self.sensor_manager.sensor_ids]
        
        # Convert temperatures to floats
        processed_temps = []
        for temp in temps_list:
            if temp is not None:
                try:
                    processed_temps.append(float(temp))
                except (ValueError, TypeError):
                    processed_temps.append(None)
            else:
                processed_temps.append(None)
        
        # Create data row and add to data list
        data_row = ["VIEW", seconds, timestamp] + processed_temps
        with self.data_processor.lock:
            self.data_processor.data.append(data_row)
        
        view_line = f"VIEW,{seconds},{timestamp}," + ",".join([str(t) if t is not None else 'ERROR' for t in processed_temps])
        self.log_to_display(view_line + "\n")
        self.schedule_view_update()

    def log_update(self):
        """Log to file and collect data."""
        if not self.running_event.is_set():
            return
            
        current_time = time.time()
        seconds = int(current_time)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with self.lock:
            temps_dict = self.sensor_manager.read_sensors()
        temps_list = [temps_dict[sid] for sid in self.sensor_manager.sensor_ids]
        
        # Convert temperatures to floats
        processed_temps = []
        for temp in temps_list:
            if temp is not None:
                try:
                    processed_temps.append(float(temp))
                except (ValueError, TypeError):
                    processed_temps.append(None)
            else:
                processed_temps.append(None)
        
        # Create data row and add to data list
        data_row = ["LOG", seconds, timestamp] + processed_temps
        with self.data_processor.lock:
            self.data_processor.data.append(data_row)
        
        if self.log_file:
            log_line = f"LOG,{seconds},{timestamp}," + ",".join([str(t) if t is not None else 'ERROR' for t in processed_temps])
            try:
                self.log_file.write(log_line + "\n")
                self.log_file.flush()
            except Exception as e:
                self.error_handler("Error", f"Failed to write to log file: {str(e)}")
        self.schedule_log_update()

    def save_data(self, format_type: str):
        """Save data using DataProcessor."""
        self.data_processor.save_data(format_type)

    def update_progress(self, current_time: float):
        """Update progress bar and label for timed measurements."""
        if self.measure_duration_sec is not None and self.measure_start_time is not None:
            elapsed = current_time - self.measure_start_time
            progress = (elapsed / self.measure_duration_sec) * 100
            remaining_sec = max(0, self.measure_duration_sec - elapsed)
            hours, rem = divmod(int(remaining_sec), 3600)
            minutes, seconds = divmod(rem, 60)
            remaining_str = f"Remaining: {hours} hr {minutes} min {seconds} sec"
            end_time = datetime.fromtimestamp(self.measure_start_time + self.measure_duration_sec)
            end_time_str = f"Expected completion: {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
            self.progress_bar['value'] = min(progress, 100)
            self.progress_label['text'] = f"{remaining_str} | {end_time_str}"
            self.progress_bar.pack(fill=tk.X, pady=2)
            self.progress_label.pack(fill=tk.X, pady=2)
        else:
            self.progress_bar.pack_forget()
            self.progress_label.pack_forget()
            
        if self.running_event.is_set():
            self.root.after(1000, self.update_progress, time.time())

    def update_loop(self):
        """Main loop for checking start/stop conditions."""
        measurement_started = False

        def check_conditions():
            if not self.running_event.is_set():
                return
                
            current_time = time.time()
            with self.lock:
                temps_dict = self.sensor_manager.read_sensors()
            temps_list = [temps_dict[sid] for sid in self.sensor_manager.sensor_ids]

            nonlocal measurement_started
            if not measurement_started:
                if any(temps_dict.get(sid, 0) is not None and temps_dict[sid] >= float(self.start_threshold.get()) for sid in self.sensor_manager.sensor_ids):
                    measurement_started = True
                    self.measure_start_time = current_time
                    self.log_to_display("Measurement started due to condition\n")

            if measurement_started:
                # Stop on temperature threshold
                if any(t is not None and t >= float(self.stop_threshold.get()) for t in temps_list):
                    self.log_to_display("Measurement stopped due to temperature threshold\n")
                    self.stop_logging()
                    return

                # Stop on duration
                if self.measure_duration_sec is not None and current_time - self.measure_start_time >= self.measure_duration_sec:
                    self.log_to_display("Measurement stopped due to duration\n")
                    self.stop_logging()
                    return

            # Reschedule condition check
            self.root.after(100, check_conditions)

        # Start condition checking
        self.root.after(100, check_conditions)

    def save_sensor_config(self):
        """Save sensor configuration to a JSON file."""
        try:
            filename = filedialog.asksaveasfilename(
                initialdir=self.config_folder,
                title="Save sensor configuration",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
            if not filename:
                return
                
            active_sensors = [sid for sid, var in self.sensor_manager.sensor_vars.items() if var.get()]
            config = {
                "active_sensors": active_sensors,
                "sensor_names": self.sensor_manager.sensor_names,
                "start_threshold": float(self.start_threshold.get()),
                "stop_threshold": float(self.stop_threshold.get()),
                "log_interval": int(self.log_interval.get()),
                "view_interval": int(self.view_interval.get()),
                "duration": float(self.duration.get()),
                "measurement_name": self.measurement_name.get()
            }
            
            with open(filename, "w", encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.log_to_display(f"Sensor configuration saved: {filename}\n")
            
        except Exception as e:
            self.error_handler("Error", f"Saving configuration failed: {str(e)}")

    def load_sensor_config(self):
        """Load sensor configuration from a JSON file and apply immediately."""
        try:
            filename = filedialog.askopenfilename(
                initialdir=self.config_folder,
                title="Load sensor configuration",
                filetypes=[("JSON files", "*.json")]
            )
            if not filename:
                return
                
            with open(filename, "r", encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            # Apply configuration
            active_sensors = loaded_config.get("active_sensors", [])
            for sid, var in self.sensor_manager.sensor_vars.items():
                var.set(sid in active_sensors)
            
            self.sensor_manager.sensor_names = loaded_config.get("sensor_names", self.sensor_manager.sensor_names)
            self.start_threshold.set(str(loaded_config.get("start_threshold", self.default_start_threshold)))
            self.stop_threshold.set(str(loaded_config.get("stop_threshold", self.default_stop_threshold)))
            self.log_interval.set(str(loaded_config.get("log_interval", self.default_log_interval)))
            self.view_interval.set(str(loaded_config.get("view_interval", self.default_view_interval)))
            self.duration.set(str(loaded_config.get("duration", 0.0)))
            self.measurement_name.set(loaded_config.get("measurement_name", "temptestlog"))
            
            # Update checkbutton texts
            for sid, chk in self.sensor_manager.sensor_checkbuttons.items():
                chk.config(text=self.sensor_manager.sensor_names[sid])
            
            self.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_manager.sensor_names[sid] for sid in self.sensor_manager.sensor_ids]
            self.log_to_display(f"Sensor configuration loaded and applied: {filename}\n")
            self.sensor_manager.list_sensors_status()
            
        except Exception as e:
            self.error_handler("Error", f"Loading configuration failed: {str(e)}")

    def on_closing(self):
        """Handle application shutdown."""
        self.stop_logging()
        self.root.destroy()
