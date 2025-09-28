# -*- coding: utf-8 -*-
"""
GUI builder for Temperature Logger application.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import TYPE_CHECKING, Dict, Any, List

# Type Hinting for better development experience (avoiding circular imports at runtime)
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
        # Clean up any existing widgets before building the new GUI
        for widget in self.root.winfo_children():
            widget.destroy()
        self.init_gui()

    def center_window(self):
        """Center the window on the screen."""
        self.root.update_idletasks()
        # Set a reasonable default size for a complex app
        width, height = 1400, 800
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def init_gui(self):
        """Initialize the GUI elements."""
        self.root.title("Temperature Logger")
        self.root.protocol("WM_DELETE_WINDOW", self.app.on_closing)
        
        # Configure grid for the main window
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Main frame
        main_frame = ttk.Frame(self.root, padding="10 10 10 10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=3)
        main_frame.grid_rowconfigure(1, weight=1) # Log/Sensor Frame
        
        # --- Top Control Frame ---
        control_frame = ttk.Frame(main_frame, padding="5 5 5 5")
        control_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # Measurement Name
        ttk.Label(control_frame, text="Measurement Name:").grid(row=0, column=0, padx=5, pady=5, sticky='W')
        ttk.Entry(control_frame, textvariable=self.app.measurement_name, width=30).grid(row=0, column=1, padx=5, pady=5, sticky='W')
        self.create_tooltip(control_frame.winfo_children()[-1], "File name for the measurement logs.")

        # Log Interval
        ttk.Label(control_frame, text="Log Interval (s):").grid(row=0, column=2, padx=5, pady=5, sticky='W')
        ttk.Entry(control_frame, textvariable=self.app.log_interval, width=10).grid(row=0, column=3, padx=5, pady=5, sticky='W')
        self.create_tooltip(control_frame.winfo_children()[-1], "Interval for writing data to log file (seconds).")

        # View Interval
        ttk.Label(control_frame, text="View Interval (s):").grid(row=0, column=4, padx=5, pady=5, sticky='W')
        ttk.Entry(control_frame, textvariable=self.app.view_interval, width=10).grid(row=0, column=5, padx=5, pady=5, sticky='W')
        self.create_tooltip(control_frame.winfo_children()[-1], "Interval for updating data on the screen (seconds).")

        # Output to CSV/Excel checkbox
        ttk.Checkbutton(control_frame, text="Generate output file (CSV/Excel)", variable=self.app.generate_output_var).grid(row=0, column=6, padx=10, pady=5, sticky='W')
        
        # Start/Stop Buttons
        self.start_button = ttk.Button(control_frame, text="Start Logging", command=self.app.start_logging, state=tk.NORMAL)
        self.start_button.grid(row=0, column=7, padx=5, pady=5, sticky='W')
        
        self.stop_button = ttk.Button(control_frame, text="Stop Logging", command=self.app.stop_logging, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=8, padx=5, pady=5, sticky='W')

        # --- Side Panel (Sensor Control and Conditions) ---
        side_panel = ttk.Frame(main_frame, padding="5 5 5 5")
        side_panel.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        side_panel.grid_rowconfigure(2, weight=1) # Log/Sensor status frame
        
        # Sensor Status Frame (Placeholder for sensor_manager to populate)
        self.app.sensor_frame = ttk.LabelFrame(side_panel, text="Sensor Status and Selection", padding="5 5 5 5")
        self.app.sensor_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        self.app.sensor_frame.grid_columnconfigure(0, weight=1)

        # Measurement Duration Frame
        duration_frame = ttk.LabelFrame(side_panel, text="Fixed Duration", padding=5)
        duration_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Checkbutton(duration_frame, text="Enable Duration Limit", variable=self.app.duration_enabled, command=self._toggle_duration_input).grid(row=0, column=0, columnspan=4, sticky='W')

        ttk.Label(duration_frame, text="Days:").grid(row=1, column=0, padx=5, pady=2, sticky='E')
        ttk.Entry(duration_frame, textvariable=self.app.duration_days, width=5).grid(row=1, column=1, padx=5, pady=2, sticky='W')
        
        ttk.Label(duration_frame, text="Hours:").grid(row=1, column=2, padx=5, pady=2, sticky='E')
        ttk.Entry(duration_frame, textvariable=self.app.duration_hours, width=5).grid(row=1, column=3, padx=5, pady=2, sticky='W')

        ttk.Label(duration_frame, text="Minutes:").grid(row=1, column=4, padx=5, pady=2, sticky='E')
        ttk.Entry(duration_frame, textvariable=self.app.duration_minutes, width=5).grid(row=1, column=5, padx=5, pady=2, sticky='W')
        
        self.duration_inputs = duration_frame.winfo_children()[2:]
        self._toggle_duration_input() # Initial state setting

        # TEMPERATURE-CONTROLLED MEASUREMENT frame - NEW STRUCTURE
        temp_control_frame = ttk.LabelFrame(side_panel, text="Temperature-Controlled Measurement", padding=5)
        temp_control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        temp_control_frame.grid_rowconfigure(1, weight=1) # Start/Stop conditions area
        temp_control_frame.grid_columnconfigure(0, weight=1)

        # --- START CONDITIONS BLOCK ---
        start_block = ttk.LabelFrame(temp_control_frame, text="Start Conditions", padding=5)
        start_block.pack(fill=tk.BOTH, expand=True, pady=2)
        start_block.grid_columnconfigure(0, weight=1)

        header_start = ttk.Frame(start_block)
        header_start.grid(row=0, column=0, sticky='EW')
        header_start.grid_columnconfigure(0, weight=1)
        
        # JAVÍTVA: Csak a TempLoggerApp-ban inicializált változóra hivatkozunk
        self.start_enable_check = ttk.Checkbutton(header_start, text="Enable Start Conditions", 
                                                variable=self.app.temp_start_enabled, command=lambda: self.app.update_conditions_list('start'))
        self.start_enable_check.grid(row=0, column=0, padx=5, pady=2, sticky='W')
        self.create_tooltip(self.start_enable_check, "Enable automatic start based on temperature conditions.")

        # Add row button for start
        ttk.Button(header_start, text="Add Start Condition", command=lambda: self._create_condition_row('start')).grid(row=0, column=1, padx=5, pady=2)
        
        self.start_conditions_container = ttk.Frame(start_block)
        self.start_conditions_container.grid(row=1, column=0, sticky='NSEW')
        self.start_conditions_container.grid_columnconfigure(0, weight=1)
        
        # --- STOP CONDITIONS BLOCK ---
        stop_block = ttk.LabelFrame(temp_control_frame, text="Stop Conditions", padding=5)
        stop_block.pack(fill=tk.BOTH, expand=True, pady=2)
        stop_block.grid_columnconfigure(0, weight=1)
        
        header_stop = ttk.Frame(stop_block)
        header_stop.grid(row=0, column=0, sticky='EW')
        header_stop.grid_columnconfigure(0, weight=1)

        # JAVÍTVA: Csak a TempLoggerApp-ban inicializált változóra hivatkozunk
        self.stop_enable_check = ttk.Checkbutton(header_stop, text="Enable Stop Conditions", 
                                               variable=self.app.temp_stop_enabled, command=lambda: self.app.update_conditions_list('stop'))
        self.stop_enable_check.grid(row=0, column=0, padx=5, pady=2, sticky='W')
        self.create_tooltip(self.stop_enable_check, "Enable automatic stop based on temperature conditions.")

        # Add row button for stop
        ttk.Button(header_stop, text="Add Stop Condition", command=lambda: self._create_condition_row('stop')).grid(row=0, column=1, padx=5, pady=2)
        
        self.stop_conditions_container = ttk.Frame(stop_block)
        self.stop_conditions_container.grid(row=1, column=0, sticky='NSEW')
        self.stop_conditions_container.grid_columnconfigure(0, weight=1)

        # --- Main Log Frame (Treeview) ---
        log_frame = ttk.Frame(main_frame, padding="5 5 5 5")
        log_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

        # Treeview (Log)
        self.app.log_tree = ttk.Treeview(log_frame, show='headings')
        self.app.log_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.app.log_tree.yview)
        v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.app.log_tree.configure(yscrollcommand=v_scroll.set)

        h_scroll = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL, command=self.app.log_tree.xview)
        h_scroll.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        self.app.log_tree.configure(xscrollcommand=h_scroll.set)
        
        # Tag for alternating row colors
        self.app.log_tree.tag_configure('oddrow', background='#f0f0f0')
        self.app.log_tree.tag_configure('evenrow', background='#ffffff')
        
        # Placeholder for initial columns
        self.app.log_tree["columns"] = ("timestamp",)
        self.app.log_tree.heading("timestamp", text="Timestamp")
        self.app.log_tree.column("timestamp", width=120)

        # --- Log Messages Area ---
        log_message_frame = ttk.LabelFrame(main_frame, text="Application Log", padding="5")
        log_message_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))
        log_message_frame.grid_rowconfigure(0, weight=1)
        log_message_frame.grid_columnconfigure(0, weight=1)
        
        self.app.log_messages = scrolledtext.ScrolledText(log_message_frame, height=5, state=tk.DISABLED)
        self.app.log_messages.grid(row=0, column=0, sticky='NSEW')

    def _toggle_duration_input(self):
        """Toggle the state of duration input fields."""
        state = tk.NORMAL if self.app.duration_enabled.get() else tk.DISABLED
        for widget in self.duration_inputs:
            if isinstance(widget, ttk.Entry):
                widget.config(state=state)

    def _create_condition_row(self, side: str):
        """Create a new condition row (start or stop)."""
        
        # Determine container and list
        if side == 'start':
            container = self.start_conditions_container
            condition_list = self.start_conditions_rows
        else: # side == 'stop'
            container = self.stop_conditions_container
            condition_list = self.stop_conditions_rows
        
        row_frame = ttk.Frame(container, padding=2)
        row_frame.pack(fill=tk.X)
        
        row_data = {
            'frame': row_frame,
            'side': side,
            'sensor_vars': {},
            'operator_var': tk.StringVar(value='>'),
            'threshold_var': tk.StringVar(value='25.0'),
            'logic_var': tk.StringVar(value='AND')
        }
        
        # 1. LOGIC (AND/OR) for subsequent rows
        if condition_list:
            logic_options = ['AND', 'OR']
            logic_menu = ttk.OptionMenu(row_frame, row_data['logic_var'], 'AND', *logic_options, 
                                        command=lambda x: self.app.update_conditions_list(side))
            logic_menu.grid(row=0, column=0, padx=5, pady=2, sticky='W')
            row_data['logic_menu'] = logic_menu
        else:
            # First row doesn't need logic, add a placeholder label
            ttk.Label(row_frame, text="First:").grid(row=0, column=0, padx=5, pady=2, sticky='W')
            row_data['logic_var'].set(None) # Set to None for the core logic
            
        col_index = 1
        
        # 2. OPERATOR
        operator_options = ['>', '<', '>=', '<=']
        ttk.OptionMenu(row_frame, row_data['operator_var'], row_data['operator_var'].get(), *operator_options,
                       command=lambda x: self.app.update_conditions_list(side)).grid(row=0, column=col_index, padx=5, pady=2)
        col_index += 1
        
        # 3. THRESHOLD
        ttk.Entry(row_frame, textvariable=row_data['threshold_var'], width=7).grid(row=0, column=col_index, padx=5, pady=2)
        row_data['threshold_var'].trace_add('write', lambda *args: self.app.update_conditions_list(side))
        col_index += 1
        
        ttk.Label(row_frame, text="°C on:").grid(row=0, column=col_index, padx=5, pady=2, sticky='W')
        col_index += 1
        
        # 4. SENSOR SELECTION (Placeholder, populated by populate_condition_checkboxes)
        sensor_frame = ttk.Frame(row_frame)
        sensor_frame.grid(row=0, column=col_index, padx=5, pady=2, sticky='W')
        row_data['sensor_frame'] = sensor_frame
        col_index += 1
        
        # 5. REMOVE BUTTON
        remove_button = ttk.Button(row_frame, text="X", width=2, command=lambda: self._remove_condition_row(row_data))
        remove_button.grid(row=0, column=col_index, padx=5, pady=2)
        
        # Add to list
        condition_list.append(row_data)
        self.app.update_conditions_list(side)
        
        # Populate sensors if available
        self.populate_condition_checkboxes(row_data)

    def _remove_condition_row(self, row_data: Dict[str, Any]):
        """Remove a condition row and update the core logic."""
        
        # Destroy the frame
        row_data['frame'].destroy()
        
        # Remove from the list
        side = row_data['side']
        if side == 'start':
            self.start_conditions_rows.remove(row_data)
        else:
            self.stop_conditions_rows.remove(row_data)
            
        # If the first row was deleted, update the logic of the new first row (remove logic dropdown)
        if (side == 'start' and self.start_conditions_rows and 'logic_menu' in self.start_conditions_rows[0]):
            first_row = self.start_conditions_rows[0]
            first_row['logic_menu'].destroy()
            ttk.Label(first_row['frame'], text="First:").grid(row=0, column=0, padx=5, pady=2, sticky='W')
            first_row['logic_var'].set(None)
            first_row.pop('logic_menu') # Clean up dict
            
        elif (side == 'stop' and self.stop_conditions_rows and 'logic_menu' in self.stop_conditions_rows[0]):
            first_row = self.stop_conditions_rows[0]
            first_row['logic_menu'].destroy()
            ttk.Label(first_row['frame'], text="First:").grid(row=0, column=0, padx=5, pady=2, sticky='W')
            first_row['logic_var'].set(None)
            first_row.pop('logic_menu') # Clean up dict
            
        # Update core logic
        self.app.update_conditions_list(side)


    def populate_condition_checkboxes(self, row_data: Optional[Dict[str, Any]] = None):
        """
        Populate sensor checkboxes for all existing condition rows, 
        or a specific new row if row_data is provided.
        """
        
        def create_checkboxes(data: Dict[str, Any]):
            # Clear previous checkboxes
            for widget in data['sensor_frame'].winfo_children():
                widget.destroy()
            
            # Create a checkbox for each sensor
            for sensor_id, sensor_name in self.app.sensor_manager.sensor_names.items():
                var = data['sensor_vars'].setdefault(sensor_id, tk.BooleanVar(value=True))
                
                check = ttk.Checkbutton(data['sensor_frame'], text=sensor_name, variable=var, 
                                        command=lambda d=data: (self.app.update_conditions_list(d['side']), self.update_selected_count(d)))
                check.pack(side=tk.LEFT, padx=3)
            
            # Initial count update for the frame border
            self.update_selected_count(data)
            
        if row_data:
            create_checkboxes(row_data)
        else:
            # Populate all existing rows (used at sensor initialization)
            for data in self.start_conditions_rows:
                create_checkboxes(data)
            for data in self.stop_conditions_rows:
                create_checkboxes(data)
            
    def update_selected_count(self, row_data: Dict[str, Any]):
        """Update visual count of selected sensors and frame border."""
        count = sum(1 for var in row_data['sensor_vars'].values() if var.get())
        frame = row_data['frame']
        
        if count == 0:
            frame.config(relief='solid', borderwidth=1)
            self.create_tooltip(frame, "Warning: Select at least 1 sensor!")
        else:
            frame.config(relief='flat', borderwidth=0)
            # JAVÍTVA: A Tooltip explicit törlése eltávolítva a kód egyszerűsítése érdekében.
            pass

    def update_log_treeview_columns(self, sensor_names: Dict[str, str]):
        """Update the Treeview columns based on discovered sensor names."""
        
        # Clear existing columns, except the hidden #0 column
        current_columns = self.app.log_tree["columns"]
        for col in current_columns:
            self.app.log_tree.heading(col, text="")
            self.app.log_tree.column(col, width=0)

        # Set new columns
        columns = ["timestamp"] + list(sensor_names.values())
        self.app.log_tree["columns"] = columns

        # Configure timestamp column
        self.app.log_tree.column("timestamp", width=120, anchor=tk.CENTER)
        self.app.log_tree.heading("timestamp", text="Timestamp")

        # Configure sensor columns
        for name in sensor_names.values():
            col_width = 80 if "Ambient" in name else 70
            self.app.log_tree.column(name, width=col_width, anchor=tk.CENTER)
            self.app.log_tree.heading(name, text=name)

    def create_tooltip(self, widget: tk.Widget, text: str):
        """Create a simple tooltip for a widget."""
        
        def enter(event):
            # Create a Toplevel window for the tooltip
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True) # Removes window decorations
            
            # Position the tooltip slightly offset from the cursor
            tooltip.wm_geometry(f"+{event.x_root + 20}+{event.y_root + 20}")
            
            label = tk.Label(tooltip, text=text, background="yellow", 
                           relief="solid", borderwidth=1, padx=5, pady=3,
                           justify=tk.LEFT)
            label.pack()
            self.tooltips.append(tooltip) # Track the tooltip
            widget.tooltip_window = tooltip # Store reference on the widget

        def leave(event):
            # Destroy the specific tooltip when mouse leaves
            if hasattr(widget, 'tooltip_window') and widget.tooltip_window in self.tooltips:
                widget.tooltip_window.destroy()
                self.tooltips.remove(widget.tooltip_window)
                del widget.tooltip_window
                
        # Bind events
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def update_start_stop_buttons(self, is_running: bool):
        """Update the state of Start/Stop buttons."""
        if is_running:
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
