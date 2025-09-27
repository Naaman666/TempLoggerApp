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
        self.create_tooltip(self.generate_output_check, "Generate plots when stopping measurement")

        # Measurement name entry
        ttk.Label(top_frame, text="Measurement Name:").grid(row=0, column=4, padx=5, pady=5)
        self.app.measurement_name = tk.StringVar(value="temptestlog")
        self.measurement_name_entry = ttk.Entry(top_frame, textvariable=self.app.measurement_name, width=20)
        self.measurement_name_entry.grid(row=0, column=5, padx=5, pady=5)

        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding=5)
        settings_frame.pack(fill=tk.X, pady=5)

        # First row of settings
        ttk.Label(settings_frame, text="Log interval (s):").grid(row=0, column=0, padx=5, pady=2, sticky='W')
        self.app.log_interval = tk.StringVar(value=str(self.app.default_log_interval))
        self.log_interval_entry = ttk.Entry(settings_frame, textvariable=self.app.log_interval, width=5)
        self.log_interval_entry.grid(row=0, column=1, padx=5, pady=2, sticky='W')

        ttk.Label(settings_frame, text="Display update (s):").grid(row=0, column=2, padx=5, pady=2, sticky='W')
        self.app.view_interval = tk.StringVar(value=str(self.app.default_view_interval))
        self.view_interval_entry = ttk.Entry(settings_frame, textvariable=self.app.view_interval, width=5)
        self.view_interval_entry.grid(row=0, column=3, padx=5, pady=2, sticky='W')

        ttk.Label(settings_frame, text="Duration (hours):").grid(row=0, column=4, padx=5, pady=2, sticky='W')
        self.app.duration = tk.StringVar(value="0.0")
        self.duration_entry = ttk.Entry(settings_frame, textvariable=self.app.duration, width=5)
        self.duration_entry.grid(row=0, column=5, padx=5, pady=2, sticky='W')

        # Second row of settings (thresholds)
        ttk.Label(settings_frame, text="Start threshold (°C):").grid(row=1, column=0, padx=5, pady=2, sticky='W')
        self.app.start_threshold = tk.StringVar(value=str(self.app.default_start_threshold))
        self.start_threshold_entry = ttk.Entry(settings_frame, textvariable=self.app.start_threshold, width=5)
        self.start_threshold_entry.grid(row=1, column=1, padx=5, pady=2, sticky='W')

        ttk.Label(settings_frame, text="Stop threshold (°C):").grid(row=1, column=2, padx=5, pady=2, sticky='W')
        self.app.stop_threshold = tk.StringVar(value=str(self.app.default_stop_threshold))
        self.stop_threshold_entry = ttk.Entry(settings_frame, textvariable=self.app.stop_threshold, width=5)
        self.stop_threshold_entry.grid(row=1, column=3, padx=5, pady=2, sticky='W')

        # Sensors frame
        sensors_frame = ttk.LabelFrame(main_frame, text="Sensors", padding=5)
        sensors_frame.pack(fill=tk.X, pady=5)

        # All sensors on/off button
        self.all_sensors_button = ttk.Button(sensors_frame, text="All Sensors On/Off", 
                                           command=self.app.toggle_all_sensors)
        self.all_sensors_button.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky='W')

        # Sensor selection frame with 2 columns
        self.app.sensor_frame = ttk.Frame(sensors_frame)
        self.app.sensor_frame.grid(row=1, column=0, columnspan=10, padx=5, pady=5, sticky='W')

        # Log display
        log_frame = ttk.LabelFrame(main_frame, text="Log Display", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.app.log_display = scrolledtext.ScrolledText(log_frame, width=160, height=20)
        self.app.log_display.pack(fill=tk.BOTH, expand=True)

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