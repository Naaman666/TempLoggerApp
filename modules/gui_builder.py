# -*- coding: utf-8 -*-
"""
GUI builder for Temperature Logger application.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .temp_logger_app import TempLoggerApp

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

        # TEMPERATURE-CONTROLLED MEASUREMENT frame
        temp_control_frame = ttk.LabelFrame(main_frame, text="Temperature-Controlled Measurement", padding=5)
        temp_control_frame.pack(fill=tk.X, pady=5)

        self.app.temp_control_enabled = tk.BooleanVar(value=False)
        temp_control_check = ttk.Checkbutton(temp_control_frame, text="Enable temperature-based start/stop", 
                                           variable=self.app.temp_control_enabled)
        temp_control_check.grid(row=0, column=0, padx=5, pady=2, sticky='W')

        ttk.Label(temp_control_frame, text="Start threshold (°C):").grid(row=0, column=1, padx=5, pady=2, sticky='W')
        self.app.start_threshold = tk.StringVar(value=str(self.app.default_start_threshold))
        self.start_threshold_entry = ttk.Entry(temp_control_frame, textvariable=self.app.start_threshold, width=8)
        self.start_threshold_entry.grid(row=0, column=2, padx=5, pady=2, sticky='W')
        self.create_tooltip(self.start_threshold_entry, "Temperature above which measurement starts (if enabled).")

        ttk.Label(temp_control_frame, text="Stop threshold (°C):").grid(row=0, column=3, padx=5, pady=2, sticky='W')
        self.app.stop_threshold = tk.StringVar(value=str(self.app.default_stop_threshold))
        self.stop_threshold_entry = ttk.Entry(temp_control_frame, textvariable=self.app.stop_threshold, width=8)
        self.stop_threshold_entry.grid(row=0, column=4, padx=5, pady=2, sticky='W')
        self.create_tooltip(self.stop_threshold_entry, "Temperature below which measurement stops (if enabled). Must be > start threshold.")

        # Sensor selection frame (assuming it's added elsewhere or after)
        sensor_frame = ttk.LabelFrame(main_frame, text="Sensor Selection", padding=5)
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
