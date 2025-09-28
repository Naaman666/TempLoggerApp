# -*- coding: utf-8 -*-
"""
Temperature Logger Application - Main Entry Point
"""

import tkinter as tk
from temp_logger_core import TempLoggerApp  # Assuming flat structure; change to modules. if needed

if __name__ == "__main__":
    root = tk.Tk()
    app = TempLoggerApp(root)
    app.update_loop()
    root.mainloop()
