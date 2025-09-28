# -*- coding: utf-8 -*-
"""
GUI builder for Temperature Logger application.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from .temp_logger_core import TempLoggerApp

class GUIBuilder:
    """Handles GUI initialization and management."""
    
    def __init__(self, root: tk.Tk, app: 'TempLoggerApp'):
        self.root = root
        self.app = app
        self.tooltips = []  # For managing tooltips to prevent leaks
        self.start_conditions_rows: List[Dict[str, Any]] = []
        self.stop_conditions_rows: List[Dict[str, Any]] = []
        self.center_window()
        for widget in self.root.winfo_children():
            widget.destroy()
        self.init_gui()

    def center_window(self):
        """Center the window on the screen."""
        self.root.update_idletasks()
        width, height = 1400, 800
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def init_gui(self):
        """Initialize the GUI elements."""
        self.root.title("Temperature Logger")
        self.root.protocol("WM_DELETE_WINDOW", self.app.on_closing)

        # Main frame for better organization
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top controls frame
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=5)

        # Start/Stop buttons
        self.start_button = ttk.Button(top_frame, text="Start", command=self.app.start_logging)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)
        self.stop_button = ttk.Button(top_frame, text="Stop", command=self.app.stop_logging, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        # Generate Output checkbox
        self.generate_output_check = ttk.Checkbutton(top_frame, text="Generate Output", 
                                                   variable=self.app.generate_output_var)
        self.generate_output_check.grid(row=0, column=2, padx=5, pady=5)
        self.create_tooltip(self.generate_output_check, 
                           "Generate plots and Excel chart when stopping measurement. The .log file is always created.")

        # Measurement name entry
        ttk.Label(top_frame, text="Measurement Name:").grid(row=0, column=4, padx=5, pady=5)
        self.measurement_name_entry = ttk.Entry(top_frame, textvariable=self.app.measurement_name, width=20)
        self.measurement_name_entry.grid(row=0, column=5, padx=5, pady=5)

        # MAIN TIMING frame
        timing_frame = ttk.LabelFrame(main_frame, text="Main Timing", padding=5)
        timing_frame.pack(fill=tk.X, pady=5)

        ttk.Label(timing_frame, text="Log interval (s):").grid(row=0, column=0, padx=5, pady=2, sticky='W')
        self.log_interval_entry = ttk.Entry(timing_frame, textvariable=self.app.log_interval, width=5)
        self.log_interval_entry.grid(row=0, column=1, padx=5, pady=2, sticky='W')

        ttk.Label(timing_frame, text="Display update (s):").grid(row=0, column=2, padx=5, pady=2, sticky='W')
        self.view_interval_entry = ttk.Entry(timing_frame, textvariable=self.app.view_interval, width=5)
        self.view_interval_entry.grid(row=0, column=3, padx=5, pady=2, sticky='W')

        # MEASUREMENT DURATION frame
        duration_frame = ttk.LabelFrame(main_frame, text="Measurement Duration", padding=5)
        duration_frame.pack(fill=tk.X, pady=5)

        duration_check = ttk.Checkbutton(duration_frame, text="Enable duration limit", 
                                       variable=self.app.duration_enabled)
        duration_check.grid(row=0, column=0, padx=5, pady=2, sticky='W')

        ttk.Label(duration_frame, text="Minutes:").grid(row=0, column=1, padx=5, pady=2, sticky='W')
        self.duration_minutes_entry = ttk.Entry(duration_frame, textvariable=self.app.duration_minutes, width=5)
        self.duration_minutes_entry.grid(row=0, column=2, padx=5, pady=2, sticky='W')

        ttk.Label(duration_frame, text="Hours:").grid(row=0, column=3, padx=5, pady=2, sticky='W')
        self.duration_hours_entry = ttk.Entry(duration_frame, textvariable=self.app.duration_hours, width=5)
        self.duration_hours_entry.grid(row=0, column=4, padx=5, pady=2, sticky='W')

        ttk.Label(duration_frame, text="Days:").grid(row=0, column=5, padx=5, pady=2, sticky='W')
        self.duration_days_entry = ttk.Entry(duration_frame, textvariable=self.app.duration_days, width=5)
        self.duration_days_entry.grid(row=0, column=6, padx=5, pady=2, sticky='W')

        # SENSORS frame - NEW
        self.app.sensor_frame = ttk.LabelFrame(main_frame, text="Sensors", padding=5)
        self.app.sensor_frame.pack(fill=tk.X, pady=5)

        # TEMPERATURE-CONTROLLED MEASUREMENT frame - NEW STRUCTURE
        temp_control_frame = ttk.LabelFrame(main_frame, text="Temperature-Controlled Measurement", padding=5)
        temp_control_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # START CONDITIONS BLOCK
        start_block = ttk.LabelFrame(temp_control_frame, text="Start Conditions", padding=5)
        start_block.pack(fill=tk.X, pady=2)

        self.app.temp_start_enabled = tk.BooleanVar(value=False)
        self.start_enable_check = ttk.Checkbutton(start_block, text="Enable Start Conditions", 
                                                variable=self.app.temp_start_enabled)
        self.start_enable_check.grid(row=0, column=0, padx=5, pady=2, sticky='W')
        self.create_tooltip(self.start_enable_check, "Enable automatic start based on temperature conditions.")

        # Add row button for start
        ttk.Button(start_block, text="Add Start Condition", command=lambda: self._create_condition_row('start')).grid(row=0, column=1, padx=5, pady=2)

        # Conditions rows container for start
        self.start_rows_container = ttk.Frame(start_block)
        self.start_rows_container.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)

        # STOP CONDITIONS BLOCK
        stop_block = ttk.LabelFrame(temp_control_frame, text="Stop Conditions", padding=5)
        stop_block.pack(fill=tk.X, pady=2)

        self.app.temp_stop_enabled = tk.BooleanVar(value=False)
        self.stop_enable_check = ttk.Checkbutton(stop_block, text="Enable Stop Conditions", 
                                               variable=self.app.temp_stop_enabled)
        self.stop_enable_check.grid(row=0, column=0, padx=5, pady=2, sticky='W')
        self.create_tooltip(self.stop_enable_check, "Enable automatic stop based on temperature conditions.")

        # Add row button for stop
        ttk.Button(stop_block, text="Add Stop Condition", command=lambda: self._create_condition_row('stop')).grid(row=0, column=1, padx=5, pady=2)

        # Conditions rows container for stop
        self.stop_rows_container = ttk.Frame(stop_block)
        self.stop_rows_container.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)

        # Log Treeview
        log_frame = ttk.LabelFrame(main_frame, text="Log Display", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self._create_log_treeview(log_frame)

        # Configure treeview tags for alternating rows
        self.app.log_tree.tag_configure("evenrow", background="#f0f0f0")
        self.app.log_tree.tag_configure("oddrow", background="white")

    def _create_condition_row(self, side: str):
        """Create a new condition row for start or stop."""
        row_frame = ttk.Frame(self.start_rows_container if side == 'start' else self.stop_rows_container)
        row_frame.pack(fill=tk.X, pady=2, padx=5)

        # Sensor selection frame
        sensor_select_frame = ttk.LabelFrame(row_frame, text=f"Condition Row (Sensors)", padding=3)
        sensor_select_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        sensor_vars = {}
        i = 0
        for sid, name in self.app.sensor_manager.sensor_names.items():
            var = tk.BooleanVar(value=False)
            sensor_vars[sid] = var
            chk = ttk.Checkbutton(sensor_select_frame, text=name, variable=var,
                                  command=lambda s=sid, r=row_frame: self.on_sensor_change(s, r, side))
            col = i % 3
            roww = i // 3
            chk.grid(row=roww, column=col, sticky='w', padx=1)
            i += 1

        # Operator and threshold frame
        op_thresh_frame = ttk.Frame(row_frame)
        op_thresh_frame.pack(side=tk.RIGHT, padx=5)

        ttk.Label(op_thresh_frame, text="Operator:").grid(row=0, column=0, sticky='w')
        operator_var = tk.StringVar(value=">")
        operator_combobox = ttk.Combobox(op_thresh_frame, textvariable=operator_var, values=['>', '<', '>=', '<=', '='], width=5, state="readonly")
        operator_combobox.grid(row=0, column=1, padx=2)

        ttk.Label(op_thresh_frame, text="Threshold:").grid(row=1, column=0, sticky='w')
        threshold_var = tk.StringVar(value="22.0")
        threshold_entry = ttk.Entry(op_thresh_frame, textvariable=threshold_var, width=8)
        threshold_entry.grid(row=1, column=1, padx=2)

        # Delete button
        ttk.Button(op_thresh_frame, text="Delete Row", command=lambda: self._delete_condition_row(row_frame, side)).grid(row=2, column=0, columnspan=2, pady=2)

        # Store row data
        row_data = {
            'frame': row_frame,
            'sensor_frame': sensor_select_frame,
            'sensor_vars': sensor_vars,
            'operator_combobox': operator_var,
            'threshold_entry': threshold_var
        }

        if side == 'start':
            self.start_conditions_rows.append(row_data)
        else:
            self.stop_conditions_rows.append(row_data)

        # Bind changes to update app
        operator_combobox.bind('<<ComboboxSelected>>', lambda e, r=row_frame: self.on_condition_change(r, side))
        threshold_entry.bind('<KeyRelease>', lambda e, r=row_frame: self.on_condition_change(r, side))

        self.update_selected_count(row_data)
        return row_data

    def _delete_condition_row(self, row_frame, side: str):
        """Delete a condition row."""
        row_frame.destroy()
        if side == 'start':
            self.start_conditions_rows = [rd for rd in self.start_conditions_rows if rd['frame'] != row_frame]
        else:
            self.stop_conditions_rows = [rd for rd in self.stop_conditions_rows if rd['frame'] != row_frame]
        self.on_condition_change(row_frame, side)

    def load_conditions_to_rows(self, conditions: List[Dict], side: str):
        """Load conditions into GUI rows."""
        # Clear existing rows
        container = self.start_rows_container if side == 'start' else self.stop_rows_container
        rows_list = self.start_conditions_rows if side == 'start' else self.stop_conditions_rows
        for row_data in rows_list[:]:
            self._delete_condition_row(row_data['frame'], side)

        # Add new rows
        for cond in conditions:
            row_data = self._create_condition_row(side)
            # Set values
            for sid in cond.get('sensors', []):
                if sid in row_data['sensor_vars']:
                    row_data['sensor_vars'][sid].set(True)
            row_data['operator_combobox'].set(cond.get('operator', '>'))
            row_data['threshold_entry'].set(str(cond.get('threshold', 0.0)))
            self.update_selected_count(row_data)

    def on_sensor_change(self, sensor_id: str, row_frame, side: str):
        """Handle sensor checkbox change."""
        # Find row_data by frame
        if side == 'start':
            row_data = next((rd for rd in self.start_conditions_rows if rd['frame'] == row_frame), None)
        else:
            row_data = next((rd for rd in self.stop_conditions_rows if rd['frame'] == row_frame), None)
        if row_data:
            self.update_selected_count(row_data)
            self.on_condition_change(row_frame, side)

    def on_condition_change(self, row_frame, side: str):
        """Handle any condition change, trigger app update."""
        if side == 'start':
            self.app.update_conditions_list('start')
        else:
            self.app.update_conditions_list('stop')

    def update_selected_count(self, row_data: Dict[str, Any]):
        """Update visual count of selected sensors."""
        count = sum(1 for var in row_data['sensor_vars'].values() if var.get())
        frame = row_data['frame']
        if count == 0:
            frame.config(relief='solid', borderwidth=1)
            self.create_tooltip(frame, "Warning: Select at least 1 sensor!")
        else:
            frame.config(relief='flat', borderwidth=0)
            # Remove tooltip if exists
            for tip in self.tooltips[:]:
                if tip.winfo_viewable():
                    tip.destroy()
                    self.tooltips.remove(tip)

    def populate_condition_checkboxes(self):
        """Repopulate sensor checkboxes in all condition rows after sensor init."""
        for side in ['start', 'stop']:
            rows = self.start_conditions_rows if side == 'start' else self.stop_conditions_rows
            for row_data in rows:
                # Clear existing checkboxes
                sensor_frame = row_data['sensor_frame']
                for child in sensor_frame.winfo_children():
                    if isinstance(child, ttk.Checkbutton):
                        child.destroy()
                # Repopulate
                sensor_vars = row_data['sensor_vars']
                sensor_vars.clear()
                i = 0
                for sid, name in self.app.sensor_manager.sensor_names.items():
                    var = tk.BooleanVar(value=False)
                    sensor_vars[sid] = var
                    chk = ttk.Checkbutton(sensor_frame, text=name, variable=var,
                                          command=lambda s=sid, r=row_data['frame']: self.on_sensor_change(s, r, side))
                    col = i % 3
                    roww = i // 3
                    chk.grid(row=roww, column=col, sticky='w', padx=1)
                    i += 1
                self.update_selected_count(row_data)

    def validate_float(self, value: str) -> bool:
        """Validate float entry."""
        if not value:
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _create_log_treeview(self, parent):
        """Create Treeview for tabular log display."""
        # Create Treeview with scrollbars
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Create vertical scrollbar
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create horizontal scrollbar
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Create Treeview
        self.app.log_tree = ttk.Treeview(tree_frame, 
                                       yscrollcommand=v_scrollbar.set,
                                       xscrollcommand=h_scrollbar.set,
                                       show='tree headings',
                                       height=10)  # Reduced for better responsiveness
        self.app.log_tree.pack(fill=tk.BOTH, expand=True)

        # Configure scrollbars
        v_scrollbar.config(command=self.app.log_tree.yview)
        h_scrollbar.config(command=self.app.log_tree.xview)

        # Configure columns (will be populated when sensors are initialized)
        self.app.log_tree["columns"] = ("timestamp",)
        self.app.log_tree.column("#0", width=0, stretch=tk.NO)  # Hide first column
        self.app.log_tree.column("timestamp", width=120, anchor=tk.CENTER)

        self.app.log_tree.heading("timestamp", text="Timestamp")

    def update_log_treeview_columns(self, sensor_names):
        """Update Treeview columns based on sensor names."""
        # Clear existing columns
        for col in self.app.log_tree["columns"]:
            self.app.log_tree.heading(col, text="")
            self.app.log_tree.column(col, width=0)

        # Set new columns
        columns = ["timestamp"] + list(sensor_names.values())
        self.app.log_tree["columns"] = columns

        # Configure timestamp column
        self.app.log_tree.column("timestamp", width=120, anchor=tk.CENTER)
        self.app.log_tree.heading("timestamp", text="Timestamp")

        # Configure sensor columns
        for i, (sensor_id, name) in enumerate(sensor_names.items(), 1):
            col_width = 80 if "Ambient" in name else 70
            self.app.log_tree.column(name, width=col_width, anchor=tk.CENTER)
            self.app.log_tree.heading(name, text=name)

    def create_tooltip(self, widget: tk.Widget, text: str):
        """Create a simple tooltip for a widget."""
        def enter(event):
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 20}+{event.y_root + 20}")
            label = tk.Label(tooltip, text=text, background="yellow", 
                           relief="solid", borderwidth=1, padx=5, pady=3)
            label.pack()
            self.tooltips.append(tooltip)

        def leave(event):
            for tip in self.tooltips[:]:
                if tip.winfo_viewable():
                    tip.destroy()
                    self.tooltips.remove(tip)

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)
