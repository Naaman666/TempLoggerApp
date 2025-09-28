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
from typing import TYPE_CHECKING, Dict, List, Optional

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
        
        # Store config values (legacy thresholds removed, but kept for compat)
        self.default_log_interval = self.config["default_log_interval"]
        self.default_view_interval = self.config["default_view_interval"]
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
        
        # New: Conditions lists (empty by default)
        self.start_conditions: List[Dict[str, any]] = []
        self.stop_conditions: List[Dict[str, any]] = []

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
        # Populate condition checkboxes in GUI
        self.gui.populate_condition_checkboxes()

    def log_to_display(self, message: str):
        """Safely log message to display."""
        print(message)  # Temporary solution - can be enhanced to a text widget

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

    def update_conditions_list(self, side: str):
        """Update conditions list from GUI rows (called by GUI on change)."""
        # Note: In full impl, this would parse GUI row_data, but for now, placeholder
        # - GUI calls this to signal change; actual parsing can be in GUI or here
        # Assuming GUI handles parsing and calls self.start_conditions = parsed_list
        # For simplicity, validate after update
        if side == 'start':
            self.validate_temp_conditions('start')
        else:
            self.validate_temp_conditions('stop')

    def validate_temp_conditions(self, side: str) -> bool:
        """Validate conditions list, show warning if invalid."""
        if side == 'start':
            conditions = self.start_conditions
            enabled = self.temp_start_enabled.get()
        else:
            conditions = self.stop_conditions
            enabled = self.temp_stop_enabled.get()
        
        if not enabled:
            return True  # No need to validate if disabled
        
        invalid_reasons = []
        for i, cond in enumerate(conditions):
            # Check sensors exist
            invalid_sensors = [sid for sid in cond.get('sensors', []) if sid not in self.sensor_manager.sensor_ids]
            if invalid_sensors:
                invalid_reasons.append(f"Condition {i+1}: Invalid sensors {invalid_sensors}")
            # Check threshold float
            if not isinstance(cond.get('threshold'), float) or cond['threshold'] < 0:
                invalid_reasons.append(f"Condition {i+1}: Invalid threshold {cond.get('threshold')}")
            # Check operator
            if cond.get('operator') not in ['>', '<', '>=', '<=', '=']:
                invalid_reasons.append(f"Condition {i+1}: Invalid operator {cond.get('operator')}")
            # Check at least one sensor
            if not cond.get('sensors'):
                invalid_reasons.append(f"Condition {i+1}: No sensors selected")
        
        if invalid_reasons:
            messagebox.showwarning("Warning", "Some conditions invalid:\n" + "\n".join(invalid_reasons) + "\nMeasurement may not trigger.")
            return False
        if not conditions:  # Empty list
            messagebox.showwarning("Warning", f"{side.capitalize()} conditions empty – no trigger possible.")
            return False
        return True

    def apply_operator(self, temp: Optional[float], thresh: float, op: str) -> bool:
        """Apply operator to temp vs threshold."""
        if temp is None:
            return False
        if op == '>':
            return temp > thresh
        elif op == '<':
            return temp < thresh
        elif op == '>=':
            return temp >= thresh
        elif op == '<=':
            return temp <= thresh
        elif op == '=':
            return temp == thresh
        return False

    def check_single_condition(self, temps_dict: Dict[str, Optional[float]], cond: Dict[str, any]) -> bool:
        """Check single condition: ALL selected sensors satisfy operator."""
        sensors = cond.get('sensors', [])
        if not sensors:
            return False
        for sid in sensors:
            temp = temps_dict.get(sid)
            if not self.apply_operator(temp, cond['threshold'], cond['operator']):
                return False
        return True

    def evaluate_conditions(self, temps_dict: Dict[str, Optional[float]], conditions: List[Dict[str, any]]) -> bool:
        """Evaluate full conditions list with AND/OR logic."""
        if not conditions:
            return False
        # First condition
        result = self.check_single_condition(temps_dict, conditions[0])
        # Subsequent with logic
        for cond in conditions[1:]:
            next_result = self.check_single_condition(temps_dict, cond)
            logic = cond.get('logic', 'AND')  # Default AND
            if logic == 'AND':
                result = result and next_result
            else:  # OR
                result = result or next_result
            if not result and logic == 'AND':  # Early exit if AND fails
                break
        return result

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

    def start_logging(self):
        """Start the logging process."""
        if self.running_event.is_set():
            return

        self.running_event.set()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.session_start_time = time.time()
        self.data_processor.reset_session()
        self.data_processor.create_session_folder()
        
        # Clear log treeview
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        
        # Validate duration if enabled
        if self.duration_enabled.get():
            if not self.validate_duration():
                self.stop_logging()
                return
        
        # Start log timer
        self.log_timer = self.root.after(self.default_log_interval * 1000, self.log_data)
        
        # Start view timer
        self.view_timer = self.root.after(self.default_view_interval * 1000, self.update_view)
        
        # Start condition checking if enabled
        measurement_started = False
        if self.temp_start_enabled.get():
            self.log_to_display("Waiting for start conditions...\n")
        else:
            measurement_started = True
            self.measure_start_time = self.session_start_time

        def check_conditions():
            if not self.running_event.is_set():
                return
                
            current_time = time.time()
            with self.lock:
                temps_dict = self.sensor_manager.read_sensors()

            nonlocal measurement_started
            if not measurement_started and self.temp_start_enabled.get():
                if self.start_conditions and self.validate_temp_conditions('start'):
                    if self.evaluate_conditions(temps_dict, self.start_conditions):
                        measurement_started = True
                        self.measure_start_time = current_time
                        self.log_to_display(f"Measurement started (start conditions met)\n")
                    else:
                        detail = self._get_conditions_detail(temps_dict, self.start_conditions, 'start')
                        self.log_to_display(f"Start conditions not met: {detail}\n")
                else:
                    self.log_to_display("Skipped start eval: invalid/empty conditions\n")

            if measurement_started:
                # Check stop conditions
                if self.temp_stop_enabled.get() and self.stop_conditions and self.validate_temp_conditions('stop'):
                    if self.evaluate_conditions(temps_dict, self.stop_conditions):
                        self.log_to_display(f"Measurement stopped (stop conditions met)\n")
                        self.stop_logging()
                        return
                    else:
                        detail = self._get_conditions_detail(temps_dict, self.stop_conditions, 'stop')
                        self.log_to_display(f"Stop conditions not met: {detail}\n")
                # Check duration stop
                if (self.measure_duration_sec is not None and 
                    self.duration_enabled.get() and
                    current_time - self.measure_start_time >= self.measure_duration_sec):
                    self.log_to_display("Measurement stopped due to duration\n")
                    self.stop_logging()
                    return

            # Reschedule
            self.root.after(100, check_conditions)

        # Start condition checking
        self.root.after(100, check_conditions)

    def _get_conditions_detail(self, temps_dict: Dict, conditions: List[Dict], side: str) -> str:
        """Get detailed string for conditions evaluation."""
        details = []
        for i, cond in enumerate(conditions):
            cond_result = self.check_single_condition(temps_dict, cond)
            sensors_str = ', '.join(cond['sensors'])
            thresh_str = f"{cond['operator']} {cond['threshold']}°C"
            detail = f"Cond {i+1} ({sensors_str} {thresh_str}): {cond_result}"
            details.append(detail)
        return ' | '.join(details)

    def stop_logging(self):
        """Stop the logging process."""
        self.running_event.clear()
        if self.log_timer:
            self.root.after_cancel(self.log_timer)
            self.log_timer = None
        if self.view_timer:
            self.root.after_cancel(self.view_timer)
            self.view_timer = None
        
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        
        self.data_processor.finalize_session_folder()
        if self.generate_output_var.get():
            self.data_processor.save_data('plot')
        
        self.log_to_display("Logging stopped.\n")

    def log_data(self):
        """Log data periodically."""
        if not self.running_event.is_set():
            return
        
        with self.lock:
            temps_dict = self.sensor_manager.read_sensors()
            elapsed = time.time() - self.measure_start_time if self.measure_start_time else 0
            temperatures = [temps_dict.get(sid) for sid in self.sensor_manager.sensor_ids]
            self.data_processor.data.append([self.measurement_name.get(), elapsed, datetime.now().isoformat()] + temperatures)
            self.log_to_treeview(elapsed, temperatures)
            self.sensor_manager.update_temperature_display(temps_dict)
        
        # Reschedule
        self.log_timer = self.root.after(int(self.log_interval.get()) * 1000, self.log_data)

    def update_view(self):
        """Update view periodically."""
        if not self.running_event.is_set():
            return
        # Update any real-time displays if needed
        self.view_timer = self.root.after(int(self.view_interval.get()) * 1000, self.update_view)

    def error_handler(self, title: str, message: str):
        """Handle errors with messagebox."""
        messagebox.showerror(title, message)

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
                "log_interval": int(self.log_interval.get()),
                "view_interval": int(self.view_interval.get()),
                "duration_enabled": self.duration_enabled.get(),
                "duration_minutes": float(self.duration_minutes.get()),
                "duration_hours": float(self.duration_hours.get()),
                "duration_days": float(self.duration_days.get()),
                "measurement_name": self.measurement_name.get(),
                "temp_start_enabled": self.temp_start_enabled.get(),
                "temp_stop_enabled": self.temp_stop_enabled.get(),
                "start_conditions": self.start_conditions,
                "stop_conditions": self.stop_conditions
                # Legacy: omit old thresholds
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
            
            # Apply basic config
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
            
            # New: Load conditions
            self.start_conditions = loaded_config.get("start_conditions", [])
            self.stop_conditions = loaded_config.get("stop_conditions", [])
            
            # Legacy conversion if old thresholds present
            if "start_threshold" in loaded_config or "stop_threshold" in loaded_config:
                if messagebox.askyesno("Legacy Config", "Convert old thresholds to conditions?"):
                    self._convert_legacy_thresholds(loaded_config)
            
            # Update sensor displays
            for sid, chk in self.sensor_manager.sensor_checkbuttons.items():
                chk.config(text=self.sensor_manager.sensor_names[sid])
            
            self.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_manager.sensor_names[sid] for sid in self.sensor_manager.sensor_ids]
            self.log_to_display(f"Sensor configuration loaded and applied: {filename}\n")
            self.sensor_manager.list_sensors_status()
            
            # Update Treeview columns
            self.gui.update_log_treeview_columns(self.sensor_manager.sensor_names)
            
            # Repopulate GUI conditions with loaded data (call GUI method if exists)
            self.gui.load_conditions_to_rows(self.start_conditions, 'start')
            self.gui.load_conditions_to_rows(self.stop_conditions, 'stop')
            
        except Exception as e:
            self.error_handler("Error", f"Loading configuration failed: {str(e)}")

    def _convert_legacy_thresholds(self, loaded_config: Dict):
        """Convert legacy thresholds to default conditions."""
        start_thresh = loaded_config.get("start_threshold", 22.0)
        stop_thresh = loaded_config.get("stop_threshold", 30.0)
        all_sensors = [sid for sid in self.sensor_manager.sensor_ids]
        
        # Default: ALL sensors > threshold for start
        self.start_conditions = [{
            'sensors': all_sensors,
            'operator': '>',
            'threshold': start_thresh,
            'logic': None  # First
        }]
        
        # For stop: ALL <= threshold
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
