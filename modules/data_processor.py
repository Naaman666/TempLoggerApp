# -*- coding: utf-8 -*-
"""
Data processor for handling data logging, storage, and export.
"""
import tkinter as tk
from tkinter import ttk
import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import threading
import atexit
from datetime import datetime
from typing import List, TYPE_CHECKING, Dict, Any, Optional

if TYPE_CHECKING:
    from .temp_logger_core import TempLoggerApp  # Adjust if needed

from .helpers import get_next_counter, generate_short_uuid, sanitize_filename, format_duration, evaluate_operator

class DataProcessor:
    """Handles data logging, limiting, and exporting."""
    
    def __init__(self, app: 'TempLoggerApp'):
        self.app = app
        self.data: List[List] = []
        self.lock = threading.Lock()
        self.current_session_folder = None
        self.session_counter = None
        self.session_uuid = None
        self.session_start_time = None
        self.session_end_time = None
        self.temp_session_folder = None
        # Register cleanup to handle app closure
        atexit.register(self.finalize_session_folder)

    def get_total_duration_seconds(self) -> Optional[int]:
        """Calculate the total logging duration in seconds."""
        try:
            days = int(self.app.duration_days.get())
            hours = int(self.app.duration_hours.get())
            minutes = int(self.app.duration_minutes.get())
            return days * 86400 + hours * 3600 + minutes * 60
        except ValueError:
            return None

    def init_new_session(self, measurement_name: str):
        """Initialize all session-specific variables and create the measurement folder."""
        # Megszerezzük a következő sorszámot
        self.session_counter = get_next_counter()
        self.session_uuid = generate_short_uuid()
        
        # Létrehozzuk a mappa nevét az AT sorszámmal (AT:xxxx) és a mérés névvel
        sanitized_name = sanitize_filename(measurement_name)
        folder_name = f"AT:{self.session_counter:04d}_{sanitized_name}_{self.session_uuid}"
        
        self.current_session_folder = os.path.join(self.app.measurement_folder, folder_name)
        
        # Mappa létrehozása
        if not os.path.exists(self.current_session_folder):
            os.makedirs(self.current_session_folder, exist_ok=True)

        self.data = []
        self.session_start_time = datetime.now()
        self.session_end_time = None
        
        # Frissítjük az oszlopneveket a Treeview-hoz és az exportáláshoz
        self.app.data_columns = ["Type", "Seconds", "Timestamp"] + [self.app.sensor_manager.sensor_names[sid] for sid in self.app.sensor_manager.sensor_ids]

        # Export állapotok visszaállítása (hogy újra exportálhassunk)
        self.app.export_manager.reset_exports()

    def finalize_session_folder(self):
        """Placeholder for cleanup."""
        pass

    def reset_session(self):
        """Reset internal data structures after logging and export."""
        self.data = []
        # Az aktuális munkamappát megtartjuk, ha meg akarják nyitni
        self.session_start_time = None
        self.session_end_time = None
        self.app.data_columns = ["Type", "Seconds", "Timestamp"] 
        self.app.gui.update_log_treeview_columns([])

    def log_data_point(self, log_entry: List[Any]):
        """Append a new data point to the internal list and optionally to the file."""
        with self.lock:
            # Add to internal data list
            self.data.append(log_entry)
            
            # Check max log lines limit for display (not logging, as per user request)
            if len(self.data) > self.app.max_log_lines * 2: # Keep some buffer
                self.data = self.data[-self.app.max_log_lines:] 

            # Write to raw JSON log file
            if self.app.log_file:
                json_data = {
                    "Type": log_entry[0],
                    "Seconds": log_entry[1],
                    "Timestamp": log_entry[2],
                    "Data": {self.app.data_columns[i]: log_entry[i] for i in range(3, len(log_entry))}
                }
                # log_entry[3:]-ban vannak a szenzor adatok
                self.app.log_file.write(json.dumps(json_data) + "\n")
                self.app.log_file.flush()

    def check_conditions(self, conditions: List[Dict[str, Any]], current_temps: Dict[str, Optional[float]]) -> bool:
        """Check if any of the given conditions are met."""
        if not conditions:
            return False

        results = []
        for cond in conditions:
            is_met = any(evaluate_operator(current_temps.get(sid), cond['threshold'], cond['operator'])
                         for sid in cond['sensors'])
            results.append(is_met)

        if not results:
            return False

        # Ha csak egy feltétel van
        if len(results) == 1:
            return results[0]

        # Ha több feltétel van, a logikai operátor határozza meg
        final_result = results[0]
        for i in range(len(results) - 1):
            cond = conditions[i]
            next_result = results[i + 1]
            logic = cond.get('logic', 'AND') # feltételezünk AND-et, ha nincs megadva

            if logic == 'OR':
                final_result = final_result or next_result
            else: # AND
                final_result = final_result and next_result
        
        return final_result

    def export_data(self):
        """Export data to CSV, Excel, and generate plots."""
        if not self.data:
            self.app.log_to_display("Export skipped: No data logged in this session.\n")
            return

        if not self.app.generate_output_var.get():
            self.app.log_to_display("Export skipped: Output generation disabled.\n")
            return
            
        self.app.log_to_display(f"Exporting data to: {self.current_session_folder}\n")
        
        base_name = os.path.basename(self.current_session_folder)
        base_path = os.path.join(self.current_session_folder, base_name)
        
        # 1. Alap adatkeret létrehozása
        df = pd.DataFrame(self.data, columns=self.app.data_columns)
        
        # Átalakítjuk a szenzor oszlopokat, hogy a "None" értékek helyett NaN legyen a plotoláshoz
        for col in self.app.data_columns[3:]:
            # Az oszlop adatait megpróbáljuk float-ra konvertálni, a None/Inactive értékeket kihagyva
            df[col] = pd.to_numeric(df[col], errors='coerce') 

        # 2. Export Excelbe
        excel_path = f"{base_path}.xlsx"
        self.app.log_to_display(f"-> Generating Excel: {excel_path}\n")
        self._save_to_excel(df, excel_path)
        
        # 3. Export CSV-be
        csv_path = f"{base_path}.csv"
        self.app.log_to_display(f"-> Generating CSV: {csv_path}\n")
        df.to_csv(csv_path, index=False)
        
        # 4. Plotok generálása
        self.app.log_to_display("-> Generating plots (PNG, PDF)...\n")
        self._save_plots(filename_png=f"{base_path}.png", filename_pdf=f"{base_path}.pdf")
        
        self.app.log_to_display("Export process finished.\n")

    def _save_to_excel(self, df: pd.DataFrame, file_path: str):
        """Save dataframe to Excel and add a chart."""
        # Workbook és sheets létrehozása
        writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
        df.to_excel(writer, sheet_name='Data', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['Data']
        
        # Oszlop szélesség beállítása
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
            worksheet.set_column(i, i, max_len)

        # Grafikon hozzáadása (XY scatter/line chart)
        chart = workbook.add_chart({'type': 'scatter'})
        
        # Add series for each temperature column
        # df.columns.get_loc("Seconds") a másodperc oszlop
        seconds_col_num = df.columns.get_loc("Seconds") + 1 # Excel oszlop index (1-től indul)
        
        # Hőmérséklet oszlopok: [3:]-tól indulnak az oszlopnevek a self.app.data_columns-ban
        for i, col in enumerate(self.app.data_columns[3:], 3):  
            # Ellenőrizzük, hogy az oszlop létezik a DataFrame-ben (a DataProcessor kezeli a lehetséges különbségeket)
            if col in df.columns:
                col_num = df.columns.get_loc(col) + 1 # Excel oszlop index
                
                # A kategóriák (X tengely) a 'Seconds' oszlop adatai
                # A 'Data' sheet, a kategóriák 2. sortól (index 1) a másodperc oszlop 2. oszlopától (index 1) indulnak
                # Categories: ['SheetName', start_row, start_col, end_row, end_col]
                # Values: ['SheetName', start_row, start_col, end_row, end_col]
                chart.add_series({
                    'name': f'=\'Data\'!${chr(65 + col_num - 1)}$1', # pl. ='Data'!$D$1
                    'categories': ['Data', 1, seconds_col_num - 1, len(df), seconds_col_num - 1],  # Seconds oszlop (pl. C oszlop, 2. sortól)
                    'values': ['Data', 1, col_num - 1, len(df), col_num - 1], # Az aktuális hőmérséklet oszlop
                })
        
        chart.set_title({'name': 'Temperature Measurements'})
        chart.set_x_axis({'name': 'Time (seconds)'})
        chart.set_y_axis({'name': 'Temperature (°C)'})
        
        # A grafikon beszúrása, például F2 cellába
        worksheet.insert_chart('F2', chart)

        # Workbook lezárása
        try:
            writer.close()
        except Exception as e:
            self.app.log_to_display(f"Error closing Excel writer: {e}\n")


    def _save_plots(self, filename_png: str = None, filename_pdf: str = None, fmt: str = 'png'):
        """Save plots as PNG and/or PDF."""
        df = pd.DataFrame(self.data, columns=self.app.data_columns)
        plt.figure(figsize=(10, 6))
        
        for col in self.app.data_columns[3:]:  # Skip Type, Seconds, Timestamp
            # Az oszlop adatait megpróbáljuk float-ra konvertálni, a None/Inactive értékeket kihagyva
            df[col] = pd.to_numeric(df[col], errors='coerce') 
            if col in df.columns:
                # Azok a sorok, ahol van adat
                valid_data = df.dropna(subset=[col])
                if not valid_data.empty:
                    plt.plot(valid_data['Seconds'], valid_data[col], label=col)
        
        plt.xlabel("Seconds")
        plt.ylabel("Temperature (°C)")
        plt.title("Temperature Logs")
        plt.legend()
        plt.grid(True)
        
        # MENTÉS
        if filename_png:
            plt.savefig(filename_png, format='png')
        if filename_pdf:
            plt.savefig(filename_pdf, format='pdf')
            
        plt.close()
