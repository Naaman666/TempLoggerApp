# -*- coding: utf-8 -*-
"""
GUI builder for Temperature Logger application.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .temp_logger_core import TempLoggerApp

class GUIBuilder:
    """Handles GUI initialization and management."""
    
    def __init__(self, root: tk.Tk, app: 'TempLoggerApp'):
        self.root = root
        self.app = app
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
        self.app.generate_output_var = tk.BooleanVar(value=True)
        self.generate_output_check = ttk.Checkbutton(top_frame, text="Generate Output", 
                                                   variable=self.app.generate_output_var)
        self.generate_output_check.grid(row=0, column=2, padx=5, pady=5)
        self.create_tooltip(self.generate_output_check, 
                           "Generate plots and Excel chart when stopping measurement. The .log file is always created.")

        # Measurement name entry
        ttk.Label(top_frame, text="Measurement Name:").grid(row=0, column=4, padx=5, pady=5)
        self.app.measurement_name = tk.StringVar(value="temptestlog")
        self.measurement_name_entry = ttk.Entry(top_frame, textvariable=self.app.measurement_name, width=20)
        self.measurement_name_entry.grid(row=0, column=5, padx=5, pady=5)

        # MAIN TIMING frame
        timing_frame = ttk.LabelFrame(main_frame, text="Main Timing", padding=5)
        timing_frame.pack(fill=tk.X, pady=5)

        ttk.Label(timing_frame, text="Log interval (s):").grid(row=0, column=0, padx=5, pady=2, sticky='W')
        self.app.log_interval = tk.StringVar(value=str(self.app.default_log_interval))
        self.log_interval_entry = ttk.Entry(timing_frame, textvariable=self.app.log_interval, width=5)
        self.log_interval_entry.grid(row=0, column=1, padx=5, pady=2, sticky='W')

        ttk.Label(timing_frame, text="Display update (s):").grid(row=0, column=2, padx=5, pady=2, sticky='W')
        self.app.view_interval = tk.StringVar(value=str(self.app.default_view_interval))
        self.view_interval_entry = ttk.Entry(timing_frame, textvariable=self.app.view_interval, width=5)
        self.view_interval_entry.grid(row=0, column=3, padx=5, pady=2, sticky='W')

        # MEASUREMENT DURATION frame
        duration_frame = ttk.LabelFrame(main_frame, text="Measurement Duration", padding=5)
        duration_frame.pack(fill=tk.X, pady=5)

        self.app.duration_enabled = tk.BooleanVar(value=False)
        duration_check = ttk.Checkbutton(duration_frame, text="Enable duration limit", 
                                       variable=self.app.duration_enabled)
        duration_check.grid(row=0, column=0, padx=5, pady=2, sticky='W')

        ttk.Label(duration_frame, text="Minutes:").grid(row=0, column=1, padx=5, pady=2, sticky='W')
        self.app.duration_minutes = tk.StringVar(value="0")
        self.duration_minutes_entry = ttk.Entry(duration_frame, textvariable=self.app.duration_minutes, width=5)
        self.duration_minutes_entry.grid(row=0, column=2, padx=5, pady=2, sticky='W')

        ttk.Label(duration_frame, text="Hours:").grid(row=0, column=3, padx=5, pady=2, sticky='W')
        self.app.duration_hours = tk.StringVar(value="0")
        self.duration_hours_entry = ttk.Entry(duration_frame, textvariable=self.app.duration_hours, width=5)
        self.duration_hours_entry.grid(row=0, column=4, padx=5, pady=2, sticky='W')

        ttk.Label(duration_frame, text="Days:").grid(row=0, column=5, padx=5, pady=2, sticky='W')
        self.app.duration_days = tk.StringVar(value="0")
        self.duration_days_entry = ttk.Entry(duration_frame, textvariable=self.app.duration_days, width=5)
        self.duration_days_entry.grid(row=0, column=6, padx=5, pady=2, sticky='W')

        # TEMPERATURE-CONTROLLED MEASUREMENT frame - NEW STRUCTURE
        temp_control_frame = ttk.LabelFrame(main_frame, text="Temperature-Controlled Measurement", padding=5)
        temp_control_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # START CONDITIONS BLOCK
        start_block = ttk.LabelFrame(temp_control_frame, text="Start Conditions", padding=5)
        start_block.pack(fill=tk.X, pady=2)

        self.app.temp_start_enabled = tk.BooleanVar(value=False)
        self.start_enable_check = ttk.Checkbutton(start_block, text="Enable temperature start",
                                                  variable=self.app.temp_start_enabled,
                                                  command=lambda: self.toggle_conditions_block('start'))
        self.start_enable_check.pack(anchor='w')

        self.start_scroll_frame = self._create_scrollable_frame(start_block)
        self.start_conditions_rows = []  # List of row frames for management
        self.start_add_button = ttk.Button(start_block, text="+ Add Condition",
                                           command=lambda: self.add_condition_row('start'))
        self.start_add_button.pack(anchor='w', pady=2)

        # STOP CONDITIONS BLOCK
        stop_block = ttk.LabelFrame(temp_control_frame, text="Stop Conditions", padding=5)
        stop_block.pack(fill=tk.X, pady=2)

        self.app.temp_stop_enabled = tk.BooleanVar(value=False)
        self.stop_enable_check = ttk.Checkbutton(stop_block, text="Enable temperature stop",
                                                 variable=self.app.temp_stop_enabled,
                                                 command=lambda: self.toggle_conditions_block('stop'))
        self.stop_enable_check.pack(anchor='w')

        self.stop_scroll_frame = self._create_scrollable_frame(stop_block)
        self.stop_conditions_rows = []  # List of row frames for management
        self.stop_add_button = ttk.Button(stop_block, text="+ Add Condition",
                                          command=lambda: self.add_condition_row('stop'))
        self.stop_add_button.pack(anchor='w', pady=2)

        # SENSOR FRAME (for checkboxes in conditions - populated after sensors init)
        sensor_frame = ttk.LabelFrame(main_frame, text="Sensors", padding=5)
        sensor_frame.pack(fill=tk.X, pady=5)
        self.app.sensor_frame = sensor_frame  # Reference for sensor_manager

        # Log display with Treeview
        log_frame = ttk.LabelFrame(main_frame, text="Log Display", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create Treeview for tabular display
        self._create_log_treeview(log_frame)

        # Bottom buttons frame
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=5)

        # Export buttons
        self.excel_button = ttk.Button(bottom_frame, text="Save Excel", 
                                     command=lambda: self.app.save_data('excel'))
        self.excel_button.pack(side=tk.LEFT, padx=2)
        
        self.csv_button = ttk.Button(bottom_frame, text="Save CSV", 
                                   command=lambda: self.app.save_data('csv'))
        self.csv_button.pack(side=tk.LEFT, padx=2)
        
        self.json_button = ttk.Button(bottom_frame, text="Save JSON", 
                                    command=lambda: self.app.save_data('json'))
        self.json_button.pack(side=tk.LEFT, padx=2)

        # Config buttons
        self.save_config_button = ttk.Button(bottom_frame, text="Save Config", 
                                           command=self.app.save_sensor_config)
        self.save_config_button.pack(side=tk.LEFT, padx=10)
        
        self.load_config_button = ttk.Button(bottom_frame, text="Load Config", 
                                           command=self.app.load_sensor_config)
        self.load_config_button.pack(side=tk.LEFT, padx=2)

        # Progress bar
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=5)

        self.app.progress_bar = ttk.Progressbar(progress_frame, orient='horizontal', 
                                              mode='determinate', maximum=100)
        self.app.progress_label = ttk.Label(progress_frame, text="")
        self.app.progress_bar.pack(fill=tk.X, pady=2)
        self.app.progress_label.pack(fill=tk.X, pady=2)
        self.app.progress_bar.pack_forget()
        self.app.progress_label.pack_forget()

        # Initially disable condition blocks
        self.toggle_conditions_block('start')
        self.toggle_conditions_block('stop')

    def _create_scrollable_frame(self, parent):
        """Create a scrollable frame using Canvas and Scrollbar."""
        canvas = tk.Canvas(parent, height=150, bg='white')
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        return scrollable_frame

    def toggle_conditions_block(self, side: str):
        """Enable/disable the conditions block based on checkbox."""
        if side == 'start':
            state = tk.NORMAL if self.app.temp_start_enabled.get() else tk.DISABLED
            for widget in self.start_scroll_frame.winfo_children():
                widget.config(state=state)
            self.start_add_button.config(state=state)
        else:
            state = tk.NORMAL if self.app.temp_stop_enabled.get() else tk.DISABLED
            for widget in self.stop_scroll_frame.winfo_children():
                widget.config(state=state)
            self.stop_add_button.config(state=state)

    def add_condition_row(self, side: str):
        """Add a new condition row to the specified side."""
        if side == 'start':
            scroll_frame = self.start_scroll_frame
            rows = self.start_conditions_rows
            add_button = self.start_add_button
        else:
            scroll_frame = self.stop_scroll_frame
            rows = self.stop_conditions_rows
            add_button = self.stop_add_button

        # Create new row frame
        row_frame = ttk.Frame(scroll_frame, relief='solid', borderwidth=1)
        row_frame.pack(fill=tk.X, padx=2, pady=2)

        # Sensor select frame (checkboxes in 3 columns)
        sensor_select_frame = ttk.LabelFrame(row_frame, text="Sensors", padding=2)
        sensor_select_frame.pack(side=tk.LEFT, fill=tk.X, padx=2)
        sensor_vars = {}  # Local vars for this row's checkboxes
        for i, (sid, name) in enumerate(self.app.sensor_manager.sensor_names.items()):
            if sid not in sensor_vars:
                var = tk.BooleanVar(value=False)
                sensor_vars[sid] = var
            chk = ttk.Checkbutton(sensor_select_frame, text=name, variable=var,
                                  command=lambda s=sid, r=row_frame: self.on_sensor_change(s, r, side))
            col = i % 3
            roww = i // 3
            chk.grid(row=roww, column=col, sticky='w', padx=1)

        # Selected count label
        selected_label = ttk.Label(sensor_select_frame, text="Selected: 0")
        selected_label.pack()

        # Operator combobox
        op_frame = ttk.Frame(row_frame)
        op_frame.pack(side=tk.LEFT, padx=2)
        ttk.Label(op_frame, text="Operator:").pack()
        op_var = tk.StringVar(value='>')
        op_combo = ttk.Combobox(op_frame, textvariable=op_var, values=['>', '<', '>=', '<=', '='], width=5,
                                state='readonly', command=lambda v=op_var, r=row_frame: self.on_condition_change(r, side))
        op_combo.pack()

        # Threshold entry
        thresh_frame = ttk.Frame(row_frame)
        thresh_frame.pack(side=tk.LEFT, padx=2)
        ttk.Label(thresh_frame, text="Threshold:").pack()
        thresh_var = tk.StringVar(value='10.0')
        thresh_entry = ttk.Entry(thresh_frame, textvariable=thresh_var, width=8,
                                 validate='key', validatecommand=(self.root.register(lambda v: self.validate_float(v)), '%P'),
                                 command=lambda r=row_frame: self.on_condition_change(r, side))
        thresh_entry.pack()
        ttk.Label(thresh_frame, text="°C").pack()

        # Logic combobox (only if not first row)
        is_first = len(rows) == 0
        logic_frame = ttk.Frame(row_frame) if not is_first else None
        if not is_first:
            logic_frame.pack(side=tk.LEFT, padx=2)
            ttk.Label(logic_frame, text="Logic:").pack()
            logic_var = tk.StringVar(value='AND')
            logic_combo = ttk.Combobox(logic_frame, textvariable=logic_var, values=['AND', 'OR'], width=5,
                                       state='readonly', command=lambda r=row_frame: self.on_condition_change(r, side))
            logic_combo.pack()

        # Delete button
        delete_btn = ttk.Button(row_frame, text='−', style='Danger.TButton', width=2,
                                command=lambda r=row_frame: self.remove_condition_row(r, side))
        delete_btn.pack(side=tk.RIGHT, padx=2)

        # Store row data
        row_data = {
            'frame': row_frame,
            'sensor_vars': sensor_vars,
            'selected_label': selected_label,
            'op_var': op_var,
            'thresh_var': thresh_var,
            'logic_var': logic_var if not is_first else None,
            'is_first': is_first
        }
        rows.append(row_data)

        # Update selected count initially
        self.update_selected_count(row_data)

        # Trigger update
        self.on_condition_change(row_frame, side)

        # Configure style for delete button (red)
        style = ttk.Style()
        style.configure('Danger.TButton', foreground='red')

    def remove_condition_row(self, row_frame, side: str):
        """Remove a condition row."""
        if side == 'start':
            rows = self.start_conditions_rows
        else:
            rows = self.stop_conditions_rows
        for row_data in rows:
            if row_data['frame'] == row_frame:
                row_frame.destroy()
                rows.remove(row_data)
                self.on_condition_change(row_frame, side)  # Trigger full update
                break

    def on_sensor_change(self, sid: str, row_frame, side: str):
        """Handle sensor checkbox change, update count and validation."""
        if side == 'start':
            rows = self.start_conditions_rows
        else:
            rows = self.stop_conditions_rows
        for row_data in rows:
            if row_data['frame'] == row_frame:
                self.update_selected_count(row_data)
                self.on_condition_change(row_frame, side)
                break

    def update_selected_count(self, row_data):
        """Update the selected sensors count label."""
        count = sum(1 for var in row_data['sensor_vars'].values() if var.get())
        row_data['selected_label'].config(text=f"Selected: {count}")
        # Highlight row if invalid (0 selected)
        if count == 0:
            row_data['frame'].config(relief='solid', borderwidth=1)  # Red border via style if needed
            self.create_tooltip(row_data['frame'], "Warning: Select at least 1 sensor!")
        else:
            row_data['frame'].config(relief='flat', borderwidth=0)

    def on_condition_change(self, row_frame, side: str):
        """Handle any condition change, trigger app update."""
        if side == 'start':
            self.app.update_conditions_list('start')
        else:
            self.app.update_conditions_list('stop')
        # Validate and warn if needed (app handles full validation)

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
                                       height=15)
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

            # Alternate column colors
            if i % 2 == 0:
                self.app.log_tree.tag_configure(f"col_{i}", background="#f0f0f0")

    def create_tooltip(self, widget: tk.Widget, text: str):
        """Create a simple tooltip for a widget."""
        def enter(event):
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 20}+{event.y_root + 20}")
            label = tk.Label(tooltip, text=text, background="yellow", 
                           relief="solid", borderwidth=1, padx=5, pady=3)
            label.pack()

        def leave(event):
            for child in widget.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.destroy()

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def populate_condition_checkboxes(self):
        """Repopulate sensor checkboxes in all condition rows after sensor init."""
        # This would be called from app.initialize_sensors after sensor init
        for side in ['start', 'stop']:
            if side == 'start':
                rows = self.start_conditions_rows
            else:
                rows = self.stop_conditions_rows
            for row_data in rows:
                # Clear existing checkboxes in sensor_select_frame
                sensor_frame = row_data['frame'].winfo_children()[0]  # First is sensor_select_frame
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
