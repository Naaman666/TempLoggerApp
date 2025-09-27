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
        # Töröld az összes meglévő widgetet a root-ból a tiszta elrendezés érdekében
        for widget in self.root.winfo_children():
            widget.destroy()
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

        # Sensor selection frame
        self.app.sensor_frame = tk.Frame(self.root)
        self.app.sensor_frame.grid(row=4, column=2, columnspan=2, padx=5, pady=5, sticky='W')

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

            # Clear sensor frame
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
                self.app.log_to_display("ERROR: No DS18B20 sensors found!\n")
                self.app.error_handler("Warning", "No DS18B20 sensors found!")

        except Exception as e:
            self.app.log_to_display(f"ERROR: Sensor initialization failed: {str(e)}\n")
            self.app.error_handler("Error", f"Sensor initialization failed: {str(e)}")

    def list_sensors_status(self):
        """Log the status of all sensors."""
        self.app.log_to_display("Sensor status diagnostics:\n")
        for sid in self.sensor_ids:
            self.app.log_to_display(f"Sensor {self.sensor_names[sid]} (ID: {sid}): {'Active' if self.sensor_vars[sid].get() else 'Inactive'}\n")

    @retry()
    def read_sensors(self) -> Dict[str, Optional[float]]:
        """Read temperatures from all sensors."""
        return {sensor.id: sensor.get_temperature() if self.sensor_vars[sensor.id].get() else None for sensor in self.sensors}

    def rename_sensor(self, sensor_id: str):
        """Rename a sensor via double-click on its checkbutton."""
        new_name = simpledialog.askstring("Rename Sensor", f"Enter new name for {self.sensor_names[sensor_id]}:", initialvalue=self.sensor_names[sensor_id])
        if new_name and new_name.strip():
            self.sensor_names[sensor_id] = sanitize_filename(new_name)
            self.sensor_checkbuttons[sensor_id].config(text=self.sensor_names[sensor_id])
            self.app.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_names[sid] for sid in self.sensor_ids]

class DataProcessor:
    """Handles data logging, limiting, and exporting."""
    def __init__(self, app):
        self.app = app
        self.data: List[List] = []
        self.lock = threading.Lock()

    def limit_log_lines(self):
        """Limit the number of lines in the log display."""
        if hasattr(self.app, 'log_display') and self.app.log_display:
            content = self.app.log_display.get("1.0", tk.END).splitlines()
            if len(content) > self.app.max_log_lines:
                self.app.log_display.delete("1.0", f"{len(content) - self.app.max_log_lines}.0")

    def save_data(self, format_type: str):
        """Save data to file in the specified format."""
        if not self.data:
            self.app.error_handler("Warning", "No data to export!")
            return
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.app.measurement_folder}/temp_log_{timestamp}.{format_type}"
            if format_type == 'excel':
                if self.app.export_manager.check_overwrite('excel'):
                    df = pd.DataFrame(self.data, columns=self.app.data_columns)
                    df.to_excel(filename, index=False)
                    self.app.export_manager.mark_exported('excel')
            elif format_type == 'csv':
                if self.app.export_manager.check_overwrite('csv'):
                    df = pd.DataFrame(self.data, columns=self.app.data_columns)
                    df.to_csv(filename, index=False)
                    self.app.export_manager.mark_exported('csv')
            elif format_type == 'json':
                if self.app.export_manager.check_overwrite('json'):
                    with open(filename, 'w') as f:
                        json.dump([dict(zip(self.app.data_columns, row)) for row in self.data], f, indent=2)
                    self.app.export_manager.mark_exported('json')
            elif format_type == 'plot':
                plt.figure(figsize=(10, 6))
                for col in self.app.data_columns[3:]:  # Skip Type, Seconds, Timestamp
                    plt.plot([row[1] for row in self.data], [row[self.app.data_columns.index(col)] for row in self.data], label=col)
                plt.xlabel("Seconds")
                plt.ylabel("Temperature (°C)")
                plt.title("Temperature Logs")
                plt.legend()
                plt.grid(True)
                plt.savefig(f"{self.app.measurement_folder}/temp_plot_{timestamp}.png")
                plt.savefig(f"{self.app.measurement_folder}/temp_plot_{timestamp}.pdf")
                plt.close()
            self.app.log_to_display(f"Data exported to {filename}\n")
        except Exception as e:
            self.app.error_handler("Error", f"Export failed: {str(e)}")

class TempLoggerApp:
    """Main application class."""
    def __init__(self, root: tk.Tk):
        self.root = root
        with open("config.json", "r") as f:
            config = json.load(f)
        self.default_log_interval = config["default_log_interval"]
        self.default_view_interval = config["default_view_interval"]
        self.default_start_threshold = config["default_start_threshold"]
        self.default_stop_threshold = config["default_stop_threshold"]
        self.max_log_lines = config["max_log_lines"]
        self.measurement_folder = config["measurement_folder"]
        self.config_folder = config["config_folder"]
        os.makedirs(self.measurement_folder, exist_ok=True)
        os.makedirs(self.config_folder, exist_ok=True)

        # Initialize GUI first
        self.gui = GUIBuilder(self.root, self)
        
        # Initialize other components after GUI
        self.sensor_manager = SensorManager(self)
        self.data_processor = DataProcessor(self)
        self.export_manager = ExportManager()
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

    def start_logging(self):
        """Start the logging process."""
        if self.running_event.is_set():
            self.error_handler("Warning", "Logging already in progress!")
            return
        
        self.running_event.set()
        self.gui.start_button.config(state="disabled")
        self.gui.stop_button.config(state="normal")
        self.gui.excel_button.config(state="disabled")
        self.gui.csv_button.config(state="disabled")
        self.gui.json_button.config(state="disabled")

        # Open log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.measurement_folder}/temp_log_{timestamp}.txt"
        try:
            self.log_file = open(filename, "w", encoding='utf-8')
            self.log_to_display(f"Logging started, file: {filename}\n")
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
        self.log_to_display(view_line + "\n")
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
            log_line = f"LOG,{seconds},{timestamp}," + ",".join([str(t) if t is not None else 'ERROR' for t in temps_list])
            try:
                self.log_file.write(log_line + "\n")
                self.log_file.flush()
            except IOError as e:
                self.error_handler("Error", f"Failed to write to log file: {str(e)}")
        self.schedule_log_update()

    def update_loop(self):
        """Main loop replaced by timers, but check start/stop conditions in timers."""
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
                "duration": float(self.duration.get())
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
            
            # Apply configuration immediately
            active_sensors = loaded_config.get("active_sensors", [])
            for sid, var in self.sensor_manager.sensor_vars.items():
                var.set(sid in active_sensors)
            
            self.sensor_manager.sensor_names = loaded_config.get("sensor_names", self.sensor_manager.sensor_names)
            self.start_threshold.set(str(loaded_config.get("start_threshold", self.default_start_threshold)))
            self.stop_threshold.set(str(loaded_config.get("stop_threshold", self.default_stop_threshold)))
            self.log_interval.set(str(loaded_config.get("log_interval", self.default_log_interval)))
            self.view_interval.set(str(loaded_config.get("view_interval", self.default_view_interval)))
            self.duration.set(str(loaded_config.get("duration", 0.0)))
            
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

if __name__ == "__main__":
    root = tk.Tk()
    app = TempLoggerApp(root)
    app.update_loop()
    root.mainloop()