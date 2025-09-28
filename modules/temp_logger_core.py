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
        
        self.temp_start_enabled = tk.BooleanVar(value=False)
        self.temp_stop_enabled = tk.BooleanVar(value=False)
        self.measure_duration_sec = None
        self.duration_enabled = tk.BooleanVar(value=False)
        self.duration_minutes = tk.StringVar(value="0")
        self.duration_hours = tk.StringVar(value="0")
        self.duration_days = tk.StringVar(value="0")
        self.generate_output_var = tk.BooleanVar(value=True)
        self.log_interval = tk.StringVar(value=str(self.default_log_interval))
        self.view_interval = tk.StringVar(value=str(self.default_view_interval))
        self.measurement_name = tk.StringVar(value="temptestlog")
        
        self.start_conditions: List[Dict[str, Any]] = []
        self.stop_conditions: List[Dict[str, Any]] = []

        self.initialize_components()
        
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
        self.gui.update_log_treeview_columns(self.sensor_manager.sensor_names)
        self.gui.populate_condition_checkboxes()

    def log_to_display(self, message: str):
        """Safely log message to display."""
        def update_text():
            try:
                self.gui.app.log_messages.config(state=tk.NORMAL)
                self.gui.app.log_messages.insert(tk.END, message)
                self.gui.app.log_messages.see(tk.END)
                self.gui.app.log_messages.config(state=tk.DISABLED)
            except AttributeError:
                print(message, end='') 

        self.root.after(0, update_text)

    def log_to_treeview(self, elapsed_seconds: float, temperatures: list):
        """Add a row to the Treeview with formatted data."""
        
        def update_tree():
            if not hasattr(self.gui.app, 'log_tree'):
                return
                
            timestamp = format_duration(elapsed_seconds)
            
            values = [timestamp]
            for temp in temperatures:
                if temp is None:
                    values.append("Inactive")
                else:
                    values.append(f"{temp:.1f}")
            
            iid = self.gui.app.log_tree.insert("", tk.END, values=values)
            row_index = len(self.gui.app.log_tree.get_children())
            tag = "evenrow" if row_index % 2 == 0 else "oddrow"
            self.gui.app.log_tree.item(iid, tags=(tag,))
            
            self.gui.app.log_tree.see(self.gui.app.log_tree.get_children()[-1])
            
        self.root.after(0, update_tree)

    def update_conditions_list(self, side: str):
        """Update conditions list from GUI rows (called by GUI on change)."""
        if side == 'start':
            conditions = self.start_conditions
            rows = self.gui.start_conditions_rows
        else:
            conditions = self.stop_conditions
            rows = self.gui.stop_conditions_rows
        
        parsed_conditions = []
        
        for row_data in rows:
            sensor_vars = row_data.get('sensor_vars', {})
            selected_sensors = [sid for sid, var in sensor_vars.items() if var.get()]
            
            threshold_str = row_data.get('threshold_var', tk.StringVar(value="")).get()
            operator = row_data.get('operator_var', tk.StringVar(value=">")).get()
            logic_op = row_data.get('logic_var', tk.StringVar(value=None)).get()
            
            try:
                threshold = float(threshold_str) if threshold_str else 0.0
                if selected_sensors:
                    cond = {
                        'sensors': selected_sensors,
                        'operator': operator,
                        'threshold': threshold,
                        'logic': logic_op if logic_op in ['AND', 'OR'] else None
                    }
                    parsed_conditions.append(cond)
            except ValueError:
                self.log_to_display(f"Warning: Invalid threshold value '{threshold_str}' encountered.\n")
                pass
        
        if side == 'start':
            self.start_conditions = parsed_conditions
        else:
            self.stop_conditions = parsed_conditions
        
        self.validate_temp_conditions(side)

    def validate_temp_conditions(self, side: str) -> bool:
        """Validate conditions list, show warning if invalid."""
        if side == 'start':
            conditions = self.start_conditions
            enabled = self.temp_start_enabled.get()
        else:
            conditions = self.stop_conditions
            enabled = self.temp_stop_enabled.get()
        
        if not enabled:
            return True
        
        invalid_reasons = []
        for i, cond in enumerate(conditions):
            invalid_sensors = [sid for sid in cond.get('sensors', []) if sid not in self.sensor_manager.sensor_ids]
            if invalid_sensors:
                invalid_reasons.append(f"Condition {i+1}: Invalid sensors {invalid_sensors}")
            if not isinstance(cond.get('threshold'), float):
                 invalid_reasons.append(f"Condition {i+1}: Invalid threshold type {cond.get('threshold')}")
            if cond.get('operator') not in ['>', '<', '>=', '<=', '=']:
                invalid_reasons.append(f"Condition {i+1}: Invalid operator {cond.get('operator')}")
            if not cond.get('sensors'):
                invalid_reasons.append(f"Condition {i+1}: No sensors selected")
        
        if invalid_reasons:
            messagebox.showwarning("Invalid Conditions", "\n".join(invalid_reasons))
            return False
        return True

    def _log_loop(self):
        """Worker thread for periodic logging."""
        log_interval_sec: float
        try:
            log_interval_sec = float(self.log_interval.get())
        except ValueError:
            log_interval_sec = self.default_log_interval
            self.log_to_display(f"Warning: Invalid log interval. Defaulting to {log_interval_sec}s.\n")
            
        self.measure_duration_sec = self.data_processor.get_total_duration_seconds()
        
        while self.running_event.is_set():
            start_time = time.time()
            
            temps: Dict[str, Optional[float]] = self.sensor_manager.read_sensors()
            
            current_time = datetime.now()
            
            if not self.session_start_time:
                self.session_start_time = current_time 
                
            seconds_elapsed = round(current_time.timestamp() - self.session_start_time.timestamp(), 1)
            
            log_data: List[Any] = ["LOG", seconds_elapsed, current_time.strftime("%Y-%m-%d %H:%M:%S")]
            
            for sensor_id in self.sensor_manager.sensor_ids:
                log_data.append(temps.get(sensor_id))

            self.data_processor.log_data_point(log_data)
            
            should_stop = False
            
            if self.temp_stop_enabled.get() and self.data_processor.check_conditions(self.stop_conditions):
                self.log_to_display("STOP condition met. Stopping logging.\n")
                should_stop = True
            
            if self.duration_enabled.get() and self.measure_duration_sec is not None and seconds_elapsed >= self.measure_duration_sec:
                self.log_to_display("Duration limit reached. Stopping logging.\n")
                should_stop = True

            if should_stop:
                self.root.after(0, self.stop_logging)
                break

            elapsed = time.time() - start_time
            sleep_time = log_interval_sec - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def update_loop(self):
        """View update loop for screen refresh."""
        
        if self.running_event.is_set():
            self.sensor_manager.read_and_update_display() 
            
            try:
                view_interval_sec = float(self.view_interval.get())
            except ValueError:
                view_interval_sec = self.default_view_interval
                
            self.view_timer = self.root.after(int(view_interval_sec * 1000), self.update_loop)
        
    def start_logging(self):
        """Start logging by creating a new session and a worker thread."""
        if self.running_event.is_set():
            return
        
        if self.temp_start_enabled.get() and not self.data_processor.check_conditions(self.start_conditions):
            self.log_to_display("START conditions enabled but not met. Please wait or disable conditions.\n")
            return

        self.session_start_time = datetime.now()
        self.data_processor.create_session_folder(self.measurement_name.get())
        
        self.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_manager.sensor_names[sid] for sid in self.sensor_manager.sensor_ids]

        self.running_event.set()
        self.gui.update_start_stop_buttons(True)
        self.log_to_display(f"Logging started: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        self.log_thread = threading.Thread(target=self._log_loop, daemon=True)
        self.log_thread.start()

        self.update_loop()

    def stop_logging(self):
        """Stop logging - finalize session."""
        if not self.running_event.is_set():
            return
        
        self.running_event.clear()
        if self.view_timer:
            self.root.after_cancel(self.view_timer)
            self.view_timer = None
        
        if self.log_thread and self.log_thread.is_alive():
            timeout = float(self.log_interval.get()) * 2 if self.log_interval.get() else 5.0
            self.log_thread.join(timeout=timeout)
            if self.log_thread.is_alive():
                self.log_to_display("Warning: Log thread failed to stop gracefully.\n")
            self.log_thread = None

        if self.generate_output_var.get():
            self.export_manager.export_data(
                self.data_processor.current_session_folder, 
                self.data_columns, 
                self.data_processor.get_all_logged_data()
            )
            self.log_to_display("Data exported to CSV/Excel.\n")
            
        self.data_processor.finalize_session_folder()
        self.gui.update_start_stop_buttons(False)
        self.log_to_display("Logging stopped. Data saved.\n")
        self.export_manager.reset_exports()

    def save_sensor_config(self):
        """Save active sensor IDs and configuration settings to a JSON file."""
        config_data = {
            "active_sensors": [sid for sid, var in self.sensor_manager.sensor_vars.items() if var.get()],
            "sensor_names": self.sensor_manager.sensor_names,
            "log_interval": self.log_interval.get(),
            "view_interval": self.view_interval.get(),
            "duration_enabled": self.duration_enabled.get(),
            "duration_minutes": self.duration_minutes.get(),
            "duration_hours": self.duration_hours.get(),
            "duration_days": self.duration_days.get(),
            "measurement_name": self.measurement_name.get(),
            "temp_start_enabled": self.temp_start_enabled.get(),
            "temp_stop_enabled": self.temp_stop_enabled.get(),
            "start_conditions": self.start_conditions,
            "stop_conditions": self.stop_conditions
        }
        
        try:
            filename = filedialog.asksaveasfilename(
                initialdir=self.config_folder,
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")],
                title="Save sensor configuration"
            )
            if not filename:
                return
                
            with open(filename, "w", encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
                
            self.log_to_display(f"Configuration saved to: {filename}\n")
            
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
            
            active_sensors = loaded_config.get("active_sensors", [])
            for sid, var in self.sensor_manager.sensor_vars.items():
                var.set(sid in active_sensors)
            
            self.sensor_manager.sensor_names = loaded_config.get("sensor_names", self.sensor_manager.sensor_names)
            self.log_interval.set(str(loaded_config.get("log_interval", self.default_log_interval)))
            self.view_interval.set(str(loaded_config.get("view_interval", self.default_view_interval)))
            self.duration_enabled.set(loaded_config.get("duration_enabled", False))
            self.duration_minutes.set(str(loaded_config.get("duration_minutes", 0)))
            self.duration_hours.set(str(loaded_config.get("duration_hours", 0)))
            self.duration_days.set(str(loaded_config.get("duration_days", 0)))
            self.measurement_name.set(loaded_config.get("measurement_name", "temptestlog"))
            self.temp_start_enabled.set(loaded_config.get("temp_start_enabled", False))
            self.temp_stop_enabled.set(loaded_config.get("temp_stop_enabled", False))
            
            self.start_conditions = loaded_config.get("start_conditions", [])
            self.stop_conditions = loaded_config.get("stop_conditions", [])
            
            if "start_threshold" in loaded_config or "stop_threshold" in loaded_config:
                if messagebox.askyesno("Legacy Config", "Convert old thresholds to conditions?"):
                    self._convert_legacy_thresholds(loaded_config)
            
            for sid, chk in self.sensor_manager.sensor_checkbuttons.items():
                chk.config(text=self.sensor_manager.sensor_names[sid])
            
            self.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_manager.sensor_names[sid] for sid in self.sensor_manager.sensor_ids]
            self.log_to_display(f"Sensor configuration loaded and applied: {filename}\n")
            self.sensor_manager.list_sensors_status()
            
            self.gui.update_log_treeview_columns(self.sensor_manager.sensor_names)
            
            try:
                self.gui.load_conditions_to_rows(self.start_conditions, 'start')
                self.gui.load_conditions_to_rows(self.stop_conditions, 'stop')
            except AttributeError:
                self.log_to_display("Warning: GUI conditions load method not available.\n")
            
            self.gui.populate_condition_checkboxes()
            
        except Exception as e:
            self.error_handler("Error", f"Loading configuration failed: {str(e)}")

    def _convert_legacy_thresholds(self, loaded_config: Dict):
        """Convert old single threshold settings to the new conditions format."""
        all_sensors = self.sensor_manager.sensor_ids
        start_thresh = loaded_config.get("start_threshold", 25.0)
        stop_thresh = loaded_config.get("stop_threshold", 30.0)
        
        if not all_sensors:
            self.log_to_display("No sensors found to apply legacy conditions.\n")
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
        
        self.log_to_display("Legacy thresholds converted to conditions.\n")

    def on_closing(self):
        """Handle application shutdown."""
        self.stop_logging()
        self.root.destroy()

    def error_handler(self, title: str, message: str):
        """Handle errors with messagebox."""
        messagebox.showerror(title, message)
