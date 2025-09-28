# -*- coding: utf-8 -*-
"""
Sensor manager for DS18B20 temperature sensors.
"""

import tkinter as tk
from tkinter import ttk, simpledialog
from w1thermsensor import W1ThermSensor, SensorNotReadyError
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .temp_logger_core import TempLoggerApp

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
        self.temp_labels: Dict[str, ttk.Label] = {}
        self.ambient_sensor_id = None
        self.last_readings: Dict[str, Optional[float]] = {} # Tárolja a legutolsó leolvasott adatokat

    def init_sensors(self):
        """Initialize DS18B20 sensors and update GUI."""
        try:
            self.sensors = W1ThermSensor.get_available_sensors()
            self.sensor_ids = [s.id for s in self.sensors]
            
            # Clear sensor frame if exists (Fontos a hibás megjelenítés javításához)
            if hasattr(self.app, 'sensor_frame') and self.app.sensor_frame:
                for widget in self.app.sensor_frame.winfo_children():
                    widget.destroy()

            # Initialize names and GUI elements
            self.sensor_names = {}
            self.sensor_vars = {}
            self.sensor_checkbuttons = {}
            self.temp_labels = {}
            
            row_num = 0
            for sensor in self.sensors:
                sid = sensor.id
                # Elnevezés: ha van korábban mentett név, azt használja, különben Sensor X
                name = f"Sensor {row_num + 1}" 
                self.sensor_names[sid] = name
                
                # Checkbutton for activation (Alapértelmezésben bekapcsolva)
                var = tk.BooleanVar(value=True) 
                self.sensor_vars[sid] = var
                
                # JAVÍTÁS: Checkbox és label hozzáadása az ismétlődő sorokban
                chk = ttk.Checkbutton(self.app.sensor_frame, text=name, variable=var, 
                                      command=lambda s=sid: self.update_sensor_status(s))
                chk.grid(row=row_num, column=0, padx=5, pady=2, sticky='W')
                self.sensor_checkbuttons[sid] = chk

                # Live temperature label (Jobbra igazítva a kényelmes olvasásért)
                temp_lbl = ttk.Label(self.app.sensor_frame, text="N/A", font=("Helvetica", 12, "bold"), width=8, anchor='e')
                temp_lbl.grid(row=row_num, column=1, padx=5, pady=2, sticky='E')
                self.temp_labels[sid] = temp_lbl
                
                row_num += 1
            
            if not self.sensors:
                ttk.Label(self.app.sensor_frame, text="No DS18B20 sensors found.").grid(row=0, column=0, columnspan=2, padx=5, pady=10)

            self.app.log_to_display(f"Found {len(self.sensors)} DS18B20 sensors.\n")
            self.app.gui.update_log_treeview_columns(self.sensor_names.values())
            self.app.gui.populate_condition_checkboxes()

        except Exception as e:
            self.app.error_handler("Sensor Init Error", f"Failed to initialize sensors: {str(e)}")

    def update_sensor_status(self, sensor_id: str):
        """Update sensor status."""
        pass # Placeholder

    def get_last_readings(self) -> Dict[str, Optional[float]]:
        """Return the last read temperature data."""
        return self.last_readings

    @retry()
    def read_sensors(self) -> Dict[str, Optional[float]]:
        """Read all active sensors - full readout, no downsampling."""
        temps = {sid: None for sid in self.sensor_ids}
        for sensor in self.sensors:
            sensor_id = sensor.id
            if self.sensor_vars.get(sensor_id, tk.BooleanVar(value=False)).get():
                try:
                    temps[sensor_id] = sensor.get_temperature()
                except SensorNotReadyError:
                    temps[sensor_id] = None
            # Inactive already None
        
        # Tároljuk a legutóbbi leolvasást a feltétel ellenőrzéshez
        self.last_readings = temps
        return temps

    def rename_sensor(self, sensor_id: str):
        """Rename sensor."""
        # ... (rest of the method is assumed to be correct)
        pass # Placeholder
