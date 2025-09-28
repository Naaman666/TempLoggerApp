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
        self.export_thread: Optional[threading.Thread] = None # ÚJ: Az exportálási szál kezeléséhez
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
        
        # Initialize sensors after GUI is set up
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

    def start_logging(self):
        """Start the logging process."""
        if self.running_event.is_set():
            self.log_to_display("Logging is already running.\n")
            return
            
        if not self.validate_temp_conditions('start') or not self.validate_temp_conditions('stop'):
            return

        self.data_processor.init_new_session(self.measurement_name.get())
        
        try:
            self.measure_start_time = datetime.now()
            self.log_thread = threading.Thread(target=self._log_loop, daemon=True)
            self.running_event.set()
            self.log_thread.start()
            
            self.gui.update_start_stop_buttons(True)
            self.root.after(0, self._update_gui_live)
            
            self.log_to_display(f"Logging started: '{self.data_processor.current_session_folder}'\n")

        except Exception as e:
            self.error_handler("Start Error", f"Failed to start logging: {str(e)}")
            self.running_event.clear()
            self.gui.update_start_stop_buttons(False)

    def stop_logging(self):
        """Stop the logging process and initiate data export."""
        if not self.running_event.is_set():
            return
            
        self.running_event.clear()
        
        if self.view_timer:
            self.root.after_cancel(self.view_timer)
            self.view_timer = None

        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.log_to_display("Logging stopped. Initiating data export...\n")

        # Disable main GUI interaction while exporting
        self.gui.update_start_stop_buttons(False)
        self.gui.start_button.config(state=tk.DISABLED) 
        self.gui.stop_button.config(state=tk.DISABLED)
        
        # Show progress bar and start export in a new thread
        self.gui.show_export_progress()
        
        self.export_thread = threading.Thread(target=self._export_and_cleanup_thread, daemon=True)
        self.export_thread.start()

    def _export_and_cleanup_thread(self):
        """
        Worker thread to export data, handle the minimum 5-second duration, 
        and safely call the GUI update.
        """
        MIN_EXPORT_TIME = 5.0 # Másodperc (felhasználói kérés minimum)
        
        export_start_time = time.time()
        
        try:
            # 1. Progress update: Export kezdete
            self.root.after(0, lambda: self.gui.update_progress(5))
            
            # 2. Fő feladat: adatok exportálása és a grafikonok generálása
            self.data_processor.export_data()
            
            # 3. Progress update: Export logikailag kész
            self.root.after(0, lambda: self.gui.update_progress(90))

            export_time = time.time() - export_start_time
            time_to_wait = MIN_EXPORT_TIME - export_time
            
            if time_to_wait > 0:
                # Várakozás a minimum 5 másodperces progress bar idő eléréséig
                time.sleep(time_to_wait)

        except Exception as e:
            self.error_handler("Export Error", f"Data export failed: {str(e)}")
        finally:
            # 4. Biztonságos GUI frissítés a fő szálon (bezárás, gombok engedélyezése)
            self.root.after(0, self._finish_export_ui)
            self.export_thread = None


    def _finish_export_ui(self):
        """Safely hide progress bar and re-enable GUI elements in the main thread."""
        
        self.gui.update_progress(100) # Progress bar teljesre állítása
        self.gui.hide_export_progress()
        self.gui.update_start_stop_buttons(is_running=False)
        self.data_processor.reset_session()
        self.log_to_display("Data export complete. GUI is now ready for a new measurement.\n")

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
            
            # 1. Stop conditions check
            if self.temp_stop_enabled.get() and self.data_processor.check_conditions(self.stop_conditions, temps):
                self.log_to_display("Stop condition met. Stopping logging.\n")
                should_stop = True
                
            # 2. Fixed duration check
            if self.duration_enabled.get() and self.measure_duration_sec is not None and seconds_elapsed >= self.measure_duration_sec:
                self.log_to_display("Fixed duration reached. Stopping logging.\n")
                should_stop = True

            if should_stop:
                self.root.after(0, self.stop_logging)
                break

            time_taken = time.time() - start_time
            sleep_time = log_interval_sec - time_taken
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _update_gui_live(self):
        """Update live temperature display and treeview."""
        if not self.running_event.is_set():
            return
            
        try:
            current_temps = self.sensor_manager.get_last_readings()
            
            # Update live temperature labels
            for sid, label in self.sensor_manager.temp_labels.items():
                temp = current_temps.get(sid)
                if temp is not None:
                    label.config(text=f"{temp:.1f} °C")
                else:
                    label.config(text="N/A")
                    
            # Update treeview (using the latest logged data, which might be slightly newer than the latest read)
            if self.data_processor.data:
                latest_data = self.data_processor.data[-1]
                seconds_elapsed = latest_data[1]
                temperatures = latest_data[3:] # Skip Type, Seconds, Timestamp
                self.log_to_treeview(seconds_elapsed, temperatures)
        
        except Exception as e:
            self.error_handler("GUI Update Error", f"Live GUI update failed: {str(e)}")
            
        # Reschedule update
        try:
            view_interval_sec = float(self.view_interval.get())
        except ValueError:
            view_interval_sec = self.default_view_interval
            
        self.view_timer = self.root.after(int(view_interval_sec * 1000), self._update_gui_live)

    # ... save_config, load_config, _convert_legacy_thresholds, on_closing, error_handler methods...
    # (These methods are assumed to be complete and correct based on previous context)

    def save_config(self):
        pass # Placeholder

    def load_config(self):
        pass # Placeholder

    def _convert_legacy_thresholds(self, loaded_config: Dict):
        pass # Placeholder

    def on_closing(self):
        """Handle application shutdown."""
        self.stop_logging()
        self.root.destroy()

    def error_handler(self, title: str, message: str):
        """Handle errors with messagebox."""
        messagebox.showerror(title, message)
