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
        
        # Store config values
        self.default_log_interval = self.config["default_log_interval"]
        self.default_view_interval = self.config["default_view_interval"]
        self.max_log_lines = self.config["max_log_lines"]
        self.measurement_folder = self.config["measurement_folder"]
        self.config_folder = self.config["config_folder"]
        
        # Runtime variables (ÁTHELYEZVE a GUI inicializálása ELÉ)
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
        self.generate_output_var = tk.BooleanVar(value=True) # <<< HIBA JAVÍTVA
        self.log_interval = tk.StringVar(value=str(self.default_log_interval))
        self.view_interval = tk.StringVar(value=str(self.default_view_interval))
        self.measurement_name = tk.StringVar(value="temptestlog")
        
        # New: Conditions lists (empty by default)
        self.start_conditions: List[Dict[str, any]] = []
        self.stop_conditions: List[Dict[str, any]] = []

        # Initialize components
        self.initialize_components()
        
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
        if not hasattr(self, 'log_tree'): # Javított feltétel
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
        iid = self.log_tree.insert("", tk.END, values=values)
        # Alternate row colors
        row_index = len(self.log_tree.get_children())
        tag = "evenrow" if row_index % 2 == 0 else "oddrow"
        self.log_tree.item(iid, tags=(tag,))
        
        # Auto-scroll to bottom
        self.log_tree.see(self.log_tree.get_children()[-1])

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
            threshold_str = row_data.get('threshold_entry', tk.StringVar(value="")).get()
            operator = row_data.get('operator_combobox', tk.StringVar(value=">")).get()
            
            try:
                threshold = float(threshold_str) if threshold_str else 0.0
                if selected_sensors:
                    cond = {
                        'sensors': selected_sensors,
                        'operator': operator,
                        'threshold': threshold,
                        'logic': None  # First level
                    }
                    parsed_conditions.append(cond)
            except ValueError:
                pass  # Invalid threshold, skip this row
        
        if side == 'start':
            self.start_conditions = parsed_conditions
        else:
            self.stop_conditions = parsed_conditions
        
        # Validate after update
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
            messagebox.showwarning("Invalid Conditions", "\n".join(invalid_reasons))
            return False
        return True

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
            
            # Repopulate GUI conditions with loaded data
            try:
                self.gui.load_conditions_to_rows(self.start_conditions, 'start')
                self.gui.load_conditions_to_rows(self.stop_conditions, 'stop')
            except AttributeError:
                self.log_to_display("Warning: GUI conditions load method not available.\n")
            
            # Repopulate checkboxes after name changes
            self.gui.populate_condition_checkboxes()
            
        except Exception as e:
            self.error_handler("Error", f"Loading configuration failed: {str(e)}")

    def _convert_legacy_thresholds(self, loaded_config: Dict):
        """Convert legacy thresholds to default conditions."""
        start_thresh = loaded_config.get("start_threshold", 22.0)
        stop_thresh = loaded_config.get("stop_threshold", 30.0)
        all_sensors = [sid for sid in self.sensor_manager.sensor_ids]
        
        if not all_sensors:
            self.log_to_display("Warning: No sensors available for legacy conversion.\n")
            return
        
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

    def error_handler(self, title: str, message: str):
        """Handle errors with messagebox."""
        messagebox.showerror(title, message)

    # Új metódus a hiba javításához: Üres update_loop (opcionálisan bővíthető kezdeti frissítéssel)
    def update_loop(self):
        """Initial update loop - startup refresh."""
        self.validate_temp_conditions('start')
        self.validate_temp_conditions('stop')
        self.sensor_manager.list_sensors_status()
        # Ensure GUI is updated
        self.root.update_idletasks()

    def start_logging(self):
        """Placeholder for start logging - implement threading."""
        pass  # Implement as needed

    def stop_logging(self):
        """Placeholder for stop logging - finalize session."""
        pass  # Implement as needed
