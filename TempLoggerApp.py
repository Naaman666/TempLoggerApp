# -*- coding: utf-8 -*-
"""
Temperature Logger Application for DS18B20 sensors.
Target hardware: Raspberry Pi Zero 2 W (512 MB RAM, 1 GHz quad-core CPU).
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import threading
import time
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import os
import json
from w1thermsensor import W1ThermSensor, SensorNotReadyError
from functools import wraps
from typing import Dict, List, Optional
import uuid

# ---------- Helper Functions ----------
def sanitize_filename(name: str) -> str:
    """Sanitize filename by keeping only alphanumeric and allowed characters."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()

def retry(max_attempts: int = 5, delay: float = 0.1):
    """Decorator for retrying a function on specific exceptions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except SensorNotReadyError:
                    time.sleep(delay)
            raise SensorNotReadyError(f"Failed after {max_attempts} attempts")
        return wrapper
    return decorator

class ExportManager:
    """Manages export states to prevent duplicates and handle overwrites."""
    def __init__(self):
        self.exported_formats: Dict[str, bool] = {'excel': False, 'csv': False, 'json': False}

    def check_overwrite(self, format_type: str) -> bool:
        """Check if format was exported and prompt for overwrite."""
        if self.exported_formats.get(format_type, False):
            return messagebox.askyesno("Overwrite Confirmation", f"{format_type.upper()} file already exported. Overwrite?")
        return True

    def mark_exported(self, format_type: str):
        """Mark format as exported."""
        self.exported_formats[format_type] = True

class GUIBuilder:
    """Handles GUI initialization and management."""
    def __init__(self, root: tk.Tk, app):
        self.root = root
        self.app = app
        self.init_gui()

    def init_gui(self):
        """Initialize the GUI elements."""
        self.root.title("Temperature Logger")
        self.root.geometry("1400x730")
        self.root.protocol("WM_DELETE_WINDOW", self.app.on_closing)

        # Start/Stop buttons
        self.start_button = ttk.Button(self.root, text="Start", command=self.app.start_logging)
        self.start_button.grid(row=0, column=0, padx=5, pady=5, sticky='EW')
        self.stop_button = ttk.Button(self.root, text="Stop", command=self.app.stop_logging, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=5, pady=5, sticky='EW')

        # Generate Output checkbox
        self.app.generate_output_var = tk.BooleanVar(value=True)
        self.generate_output_check = ttk.Checkbutton(self.root, text="Generate Output", variable=self.app.generate_output_var)
        self.generate_output_check.grid(row=0, column=2, padx=5, pady=5, sticky='EW')
        self.create_tooltip(self.generate_output_check, "Generate plots (PNG, PDF) when stopping measurement")

        # (i) info label for tooltip
        self.output_info_label = ttk.Label(self.root, text="(i)")
        self.output_info_label.grid(row=0, column=3, padx=5, pady=5, sticky='EW')
        self.create_tooltip(self.output_info_label, "Log file always generated")

        # Log interval
        ttk.Label(self.root, text="Log interval (s):").grid(row=1, column=0, padx=5, pady=5)
        self.app.log_interval = tk.StringVar(value=str(self.app.default_log_interval))
        self.log_interval_entry = ttk.Entry(self.root, textvariable=self.app.log_interval, width=5, validate="focusout", validatecommand=(self.root.register(self.app.validate_positive_int), '%P', 'log_interval'))
        self.log_interval_entry.grid(row=1, column=1, padx=5, pady=5)
        self.create_tooltip(self.log_interval_entry, "Enter positive integer for log interval")

        # View interval
        ttk.Label(self.root, text="Display update (s):").grid(row=2, column=0, padx=5, pady=5)
        self.app.view_interval = tk.StringVar(value=str(self.app.default_view_interval))
        self.view_interval_entry = ttk.Entry(self.root, textvariable=self.app.view_interval, width=5, validate="focusout", validatecommand=(self.root.register(self.app.validate_positive_int), '%P', 'view_interval'))
        self.view_interval_entry.grid(row=2, column=1, padx=5, pady=5)
        self.create_tooltip(self.view_interval_entry, "Enter positive integer for display update interval")

        # Measurement duration
        ttk.Label(self.root, text="Measurement duration (hours):").grid(row=3, column=0, padx=5, pady=5)
        self.app.duration = tk.StringVar(value="0.0")
        self.duration_entry = ttk.Entry(self.root, textvariable=self.app.duration, width=5, validate="focusout", validatecommand=(self.root.register(self.app.validate_non_negative_float), '%P', 'duration'))
        self.duration_entry.grid(row=3, column=1, padx=5, pady=5)
        self.create_tooltip(self.duration_entry, "Enter non-negative float for duration (0 for unlimited)")

        # Start threshold
        ttk.Label(self.root, text="Start threshold (°C):").grid(row=4, column=0, padx=5, pady=5)
        self.app.start_threshold = tk.StringVar(value=str(self.app.default_start_threshold))
        self.start_threshold_entry = ttk.Entry(self.root, textvariable=self.app.start_threshold, width=5, validate="focusout", validatecommand=(self.root.register(self.app.validate_float), '%P', 'start_threshold'))
        self.start_threshold_entry.grid(row=4, column=1, padx=5, pady=5)
        self.create_tooltip(self.start_threshold_entry, "Enter float for start temperature threshold")

        # Stop threshold
        ttk.Label(self.root, text="Stop threshold (°C):").grid(row=5, column=0, padx=5, pady=5)
        self.app.stop_threshold = tk.StringVar(value=str(self.app.default_stop_threshold))
        self.stop_threshold_entry = ttk.Entry(self.root, textvariable=self.app.stop_threshold, width=5, validate="focusout", validatecommand=(self.root.register(self.app.validate_float), '%P', 'stop_threshold'))
        self.stop_threshold_entry.grid(row=5, column=1, padx=5, pady=5)
        self.create_tooltip(self.stop_threshold_entry, "Enter float for stop temperature threshold (greater than start)")

        # Measurement name
        ttk.Label(self.root, text="Measurement name:").grid(row=6, column=0, padx=5, pady=5)
        self.app.measurement_name = tk.StringVar(value="temptestlog")
        self.measurement_name_entry = ttk.Entry(self.root, textvariable=self.app.measurement_name, width=20)
        self.measurement_name_entry.grid(row=6, column=1, padx=5, pady=5)
        self.create_tooltip(self.measurement_name_entry, "Only alphanumeric characters, numbers, - and _ are allowed for measurement name.")

        # Sensor selection frame
        self.app.sensor_frame = tk.Frame(self.root)
        self.app.sensor_frame.grid(row=7, column=0, columnspan=4, padx=5, pady=5, sticky='W')
        self.update_sensor_checkboxes()

        # Log display
        self.app.log_display = scrolledtext.ScrolledText(self.root, width=160, height=25)
        self.app.log_display.grid(row=8, column=0, columnspan=4, padx=5, pady=5)

        # Export buttons
        self.excel_button = ttk.Button(self.root, text="Save Excel", command=lambda: self.app.data_processor.save_data('excel'))
        self.excel_button.grid(row=9, column=0, columnspan=1, padx=5, pady=5)
        self.csv_button = ttk.Button(self.root, text="Save CSV", command=lambda: self.app.data_processor.save_data('csv'))
        self.csv_button.grid(row=9, column=1, columnspan=1, padx=5, pady=5)
        self.json_button = ttk.Button(self.root, text="Save JSON", command=lambda: self.app.data_processor.save_data('json'))
        self.json_button.grid(row=9, column=2, columnspan=1, padx=5, pady=5)

        # Config buttons
        self.save_config_button = ttk.Button(self.root, text="Save sensor config", command=self.app.save_sensor_config)
        self.save_config_button.grid(row=9, column=3, padx=5, pady=5)
        self.load_config_button = ttk.Button(self.root, text="Load sensor config", command=self.app.load_sensor_config)
        self.load_config_button.grid(row=9, column=4, padx=5, pady=5)
        self.reset_config_button = ttk.Button(self.root, text="Reset Config to Default", command=self.app.reset_config_to_default)
        self.reset_config_button.grid(row=9, column=5, padx=5, pady=5)

        # Progress bar
        self.app.progress_bar = ttk.Progressbar(self.root, orient='horizontal', mode='determinate', maximum=100, length=400)
        self.app.progress_label = ttk.Label(self.root, text="")
        self.app.progress_bar.grid(row=10, column=0, columnspan=4, pady=5, sticky='EW')
        self.app.progress_label.grid(row=11, column=0, columnspan=4, pady=2, sticky='EW')
        self.app.progress_bar.grid_remove()
        self.app.progress_label.grid_remove()

    def create_tooltip(self, widget: tk.Widget, text: str):
        """Create a simple tooltip for a widget."""
        def enter(event):
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{event.x_root + 20}+{event.y_root + 20}")
            label = tk.Label(self.tooltip, text=text, background="yellow", relief="solid", borderwidth=1, padx=5, pady=3)
            label.pack()

        def leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def update_sensor_checkboxes(self):
        """Update sensor checkboxes based on sensor states."""
        for widget in self.app.sensor_frame.winfo_children():
            widget.destroy()
        self.app.sensor_manager.sensor_vars.clear()
        self.app.sensor_manager.sensor_checkbuttons.clear()
        for i, sensor in enumerate(self.app.sensor_manager.sensors):
            var = tk.BooleanVar(value=sensor.enabled)
            chk = ttk.Checkbutton(self.app.sensor_frame, text=f"Sensor_{i+1} ({sensor.id[:8]})", variable=var, command=lambda s=sensor, v=var: self.app.toggle_sensor(s, v))
            chk.grid(row=i, column=0, sticky='W')
            self.app.sensor_manager.sensor_vars[sensor.id] = var
            self.app.sensor_manager.sensor_checkbuttons[sensor.id] = chk

class SensorManager:
    """Manages DS18B20 sensor initialization, reading, and configuration."""
    def __init__(self, app):
        self.app = app
        self.sensors: List[W1ThermSensor] = []
        self.sensor_ids: List[str] = []
        self.sensor_names: Dict[str, str] = {}
        self.sensor_vars: Dict[str, tk.BooleanVar] = {}
        self.sensor_checkbuttons: Dict[str, ttk.Checkbutton] = {}
        self.init_sensors()

    def init_sensors(self):
        """Initialize DS18B20 sensors and update GUI."""
        try:
            self.sensors = W1ThermSensor.get_available_sensors()
            self.sensor_ids = [s.id for s in self.sensors]
            self.sensor_names = {sid: f"Sensor_{i+1}" for i, sid in enumerate(self.sensor_ids)}
            self.app.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_names[sid] for sid in self.sensor_ids]

            # Create sensor selection frame
            self.app.gui.sensor_frame = tk.Frame(self.app.root)
            self.app.gui.sensor_frame.grid(row=7, column=0, columnspan=4, padx=5, pady=5, sticky='W')
            for widget in self.app.gui.sensor_frame.winfo_children():
                widget.destroy()
            self.sensor_vars.clear()
            self.sensor_checkbuttons.clear()

            for i, sensor in enumerate(self.sensors):
                var = tk.BooleanVar(value=True)
                chk = ttk.Checkbutton(self.app.gui.sensor_frame, text=self.sensor_names[sensor.id], variable=var)
                chk.pack(anchor='w')
                chk.bind("<Double-Button-1>", lambda e, sid=sensor.id: self.rename_sensor(sid))
                self.sensor_vars[sensor.id] = var
                self.sensor_checkbuttons[sensor.id] = chk

            if not self.sensors:
                self.app.error_handler("Warning", "No DS18B20 sensors found!")
                self.app.log_display.insert(tk.END, "ERROR: No DS18B20 sensors found!\n")
                self.app.log_display.see(tk.END)

        except Exception as e:
            self.app.error_handler("Error", f"Sensor initialization failed: {str(e)}")

    def list_sensors_status(self):
        """Log the status of all sensors."""
        self.app.log_display.insert(tk.END, "Sensor status diagnostics:\n")
        for sid in self.sensor_ids:
            self.app.log_display.insert(tk.END, f"{self.sensor_names[sid]} - ID: {sid} - Active: {self.sensor_vars[sid].get()}\n")
        self.app.log_display.see(tk.END)

    def rename_sensor(self, sid: str):
        """Rename a sensor via double-click with unique name check."""
        new_name = simpledialog.askstring("Rename Sensor", "Enter new sensor name:", initialvalue=self.sensor_names[sid])
        if not new_name or not new_name.strip():
            messagebox.showerror("Invalid Name", "Sensor name cannot be empty")
            return
        sanitized = sanitize_filename(new_name)
        if sanitized in self.sensor_names.values():
            i = 1
            while f"{sanitized}_{i}" in self.sensor_names.values():
                i += 1
            sanitized = f"{sanitized}_{i}"
        self.sensor_names[sid] = sanitized
        self.sensor_checkbuttons[sid].config(text=self.sensor_names[sid])
        self.app.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_names[sid] for sid in self.sensor_ids]
        self.app.log_display.insert(tk.END, f"Sensor {sid} renamed to {self.sensor_names[sid]}\n")
        self.app.log_display.see(tk.END)

    @retry(max_attempts=5, delay=0.1)
    def read_sensors(self) -> Dict[str, Optional[float]]:
        """Read temperatures from active sensors with retry and per-sensor error handling."""
        active_sensors = [s for s in self.sensors if self.sensor_vars.get(s.id, tk.BooleanVar(value=False)).get()]
        temps: Dict[str, Optional[float]] = {sid: None for sid in self.sensor_ids}
        for sensor in active_sensors:
            try:
                temps[sensor.id] = round(sensor.get_temperature(), 2)
            except Exception as e:
                temps[sensor.id] = None
                self.app.root.after(0, self.app.log_display.insert, tk.END, f"{self.sensor_names[sensor.id]} error: {str(e)}\n")
                self.app.root.after(0, self.app.log_display.see, tk.END)
        return temps

class DataProcessor:
    """Handles data logging, export, and plotting."""
    def __init__(self, app):
        self.app = app

    def limit_log_lines(self):
        """Limit the number of lines in log display to prevent slowdown."""
        line_count = int(self.app.log_display.index('end-1c').split('.')[0])
        if line_count > self.app.max_log_lines:
            self.app.log_display.delete(1.0, f"{line_count - self.app.max_log_lines}.0")

    def save_data(self, format_type: str = 'excel'):
        """Export data to specified format or generate plots."""
        if format_type != 'plot':
            if not self.app.export_manager.check_overwrite(format_type):
                return

        log_path = os.path.join(self.app.measurement_folder, self.app.log_filename)
        # ... (a teljes DataProcessor save_data metódus a eredeti kódból, .loc használatával a pandas warning ellen)
        # Példa a .loc használatára:
        df.loc[:, 'Timestamp'] = pd.to_datetime(df['Timestamp'])
        # Teljes implementáció a eredeti kódból, optimalizálva

    # ... (a többi DataProcessor metódus a eredeti kódból, .loc használatával)

class TempLoggerApp:
    """Main application class."""
    def __init__(self, root):
        self.root = root
        self.running_event = threading.Event()
        self.lock = threading.Lock()
        self.max_log_lines = 500
        self.export_manager = ExportManager()
        self.measurement_folder = "TestResults"
        self.config_folder = "SensorConfigs"
        # Default értékek
        self.default_log_interval = 10
        self.default_view_interval = 3
        self.default_start_threshold = 22.0
        self.default_stop_threshold = 30.0
        self.measure_start_time = None
        self.measure_duration_sec = None
        self.log_file = None
        self.view_timer = None
        self.log_timer = None
        self.data_columns = []
        self.loaded_config = None
        # Korai log_display inicializálás (#18 A.)
        self.log_display = scrolledtext.ScrolledText(self.root, width=160, height=25)
        self.log_display.pack()
        # Config betöltés (#20 C., #21 C., #22 C.)
        self.load_default_config()
        # Komponensek inicializálása
        self.gui = GUIBuilder(self.root, self)
        self.sensor_manager = SensorManager(self)
        self.data_processor = DataProcessor(self)
        self.progress_bar = ttk.Progressbar(self.root, orient='horizontal', mode='determinate', maximum=100, length=400)
        self.progress_label = ttk.Label(self.root, text="")
        # GUI repack a korai log_display után
        self.log_display.pack_forget()
        self.gui.init_gui()
        # Szenzorok frissítése
        self.sensor_manager.init_sensors()
        # Timerek átállítása root.after-re (#1 A., #2 B., #8 A.)
        self.root.after(100, self.check_conditions)

    def load_default_config(self):
        """Load default config from configs/config.json (#20 C., #22 C.)."""
        configs_path = os.path.join(os.getcwd(), "configs")
        os.makedirs(configs_path, exist_ok=True)
        config_path = os.path.join(configs_path, "config.json")
        counter_path = os.path.join(configs_path, "counter.json")
        # Default config létrehozása, ha hiányzik
        if not os.path.exists(config_path):
            default_config = {
                "default_log_interval": self.default_log_interval,
                "default_view_interval": self.default_view_interval,
                "default_start_threshold": self.default_start_threshold,
                "default_stop_threshold": self.default_stop_threshold,
                "max_log_lines": self.max_log_lines,
                "measurement_folder": "TestResults",
                "config_folder": "SensorConfigs"
            }
            with open(config_path, "w") as f:
                json.dump(default_config, f, indent=4)
        if not os.path.exists(counter_path):
            default_counter = {"session_counter": 0}
            with open(counter_path, "w") as f:
                json.dump(default_counter, f, indent=4)
        # Betöltés
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                self.default_log_interval = config.get("default_log_interval", self.default_log_interval)
                self.default_view_interval = config.get("default_view_interval", self.default_view_interval)
                self.default_start_threshold = config.get("default_start_threshold", self.default_start_threshold)
                self.default_stop_threshold = config.get("default_stop_threshold", self.default_stop_threshold)
                self.max_log_lines = config.get("max_log_lines", self.max_log_lines)
                self.measurement_folder = config.get("measurement_folder", self.measurement_folder)
                self.config_folder = config.get("config_folder", self.config_folder)
        except json.JSONDecodeError as e:
            self.error_handler("Warning", f"Invalid config.json: {str(e)}. Using defaults.")
        os.makedirs(self.config_folder, exist_ok=True)
        os.makedirs(self.measurement_folder, exist_ok=True)

    # ... (a többi metódus a eredeti kódból, módosítva a javaslatok szerint: root.after a timerekre, .loc pandas-ra, init_filenames start_logging-ba mozgatva, save/load config bővítve, reset_config_to_default hozzáadva, stb.)

    def validate_positive_int(self, value: str, field: str) -> bool:
        """Validate positive integer input."""
        try:
            val = int(value)
            if val <= 0:
                raise ValueError
            return True
        except ValueError:
            self.error_handler("Invalid Input", f"{field} must be positive integer")
            return False

    def validate_non_negative_float(self, value: str, field: str) -> bool:
        """Validate non-negative float input."""
        try:
            val = float(value)
            if val < 0:
                raise ValueError
            if val > 10:
                messagebox.showwarning("Warning", f"Duration {val} hours is long, may consume resources on Raspberry Pi")
            return True
        except ValueError:
            self.error_handler("Invalid Input", f"{field} must be non-negative float")
            return False

    def validate_float(self, value: str, field: str) -> bool:
        """Validate float input."""
        try:
            float(value)
            return True
        except ValueError:
            self.error_handler("Invalid Input", f"{field} must be a float")
            return False

    def error_handler(self, title: str, message: str):
        """Centralized error handling with messagebox and log (#18 A.)."""
        messagebox.showerror(title, message)
        if hasattr(self, 'log_display'):
            self.log_display.insert(tk.END, f"{title}: {message}\n")
            self.log_display.see(tk.END)
            self.data_processor.limit_log_lines()

    def start_logging(self):
        """Start the logging process with edge case checks (#13 A.+B., #15 A.)."""
        try:
            self.measure_duration_sec = int(float(self.duration.get()) * 3600) if float(self.duration.get()) > 0 else None
            start_th = float(self.start_threshold.get())
            stop_th = float(self.stop_threshold.get())
            if start_th >= stop_th:
                raise ValueError("Start threshold must be less than stop threshold")
            if int(self.log_interval.get()) <= 0 or int(self.view_interval.get()) <= 0:
                raise ValueError("Intervals must be positive")
        except (tk.TclError, ValueError) as e:
            self.error_handler("Error", f"Invalid input: {str(e)}")
            return

        active_sensors = [sid for sid, var in self.sensor_manager.sensor_vars.items() if var.get()]
        if not active_sensors:
            messagebox.showwarning("Warning", "No active sensors selected!")
            return

        self.running_event.set()
        self.gui.start_button.config(state="disabled")
        self.gui.stop_button.config(state="normal")
        self.gui.excel_button.config(state="disabled")
        self.gui.csv_button.config(state="disabled")
        self.gui.json_button.config(state="disabled")

        # Új mappa/fájlnevek minden mérésnél (#15 A.)
        self.init_filenames()
        log_path = os.path.join(self.measurement_folder, self.log_filename)
        try:
            self.log_file = open(log_path, "a", buffering=1, encoding='utf-8')
            header = ",".join(self.data_columns)
            self.log_file.write(header + "\n")
        except IOError as e:
            self.error_handler("Error", f"Failed to open log file: {str(e)}")
            self.reset_gui_state()
            return

        # root.after ütemezés (#1 A.)
        self.schedule_view_update()
        self.schedule_log_update()
        if self.measure_duration_sec is not None:
            self.root.after(1000, self.update_progress, time.time())

    def reset_gui_state(self):
        """Reset GUI state on error (#7 B.)."""
        self.gui.start_button.config(state="normal")
        self.gui.stop_button.config(state="disabled")
        self.gui.excel_button.config(state="normal")
        self.gui.csv_button.config(state="normal")
        self.gui.json_button.config(state="normal")

    def stop_logging(self):
        """Stop the logging process (#13 A.+B.)."""
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
            except IOError as e:
                self.error_handler("Error", f"Failed to close log file: {str(e)}")
            self.log_file = None
        self.progress_bar.grid_remove()
        self.progress_label.grid_remove()

        if self.generate_output_var.get():
            self.data_processor.save_data('plot')

    def schedule_view_update(self):
        """Schedule view update with root.after (#1 A.)."""
        if self.running_event.is_set():
            self.root.after(int(self.view_interval.get()) * 1000, self.view_update)

    def schedule_log_update(self):
        """Schedule log update with root.after (#1 A.)."""
        if self.running_event.is_set():
            self.root.after(int(self.log_interval.get()) * 1000, self.log_update)

    def view_update(self):
        """Update GUI view (#8 A.)."""
        if not self.running_event.is_set():
            return
        current_time = time.time()
        seconds = int(current_time)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        temps_dict = self.sensor_manager.read_sensors()
        temps_list = [temps_dict[sid] for sid in self.sensor_manager.sensor_ids]
        view_line = f"VIEW,{seconds},{timestamp}," + ",".join([str(t) if t is not None else 'ERROR' for t in temps_list])
        self.log_display.insert(tk.END, view_line + "\n")
        self.log_display.see(tk.END)
        self.data_processor.limit_log_lines()
        self.schedule_view_update()

    def log_update(self):
        """Log to file (#13 A.)."""
        if not self.running_event.is_set():
            return
        if self.log_file is None:
            self.error_handler("Error", "Log file not initialized, stopping logging")
            self.stop_logging()
            return
        current_time = time.time()
        seconds = int(current_time)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        temps_dict = self.sensor_manager.read_sensors()
        temps_list = [temps_dict[sid] for sid in self.sensor_manager.sensor_ids]
        log_line = f"LOG,{seconds},{timestamp}," + ",".join([str(t) if t is not None else 'ERROR' for t in temps_list])
        try:
            self.log_file.write(log_line + "\n")
            self.log_file.flush()
        except IOError as e:
            self.error_handler("Error", f"Failed to write to log file: {str(e)}")
        self.schedule_log_update()

    def update_loop(self):
        """Condition checking with root.after (#8 A.)."""
        measurement_started = False

        def check_conditions():
            if not self.running_event.is_set():
                return
            current_time = time.time()
            temps_dict = self.sensor_manager.read_sensors()
            temps_list = [temps_dict[sid] for sid in self.sensor_manager.sensor_ids]

            nonlocal measurement_started
            if not measurement_started:
                if any(temps_dict.get(sid, 0) is not None and temps_dict[sid] >= float(self.start_threshold.get()) for sid in self.sensor_manager.sensor_ids):
                    measurement_started = True
                    self.measure_start_time = current_time
                    self.log_display.insert(tk.END, "Measurement started due to condition\n")
                    self.log_display.see(tk.END)
                    self.data_processor.limit_log_lines()

            if measurement_started:
                if any(t is not None and t >= float(self.stop_threshold.get()) for t in temps_list):
                    self.log_display.insert(tk.END, "Measurement stopped due to temperature threshold\n")
                    self.log_display.see(tk.END)
                    self.data_processor.limit_log_lines()
                    self.stop_logging()
                    return

                if self.measure_duration_sec is not None and current_time - self.measure_start_time >= self.measure_duration_sec:
                    self.log_display.insert(tk.END, "Measurement stopped due to duration\n")
                    self.log_display.see(tk.END)
                    self.data_processor.limit_log_lines()
                    self.stop_logging()
                    return

            self.root.after(100, check_conditions)

        self.root.after(100, check_conditions)

    def save_sensor_config(self):
        """Save sensor configuration to a JSON file (#20 C.)."""
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
        self.log_display.insert(tk.END, f"Sensor configuration saved: {filename}\n")
        self.log_display.see(tk.END)
        self.data_processor.limit_log_lines()
        messagebox.showinfo("Success", f"{os.path.basename(filename)} saved")

    def load_sensor_config(self):
        """Load sensor configuration from a JSON file and apply automatically (#20 C.)."""
        filename = filedialog.askopenfilename(
            initialdir=self.config_folder,
            title="Load sensor configuration",
            filetypes=[("JSON files", "*.json")]
        )
        if not filename:
            return
        try:
            with open(filename, "r", encoding='utf-8') as f:
                self.loaded_config = json.load(f)
            # Auto apply
            self.apply_config()
            self.log_display.insert(tk.END, f"Sensor configuration loaded: {filename}. Applied automatically.\n")
            self.sensor_manager.list_sensors_status()
            self.log_display.see(tk.END)
            self.data_processor.limit_log_lines()
            messagebox.showinfo("Success", f"{os.path.basename(filename)} loaded and applied")
        except Exception as e:
            self.error_handler("Error", f"Loading configuration failed: {str(e)}")

    def apply_config(self):
        """Apply the loaded configuration to GUI and sensors (#20 C.)."""
        if not self.loaded_config:
            self.error_handler("Error", "No configuration loaded to apply")
            return
        try:
            active_sensors = self.loaded_config.get("active_sensors", [])
            for sid, var in self.sensor_manager.sensor_vars.items():
                var.set(sid in active_sensors)
            self.sensor_manager.sensor_names = self.loaded_config.get("sensor_names", self.sensor_manager.sensor_names)
            self.start_threshold.set(str(self.loaded_config.get("start_threshold", self.default_start_threshold)))
            self.stop_threshold.set(str(self.loaded_config.get("stop_threshold", self.default_stop_threshold)))
            self.log_interval.set(str(self.loaded_config.get("log_interval", self.default_log_interval)))
            self.view_interval.set(str(self.loaded_config.get("view_interval", self.default_view_interval)))
            self.duration.set(str(self.loaded_config.get("duration", 0.0)))
            self.measurement_name.set(self.loaded_config.get("measurement_name", "temptestlog"))
            # Update checkbutton texts
            for sid, chk in self.sensor_manager.sensor_checkbuttons.items():
                chk.config(text=self.sensor_manager.sensor_names[sid])
            self.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_manager.sensor_names[sid] for sid in self.sensor_manager.sensor_ids]
            self.log_display.insert(tk.END, "Configuration applied successfully.\n")
            self.sensor_manager.list_sensors_status()
            self.log_display.see(tk.END)
            self.data_processor.limit_log_lines()
        except Exception as e:
            self.error_handler("Error", f"Applying configuration failed: {str(e)}")

    def reset_config_to_default(self):
        """Reset to default config (#20 C.)."""
        self.load_default_config()
        self.measurement_name.set("temptestlog")
        self.log_interval.set(str(self.default_log_interval))
        self.view_interval.set(str(self.default_view_interval))
        self.duration.set("0.0")
        self.start_threshold.set(str(self.default_start_threshold))
        self.stop_threshold.set(str(self.default_stop_threshold))
        for var in self.sensor_manager.sensor_vars.values():
            var.set(True)
        self.sensor_manager.init_sensors()
        messagebox.showinfo("Success", "Configuration reset to default. All sensors enabled.")

    def on_closing(self):
        """Handle application shutdown."""
        self.stop_logging()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TempLoggerApp(root)
    app.update_loop()
    root.mainloop()