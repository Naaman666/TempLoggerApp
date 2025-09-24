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
        self.root.title("Temperature Logger - DeepSeek v5")
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

        # Log display
        self.app.log_display = scrolledtext.ScrolledText(self.root, width=160, height=25)
        self.app.log_display.grid(row=6, column=0, columnspan=4, padx=5, pady=5)

        # Export buttons
        self.excel_button = ttk.Button(self.root, text="Save Excel", command=lambda: self.app.save_data('excel'))
        self.excel_button.grid(row=7, column=0, columnspan=1, padx=5, pady=5)
        self.csv_button = ttk.Button(self.root, text="Save CSV", command=lambda: self.app.save_data('csv'))
        self.csv_button.grid(row=7, column=1, columnspan=1, padx=5, pady=5)
        self.json_button = ttk.Button(self.root, text="Save JSON", command=lambda: self.app.save_data('json'))
        self.json_button.grid(row=7, column=2, columnspan=1, padx=5, pady=5)

        # Config buttons
        self.save_config_button = ttk.Button(self.root, text="Save sensor config", command=self.app.save_sensor_config)
        self.save_config_button.grid(row=7, column=3, padx=5, pady=5)
        self.load_config_button = ttk.Button(self.root, text="Load sensor config", command=self.app.load_sensor_config)
        self.load_config_button.grid(row=7, column=4, padx=5, pady=5)
        self.apply_config_button = ttk.Button(self.root, text="Apply Config", command=self.app.apply_config)
        self.apply_config_button.grid(row=7, column=5, padx=5, pady=5)

        # Progress bar
        self.app.progress_bar = ttk.Progressbar(self.root, orient='horizontal', mode='determinate', maximum=100, length=400)
        self.app.progress_label = ttk.Label(self.root, text="")
        self.app.progress_bar.grid(row=8, column=0, columnspan=4, pady=5, sticky='EW')
        self.app.progress_label.grid(row=9, column=0, columnspan=4, pady=2, sticky='EW')
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

class SensorManager:
    """Manages DS18B20 sensor initialization, reading, and configuration."""
    def __init__(self, app):
        self.app = app
        self.sensors: List[W1ThermSensor] = []
        self.sensor_ids: List[str] = []
        self.sensor_names: Dict[str, str] = {}
        self.sensor_vars: Dict[str, tk.BooleanVar] = {}
        self.sensor_checkbuttons: Dict[str, ttk.Checkbutton] = {}

    def init_sensors(self):
        """Initialize DS18B20 sensors and update GUI."""
        try:
            self.sensors = W1ThermSensor.get_available_sensors()
            self.sensor_ids = [s.id for s in self.sensors]
            self.sensor_names = {sid: f"Sensor_{i+1}" for i, sid in enumerate(self.sensor_ids)}
            self.app.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_names[sid] for sid in self.sensor_ids]

            # Create sensor selection frame
            self.app.sensor_frame = tk.Frame(self.app.root)
            self.app.sensor_frame.grid(row=4, column=2, columnspan=2, padx=5, pady=5, sticky='W')
            for widget in self.app.sensor_frame.winfo_children():
                widget.destroy()
            self.sensor_vars.clear()
            self.sensor_checkbuttons.clear()

            for i, sensor in enumerate(self.sensors):
                var = tk.BooleanVar(value=True)
                chk = ttk.Checkbutton(self.app.sensor_frame, text=self.sensor_names[sensor.id], variable=var)
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
        if not os.path.exists(log_path) or os.path.getsize(log_path) == 0:
            messagebox.showwarning("Warning", "No data to save in log file!")
            return

        chunksize = 10000
        try:
            if format_type == 'plot':
                # Collect data for plotting incrementally
                timestamps = []
                temp_data = {col: [] for col in self.app.data_columns[3:]}
                active_sensor_cols = [col for col in self.app.data_columns[3:] if col in self.app.sensor_manager.sensor_names.values()]

                for chunk in pd.read_csv(log_path, chunksize=chunksize):
                    if 'Type' not in chunk.columns or chunk[chunk['Type'] == 'LOG'].empty:
                        continue
                    df = chunk[chunk['Type'] == 'LOG']
                    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
                    timestamps.extend(df['Timestamp'].tolist())
                    for col in active_sensor_cols:
                        if col in df.columns:
                            temp_data[col].extend(df[col].dropna().tolist())  # Drop NaN to avoid plot issues

                # Plot once after collecting all data
                plt.figure(figsize=(12, 6))
                for col in active_sensor_cols:
                    if temp_data[col]:
                        plt.plot(timestamps[:len(temp_data[col])], temp_data[col], label=col)

                plt.xlabel("Timestamp")
                plt.ylabel("Temperature (°C)")
                plt.title("Temperature Log")
                ncol = min(4, len(active_sensor_cols) // 3 + 1)
                plt.legend(bbox_to_anchor=(0.5, -0.15), loc='upper center', ncol=ncol)
                plt.xticks(rotation=45)
                plt.grid(True)
                plt.tight_layout()
                plt.subplots_adjust(bottom=0.25)

                # Save PDF and PNG
                pdf_path = os.path.join(self.app.measurement_folder, self.app.graph_pdf_filename)
                png_path = os.path.join(self.app.measurement_folder, self.app.graph_filename)
                plt.savefig(pdf_path, format='pdf', dpi=100, bbox_inches='tight')
                plt.savefig(png_path, format='png', dpi=100, bbox_inches='tight')
                plt.close()

                messagebox.showinfo("Success", f"Plots saved: {png_path}, {pdf_path}")

            else:
                # Export data chunk-by-chunk without plotting
                path = ""
                for chunk in pd.read_csv(log_path, chunksize=chunksize):
                    if 'Type' not in chunk.columns or chunk[chunk['Type'] == 'LOG'].empty:
                        continue
                    df = chunk[chunk['Type'] == 'LOG']
                    if format_type == 'excel':
                        path = os.path.join(self.app.measurement_folder, self.app.excel_filename)
                        with pd.ExcelWriter(path, mode='a' if os.path.exists(path) else 'w', engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, header=not os.path.exists(path))
                    elif format_type == 'csv':
                        path = os.path.join(self.app.measurement_folder, self.app.csv_filename)
                        df.to_csv(path, mode='a', index=False, header=not os.path.exists(path))
                    elif format_type == 'json':
                        path = os.path.join(self.app.measurement_folder, self.app.json_filename)
                        with open(path, 'a', encoding='utf-8') as f:
                            df.to_json(f, orient='records', lines=True, force_ascii=False)

                self.app.export_manager.mark_exported(format_type)
                messagebox.showinfo("Success", f"Data saved: {path}")

        except Exception as e:
            self.app.error_handler("Error", f"Data saving or plotting failed: {str(e)}")

class TempLoggerApp:
    """Main application class coordinating GUI, sensors, and data processing."""
    def __init__(self, root: tk.Tk):
        self.root = root
        self.data_columns: List[str] = []
        self.measurement_folder: str = ""
        self.config_folder: str = ""
        self.log_filename: str = ""
        self.excel_filename: str = ""
        self.csv_filename: str = ""
        self.json_filename: str = ""
        self.graph_filename: str = ""
        self.graph_pdf_filename: str = ""
        self.running_event = threading.Event()
        self.view_timer: Optional[threading.Timer] = None
        self.log_timer: Optional[threading.Timer] = None
        self.log_file = None
        self.measure_duration_sec: Optional[int] = None
        self.measure_start_time: Optional[float] = None
        self.default_log_interval: int = 10
        self.default_view_interval: int = 3
        self.default_start_threshold: float = 22.0
        self.default_stop_threshold: float = 30.0
        self.max_log_lines: int = 500
        self.lock = threading.Lock()  # For thread safety
        self.loaded_config: Optional[Dict] = None  # For apply_config
        self.generate_output_var: tk.BooleanVar = None  # Initialized in GUI

        # Load default config
        self.load_default_config()

        # Initialize components
        self.export_manager = ExportManager()
        self.gui = GUIBuilder(self.root, self)
        self.sensor_manager = SensorManager(self)
        self.data_processor = DataProcessor(self)

        # Initialize filenames
        self.init_filenames()

        # Create folders
        os.makedirs(self.measurement_folder, exist_ok=True)
        os.makedirs(self.config_folder, exist_ok=True)

        # Initialize sensors
        self.sensor_manager.init_sensors()
        self.sensor_manager.list_sensors_status()

    def load_default_config(self):
        """Load default configuration from JSON file in root directory with fallback and validation."""
        default_config_path = "config.json"
        try:
            with open(default_config_path, "r", encoding='utf-8') as f:
                config = json.load(f)
            self.default_log_interval = int(config.get("default_log_interval", self.default_log_interval))
            if self.default_log_interval <= 0:
                raise ValueError("default_log_interval must be positive")
            self.default_view_interval = int(config.get("default_view_interval", self.default_view_interval))
            if self.default_view_interval <= 0:
                raise ValueError("default_view_interval must be positive")
            self.default_start_threshold = float(config.get("default_start_threshold", self.default_start_threshold))
            self.default_stop_threshold = float(config.get("default_stop_threshold", self.default_stop_threshold))
            if self.default_start_threshold >= self.default_stop_threshold:
                raise ValueError("start_threshold must be less than stop_threshold")
            self.max_log_lines = int(config.get("max_log_lines", self.max_log_lines))
            if self.max_log_lines <= 0:
                raise ValueError("max_log_lines must be positive")
            self.measurement_folder = config.get("measurement_folder", "TestResults")
            self.config_folder = config.get("config_folder", "SensorConfigs")
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            self.log_display.insert(tk.END, f"Warning: Failed to load config.json, using hardcoded values: {str(e)}\n")
            self.log_display.see(tk.END)
            # Fallback to hardcoded
            self.default_log_interval = 10
            self.default_view_interval = 3
            self.default_start_threshold = 22.0
            self.default_stop_threshold = 30.0
            self.max_log_lines = 500
            self.measurement_folder = "TestResults"
            self.config_folder = "SensorConfigs"

    def init_filenames(self):
        """Initialize output file names with timestamp."""
        now_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.measurement_folder = os.path.join(self.measurement_folder, f"temptestlog-{now_str}")
        os.makedirs(self.measurement_folder, exist_ok=True)
        self.log_filename = f"temptestlog-{now_str}.log"
        self.excel_filename = f"temptestlog-{now_str}.xlsx"
        self.csv_filename = f"temptestlog-{now_str}.csv"
        self.json_filename = f"temptestlog-{now_str}.json"
        self.graph_filename = f"temptestlog-{now_str}.png"
        self.graph_pdf_filename = f"temptestlog-{now_str}.pdf"

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
            if val > 10:  # Warning for long duration
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
        """Centralized error handling with messagebox and log."""
        messagebox.showerror(title, message)
        self.log_display.insert(tk.END, f"{title}: {message}\n")
        self.log_display.see(tk.END)
        self.data_processor.limit_log_lines()

    def start_logging(self):
        """Start the logging process with edge case checks."""
        try:
            with self.lock:
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

        log_path = os.path.join(self.measurement_folder, self.log_filename)
        try:
            with self.lock:
                self.log_file = open(log_path, "a", buffering=1, encoding='utf-8')
                header = ",".join(self.data_columns)
                self.log_file.write(header + "\n")
        except IOError as e:
            self.error_handler("Error", f"Failed to open log file: {str(e)}")
            return

        # Schedule first timers
        self.schedule_view_update()
        self.schedule_log_update()
        if self.measure_duration_sec is not None:
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
                with self.lock:
                    self.log_file.close()
            except IOError as e:
                self.error_handler("Error", f"Failed to close log file: {str(e)}")
            self.log_file = None
        self.progress_bar.grid_remove()
        self.progress_label.grid_remove()

        # Generate plots if checkbox is checked
        if self.generate_output_var.get():
            self.data_processor.save_data('plot')

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
            self.progress_bar.grid()
            self.progress_label.grid()
        else:
            self.progress_bar.grid_remove()
            self.progress_label.grid_remove()
        if self.running_event.is_set():
            self.root.after(1000, self.update_progress, time.time())

    def schedule_view_update(self):
        if self.running_event.is_set():
            self.view_timer = threading.Timer(int(self.view_interval.get()), self.view_update)
            self.view_timer.start()

    def schedule_log_update(self):
        if self.running_event.is_set():
            self.log_timer = threading.Timer(int(self.log_interval.get()), self.log_update)
            self.log_timer.start()

    def view_update(self):
        """Update GUI view."""
        if not self.running_event.is_set():
            return
        current_time = time.time()
        seconds = int(current_time)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.lock:
            temps_dict = self.sensor_manager.read_sensors()
        temps_list = [temps_dict[sid] for sid in self.sensor_manager.sensor_ids]
        view_line = f"VIEW,{seconds},{timestamp}," + ",".join([str(t) if t is not None else 'ERROR' for t in temps_list])
        self.root.after(0, self.log_display.insert, tk.END, view_line + "\n")
        self.root.after(0, self.log_display.see, tk.END)
        self.data_processor.limit_log_lines()
        self.schedule_view_update()

    def log_update(self):
        """Log to file."""
        if not self.running_event.is_set():
            return
        current_time = time.time()
        seconds = int(current_time)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.lock:
            temps_dict = self.sensor_manager.read_sensors()
        temps_list = [temps_dict[sid] for sid in self.sensor_manager.sensor_ids]
        if self.log_file:
            with self.lock:
                log_line = f"LOG,{seconds},{timestamp}," + ",".join([str(t) if t is not None else 'ERROR' for t in temps_list])
                try:
                    self.log_file.write(log_line + "\n")
                except IOError as e:
                    self.error_handler("Error", f"Failed to write to log file: {str(e)}")
        self.schedule_log_update()

    def update_loop(self):
        """Main loop replaced by timers, but check start/stop conditions in timers."""
        # The loop is now event-driven via timers, start/stop handled in view/log updates
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
                    self.root.after(0, self.log_display.insert, tk.END, "Measurement started due to condition\n")
                    self.root.after(0, self.log_display.see, tk.END)
                    self.data_processor.limit_log_lines()

            if measurement_started:
                # Stop on temperature threshold
                if any(t is not None and t >= float(self.stop_threshold.get()) for t in temps_list):
                    self.root.after(0, self.log_display.insert, tk.END, "Measurement stopped due to temperature threshold\n")
                    self.root.after(0, self.log_display.see, tk.END)
                    self.data_processor.limit_log_lines()
                    self.stop_logging()
                    return

                # Stop on duration
                if self.measure_duration_sec is not None and current_time - self.measure_start_time >= self.measure_duration_sec:
                    self.root.after(0, self.log_display.insert, tk.END, "Measurement stopped due to duration\n")
                    self.root.after(0, self.log_display.see, tk.END)
                    self.data_processor.limit_log_lines()
                    self.stop_logging()
                    return

            # Reschedule condition check (e.g., every 0.1s)
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
                "duration": float(self.duration.get())
            }
            with open(filename, "w", encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.log_display.insert(tk.END, f"Sensor configuration saved: {filename}\n")
            self.log_display.see(tk.END)
            self.data_processor.limit_log_lines()
        except Exception as e:
            self.error_handler("Error", f"Saving configuration failed: {str(e)}")

    def load_sensor_config(self):
        """Load sensor configuration from a JSON file and store for apply."""
        try:
            filename = filedialog.askopenfilename(
                initialdir=self.config_folder,
                title="Load sensor configuration",
                filetypes=[("JSON files", "*.json")]
            )
            if not filename:
                return
            with open(filename, "r", encoding='utf-8') as f:
                self.loaded_config = json.load(f)
            self.log_display.insert(tk.END, f"Sensor configuration loaded: {filename}. Click 'Apply Config' to apply.\n")
            self.sensor_manager.list_sensors_status()
            self.log_display.see(tk.END)
            self.data_processor.limit_log_lines()
        except Exception as e:
            self.error_handler("Error", f"Loading configuration failed: {str(e)}")

    def apply_config(self):
        """Apply the loaded configuration to GUI and sensors."""
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

    def on_closing(self):
        """Handle application shutdown."""
        self.stop_logging()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TempLoggerApp(root)
    app.update_loop()  # Start the condition checking
    root.mainloop()