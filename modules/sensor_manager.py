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

    def init_sensors(self):
        """Initialize DS18B20 sensors and update GUI."""
        try:
            self.sensors = W1ThermSensor.get_available_sensors()
            self.sensor_ids = [s.id for s in self.sensors]
            
            # Clear sensor frame if exists
            if hasattr(self.app, 'sensor_frame') and self.app.sensor_frame:
                for widget in self.app.sensor_frame.winfo_children():
                    widget.destroy()
            self.sensor_vars.clear()
            self.sensor_checkbuttons.clear()
            self.sensor_labels.clear()
            self.temp_labels.clear()

            # Create sensor names
            for i, sensor in enumerate(self.sensors, 1):
                sensor_id = sensor.id
                self.sensor_names[sensor_id] = f"Sensor-{i}"
                
                if i == 25:
                    self.ambient_sensor_id = sensor_id
                    self.sensor_names[sensor_id] = "Sensor-25 (Ambient)"

            # Create grid dynamically
            self._create_sensor_grid()
            
            self.app.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_names[sid] for sid in self.sensor_ids]

            if not self.sensors:
                self.app.log_to_display("WARNING: No DS18B20 sensors found!\n")
            else:
                self.app.log_to_display(f"Found {len(self.sensors)} sensors.\n")

        except Exception as e:
            self.app.log_to_display(f"ERROR: Sensor init failed: {str(e)}\n")
            self.app.error_handler("Error", f"Sensor init failed: {str(e)}")

    def _create_sensor_grid(self):
        """Create dynamic sensor grid."""
        num_sensors = len(self.sensors)
        row_offset = 1 if self.ambient_sensor_id else 0
        sensor_index = 1  # Global index for numbering
        
        if self.ambient_sensor_id:
            ambient_index = self.sensors.index(next(s for s in self.sensors if s.id == self.ambient_sensor_id))
            self._create_sensor_row(self.ambient_sensor_id, 0, 0, sensor_index, is_ambient=True)
            sensor_index += 1
        
        for i in range(num_sensors):
            if self.sensors[i].id != self.ambient_sensor_id:
                row = (i // 3) + row_offset if not self.ambient_sensor_id or i < ambient_index else ((i - 1) // 3) + row_offset
                col = (i % 3) * 3 if not self.ambient_sensor_id or i < ambient_index else ((i - 1) % 3) * 3
                sensor_id = self.sensors[i].id
                self._create_sensor_row(sensor_id, row, col, sensor_index)
                sensor_index += 1
            else:
                continue  # Ambient already handled

        # Fill empty slots if less than max (optional, for fixed layout)
        max_sensors = 25
        while sensor_index <= max_sensors:
            row = ((sensor_index - 1) // 3) + row_offset
            col = ((sensor_index - 1) % 3) * 3
            self._create_empty_slot(row, col, sensor_index)
            sensor_index += 1

    def _create_sensor_row(self, sensor_id: str, row: int, col: int, sensor_index: int, is_ambient: bool = False):
        """Create sensor row."""
        num_label = ttk.Label(self.app.sensor_frame, text=f"{sensor_index}.")
        num_label.grid(row=row, column=col, padx=2, pady=1, sticky='W')
        
        var = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(
            self.app.sensor_frame, 
            text=self.sensor_names[sensor_id], 
            variable=var,
            command=lambda sid=sensor_id: self._update_sensor_status(sid)
        )
        chk.grid(row=row, column=col+1, padx=2, pady=1, sticky='W')
        
        chk.bind("<Button-3>", lambda e, sid=sensor_id: self.rename_sensor(sid))
        
        status_temp_label = ttk.Label(
            self.app.sensor_frame, 
            text="Active --.--°C", 
            foreground="green",
            font=("Arial", 8)
        )
        status_temp_label.grid(row=row+1, column=col+1, padx=2, pady=0, sticky='W')
        
        separator = ttk.Separator(self.app.sensor_frame, orient='horizontal')
        separator.grid(row=row+2, column=col, columnspan=4, sticky='ew', padx=2, pady=1)
        
        self.sensor_vars[sensor_id] = var
        self.sensor_checkbuttons[sensor_id] = chk
        self.temp_labels[sensor_id] = status_temp_label
        
        self._create_tooltip(chk, "Right-click to rename")

    def _create_empty_slot(self, row: int, col: int, slot_num: int):
        """Create empty slot."""
        num_label = ttk.Label(self.app.sensor_frame, text=f"{slot_num}.")
        num_label.grid(row=row, column=col, padx=2, pady=1, sticky='W')
        
        empty_label = ttk.Label(self.app.sensor_frame, text="Empty", foreground="gray")
        empty_label.grid(row=row, column=col+1, padx=2, pady=1, sticky='W')
        
        status_label = ttk.Label(self.app.sensor_frame, text="--", foreground="gray", font=("Arial", 8))
        status_label.grid(row=row+1, column=col+1, padx=2, pady=0, sticky='W')
        
        separator = ttk.Separator(self.app.sensor_frame, orient='horizontal')
        separator.grid(row=row+2, column=col, columnspan=4, sticky='ew', padx=2, pady=1)

    def _create_tooltip(self, widget: tk.Widget, text: str):
        """Create tooltip."""
        def enter(event):
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 20}+{event.y_root + 20}")
            label = tk.Label(tooltip, text=text, background="yellow", relief="solid", borderwidth=1, padx=5, pady=3)
            label.pack()

        def leave(event):
            for child in widget.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.destroy()

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def _update_sensor_status(self, sensor_id: str):
        """Update status label."""
        if sensor_id in self.temp_labels:
            is_active = self.sensor_vars[sensor_id].get()
            status = "Active" if is_active else "Inactive"
            color = "green" if is_active else "red"
            
            current_text = self.temp_labels[sensor_id].cget("text")
            temp_part = current_text.split(" ")[-1] if "°C" in current_text else "--°C"
            
            self.temp_labels[sensor_id].config(text=f"{status} {temp_part}", foreground=color)

    def update_temperature_display(self, temps_dict: Dict[str, Optional[float]]):
        """Update temperature displays."""
        for sensor_id, temp in temps_dict.items():
            if sensor_id in self.temp_labels:
                is_active = self.sensor_vars[sensor_id].get()
                status = "Active" if is_active else "Inactive"
                color = "green" if is_active else "red"
                
                if not is_active:
                    temp_str = "--°C"
                else:
                    temp_str = f"{temp:.1f}°C" if temp is not None else "--.--°C"
                
                self.temp_labels[sensor_id].config(text=f"{status} {temp_str}", foreground=color)

    def list_sensors_status(self):
        """Log sensor status."""
        self.app.log_to_display("Sensor status:\n")
        for sid in self.sensor_ids:
            status = "Active" if self.sensor_vars[sid].get() else "Inactive"
            self.app.log_to_display(f"{self.sensor_names[sid]} (ID: {sid}): {status}\n")

    def toggle_all_sensors(self, state: Optional[bool] = None):
        """Toggle all sensors."""
        if state is None:
            any_active = any(var.get() for var in self.sensor_vars.values())
            new_state = not any_active
        else:
            new_state = state

        for sid, var in self.sensor_vars.items():
            var.set(new_state)
            self._update_sensor_status(sid)

        action = "activated" if new_state else "deactivated"
        self.app.log_to_display(f"All sensors {action}\n")

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
        return temps

    def rename_sensor(self, sensor_id: str):
        """Rename sensor."""
        new_name = simpledialog.askstring("Rename Sensor", f"New name for {self.sensor_names[sensor_id]}:", initialvalue=self.sensor_names[sensor_id])
        if new_name and new_name.strip():
            with self.app.lock:
                self.sensor_names[sensor_id] = sanitize_filename(new_name)
                if sensor_id in self.sensor_checkbuttons:
                    self.sensor_checkbuttons[sensor_id].config(text=self.sensor_names[sensor_id])
                # Update app data_columns if needed
                self.app.data_columns = ["Type", "Seconds", "Timestamp"] + [self.sensor_names[sid] for sid in self.sensor_ids]
                self.app.gui.update_log_treeview_columns(self.sensor_names)
