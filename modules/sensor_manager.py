# -*- coding: utf-8 -*-
"""
Sensor manager for DS18B20 temperature sensors.
"""

import tkinter as tk
from tkinter import ttk, simpledialog
from w1thermsensor import W1ThermSensor, SensorNotReadyError
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .temp_logger_app import TempLoggerApp

from .helpers import sanitize_filename, retry

class SensorManager:
    """Manages DS18B20 sensor initialization, reading, and configuration."""
    
    def __init__(self, app: 'TempLoggerApp'):
        self.app = app
        self.sensors: List[W1ThermSensor] = []
        self.sensor_ids: List[str] = []
        self.sensor_names: Dict[str, str] = {}
        self.sensor_vars: Dict[str, tk.BooleanVar] = {}
        self.sensor_checkbuttons: Dict[str, ttk.Checkbutton] = {}
        self.sensor_labels: Dict[str, ttk.Label] = {}

    def init_sensors(self):
        """Initialize DS18B20 sensors and update GUI."""
        try:
            self.sensors = W1ThermSensor.get_available_sensors()
            self.sensor_ids = [s.id for s in self.sensors]
            
            # Always show 20 sensor slots
            max_sensors = 20
            
            # Clear sensor frame
            for widget in self.app.sensor_frame.winfo_children():
                widget.destroy()
            self.sensor_vars.clear()
            self.sensor_checkbuttons.clear()
            self.sensor_labels.clear()

            # Create 2 columns for sensors
            for i in range(max_sensors):
                row = i % 10  # 10 sensors per column
                col = i // 10  # 0 or 1 for column

                # Sensor number label
                sensor_num_label = ttk.Label(self.app.sensor_frame, text=f"{i+1}.")
                sensor_num_label.grid(row=row, column=col*3, padx=2, pady=1, sticky='W')

                if i < len(self.sensors):
                    sensor = self.sensors[i]
                    sensor_id = sensor.id
                    self.sensor_names[sensor_id] = f"Sensor_{i+1}"
                    
                    var = tk.BooleanVar(value=True)
                    chk = ttk.Checkbutton(self.app.sensor_frame, text=self.sensor_names[sensor_id], variable=var)
                    chk.grid(row=row, column=col*3+1, padx=2, pady=1, sticky='W')
                    chk.bind("<Double-Button-1>", lambda e, sid=sensor_id: self.rename_sensor(sid))
                    
                    status_label = ttk.Label(self.app.sensor_frame, text="Active", foreground="green")
                    status_label.grid(row=row, column=col*3+2, padx=5, pady=1, sticky='W')
                    
                    self.sensor_vars[sensor_id] = var
                    self.sensor_checkbuttons[sensor_id] = chk
                    self.sensor_labels[sensor_id] = status_label
                else:
                    # Empty sensor slot
                    empty_label = ttk.Label(self.app.sensor_frame, text="Empty", foreground="gray")
                    empty_label.grid(row=row, column=col*3+1, padx=2, pady=1, sticky='W')
                    
                    # Placeholder for alignment
                    placeholder = ttk.Label(self.app.sensor_frame, text="")
                    placeholder.grid(row=row, column=col*3+2, padx=5, pady=1, sticky='W')

            self.app.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_names[sid] for sid in self.sensor_ids]

            if not self.sensors:
                self.app.log_to_display("WARNING: No DS18B20 sensors found! Showing empty slots.\n")
            else:
                self.app.log_to_display(f"Found {len(self.sensors)} sensors. {max_sensors} slots available.\n")

        except Exception as e:
            self.app.log_to_display(f"ERROR: Sensor initialization failed: {str(e)}\n")
            self.app.error_handler("Error", f"Sensor initialization failed: {str(e)}")

    def list_sensors_status(self):
        """Log the status of all sensors."""
        self.app.log_to_display("Sensor status diagnostics:\n")
        for sid in self.sensor_ids:
            status = "Active" if self.sensor_vars[sid].get() else "Inactive"
            self.app.log_to_display(f"Sensor {self.sensor_names[sid]} (ID: {sid}): {status}\n")

    def toggle_all_sensors(self, state: Optional[bool] = None):
        """Toggle all active sensors on/off."""
        if state is None:
            # Toggle based on current state
            any_active = any(var.get() for var in self.sensor_vars.values())
            new_state = not any_active
        else:
            new_state = state

        for sid, var in self.sensor_vars.items():
            var.set(new_state)
            # Update status label
            if sid in self.sensor_labels:
                self.sensor_labels[sid].config(
                    text="Active" if new_state else "Inactive",
                    foreground="green" if new_state else "red"
                )

        action = "activated" if new_state else "deactivated"
        self.app.log_to_display(f"All sensors {action}\n")

    @retry()
    def read_sensors(self) -> Dict[str, Optional[float]]:
        """Read temperatures from all active sensors."""
        temps = {}
        for sensor in self.sensors:
            if self.sensor_vars.get(sensor.id, tk.BooleanVar(value=False)).get():
                try:
                    temps[sensor.id] = sensor.get_temperature()
                except SensorNotReadyError:
                    temps[sensor.id] = None
            else:
                temps[sensor.id] = None
        return temps

    def rename_sensor(self, sensor_id: str):
        """Rename a sensor via double-click on its checkbutton."""
        new_name = simpledialog.askstring("Rename Sensor", 
                                         f"Enter new name for {self.sensor_names[sensor_id]}:", 
                                         initialvalue=self.sensor_names[sensor_id])
        if new_name and new_name.strip():
            self.sensor_names[sensor_id] = sanitize_filename(new_name)
            self.sensor_checkbuttons[sensor_id].config(text=self.sensor_names[sensor_id])
            self.app.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_names[sid] for sid in self.sensor_ids]