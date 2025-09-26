# Temperature Logger Application

## Overview
This Python application logs temperature data from DS18B20 sensors connected to a Raspberry Pi Zero 2 W. It features a Tkinter-based GUI for real-time monitoring, data export (CSV, Excel, JSON), and plot generation (PNG, PDF). The app supports configurable logging intervals, temperature thresholds, and sensor management, with settings saved in a JSON configuration file.

## Features
- **Real-time Monitoring**: Displays temperature readings with customizable update intervals.
- **Data Logging**: Logs data to a file with configurable intervals.
- **Export Options**: Save data as CSV, Excel, or JSON; generate temperature plots as PNG and PDF.
- **Sensor Configuration**: Rename sensors, save/load configurations, and select active sensors.
- **Threshold-based Control**: Start/stop logging based on temperature thresholds.
- **Progress Tracking**: Displays progress for timed measurements with a progress bar.

## Requirements
- **Hardware**: Raspberry Pi Zero 2 W with DS18B20 temperature sensors.
- **Software**:
  - Python 3.7+
  - Libraries: `tkinter`, `pandas`, `matplotlib`, `w1thermsensor`
  - Install dependencies: `pip install pandas matplotlib w1thermsensor openpyxl`

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/Naaman666/TempLoggerApp.git
   cd TempLoggerApp
   ```
2. Install required Python libraries:
   ```bash
   pip install -r requirements.txt
   ```
3. Ensure DS18B20 sensors are connected and the `w1-gpio` and `w1-therm` kernel modules are enabled on the Raspberry Pi.

## Usage
1. Run the application (in TempLoggerApp dir):
   ```bash
   python TempLoggerApp.py
   ```
2. Configure settings in the GUI:
   - Set log and display update intervals.
   - Define start/stop temperature thresholds.
   - Specify measurement duration (0 for unlimited).
   - Select active sensors and rename them via double-click.
3. Start logging with the "Start" button.
4. Export data or generate plots using the respective buttons.
5. Save or load sensor configurations via the config buttons.

## Configuration
- **config.json**: Located in the project root, it defines default settings (e.g., log intervals, thresholds, folders).
- **Output Files**: Logs and exports are saved in `TestResults/<timestamp>`; configurations in `SensorConfigs`.

## Notes
- Designed for Raspberry Pi Zero 2 W (512 MB RAM, 1 GHz quad-core CPU).
- Handles sensor errors with retries and logs issues to the GUI.
- Limits GUI log display to prevent slowdown (default: 500 lines).

## License
MIT License. See `LICENSE` for details.
