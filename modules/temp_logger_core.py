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
        
        # Validate duration
        if not self.validate_duration():
            return
        
        # Reset session counter before creating new session
        self.data_processor.reset_session()
        
        # Create session folder and clear previous data
        session_folder = self.data_processor.create_session_folder()
        with self.data_processor.lock:
            self.data_processor.data.clear()
        
        # Clear Treeview
        if hasattr(self, 'log_tree'):
            for item in self.log_tree.get_children():
                self.log_tree.delete(item)
        
        self.running_event.set()
        self.session_start_time = time.time()
        self.gui.start_button.config(state="disabled")
        self.gui.stop_button.config(state="normal")
        self.gui.excel_button.config(state="disabled")
        self.gui.csv_button.config(state="disabled")
        self.gui.json_button.config(state="normal")

        # Open log file in session folder
        log_filename = self.data_processor.get_session_filename("temp_log", "log")
        try:
            self.log_file = open(log_filename, "w", encoding='utf-8')
            self.log_to_display("Logging started...\n")
            self.log_to_display(f"Session folder: {session_folder}\n")
            self.log_to_display(f"Log file: {os.path.basename(log_filename)}\n")
        except Exception as e:
            self.error_handler("Error", f"Failed to open log file: {str(e)}")
            self.running_event.clear()
            self.gui.start_button.config(state="normal")
            self.gui.stop_button.config(state="disabled")
            return

        # Schedule first timers
        self.schedule_view_update()
        self.schedule_log_update()
        
        # Start progress update if duration is set
        if self.measure_duration_sec is not None and self.duration_enabled.get():
            self.measure_start_time = time.time()
            self.root.after(1000, self.update_progress, time.time())

        # Start condition checking
        self.update_loop()

    def stop_logging(self):
        """Stop the logging process."""
        self.running_event.clear()
        if self.view_timer:
            self.view_timer.cancel()
        if self.log_timer:
            self.log_timer.cancel()
            
        # Finalize session folder with end timestamp
        self.data_processor.session_end_time = datetime.now()
        self.data_processor.finalize_session_folder()
            
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
                self.log_to_display("Plots generated successfully:\n")
                self.log_to_display(f"Session folder: {self.data_processor.current_session_folder}\n")
                plot_files = [
                    "temp_plot-[AT:{self.data_processor.session_counter}]-...png",
                    "temp_plot-[AT:{self.data_processor.session_counter}]-...pdf", 
                    "temp_chart-[AT:{self.data_processor.session_counter}]-...xlsx"
                ]
                for file in plot_files:
                    self.log_to_display(f"- {file}\n")
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
        elapsed_seconds = current_time - self.session_start_time
        
        with self.lock:
            temps_dict = self.sensor_manager.read_sensors()
        
        # Update temperature displays
        self.sensor_manager.update_temperature_display(temps_dict)
        
        # Convert temperatures to floats and prepare for display
        temps_list = []
        for sid in self.sensor_manager.sensor_ids:
            temp = temps_dict.get(sid)
            if temp is not None:
                try:
                    temps_list.append(float(temp))
                except (ValueError, TypeError):
                    temps_list.append(None)
            else:
                temps_list.append(None)
        
        # Add to Treeview
        self.log_to_treeview(elapsed_seconds, temps_list)
        
        # Create data row and add to data list
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_row = ["VIEW", elapsed_seconds, timestamp] + temps_list
        with self.data_processor.lock:
            self.data_processor.data.append(data_row)
        
        self.schedule_view_update()

    def log_update(self):
        """Log to file and collect data."""
        if not self.running_event.is_set():
            return
            
        current_time = time.time()
        elapsed_seconds = current_time - self.session_start_time
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with self.lock:
            temps_dict = self.sensor_manager.read_sensors()
        
        # Convert temperatures to floats
        temps_list = []
        for sid in self.sensor_manager.sensor_ids:
            temp = temps_dict.get(sid)
            if temp is not None:
                try:
                    temps_list.append(float(temp))
                except (ValueError, TypeError):
                    temps_list.append(None)
            else:
                temps_list.append(None)
        
        # Create data row and add to data list
        data_row = ["LOG", elapsed_seconds, timestamp] + temps_list
        with self.data_processor.lock:
            self.data_processor.data.append(data_row)
        
        # Write to log file
        if self.log_file:
            log_line = f"LOG,{elapsed_seconds},{timestamp}," + ",".join(
                [f"{t:.1f}" if t is not None else "Inactive" for t in temps_list]
            )
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
        if (self.measure_duration_sec is not None and 
            self.measure_start_time is not None and
            self.duration_enabled.get()):
            
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

            nonlocal measurement_started
            if not measurement_started:
                # Start condition checking would go here
                # Placeholder for temperature-controlled start
                measurement_started = True
                self.measure_start_time = current_time
                self.log_to_display("Measurement started\n")

            if measurement_started:
                # Stop condition checking would go here
                # Placeholder for temperature-controlled stop
                pass

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
            self.duration_enabled.set(loaded_config.get("duration_enabled", False))
            self.duration_minutes.set(str(loaded_config.get("duration_minutes", 0)))
            self.duration_hours.set(str(loaded_config.get("duration_hours", 0)))
            self.duration_days.set(str(loaded_config.get("duration_days", 0)))
            self.measurement_name.set(loaded_config.get("measurement_name", "temptestlog"))
            
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
