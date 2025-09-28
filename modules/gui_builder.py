# -*- coding: utf-8 -*-
"""
GUI builder for Temperature Logger application.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import TYPE_CHECKING, Dict, Any, List, Optional

if TYPE_CHECKING:
    from .temp_logger_core import TempLoggerApp

class GUIBuilder:
    """Handles GUI initialization and management."""
    
    def __init__(self, root: tk.Tk, app: 'TempLoggerApp'):
        self.root = root
        self.app = app
        self.tooltips = []
        self.start_conditions_rows: List[Dict[str, Any]] = []
        self.stop_conditions_rows: List[Dict[str, Any]] = []
        self.progress_window: Optional[tk.Toplevel] = None
        self.progress_bar: Optional[ttk.Progressbar] = None
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
        
    def center_progress_window(self, toplevel: tk.Toplevel):
        """Center the progress window on the screen."""
        toplevel.update_idletasks()
        width = 300
        height = 80
        x = (toplevel.winfo_screenwidth() // 2) - (width // 2)
        y = (toplevel.winfo_screenheight() // 2) - (height // 2)
        toplevel.geometry(f'{width}x{height}+{x}+{y}')

    def show_export_progress(self):
        """Show the progress bar window and disable main window interaction."""
        if self.progress_window:
            return

        self.progress_window = tk.Toplevel(self.root)
        self.progress_window.title("Exporting Data...")
        self.progress_window.transient(self.root) 
        self.progress_window.grab_set()          # Modal: blocks input to other windows
        self.progress_window.resizable(False, False)
        
        # Remove window decorations (title bar, buttons) for a cleaner pop-up
        self.progress_window.overrideredirect(True) 
        
        self.center_progress_window(self.progress_window)
        
        frame = ttk.Frame(self.progress_window, padding="15")
        frame.pack(expand=True, fill='both')

        ttk.Label(frame, text="Generating plots and files...").pack(pady=(0, 10))

        self.progress_bar = ttk.Progressbar(frame, orient='horizontal', length=250, mode='determinate')
        self.progress_bar.pack(fill='x')
        self.progress_bar['maximum'] = 100 # Percentage based

        self.root.config(cursor="wait")
        self.root.update()

    def update_progress(self, value: int):
        """Update the progress bar value (0-100)."""
        if self.progress_bar:
            self.progress_bar['value'] = value
            self.progress_window.update_idletasks()

    def hide_export_progress(self):
        """Destroy the progress bar window and re-enable main window."""
        if self.progress_window:
            self.progress_window.grab_release()
            self.progress_window.destroy()
            self.progress_window = None
            self.progress_bar = None
            self.root.config(cursor="")
            self.root.update()

    def init_gui(self):
        """Initialize the GUI elements."""
        self.root.title("Temperature Logger")
        self.root.protocol("WM_DELETE_WINDOW", self.app.on_closing)
        
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, padding="10 10 10 10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=3)
        main_frame.grid_rowconfigure(1, weight=1)
        
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

        # --- Side Panel (Container for Notebook) ---
        side_panel = ttk.Frame(main_frame, padding="5 5 5 5")
        side_panel.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        side_panel.grid_rowconfigure(0, weight=1)
        side_panel.grid_columnconfigure(0, weight=1)

        # --- Settings Notebook ---
        self.settings_notebook = ttk.Notebook(side_panel)
        self.settings_notebook.grid(row=0, column=0, sticky='NSEW')
        
        # --- TAB 1: Main Settings ---
        main_tab = ttk.Frame(self.settings_notebook, padding="5")
        self.settings_notebook.add(main_tab, text='Main')
        main_tab.grid_columnconfigure(0, weight=1)
        
        # Sensor Status Frame
        self.app.sensor_frame = ttk.LabelFrame(main_tab, text="Sensor Status and Selection", padding="5 5 5 5")
        self.app.sensor_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        self.app.sensor_frame.grid_columnconfigure(0, weight=1)

        # Measurement Duration Frame (Fixed Duration)
        duration_frame = ttk.LabelFrame(main_tab, text="Fixed Duration", padding=5)
        duration_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Checkbutton(duration_frame, text="Enable Duration Limit", variable=self.app.duration_enabled, command=self._toggle_duration_input).grid(row=0, column=0, columnspan=4, sticky='W')

        ttk.Label(duration_frame, text="Days:").grid(row=1, column=0, padx=5, pady=2, sticky='E')
        ttk.Entry(duration_frame, textvariable=self.app.duration_days, width=5).grid(row=1, column=1, padx=5, pady=2, sticky='W')
        
        ttk.Label(duration_frame, text="Hours:").grid(row=1, column=2, padx=5, pady=2, sticky='E')
        ttk.Entry(duration_frame, textvariable=self.app.duration_hours, width=5).grid(row=1, column=3, padx=5, pady=2, sticky='W')

        ttk.Label(duration_frame, text="Minutes:").grid(row=1, column=4, padx=5, pady=2, sticky='E')
        ttk.Entry(duration_frame, textvariable=self.app.duration_minutes, width=5).grid(row=1, column=5, padx=5, pady=2, sticky='W')
        
        self.duration_inputs = duration_frame.winfo_children()[2:]
        self._toggle_duration_input()

        # --- TAB 2: Duration/Conditions (Temperature-Controlled) ---
        conditions_tab = ttk.Frame(self.settings_notebook, padding="5")
        self.settings_notebook.add(conditions_tab, text='Duration/Conditions')
        conditions_tab.grid_columnconfigure(0, weight=1)
        conditions_tab.grid_rowconfigure(0, weight=1)
        
        # TEMPERATURE-CONTROLLED MEASUREMENT frame
        temp_control_frame = ttk.LabelFrame(conditions_tab, text="Temperature-Controlled Measurement", padding=5)
        temp_control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        temp_control_frame.grid_rowconfigure(0, weight=1)
        temp_control_frame.grid_rowconfigure(1, weight=1)
        temp_control_frame.grid_columnconfigure(0, weight=1)

        # --- START CONDITIONS BLOCK ---
        start_block = ttk.LabelFrame(temp_control_frame, text="Start Conditions", padding=5)
        start_block.grid(row=0, column=0, sticky='NSEW', pady=2)
        start_block.grid_columnconfigure(0, weight=1)

        header_start = ttk.Frame(start_block)
        header_start.grid(row=0, column=0, sticky='EW')
        header_start.grid_columnconfigure(0, weight=1)
        
        self.start_enable_check = ttk.Checkbutton(header_start, text="Enable Start Conditions", 
                                                variable=self.app.temp_start_enabled, 
                                                command=lambda: self.app.update_conditions_list('start'))
        self.start_enable_check.grid(row=0, column=0, padx=5, pady=2, sticky='W')
        self.create_tooltip(self.start_enable_check, "Enable automatic start based on temperature conditions.")
        
        ttk.Button(header_start, text="Add Start Condition", 
                   command=lambda: self._create_condition_row('start')).grid(row=0, column=1, padx=5, pady=2)

        self.start_conditions_container = ttk.Frame(start_block)
        self.start_conditions_container.grid(row=1, column=0, sticky='NSEW')
        self.start_conditions_container.grid_columnconfigure(0, weight=1)

        # --- STOP CONDITIONS BLOCK ---
        stop_block = ttk.LabelFrame(temp_control_frame, text="Stop Conditions", padding=5)
        stop_block.grid(row=1, column=0, sticky='NSEW', pady=2)
        stop_block.grid_columnconfigure(0, weight=1)

        header_stop = ttk.Frame(stop_block)
        header_stop.grid(row=0, column=0, sticky='EW')
        header_stop.grid_columnconfigure(0, weight=1)

        self.stop_enable_check = ttk.Checkbutton(header_stop, text="Enable Stop Conditions", 
                                                variable=self.app.temp_stop_enabled,
                                                command=lambda: self.app.update_conditions_list('stop'))
        self.stop_enable_check.grid(row=0, column=0, padx=5, pady=2, sticky='W')
        self.create_tooltip(self.stop_enable_check, "Enable automatic stop based on temperature conditions.")
        
        ttk.Button(header_stop, text="Add Stop Condition", 
                   command=lambda: self._create_condition_row('stop')).grid(row=0, column=1, padx=5, pady=2)

        self.stop_conditions_container = ttk.Frame(stop_block)
        self.stop_conditions_container.grid(row=1, column=0, sticky='NSEW')
        self.stop_conditions_container.grid_columnconfigure(0, weight=1)

        # --- Right Panel: Logs and Plots ---
        right_panel = ttk.Frame(main_frame, padding="5 5 5 5")
        right_panel.grid(row=1, column=1, sticky=(tk.N, tk.S, tk.W, tk.E))
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        
        # Log View (Treeview)
        log_view_frame = ttk.LabelFrame(right_panel, text="Live Log Data", padding="5")
        log_view_frame.grid(row=0, column=0, sticky='NSEW', pady=5)
        log_view_frame.grid_rowconfigure(0, weight=1)
        log_view_frame.grid_columnconfigure(0, weight=1)
        
        self.app.log_tree = ttk.Treeview(log_view_frame, columns=("Seconds", "Timestamp"), show="headings")
        self.app.log_tree.grid(row=0, column=0, sticky='NSEW')

        # Scrollbars for Treeview
        log_tree_scrollbar_y = ttk.Scrollbar(log_view_frame, orient="vertical", command=self.app.log_tree.yview)
        log_tree_scrollbar_y.grid(row=0, column=1, sticky='NS')
        self.app.log_tree.config(yscrollcommand=log_tree_scrollbar_y.set)

        # Log Messages (ScrolledText)
        message_frame = ttk.LabelFrame(right_panel, text="Application Messages", padding="5")
        message_frame.grid(row=1, column=0, sticky='NSEW', pady=5)
        message_frame.grid_rowconfigure(0, weight=1)
        message_frame.grid_columnconfigure(0, weight=1)

        self.app.log_messages = scrolledtext.ScrolledText(message_frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        self.app.log_messages.grid(row=0, column=0, sticky='NSEW')
        
        # Styles for Treeview rows
        self.app.log_tree.tag_configure('oddrow', background='#E0E0E0')
        self.app.log_tree.tag_configure('evenrow', background='#F0F0F0')

        self.update_start_stop_buttons(False)
        self.app.data_columns = ["Type", "Seconds", "Timestamp"] 
        self.update_log_treeview_columns([])
        self.app.log_to_display("Application initialized. Searching for sensors...\n")

    def _toggle_duration_input(self):
        """Toggle fixed duration input fields."""
        state = tk.NORMAL if self.app.duration_enabled.get() else tk.DISABLED
        for entry in self.duration_inputs:
            entry.config(state=state)

    # ... _create_condition_row, _delete_condition_row, _update_condition_row, update_log_treeview_columns, 
    #     populate_condition_checkboxes, create_tooltip, update_start_stop_buttons, load_conditions_to_rows methods...
    # (These methods are assumed to be complete and correct based on previous context)
    
    # Placeholders for missing methods if they exist outside the snippet:

    def _create_condition_row(self, side: str):
        pass # Placeholder

    def _delete_condition_row(self, row_data: Dict[str, Any], side: str):
        pass # Placeholder

    def _update_condition_row(self, row_data: Dict[str, Any], side: str):
        pass # Placeholder

    def update_log_treeview_columns(self, sensor_names: List[str]):
        pass # Placeholder
        
    def populate_condition_checkboxes(self):
        pass # Placeholder
        
    def create_tooltip(self, widget: tk.Widget, text: str):
        pass # Placeholder

    def update_start_stop_buttons(self, is_running: bool):
        """Update the state of Start/Stop buttons."""
        if is_running:
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def load_conditions_to_rows(self, conditions: List[Dict[str, Any]], side: str):
        pass # Placeholder
