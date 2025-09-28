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
from typing import TYPE_CHECKING

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
        self.session_start_time = None
        self.data_columns = []
        self.lock = threading.Lock()
        self.loaded_config = None
        self.temp_control_enabled = tk.BooleanVar(value=False)
        self.measure_duration_sec = None
        self.duration_enabled = tk.BooleanVar(value=False)
        self.duration_minutes = tk.StringVar(value="0")
        self.duration_hours = tk.StringVar(value="0")
        self.duration_days = tk.StringVar(value="0")
        self.generate_output_var = tk.BooleanVar(value=True)
        self.log_interval = tk.StringVar(value=str(self.default_log_interval))
        self.view_interval = tk.StringVar(value=str(self.default_view_interval))
        self.start_threshold = tk.StringVar(value=str(self.default_start_threshold))
        self.stop_threshold = tk.StringVar(value=str(self.default_stop_threshold))
        self.measurement_name = tk.StringVar(value="temptestlog")

        # Initialize sensors after GUI is ready
        self.root.after(100, self.initialize_sensors)

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

    def initialize_sensors(self):
        """Initialize sensors and update GUI."""
        self.sensor_manager.init_sensors()
        # Update Treeview columns with sensor names
        self.gui.update_log_treeview_columns(self.sensor_manager.sensor_names)

    def log_to_display(self, message: str):
        """Safely log message to display."""
        # For non-tabular messages, we might need a separate text area
        # Currently focused on Treeview for data display
        print(message)  # Temporary solution

    def log_to_treeview(self, elapsed_seconds: float, temperatures: list):
        """Add a row to the Treeview with formatted data."""
        if not hasattr(self, 'log_tree') or not self.log_tree:
            return
            
        # Format timestamp
        timestamp = format_duration(elapsed_seconds)
        
        # Prepare values
        values = [timestamp]
        for temp in temperatures:
            if temp is None:
                values.append("Inactive")
            else:
                values.append(f"{temp:.1f}")
        
        # Add to Treeview
        self.log_tree.insert("", tk.END, values=values)
        
        # Auto-scroll to bottom
        self.log_tree.see(self.log_tree.get_children()[-1])

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

    def validate_duration(self) -> bool:
        """Validate duration entries."""
        try:
            minutes = float(self.duration_minutes.get() or 0)
            hours = float(self.duration_hours.get() or 0)
            days = float(self.duration_days.get() or 0)
            
            if minutes < 0 or hours < 0 or days < 0:
                raise ValueError("Duration values must be non-negative")
                
            total_seconds = (minutes * 60) + (hours * 3600) + (days * 86400)
            self.measure_duration_sec = total_seconds if total_seconds > 0 else None
            return True
        except ValueError as e:
            self.error_handler("Error", str(e))
            return False

    def validate_non_negative_float(self, value: str, field: str) -> bool:
        """Validate that the entry is a non-negative float."""
        if not value:
            return True
        try:
            val = float(value)
            if val < 0:
                raise ValueError
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

        # Validate inputs before starting
        if not self.validate_duration():
            return
        if self.temp_control_enabled.get():
            if not self.validate_float(self.start_threshold.get(), 'start_threshold') or \
               not self.validate_float(self.stop_threshold.get(), 'stop_threshold'):
                return

        # Create session folder
        self.data_processor.create_session_folder()
        self.session_start_time = time.time()
        self.running_event.set()

        # Update buttons
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

        # Start timers
        log_interval = int(self.log_interval.get())
        view_interval = int(self.view_interval.get())

        def log_loop():
            while self.running_event.is_set():
                with self.lock:
                    temps_dict = self.sensor_manager.read_sensors()
                    temperatures = [temps_dict.get(sid) for sid in self.sensor_manager.sensor_ids]
                    elapsed = time.time() - self.session_start_time
                    self.data_processor.data.append([self.data_processor.session_start_time, elapsed, datetime.now().isoformat()] + temperatures)
                    self.log_to_treeview(elapsed, temperatures)
                time.sleep(log_interval)

        def view_loop():
            while self.running_event.is_set():
                self.sensor_manager.update_temperature_display(self.sensor_manager.read_sensors())
                if self.measure_duration_sec:
                    self.update_progress(time.time())
                time.sleep(view_interval)

        self.log_timer = threading.Thread(target=log_loop, daemon=True)
        self.view_timer = threading.Thread(target=view_loop, daemon=True)
        self.log_timer.start()
        self.view_timer.start()

        self.log_to_display("Logging started\n")
        self.update_loop()

    def stop_logging(self):
        """Stop the logging process."""
        if not self.running_event.is_set():
            return

        self.running_event.clear()

        # Wait for timers to finish current cycle (optional, but safe)
        if self.log_timer:
            self.log_timer.join(timeout=1)
        if self.view_timer:
            self.view_timer.join(timeout=1)

        # Finalize session
        self.data_processor.finalize_session_folder()

        # Update buttons
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

        # Generate output if enabled
        if self.generate_output_var.get():
            self.data_processor.save_data('plot')
            self.data_processor.save_data('excel')

        # Always save log (as CSV for simplicity, but can be extended)
        self.data_processor.save_data('csv')

        self.log_to_display("Logging stopped\n")
        self.data_processor.reset_session()

    def update_progress(self, current_time):
        """Update progress bar for duration-limited measurements."""
        if not self.measure_duration_sec:
            return

        elapsed = current_time - self.measure_start_time
        progress = (elapsed / self.measure_duration_sec) * 100
        remaining = self.measure_duration_sec - elapsed
        end_time = datetime.fromtimestamp(current_time + remaining)

        remaining_str = format_duration(remaining)
        end_time_str = f"Completion: {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.progress_bar['value'] = min(progress, 100)
        self.progress_label['text'] = f"{remaining_str} | {end_time_str}"
        self.progress_bar.pack(fill=tk.X, pady=2)
        self.progress_label.pack(fill=tk.X, pady=2)
        
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
                avg_temp = sum(t for t in temps_dict.values() if t is not None) / len([t for t in temps_dict.values() if t is not None]) if any(t is not None for t in temps_dict.values()) else 0

            nonlocal measurement_started
            if not measurement_started and self.temp_control_enabled.get():
                if avg_temp >= float(self.start_threshold.get()):
                    measurement_started = True
                    self.measure_start_time = current_time
                    self.log_to_display("Measurement started (temp threshold reached)\n")

            if measurement_started:
                if self.temp_control_enabled.get() and avg_temp <= float(self.stop_threshold.get()):
                    self.log_to_display("Measurement stopped (temp threshold reached)\n")
                    self.stop_logging()
                    return

                # Stop on duration
                if (self.measure_duration_sec is not None and 
                    self.duration_enabled.get() and
                    current_time - self.measure_start_time >= self.measure_duration_sec):
                    self.log_to_display("Measurement stopped due to duration\n")
                    self.stop_logging()
                    return

            # Reschedule condition check
            self.root.after(100, check_conditions)

        # Start condition checking
        self.root.after(100, check_conditions)

    def save_data(self, format_type: str):
        """Save data to file in the specified format."""
        self.data_processor.save_data(format_type)

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
                "duration_enabled": self.duration_enabled.get(),
                "duration_minutes": float(self.duration_minutes.get()),
                "duration_hours": float(self.duration_hours.get()),
                "duration_days": float(self.duration_days.get()),
                "measurement_name": self.measurement_name.get(),
                "temp_control_enabled": self.temp_control_enabled.get()
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
            self.duration_enabled.set(loaded_config.get("duration_enabled", False))
            self.duration_minutes.set(str(loaded_config.get("duration_minutes", 0)))
            self.duration_hours.set(str(loaded_config.get("duration_hours", 0)))
            self.duration_days.set(str(loaded_config.get("duration_days", 0)))
            self.measurement_name.set(loaded_config.get("measurement_name", "temptestlog"))
            self.temp_control_enabled.set(loaded_config.get("temp_control_enabled", False))
            
            # Update sensor displays
            for sid, chk in self.sensor_manager.sensor_checkbuttons.items():
                chk.config(text=self.sensor_manager.sensor_names[sid])
            
            self.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_manager.sensor_names[sid] for sid in self.sensor_manager.sensor_ids]
            self.log_to_display(f"Sensor configuration loaded and applied: {filename}\n")
            self.sensor_manager.list_sensors_status()
            
            # Update Treeview columns
            self.gui.update_log_treeview_columns(self.sensor_manager.sensor_names)
            
        except Exception as e:
            self.error_handler("Error", f"Loading configuration failed: {str(e)}")

    def on_closing(self):
        """Handle application shutdown."""
        self.stop_logging()
        self.root.destroy()
