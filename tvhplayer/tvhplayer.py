from datetime import datetime, timedelta
import sys
from tkinter.filedialog import FileDialog
import vlc
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QComboBox, QAction, QSplitter, QFrame,
    QListWidget, QDialog, QFormLayout, QLineEdit,
    QDialogButtonBox, QMessageBox, QApplication,
    QPushButton, QLabel, QSlider, QStatusBar, QGridLayout, QMenuBar, QRadioButton, QSpinBox, QGraphicsOpacityEffect, QFileDialog,
    QMenu, QListWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QTextEdit, QSizePolicy, QToolButton, QShortcut, QCheckBox, QGroupBox  # Added QGroupBox here
)
from PyQt5.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve, QAbstractAnimation, QRect, QCoreApplication
from PyQt5.QtGui import QIcon, QPainter, QColor, QKeySequence, QPalette, QPixmap, QFont
from PyQt5.QtWidgets import QStyledItemDelegate, QStyle
import json
import re
import requests
import time
import subprocess
import os
import traceback
from pathlib import Path
import logging
import platform
import shutil
import webbrowser
import base64

# Try to import psutil (optional dependency for system info logging)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Flexible import for resources_rc (package vs direct import)
try:
    from . import resources_rc  # Try package import first
except ImportError:
    import resources_rc  # Fall back to direct import when running from source

# User-Agent for API requests
USER_AGENT = "TVHplayer/4.0 (https://github.com/mfat/tvhplayer)"

# Global session for all HTTP requests (connection pooling + User-Agent)
session = requests.Session()
session.headers.update({'User-Agent': USER_AGENT})


class Logger:
    def __init__(self, name="TVHplayer"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Create logs directory
        log_dir = Path.home() / '.tvhplayer' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'tvhplayer_{timestamp}.log'

        # File handler with detailed formatting
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)

        # Console handler with simpler formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)

        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Store log file path
        self.log_file = log_file

        # Log system info at startup
        self.log_system_info()

    def log_system_info(self):
        """Log detailed system information"""
        psutil_module = psutil if PSUTIL_AVAILABLE else None

        self.logger.info("=== System Information ===")
        self.logger.info(f"OS: {platform.platform()}")
        self.logger.info(f"Python: {sys.version}")
        self.logger.info(f"CPU: {platform.processor()}")

        if psutil_module:
            self.logger.info(f"Memory: {psutil_module.virtual_memory().total / (1024**3):.2f} GB")
            self.logger.info(f"Disk Space: {psutil_module.disk_usage('/').free / (1024**3):.2f} GB free")

        # Log environment variables
        self.logger.info("=== Environment Variables ===")
        for key, value in os.environ.items():
            if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                self.logger.info(f"{key}=<REDACTED>")
            else:
                self.logger.info(f"{key}={value}")

        self.logger.info("=== Dependencies ===")
        try:
            from PyQt5 import QtCore
            self.logger.info(f"PyQt5 version: {QtCore.QT_VERSION_STR}")
        except (ImportError, AttributeError):
            self.logger.error("PyQt5 not found")

        try:
            import vlc
            self.logger.info(f"python-vlc version: {vlc.__version__}")
        except ImportError:
            self.logger.error("python-vlc not found")

        try:
            import requests
            self.logger.info(f"requests version: {requests.__version__}")
        except ImportError:
            self.logger.error("requests not found")

    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        self.logger.critical(msg)

    def exception(self, msg):
        self.logger.exception(msg)

class DVRStatusDialog(QDialog):
    def __init__(self, server, parent=None):
        super().__init__(parent)
        self.server = server
        self.setWindowTitle("DVR Status")
        self.resize(800, 600)
        self.setup_ui()

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(5000)  # Update every 5 seconds

        # Initial update
        self.update_status()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Upcoming/Current recordings tab
        self.upcoming_table = QTableWidget()
        self.upcoming_table.setColumnCount(5)  # Added one more column for status
        self.upcoming_table.setHorizontalHeaderLabels(['Channel', 'Title', 'Start Time', 'Duration', 'Status'])
        self.upcoming_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabs.addTab(self.upcoming_table, "Upcoming/Current")  # Changed tab title

        # Finished recordings tab
        self.finished_table = QTableWidget()
        self.finished_table.setColumnCount(4)
        self.finished_table.setHorizontalHeaderLabels(['Channel', 'Title', 'Start Time', 'Duration'])
        self.finished_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabs.addTab(self.finished_table, "Finished")

        # Failed recordings tab
        self.failed_table = QTableWidget()
        self.failed_table.setColumnCount(4)
        self.failed_table.setHorizontalHeaderLabels(['Channel', 'Title', 'Start Time', 'Error'])
        self.failed_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabs.addTab(self.failed_table, "Failed")

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def update_status(self):
        try:
            # Create auth if needed
            auth = None
            if self.server.get('username') or self.server.get('password'):
                auth = (self.server.get('username', ''), self.server.get('password', ''))

            # Get DVR entries
            api_url = f'{self.server["url"]}/api/dvr/entry/grid'
            response = session.get(api_url, auth=auth)

            if response.status_code == 200:
                data = response.json()
                entries = data.get('entries', [])
                print(f"Debug: Found {len(entries)} DVR entries")

                # Sort entries by status
                upcoming = []
                finished = []
                failed = []

                for entry in entries:
                    status = entry.get('status', '')  # Don't convert to lowercase yet
                    sched_status = entry.get('sched_status', '').lower()
                    errors = entry.get('errors', 0)
                    error_code = entry.get('errorcode', 0)

                    print(f"\nDebug: Processing entry: {entry.get('disp_title', 'Unknown')}")
                    print(f"  Status: {status}")
                    print(f"  Sched Status: {sched_status}")

                    # Check status (case-sensitive for "Running")
                    if status == "Running":
                        print(f"Debug: Found active recording: {entry.get('disp_title', 'Unknown')}")
                        upcoming.append((entry.get('channelname', 'Unknown'), entry.get('disp_title', 'Unknown'), datetime.fromtimestamp(entry.get('start', 0)), timedelta(seconds=entry.get('duration', 0)), True))
                    elif 'scheduled' in status.lower() or sched_status == 'scheduled':
                        upcoming.append((entry.get('channelname', 'Unknown'), entry.get('disp_title', 'Unknown'), datetime.fromtimestamp(entry.get('start', 0)), timedelta(seconds=entry.get('duration', 0)), False))
                    elif 'completed' in status.lower() or status.lower() == 'finished':
                        finished.append((entry.get('channelname', 'Unknown'), entry.get('disp_title', 'Unknown'), datetime.fromtimestamp(entry.get('start', 0)), timedelta(seconds=entry.get('duration', 0))))
                    elif ('failed' in status.lower() or 'invalid' in status.lower() or
                          'error' in status.lower() or errors > 0 or error_code != 0):
                        error_msg = entry.get('error', '')
                        if not error_msg and errors > 0:
                            error_msg = f"Recording failed with {errors} errors"
                        if not error_msg and error_code != 0:
                            error_msg = f"Error code: {error_code}"
                        if not error_msg:
                            error_msg = "Unknown error"
                        failed.append((entry.get('channelname', 'Unknown'), entry.get('disp_title', 'Unknown'), datetime.fromtimestamp(entry.get('start', 0)), error_msg))
                        print(f"Debug: Added to failed: {entry.get('disp_title', 'Unknown')} (Error: {error_msg})")
                    else:
                        print(f"Debug: Unhandled status: {status} for entry: {entry.get('disp_title', 'Unknown')}")

                print(f"\nDebug: Sorted entries - Upcoming: {len(upcoming)}, "
                      f"Finished: {len(finished)}, Failed: {len(failed)}")

                # Sort upcoming recordings by start time
                upcoming.sort(key=lambda x: x[2])  # Sort by start_time

                # Update tables
                self.upcoming_table.setRowCount(len(upcoming))
                for i, (channel, title, start, duration, is_recording) in enumerate(upcoming):
                    self.upcoming_table.setItem(i, 0, QTableWidgetItem(channel))
                    self.upcoming_table.setItem(i, 1, QTableWidgetItem(title))
                    self.upcoming_table.setItem(i, 2, QTableWidgetItem(start.strftime('%Y-%m-%d %H:%M')))
                    self.upcoming_table.setItem(i, 3, QTableWidgetItem(str(duration)))

                    # Add status column
                    status = "Recording" if is_recording else entry.get('sched_status', 'scheduled').capitalize()
                    self.upcoming_table.setItem(i, 4, QTableWidgetItem(status))

                    # Highlight currently recording entries
                    if is_recording:
                        for col in range(5):  # Update range to include new column
                            self.upcoming_table.item(i, col).setBackground(Qt.green)

                # Sort finished recordings by start time (most recent first)
                finished.sort(key=lambda x: x[2], reverse=True)

                self.finished_table.setRowCount(len(finished))
                for i, (channel, title, start, duration) in enumerate(finished):
                    self.finished_table.setItem(i, 0, QTableWidgetItem(channel))
                    self.finished_table.setItem(i, 1, QTableWidgetItem(title))
                    self.finished_table.setItem(i, 2, QTableWidgetItem(start.strftime('%Y-%m-%d %H:%M')))
                    self.finished_table.setItem(i, 3, QTableWidgetItem(str(duration)))

                # Sort failed recordings by start time (most recent first)
                failed.sort(key=lambda x: x[2], reverse=True)

                self.failed_table.setRowCount(len(failed))
                for i, (channel, title, start, error) in enumerate(failed):
                    self.failed_table.setItem(i, 0, QTableWidgetItem(channel))
                    self.failed_table.setItem(i, 1, QTableWidgetItem(title))
                    self.failed_table.setItem(i, 2, QTableWidgetItem(start.strftime('%Y-%m-%d %H:%M')))
                    self.failed_table.setItem(i, 3, QTableWidgetItem(error))
                    # Highlight failed entries in red
                    for col in range(4):
                        self.failed_table.item(i, col).setBackground(Qt.red)

            else:
                print(f"Debug: Failed to fetch DVR entries. Status code: {response.status_code}")

        except Exception as e:
            print(f"Debug: Error updating DVR status: {str(e)}")
            print(f"Debug: Traceback: {traceback.format_exc()}")

    def closeEvent(self, event):
        self.update_timer.stop()
        super().closeEvent(event)

class RecordingDurationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recording Duration")
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Quick duration buttons
        quick_duration_layout = QHBoxLayout()

        btn_30min = QPushButton("30 minutes")
        btn_1hr = QPushButton("1 hour")
        btn_2hr = QPushButton("2 hours")
        btn_4hr = QPushButton("4 hours")

        btn_30min.clicked.connect(lambda: self.set_duration(0, 30))
        btn_1hr.clicked.connect(lambda: self.set_duration(1, 0))
        btn_2hr.clicked.connect(lambda: self.set_duration(2, 0))
        btn_4hr.clicked.connect(lambda: self.set_duration(4, 0))

        quick_duration_layout.addWidget(btn_30min)
        quick_duration_layout.addWidget(btn_1hr)
        quick_duration_layout.addWidget(btn_2hr)
        quick_duration_layout.addWidget(btn_4hr)

        layout.addLayout(quick_duration_layout)

        # Duration spinboxes
        duration_layout = QHBoxLayout()

        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(0, 24)
        self.hours_spin.setSuffix(" hours")

        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 59)
        self.minutes_spin.setSuffix(" minutes")

        duration_layout.addWidget(self.hours_spin)
        duration_layout.addWidget(self.minutes_spin)

        layout.addWidget(QLabel("Set custome recording duration:"))
        layout.addLayout(duration_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_duration(self, hours, minutes):
        self.hours_spin.setValue(hours)
        self.minutes_spin.setValue(minutes)
    def get_duration(self):
        """Return duration in seconds"""
        hours = self.hours_spin.value()
        minutes = self.minutes_spin.value()
        return (hours * 3600) + (minutes * 60)

class ServerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Management")
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Server list
        self.server_list = QListWidget()
        layout.addWidget(QLabel("Configured Servers:"))
        layout.addWidget(self.server_list)

        # Connect double-click signal
        self.server_list.itemDoubleClicked.connect(self.edit_server)

        # Buttons
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Server")
        edit_btn = QPushButton("Edit Server")
        remove_btn = QPushButton("Remove Server")

        add_btn.clicked.connect(self.add_server)
        edit_btn.clicked.connect(self.edit_server)
        remove_btn.clicked.connect(self.remove_server)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(remove_btn)
        layout.addLayout(btn_layout)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def load_servers(self, servers):
        self.servers = servers
        self.server_list.clear()
        for server in self.servers:
            self.server_list.addItem(server['name'])

    def add_server(self):
        print("Debug: Opening add server dialog")
        dialog = ServerConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            server = dialog.get_server_config()
            print(f"Debug: Adding new server: {server['name']}")
            self.servers.append(server)
            self.server_list.addItem(server['name'])

    def edit_server(self):
        current_row = self.server_list.currentRow()
        if current_row >= 0:
            print(f"Debug: Editing server at index {current_row}")
            dialog = ServerConfigDialog(self)
            dialog.set_server_config(self.servers[current_row])
            if dialog.exec_() == QDialog.Accepted:
                self.servers[current_row] = dialog.get_server_config()
                print(f"Debug: Updated server: {self.servers[current_row]['name']}")
                self.server_list.item(current_row).setText(self.servers[current_row]['name'])

    def remove_server(self):
        current_row = self.server_list.currentRow()
        if current_row >= 0:
            server_name = self.servers[current_row]['name']
            print(f"Debug: Removing server: {server_name}")
            self.servers.pop(current_row)
            self.server_list.takeItem(current_row)
        else:
            print("Debug: No server selected for removal")

class ServerConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Configuration")
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.url_input = QLineEdit()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        # Style placeholder text
        placeholder_color = QColor(100, 100, 100)  # Dark gray color
        palette = self.palette()
        palette.setColor(QPalette.PlaceholderText, placeholder_color)
        self.setPalette(palette)

        # Apply placeholder text
        layout.addRow("Name:", self.name_input)
        self.name_input.setPlaceholderText("My Server")
        layout.addRow("Server address:", self.url_input)
        self.url_input.setPlaceholderText("http://127.0.0.1:9981")
        layout.addRow("Username:", self.username_input)
        self.username_input.setPlaceholderText("Optional")
        layout.addRow("Password:", self.password_input)
        self.password_input.setPlaceholderText("Optional")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_server_config(self):
        return {
            'name': self.name_input.text(),
            'url': self.url_input.text(),
            'username': self.username_input.text(),
            'password': self.password_input.text()
        }

    def set_server_config(self, config):
        self.name_input.setText(config.get('name', ''))
        self.url_input.setText(config.get('url', ''))
        self.username_input.setText(config.get('username', ''))
        self.password_input.setText(config.get('password', ''))

    def validate_url(self, url):
        """Validate server URL format"""
        if not url.startswith('http://') and not url.startswith('https://'):
            return False, "URL must start with http:// or https://"

        # Remove http:// or https:// for validation
        if url.startswith('http://'):
            url = url[7:]
        else:  # https://
            url = url[8:]

        # Split URL into host:port and path parts
        url_parts = url.split('/', 1)
        host_port = url_parts[0]

        # Split host and port
        if ':' in host_port:
            host, port = host_port.split(':')
            # Validate port
            try:
                port = int(port)
                if port < 1 or port > 65535:
                    return False, "Port must be between 1 and 65535"
            except ValueError:
                return False, "Invalid port number"
        else:
            host = host_port

        # Validate IP address format if it looks like an IP
        if all(c.isdigit() or c == '.' for c in host):
            parts = host.split('.')
            if len(parts) != 4:
                return False, "Invalid IP address format"
            for part in parts:
                try:
                    num = int(part)
                    if num < 0 or num > 255:
                        return False, "IP numbers must be between 0 and 255"
                except ValueError:
                    return False, "Invalid IP address format"

        return True, ""

    def accept(self):
        print("Debug: Validating server configuration")
        config = self.get_server_config()
        print(f"Debug: Server config: {config['name']} @ {config['url']}")

        if not config['name']:
            QMessageBox.warning(self, "Invalid Configuration",
                              "Please provide a server name")
            return

        if not config['url']:
            QMessageBox.warning(self, "Invalid Configuration",
                              "Please provide a server URL")
            return

        # Validate URL format
        is_valid, error_msg = self.validate_url(config['url'])
        if not is_valid:
            QMessageBox.warning(self, "Invalid Configuration",
                              f"Invalid server URL: {error_msg}")
            return

        super().accept()
class ConnectionErrorDialog(QDialog):
    def __init__(self, server_name, error_msg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connection Error")
        self.setup_ui(server_name, error_msg)

    def setup_ui(self, server_name, error_msg):
        layout = QVBoxLayout(self)

        # Error icon and message
        message_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(QMessageBox.standardIcon(QMessageBox.Critical))
        message_layout.addWidget(icon_label)

        error_text = QLabel(
            f"Failed to connect to server: {server_name}\n"
            f"Error: {error_msg}\n\n"
            "Would you like to retry the connection?"
        )
        error_text.setWordWrap(True)
        message_layout.addWidget(error_text)
        layout.addLayout(message_layout)

        # Buttons
        button_layout = QHBoxLayout()
        retry_btn = QPushButton("Retry")
        abort_btn = QPushButton("Abort")

        retry_btn.clicked.connect(self.accept)
        abort_btn.clicked.connect(self.reject)

        button_layout.addWidget(retry_btn)
        button_layout.addWidget(abort_btn)
        layout.addLayout(button_layout)

class ServerStatusDialog(QDialog):
    def __init__(self, server, parent=None):
        super().__init__(parent)
        self.server = server
        self.parent = parent
        self.setWindowTitle("Server Status")
        self.resize(800, 600)
        self.setup_ui()

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(5000)  # Update every 5 seconds

        # Initial update
        self.update_status()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Active streams/subscriptions tab
        self.subscriptions_table = QTableWidget()
        self.subscriptions_table.setColumnCount(5)
        self.subscriptions_table.setHorizontalHeaderLabels([
            'Channel/Peer',
            'User',
            'Start Time',
            'Duration',
            'Type/Status'
        ])
        self.subscriptions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabs.addTab(self.subscriptions_table, "Active Streams")

        # Signal Status tab (new)
        self.signal_table = QTableWidget()
        self.signal_table.setColumnCount(5)
        self.signal_table.setHorizontalHeaderLabels([
            'Input',
            'Signal Strength',
            'SNR',
            'Stream',
            'Weight'
        ])
        self.signal_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabs.addTab(self.signal_table, "Signal Status")

        # Server info tab
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.tabs.addTab(self.info_text, "Server Info")

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def update_status(self):
        try:
            auth = None
            if self.server.get('username') or self.server.get('password'):
                auth = (self.server.get('username', ''), self.server.get('password', ''))

            # 1. Update Server Info Tab
            server_info = f"Server Information:\n\n"
            server_info += f"Name: {self.server.get('name', 'Unknown')}\n"
            server_info += f"URL: {self.server.get('url', 'Unknown')}\n"

            # Get server version and capabilities
            version_url = f"{self.server['url']}/api/serverinfo"
            try:
                version_response = session.get(version_url, auth=auth)
                if version_response.status_code == 200:
                    server_data = version_response.json()
                    server_info += f"\nServer Version: {server_data.get('sw_version', 'Unknown')}\n"
                    server_info += f"API Version: {server_data.get('api_version', 'Unknown')}\n"
                    server_info += f"Server Name: {server_data.get('server_name', 'Unknown')}\n"

                    if 'capabilities' in server_data:
                        server_info += "\nCapabilities:\n"
                        for cap in server_data['capabilities']:
                            server_info += f"- {cap}\n"
            except Exception as e:
                server_info += f"\nError fetching server info: {str(e)}\n"

            self.info_text.setText(server_info)

            # 2. Update Signal Status Tab
            inputs_url = f"{self.server['url']}/api/status/inputs"
            try:
                inputs_response = session.get(inputs_url, auth=auth)

                if inputs_response.status_code == 200:
                    inputs = inputs_response.json().get('entries', [])

                    # Set up table with double the rows (signal and SNR on separate rows)
                    self.signal_table.setRowCount(len(inputs) * 2)

                    for i, input in enumerate(inputs):
                        # Base row for this input (multiply by 2 since we're using 2 rows per input)
                        base_row = i * 2

                        # Input name spans both rows
                        input_item = QTableWidgetItem(str(input.get('input', 'Unknown')))
                        self.signal_table.setItem(base_row, 0, input_item)
                        self.signal_table.setSpan(base_row, 0, 2, 1)  # Span 2 rows

                        # Signal row
                        signal = input.get('signal')
                        signal_scale = input.get('signal_scale', 0)
                        if signal is not None and signal_scale > 0:
                            if signal_scale == 1:  # Relative (65535 = 100%)
                                signal_value = f"{(signal * 100 / 65535):.1f}%"
                            elif signal_scale == 2:  # Absolute (1000 = 1dB)
                                signal_value = f"{(signal / 1000):.1f} dB"
                            else:
                                signal_value = "N/A"
                        else:
                            signal_value = "N/A"

                        signal_item = QTableWidgetItem(signal_value)
                        self.signal_table.setItem(base_row, 1, signal_item)
                        self.signal_table.setItem(base_row, 2, QTableWidgetItem("Signal"))

                        # SNR row
                        snr = input.get('snr')
                        snr_scale = input.get('snr_scale', 0)
                        if snr is not None and snr_scale > 0:
                            if snr_scale == 1:  # Relative (65535 = 100%)
                                snr_value = f"{(snr * 100 / 65535):.1f}%"
                            elif snr_scale == 2:  # Absolute (1000 = 1dB)
                                snr_value = f"{(snr / 1000):.1f} dB"
                            else:
                                snr_value = "N/A"
                        else:
                            snr_value = "N/A"

                        snr_item = QTableWidgetItem(snr_value)
                        self.signal_table.setItem(base_row + 1, 1, snr_item)
                        self.signal_table.setItem(base_row + 1, 2, QTableWidgetItem("SNR"))

                        # Stream and Weight info (spans both rows)
                        self.signal_table.setItem(base_row, 3, QTableWidgetItem(str(input.get('stream', 'N/A'))))
                        self.signal_table.setItem(base_row, 4, QTableWidgetItem(str(input.get('weight', 'N/A'))))
                        self.signal_table.setSpan(base_row, 3, 2, 1)  # Span 2 rows for stream
                        self.signal_table.setSpan(base_row, 4, 2, 1)  # Span 2 rows for weight

                        # Color coding for signal and SNR
                        self.color_code_cell(signal_item, signal, signal_scale, 'signal')
                        self.color_code_cell(snr_item, snr, snr_scale, 'snr')
            except Exception as e:
                print(f"Debug: Error updating signal status: {str(e)}")

            # 3. Update Active Streams Tab
            connections_url = f"{self.server['url']}/api/status/connections"
            subscriptions_url = f"{self.server['url']}/api/status/subscriptions"

            try:
                # Get both connections and subscriptions
                connections_response = session.get(connections_url, auth=auth)
                subscriptions_response = session.get(subscriptions_url, auth=auth)

                if connections_response.status_code == 200 and subscriptions_response.status_code == 200:
                    connections = connections_response.json().get('entries', [])
                    subscriptions = subscriptions_response.json().get('entries', [])

                    # Calculate total rows needed (connections + subscriptions)
                    total_rows = len(connections) + len(subscriptions)
                    self.subscriptions_table.setRowCount(total_rows)

                    # Add connections
                    row = 0
                    for conn in connections:
                        # Peer (IP address/hostname)
                        peer = conn.get('peer', 'Unknown')
                        self.subscriptions_table.setItem(row, 0, QTableWidgetItem(str(peer)))
                        self.subscriptions_table.setItem(row, 1, QTableWidgetItem(str(conn.get('user', 'N/A'))))

                        # Start time
                        start = datetime.fromtimestamp(conn.get('started', 0)).strftime('%H:%M:%S')
                        self.subscriptions_table.setItem(row, 2, QTableWidgetItem(start))

                        # Duration
                        duration = int(time.time() - conn.get('started', 0))
                        hours = duration // 3600
                        minutes = (duration % 3600) // 60
                        seconds = duration % 60
                        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        self.subscriptions_table.setItem(row, 3, QTableWidgetItem(duration_str))

                        # Type/Status
                        self.subscriptions_table.setItem(row, 4, QTableWidgetItem("Connection"))

                        row += 1

                    # Add subscriptions
                    for sub in subscriptions:
                        # Channel/Service name
                        channel = sub.get('channel', 'Unknown')
                        if isinstance(channel, dict):
                            channel = channel.get('name', 'Unknown')
                        self.subscriptions_table.setItem(row, 0, QTableWidgetItem(str(channel)))
                        self.subscriptions_table.setItem(row, 1, QTableWidgetItem(str(sub.get('username', 'N/A'))))

                        # Start time
                        start = datetime.fromtimestamp(sub.get('start', 0)).strftime('%H:%M:%S')
                        self.subscriptions_table.setItem(row, 2, QTableWidgetItem(start))

                        # Duration
                        duration = int(time.time() - sub.get('start', 0))
                        hours = duration // 3600
                        minutes = (duration % 3600) // 60
                        seconds = duration % 60
                        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        self.subscriptions_table.setItem(row, 3, QTableWidgetItem(duration_str))

                        # Type/Status
                        status = f"Subscription ({sub.get('state', 'Unknown')})"
                        self.subscriptions_table.setItem(row, 4, QTableWidgetItem(status))

                        row += 1

            except Exception as e:
                print(f"Debug: Error fetching connections/subscriptions: {str(e)}")

        except Exception as e:
            print(f"Debug: Error in update_status: {str(e)}")
            print(f"Debug: Traceback: {traceback.format_exc()}")

    def color_code_cell(self, item, value, scale, type='signal'):
        """Helper method to color code signal and SNR values"""
        if value is not None and scale > 0:
            if scale == 1:
                quality = (value * 100 / 65535)
            else:  # scale == 2
                if type == 'signal':
                    quality = min(100, max(0, (value / 1000 + 15) * 6.67))
                else:  # SNR
                    quality = min(100, max(0, (value / 1000 - 10) * 10))

            if quality >= 80:
                item.setBackground(Qt.green)
            elif quality >= 60:
                item.setBackground(Qt.yellow)
            elif quality >= 40:
                item.setBackground(Qt.darkYellow)
            else:
                item.setBackground(Qt.red)

    def closeEvent(self, event):
        self.update_timer.stop()
        super().closeEvent(event)

def natural_sort_key(channel_name):
    """
    Create a sort key for natural/human sorting of channel names.

    Returns tuple: (base_name, number)
    - Extracts number from channel name (e.g., "Channel 1 HD" -> "Channel HD", 1)
    - If no number found, uses -1 to sort before numbered channels

    Examples:
    - "Channel HD" -> ("channel hd", -1) - comes first
    - "Channel 1 HD" -> ("channel hd", 1)
    - "Channel 10 HD" -> ("channel hd", 10)
    """
    # Search for number surrounded by whitespace
    match = re.search(r'\s(\d+)\s', channel_name)

    if match:
        # Number found: remove it to get base name
        base_name = re.sub(r'\s\d+\s', ' ', channel_name)
        number = int(match.group(1))
        return (base_name.lower(), number)
    else:
        # No number: use -1 to sort before numbered variants
        return (channel_name.lower(), -1)

class NaturalSortTableWidgetItem(QTableWidgetItem):
    """Custom QTableWidgetItem that uses natural sorting for comparison"""
    def __lt__(self, other):
        """Override less-than operator to use natural sorting"""
        return natural_sort_key(self.text()) < natural_sort_key(other.text())

class ProgressBarDelegate(QStyledItemDelegate):
    """Custom delegate to draw progress bar in EPG cells"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        """Custom paint method to draw progress bar"""
        # Get data from the cell
        data = index.data(Qt.UserRole)

        if not data or not isinstance(data, dict):
            # No progress data, use default painting
            super().paint(painter, option, index)
            return

        # Extract program info
        title = data.get('title', '')
        start_time = data.get('start', 0)
        stop_time = data.get('stop', 0)

        if not title or not start_time or not stop_time:
            super().paint(painter, option, index)
            return

        # Calculate progress (0.0 to 1.0)
        now = time.time()
        duration = stop_time - start_time
        if duration > 0 and start_time <= now <= stop_time:
            progress = (now - start_time) / duration
        elif now > stop_time:
            progress = 1.0
        else:
            progress = 0.0

        # Format time string
        start_str = datetime.fromtimestamp(start_time).strftime('%H:%M')
        stop_str = datetime.fromtimestamp(stop_time).strftime('%H:%M')
        time_text = f"{start_str}-{stop_str}"

        # Draw background
        painter.save()

        # Fill selection background if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            painter.fillRect(option.rect, option.palette.base())

        # Define areas (adjusted for 60px row height)
        padding = 6
        text_height = 30  # Height for text area (allows 2-line wrapping)
        bar_height = 10
        text_bar_spacing = 6  # Space between text and progress bar

        # Time text area (left aligned)
        time_rect = option.rect.adjusted(padding, padding, -padding, 0)
        time_rect.setWidth(80)
        time_rect.setHeight(text_height)

        # Title text area (starts after time, at x=85) - allows wrapping
        title_rect = option.rect.adjusted(padding + 85, padding, -padding, 0)
        title_rect.setHeight(text_height)

        # Progress bar area (bottom with more spacing)
        bar_rect = option.rect.adjusted(padding, padding + text_height + text_bar_spacing, -padding, -padding)
        bar_rect.setHeight(bar_height)

        # Draw time text with explicit color
        if option.state & QStyle.State_Selected:
            painter.setPen(option.palette.color(QPalette.HighlightedText))
        else:
            painter.setPen(QColor(0, 0, 0))  # Black for better visibility

        font = QFont()
        font.setPointSize(9)  # Increased from 8
        painter.setFont(font)
        painter.drawText(time_rect, Qt.AlignLeft | Qt.AlignVCenter, time_text)

        # Draw title text with same size as time and word wrapping
        font.setPointSize(9)  # Same size as time text
        font.setBold(False)  # Normal text, not bold
        painter.setFont(font)

        # Check if text will wrap by measuring width
        font_metrics = painter.fontMetrics()
        text_width = font_metrics.horizontalAdvance(title)
        available_width = title_rect.width()

        # Use AlignTop if text wraps (multi-line), AlignVCenter if single line
        if text_width > available_width:
            alignment = Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap
        else:
            alignment = Qt.AlignLeft | Qt.AlignVCenter

        painter.drawText(title_rect, alignment, title)

        # Draw progress bar background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(200, 200, 200))
        painter.drawRect(bar_rect)

        # Draw progress bar fill
        if progress > 0:
            fill_rect = bar_rect.adjusted(0, 0, 0, 0)
            fill_rect.setWidth(int(bar_rect.width() * progress))

            # Color based on progress
            if progress < 0.25:
                color = QColor(76, 175, 80)  # Green
            elif progress < 0.75:
                color = QColor(33, 150, 243)  # Blue
            else:
                color = QColor(255, 152, 0)  # Orange

            painter.setBrush(color)
            painter.drawRect(fill_rect)

        painter.restore()

    def sizeHint(self, option, index):
        """Return the size hint for the cell"""
        # Minimum height for text + progress bar
        return QSize(option.rect.width(), 35)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Channel Icon Settings")
        self.setModal(True)
        self.resize(400, 300)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Icon Settings Group
        icon_group = QGroupBox("Channel Icon Size")
        icon_layout = QVBoxLayout()

        # Preset radio buttons (larger sizes, max 100px)
        self.preset_small = QRadioButton("Small (48px)")
        self.preset_medium = QRadioButton("Medium (64px)")
        self.preset_large = QRadioButton("Large (80px)")
        self.preset_xlarge = QRadioButton("Extra Large (100px)")
        self.preset_custom = QRadioButton("Custom")

        # Custom input
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("Icon Size:"))
        self.custom_icon_size = QSpinBox()
        self.custom_icon_size.setRange(24, 128)
        self.custom_icon_size.setSuffix(" px")
        custom_layout.addWidget(self.custom_icon_size)
        custom_layout.addStretch()

        # Add to icon layout
        icon_layout.addWidget(self.preset_small)
        icon_layout.addWidget(self.preset_medium)
        icon_layout.addWidget(self.preset_large)
        icon_layout.addWidget(self.preset_xlarge)
        icon_layout.addWidget(self.preset_custom)
        icon_layout.addLayout(custom_layout)

        icon_group.setLayout(icon_layout)
        layout.addWidget(icon_group)

        # Enable/disable custom inputs based on selection
        self.preset_small.toggled.connect(lambda: self.toggle_custom_inputs(False))
        self.preset_medium.toggled.connect(lambda: self.toggle_custom_inputs(False))
        self.preset_large.toggled.connect(lambda: self.toggle_custom_inputs(False))
        self.preset_xlarge.toggled.connect(lambda: self.toggle_custom_inputs(False))
        self.preset_custom.toggled.connect(lambda: self.toggle_custom_inputs(True))

        # Load current settings
        self.load_current_settings()

        # Buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def toggle_custom_inputs(self, enabled):
        self.custom_icon_size.setEnabled(enabled)

    def load_current_settings(self):
        if not self.parent_window:
            return

        current_size = self.parent_window.config.get('icon_size', 48)

        # Check which preset matches (only icon size)
        if current_size == 48:
            self.preset_small.setChecked(True)
        elif current_size == 64:
            self.preset_medium.setChecked(True)
        elif current_size == 80:
            self.preset_large.setChecked(True)
        elif current_size == 100:
            self.preset_xlarge.setChecked(True)
        else:
            self.preset_custom.setChecked(True)
            self.custom_icon_size.setValue(current_size)

    def get_settings(self):
        """Return selected icon size only"""
        if self.preset_small.isChecked():
            return 48
        elif self.preset_medium.isChecked():
            return 64
        elif self.preset_large.isChecked():
            return 80
        elif self.preset_xlarge.isChecked():
            return 100
        else:  # Custom
            return self.custom_icon_size.value()

class TVHeadendClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setup_paths()

        # Get OS-specific config path using sys.platform
        if sys.platform == 'darwin':  # macOS
            self.config_dir = os.path.join(os.path.expanduser('~/Library/Application Support'), 'TVHplayer')
        elif sys.platform == 'win32':  # Windows
            self.config_dir = os.path.join(os.getenv('APPDATA'), 'TVHplayer')
        else:  # Linux/Unix
            CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
            self.config_dir = os.path.join(CONFIG_HOME, "tvhplayer")

        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)

        # Set config file path
        self.config_file = os.path.join(self.config_dir, 'tvhplayer.conf')
        self.config = self.load_config()

        # Initialize fullscreen state
        # Rest of initialization code...


        # Set window title and geometry from config
        self.setWindowTitle("TVHplayer")
        geometry = self.config.get('window_geometry', {'x': 100, 'y': 100, 'width': 1200, 'height': 700})
        self.setGeometry(
            geometry['x'],
            geometry['y'],
            geometry['width'],
            geometry['height']
        )

        # Initialize servers from config
        self.servers = self.config.get('servers', [])
        print(f"Debug: Loaded {len(self.servers)} servers")

        # Initialize channels list
        self.channels = []

        # Initialize icon cache for channel logos
        self.icon_cache = {}

        # Base cache directory for channel icons (subdirectories created per server)
        self.icon_cache_base_dir = os.path.join(self.config_dir, 'channel_icons')
        os.makedirs(self.icon_cache_base_dir, exist_ok=True)

        self.is_fullscreen = False


        # Add recording indicator variables
        self.recording_indicator_timer = None
        self.recording_indicator_visible = False
        self.is_recording = False
        self.recording_animation = None
        self.opacity_effect = None

        # Timer for debouncing column resize saves
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.save_all_column_widths)
        self.pending_column_resize = None

        # Timer for debouncing splitter position saves
        self.splitter_timer = QTimer()
        self.splitter_timer.setSingleShot(True)
        self.splitter_timer.timeout.connect(self.save_splitter_sizes)
        self.pending_splitter_sizes = None

        # Initialize VLC with basic instance first
        print("Debug: Initializing VLC instance")
        try:
            if getattr(sys, 'frozen', False):
                # If running as compiled executable
                base_path = sys._MEIPASS
                plugin_path = os.path.join(base_path, 'vlc', 'plugins')

                # Set VLC plugin path via environment variable
                os.environ['VLC_PLUGIN_PATH'] = plugin_path

                # On Linux, might also need these
                if sys.platform.startswith('linux'):
                    os.environ['LD_LIBRARY_PATH'] = base_path

                print(f"Debug: VLC plugin path set to: {plugin_path}")

            # Initialize VLC with hardware acceleration parameters
            vlc_args = [
                # Enable hardware decoding
                '--avcodec-hw=any',  # Try any hardware acceleration method
                '--file-caching=1000',  # Increase file caching for smoother playback
                '--network-caching=1000',  # Increase network caching for streaming
                '--no-video-title-show',  # Don't show the video title
                '--no-snapshot-preview',  # Don't show snapshot previews
            ]

            self.instance = vlc.Instance(vlc_args)
            if not self.instance:
                raise RuntimeError("VLC Instance creation returned None")

            print("Debug: VLC instance created successfully with hardware acceleration")

            self.media_player = self.instance.media_player_new()
            if not self.media_player:
                raise RuntimeError("VLC media player creation returned None")

            print("Debug: VLC media player created successfully")

        except Exception as e:
            print(f"Error initializing VLC: {str(e)}")
            raise RuntimeError(f"Failed to initialize VLC: {str(e)}")

        # Then setup UI
        self.setup_ui()

        # Update to use config for last server
        self.server_combo.setCurrentIndex(self.config.get('last_server', 0))

        # Now configure hardware acceleration after UI is set up
        try:
            # Set player window - with proper type conversion
            if sys.platform.startswith('linux'):
                handle = self.video_frame.winId().__int__()
                if handle is not None:
                    self.media_player.set_xwindow(handle)
            elif sys.platform == "win32":
                self.media_player.set_hwnd(self.video_frame.winId().__int__())
            elif sys.platform == "darwin":
                self.media_player.set_nsobject(self.video_frame.winId().__int__())

            # Set hardware decoding to automatic
            if hasattr(self.media_player, 'set_hardware_decoding'):
                self.media_player.set_hardware_decoding(True)
            else:
                # Alternative method for older VLC Python bindings
                self.media_player.video_set_key_input(False)
                self.media_player.video_set_mouse_input(False)

            # Add a timer to check which hardware acceleration method is being used
            # This will check after playback starts
            self.hw_check_timer = QTimer()
            self.hw_check_timer.setSingleShot(True)
            self.hw_check_timer.timeout.connect(self.check_hardware_acceleration)
            self.hw_check_timer.start(5000)  # Check after 5 seconds of playback

            print("Debug: Hardware acceleration configured for VLC")

        except Exception as e:
            print(f"Warning: Could not configure hardware acceleration: {str(e)}")
            print("Continuing without hardware acceleration")

    def setup_paths(self):
        """Setup application paths for resources"""
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle
            self.app_dir = Path(sys._MEIPASS)
        else:
            # Running in development
            self.app_dir = Path(os.path.dirname(os.path.abspath(__file__)))

        # Ensure icons directory exists
        self.icons_dir = self.app_dir / 'icons'
        if not self.icons_dir.exists():
            print(f"Warning: Icons directory not found at {self.icons_dir}")
            # Try looking up one directory (in case we're in src/)
            self.icons_dir = self.app_dir.parent / 'icons'
            if not self.icons_dir.exists():
                # Try system icon directories
                system_icon_dirs = []
                if sys.platform.startswith('linux'):
                    system_icon_dirs = [
                        Path('/usr/share/icons/tvhplayer'),
                        Path('/usr/local/share/icons/tvhplayer'),
                        Path(os.path.expanduser('~/.local/share/icons/tvhplayer'))
                    ]
                elif sys.platform == 'darwin':
                    system_icon_dirs = [
                        Path('/System/Library/Icons'),
                        Path('/Library/Icons'),
                        Path(os.path.expanduser('~/Library/Icons'))
                    ]
                elif sys.platform == 'win32':
                    system_icon_dirs = [
                        Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / 'Icons',
                        Path(os.environ['SYSTEMROOT']) / 'System32' / 'icons'
                    ]

                for dir in system_icon_dirs:
                    if dir.exists():
                        self.icons_dir = dir
                        print(f"Using system icons directory: {self.icons_dir}")
                        break
                else:
                    raise RuntimeError(f"Icons directory not found in {self.app_dir}, parent directory, or system locations")

        print(f"Debug: Using icons directory: {self.icons_dir}")

    def get_icon(self, icon_name):
        """Get icon path and verify it exists"""
        # Always use app_dir/icons path
        icon_path = self.app_dir / 'icons' / icon_name
        if not icon_path.exists():
            print(f"Warning: Icon not found: {icon_path}")
            return None
        return str(icon_path)

    def setup_ui(self):
        """Setup the UI elements"""


        # Create buttons with icons
        self.play_btn = QAction(QIcon(self.get_icon('play.svg')), 'Play', self)
        self.stop_btn = QAction(QIcon(self.get_icon('stop.svg')), 'Stop', self)
        self.record_btn = QAction(QIcon(self.get_icon('record.svg')), 'Record', self)
        self.stop_record_btn = QAction(QIcon(self.get_icon('stoprec.svg')), 'Stop Recording', self)



        # Create menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        view_menu = menubar.addMenu("View")
        settings_menu = menubar.addMenu("Settings")
        help_menu = menubar.addMenu("Help")

        # Add User Guide action to Help menu
        user_guide_action = QAction("User Guide", self)
        user_guide_action.triggered.connect(self.show_user_guide)
        help_menu.addAction(user_guide_action)

        # Add About action to Help menu
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)



        # Add Fullscreen action to View menu
        fullscreen_action = QAction("Fullscreen", self)
        fullscreen_action.setShortcut("F")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        # Add Channel Icons action to Settings menu
        channel_icons_action = QAction("Channel Icons", self)
        channel_icons_action.triggered.connect(self.show_settings)
        settings_menu.addAction(channel_icons_action)

        # Add Clear Icon Cache action to Settings menu
        clear_cache_action = QAction("Clear Icon Cache", self)
        clear_cache_action.triggered.connect(self.clear_icon_cache)
        settings_menu.addAction(clear_cache_action)

        # Add separator before reset option
        settings_menu.addSeparator()

        # Add Reset to Defaults action to Settings menu
        reset_action = QAction("Reset to Factory Defaults", self)
        reset_action.triggered.connect(self.reset_to_defaults)
        settings_menu.addAction(reset_action)

        # Create actions
        exit_action = QAction("Exit", self)
        if sys.platform == "darwin":  # macOS
            exit_action.setShortcut("Cmd+Q")
        else:  # Windows/Linux
            exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Create splitter for resizable panes
        self.splitter = QSplitter(Qt.Horizontal)

        # Left pane
        left_pane = QFrame()
        left_pane.setFrameStyle(QFrame.Panel | QFrame.Raised)
        left_layout = QVBoxLayout(left_pane)

        # Server selection with add/remove buttons
        server_layout = QHBoxLayout()
        self.server_combo = QComboBox()
        self.server_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for server in self.servers:
            self.server_combo.addItem(server['name'])

        # Connect server combo box change signal
        self.server_combo.currentIndexChanged.connect(self.on_server_changed)

        manage_servers_btn = QToolButton()
        manage_servers_btn.clicked.connect(self.manage_servers)

        server_layout.addWidget(QLabel("Server:"))
        server_layout.addWidget(self.server_combo)
        manage_servers_btn.setText("⚙️")  # Unicode settings icon
        manage_servers_btn.setStyleSheet("font-size: 18px;")  # Make icon bigger
        manage_servers_btn.setToolTip("Manage servers")
        server_layout.addWidget(manage_servers_btn)
        left_layout.addLayout(server_layout)



        # Channel list with 5 columns
        self.channel_list = QTableWidget()
        self.channel_list.setColumnCount(5)
        self.channel_list.setHorizontalHeaderLabels(['#', 'Icon', 'Channel', 'Current Program', 'Next Program'])

        # Configure column resize modes
        self.channel_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Channel number

        # Icon column - fixed width based on icon size
        self.channel_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        icon_size = self.config.get('icon_size', 48)
        self.channel_list.setColumnWidth(1, icon_size + 10)

        # Channel name - user resizable
        self.channel_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        channel_column_width = self.config.get('channel_column_width', 80)  # Minimal width for channel names
        self.channel_list.setColumnWidth(2, channel_column_width)

        # EPG columns - both Current Program and Next Program user resizable
        self.channel_list.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)  # Current program - user resizable
        current_program_width = self.config.get('current_program_width', 300)  # Default 300px, or saved value
        self.channel_list.setColumnWidth(3, current_program_width)

        self.channel_list.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive)  # Next program - user resizable
        next_program_width = self.config.get('next_program_width', 300)  # Default 300px, or saved value
        self.channel_list.setColumnWidth(4, next_program_width)

        # Set custom delegate for progress bars in column 3 (Current Program)
        self.progress_delegate = ProgressBarDelegate(self.channel_list)
        self.channel_list.setItemDelegateForColumn(3, self.progress_delegate)

        # Track last valid sort for blocking sorts on certain columns
        self.last_valid_sort_column = 0
        self.last_valid_sort_order = Qt.AscendingOrder

        # Enable word wrap for Next Program column (column 4) for two-line display
        self.channel_list.setWordWrap(True)

        self.channel_list.verticalHeader().setVisible(False)

        # Set row height for better visibility (icon + text)
        self.channel_list.verticalHeader().setDefaultSectionSize(60)

        # Set icon size for the table (crucial for icon display!)
        icon_size = self.config.get('icon_size', 48)
        self.channel_list.setIconSize(QSize(icon_size, icon_size))

        self.channel_list.setSelectionBehavior(QTableWidget.SelectRows)
        self.channel_list.setSelectionMode(QTableWidget.SingleSelection)
        self.channel_list.setSortingEnabled(True)

        # Hide horizontal scrollbar - user should resize splitter instead
        self.channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.channel_list.setEditTriggers(QTableWidget.NoEditTriggers)

        # Show sort indicator on header
        self.channel_list.horizontalHeader().setSortIndicatorShown(True)

        # Enable header context menu for column visibility
        self.channel_list.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.channel_list.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)

        # Save column widths when user manually resizes
        self.channel_list.horizontalHeader().sectionResized.connect(self.save_column_width)

        # Handle sort changes (block certain columns, save valid sorts)
        self.channel_list.horizontalHeader().sortIndicatorChanged.connect(self.handle_sort_changed)

        # Connect double-click to play
        self.channel_list.itemDoubleClicked.connect(self.play_channel_from_table)

        # Connect context menu
        self.channel_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.channel_list.customContextMenuRequested.connect(self.show_channel_context_menu)

        left_layout.addWidget(QLabel(""))
        left_layout.addWidget(self.channel_list)

        # Right pane
        right_pane = QFrame()
        right_pane.setFrameStyle(QFrame.Panel | QFrame.Raised)
        right_layout = QVBoxLayout(right_pane)
        right_layout.setObjectName("right_layout")

        # VLC player widget
        self.video_frame = QWidget()
        self.video_frame.setStyleSheet("""
            background-color: black;
            background-image: url(icons/playerbg.svg);
            background-position: center;
            background-repeat: no-repeat;
        """)

        right_layout.addWidget(self.video_frame)

        # Player controls
        controls_layout = QHBoxLayout()
       # Create frame for play/stop buttons
        playback_frame = QFrame()
        playback_frame.setStyleSheet(".QFrame{border: 1px solid grey; border-radius: 8px;}");
        playback_frame.setWindowTitle("Playback")
        playback_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        playback_frame.setLineWidth(5)  # Make frame thicker
        playback_layout = QHBoxLayout(playback_frame)

        # Play button
        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(48, 48)
        self.play_btn.setIcon(QIcon(f"{self.icons_dir}/play.svg"))
        self.play_btn.setIconSize(QSize(48, 48))
        self.play_btn.setStyleSheet("QPushButton { border-radius: 24px; }")
        self.play_btn.clicked.connect(lambda: self.play_channel_by_data(
            self.channel_list.currentItem().data(Qt.UserRole) if self.channel_list.currentItem()
            else self.channel_list.item(0, 2).data(Qt.UserRole) if self.channel_list.rowCount() > 0
            else None))
        self.play_btn.setToolTip("Play selected channel")
        playback_layout.addWidget(self.play_btn)

        # Stop button
        self.stop_btn = QPushButton()
        self.stop_btn.setFixedSize(48, 48)
        self.stop_btn.setIcon(QIcon(f"{self.icons_dir}/stop.svg"))
        self.stop_btn.setIconSize(QSize(48, 48))
        self.stop_btn.setStyleSheet("QPushButton { border-radius: 24px; }")
        self.stop_btn.clicked.connect(self.media_player.stop)
        self.stop_btn.setToolTip("Stop playback")
        playback_layout.addWidget(self.stop_btn)

        controls_layout.addWidget(playback_frame)

        # Create frame for record buttons
        record_frame = QFrame()
        record_frame.setStyleSheet(".QFrame{border: 1px solid grey; border-radius: 8px;}");
        record_frame.setWindowTitle("Recording")
        record_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        record_frame.setLineWidth(5)  # Make frame thicker
        record_layout = QHBoxLayout(record_frame)

        # Start Record button
        self.start_record_btn = QPushButton()
        self.start_record_btn.setFixedSize(48, 48)  # Remove extra parenthesis
        self.start_record_btn.setIcon(QIcon(f"{self.icons_dir}/record.svg"))
        self.start_record_btn.setIconSize(QSize(48, 48))
        self.start_record_btn.setStyleSheet("QPushButton { border-radius: 24px; }")
        self.start_record_btn.setToolTip("Start Recording")
        self.start_record_btn.clicked.connect(self.start_recording)
        record_layout.addWidget(self.start_record_btn)

        # Stop Record button
        self.stop_record_btn = QPushButton()
        self.stop_record_btn.setFixedSize(48, 48)  # Remove extra parenthesis
        self.stop_record_btn.setIcon(QIcon(f"{self.icons_dir}/stoprec.svg"))
        self.stop_record_btn.setIconSize(QSize(48, 48))
        self.stop_record_btn.setStyleSheet("QPushButton { border-radius: 24px; }")
        self.stop_record_btn.setToolTip("Stop Recording")
        self.stop_record_btn.clicked.connect(self.stop_recording)
        record_layout.addWidget(self.stop_record_btn)

        controls_layout.addWidget(record_frame)

        # Create frame for local record buttons
        local_record_frame = QFrame()
        local_record_frame.setStyleSheet(".QFrame{border: 1px solid grey; border-radius: 8px;}");
        local_record_frame.setWindowTitle("Local Recording")
        local_record_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        local_record_layout = QHBoxLayout(local_record_frame)

        # Start Local Record button
        self.start_local_record_btn = QPushButton()
        self.start_local_record_btn.setFixedSize(48, 48)  # Remove extra parenthesis
        self.start_local_record_btn.setIcon(QIcon(f"{self.icons_dir}/reclocal.svg"))
        self.start_local_record_btn.setIconSize(QSize(48, 48))
        self.start_local_record_btn.setStyleSheet("QPushButton { border-radius: 24px; }")
        self.start_local_record_btn.setToolTip("Start Local Recording")
        self.start_local_record_btn.clicked.connect(
            lambda: self.start_local_recording(
                self.channel_list.currentItem().text() if self.channel_list.currentItem() else None
            ))
        local_record_layout.addWidget(self.start_local_record_btn)

        # Stop Local Record button
        self.stop_local_record_btn = QPushButton()
        self.stop_local_record_btn.setFixedSize(48, 48)  # Remove extra parenthesis
        self.stop_local_record_btn.setIcon(QIcon(f"{self.icons_dir}/stopreclocal.svg"))
        self.stop_local_record_btn.setIconSize(QSize(48, 48))
        self.stop_local_record_btn.setStyleSheet("QPushButton { border-radius: 24px; }")
        self.stop_local_record_btn.setToolTip("Stop Local Recording")
        self.stop_local_record_btn.clicked.connect(self.stop_local_recording)
        local_record_layout.addWidget(self.stop_local_record_btn)

        controls_layout.addWidget(local_record_frame)



        # Volume slider and mute button
        # Mute button with icons for different states



        self.mute_btn = QPushButton()
        self.mute_btn.setIcon(QIcon(f"{self.icons_dir}/unmute.svg"))
        self.mute_btn.setIconSize(QSize(32, 32))
        self.mute_btn.setFixedSize(32, 32)  # Remove extra parenthesis
        self.mute_btn.setCheckable(True)  # Make the button checkable
        self.mute_btn.clicked.connect(self.toggle_mute)
        self.mute_btn.setToolTip("Toggle Mute")
        self.mute_btn.setStyleSheet("QPushButton { border: none; }")


        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(150)  # Set fixed width to make slider less wide
        self.volume_slider.valueChanged.connect(self.on_volume_changed)

        # Fullscreen button with icon
        fullscreen_btn = QPushButton()
        fullscreen_btn.setIcon(QIcon(f"{self.icons_dir}/fullscreen.svg"))
        fullscreen_btn.setIconSize(QSize(32, 32))
        fullscreen_btn.setFixedSize(32, 32)  # Remove extra parenthesis
        fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        fullscreen_btn.setToolTip("Toggle Fullscreen")
        fullscreen_btn.setStyleSheet("QPushButton { border: none; }")

        controls_layout.addStretch()  # Add stretch to push widgets to the right
        controls_layout.addWidget(self.mute_btn)
        controls_layout.addWidget(self.volume_slider)
        controls_layout.addWidget(fullscreen_btn)
        right_layout.addLayout(controls_layout)

        # Add panes to splitter instead of layout
        self.splitter.addWidget(left_pane)
        self.splitter.addWidget(right_pane)

        # Restore saved splitter sizes or use defaults
        saved_sizes = self.config.get('splitter_sizes', [300, 900])
        self.splitter.setSizes(saved_sizes)

        # Save splitter position when user moves it
        self.splitter.splitterMoved.connect(self.save_splitter_position)

        # Add splitter to main layout
        layout.addWidget(self.splitter)


        # Buttons removed

        # Status bar setup
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        # Create a container widget for status bar items
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(10)  # Space between indicator and text

        # Create recording indicator
        self.recording_indicator = QLabel()
        self.recording_indicator.setFixedSize(16, 16)
        self.recording_indicator.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 0, 0, 0.8);
                min-width: 16px;
                max-width: 16px;
                min-height: 16px;
                max-height: 16px;
                border-radius: 8px;
                margin: 2px;
            }
            QLabel[recording="false"] {
                background-color: transparent;
            }
        """)
        self.recording_indicator.setProperty("recording", False)

        # Create status message label
        self.status_label = QLabel("Ready")

        # Add widgets to horizontal layout
        status_layout.addWidget(self.recording_indicator)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()  # This pushes everything to the left

        # Add the container to the status bar
        self.statusbar.addWidget(status_container)

        # Override showMessage to update our custom label
        def custom_show_message(message, timeout=0):
            self.status_label.setText(message)
        self.statusbar.showMessage = custom_show_message

        # Load column visibility settings from config
        column_visibility = self.config.get('column_visibility', {})
        if column_visibility:
            # Use saved settings
            for col_idx_str, visible in column_visibility.items():
                col_idx = int(col_idx_str)
                self.channel_list.setColumnHidden(col_idx, not visible)
        else:
            # Default: hide icon column (column 1) for better performance
            self.channel_list.setColumnHidden(1, True)

        # Initialize
        self.fetch_channels()

        # Connect channel list double click to play

        # Add event filter to video frame for double-click
        self.video_frame.installEventFilter(self)

        # Add key event filter to main window
        self.installEventFilter(self)

        # Add Server Status to View menu
        server_status_action = view_menu.addAction("Server Status")
        server_status_action.triggered.connect(self.show_server_status)

        # Add DVR Status to View menu
        dvr_status_action = view_menu.addAction("DVR Status")
        dvr_status_action.triggered.connect(self.show_dvr_status)

        # Add search box before styling it
        search_layout = QHBoxLayout()
        search_icon = QLabel("🔍")  # Unicode search icon
        self.search_box = QLineEdit()

        # Style placeholder text
        placeholder_color = QColor(100, 100, 100)  # Dark gray color
        search_palette = self.search_box.palette()
        search_palette.setColor(QPalette.PlaceholderText, placeholder_color)
        self.search_box.setPalette(search_palette)

        self.search_box.setPlaceholderText("Press S to search channels...")
        self.search_box.textChanged.connect(self.filter_channels)
        self.search_box.setClearButtonEnabled(True)  # Add clear button inside search box

        # Add Ctrl+F shortcut for search box
        search_shortcut = QShortcut(QKeySequence(Qt.Key_S, Qt.NoModifier), self)
        search_shortcut.activated.connect(self.search_box.setFocus)

        # Create custom clear button action
        clear_action = QAction("⌫", self.search_box)
        self.search_box.addAction(clear_action, QLineEdit.TrailingPosition)

        search_layout.addWidget(search_icon)
        search_layout.addWidget(self.search_box)
        left_layout.addLayout(search_layout)  # Add to left pane layout

        # Now style the search box with custom clear button styling


        # Add margins to search layout
        search_layout.setContentsMargins(0, 5, 0, 5)
        search_layout.setSpacing(5)

    def fetch_channels(self):
        """Fetch channel list from current TVHeadend server"""
        try:
            if not self.servers:
                print("Debug: No servers configured")
                self.statusbar.showMessage("No servers configured")
                return

            server = self.servers[self.server_combo.currentIndex()]
            print(f"Debug: Fetching channels from server: {server['url']}")

            # Initialize verification list
            channel_verification = []

            # Update status bar
            self.statusbar.showMessage("Connecting to server...")

            # Clean and format the URL properly
            url = server['url']
            if url.startswith('https://') or url.startswith('http://'):
                base_url = url
            else:
                base_url = f"http://{url}"

            api_url = f'{base_url}/api/channel/grid?limit=10000'
            print(f"Debug: Making request to: {api_url}")

            # Create auth tuple if credentials exist
            auth = None
            if server.get('username') or server.get('password'):
                auth = (server.get('username', ''), server.get('password', ''))
                print(f"Debug: Using authentication with username: {server.get('username', '')}")

            # Add timeout parameter (10 seconds)
            response = session.get(api_url, auth=auth, timeout=10)

            # Check for HTTP errors before parsing JSON
            if response.status_code == 401:
                print("Debug: Authentication failed (401 Unauthorized)")
                self.statusbar.showMessage("Authentication failed - check username/password")
                QMessageBox.warning(
                    self,
                    "Authentication Failed",
                    f"Failed to authenticate with server '{server['name']}'.\n\n"
                    "Please check your username and password in the server configuration.\n\n"
                    "Note: TVHeadend requires both Digest and Plain authentication to be enabled."
                )
                return

            # Raise exception for other HTTP errors
            response.raise_for_status()

            channels = response.json()['entries']
            print(f"Debug: Found {len(channels)} channels")

            # Disable sorting while adding items (prevents Qt from auto-sorting during insert)
            self.channel_list.setSortingEnabled(False)

            # Clear existing items
            self.channel_list.setRowCount(0)

            # Create a list to store channel data for sorting
            channel_data = []

            # Process all channels first
            for channel in channels:
                try:
                    channel_name = channel.get('name', 'Unknown Channel')
                    channel_number = channel.get('number', 0)  # Use 0 as default for unnumbered channels

                    # Store channel data for sorting
                    channel_data.append({
                        'number': channel_number,
                        'name': channel_name,
                        'data': channel
                    })

                except Exception as e:
                    print(f"Debug: Error processing channel {channel.get('name', 'Unknown')}: {str(e)}")
                    continue

            # Sort channels by number, then name (natural/human sorting for names)
            channel_data.sort(key=lambda x: (x['number'] or float('inf'), natural_sort_key(x['name'])))

            # Now add sorted channels to the table
            for idx, channel in enumerate(channel_data):
                try:
                    print(f"Debug: Adding channel {idx + 1}/{len(channel_data)}: {channel['name']}")

                    # Create all items first, before inserting row
                    # Column 0: Channel number
                    number_item = QTableWidgetItem()
                    number_item.setData(Qt.DisplayRole, channel['number'])

                    # Column 1: Icon only
                    icon_item = QTableWidgetItem()
                    icon_item.setData(Qt.UserRole, channel['data'])  # Store channel data on icon item too

                    # Column 2: Channel name (use NaturalSortTableWidgetItem for natural sorting)
                    name_item = NaturalSortTableWidgetItem(channel['name'])
                    name_item.setData(Qt.UserRole, channel['data'])  # Store channel data

                    # Column 3: Current program (will be populated by EPG update with progress)
                    current_item = QTableWidgetItem("")

                    # Column 4: Next program (will be populated by EPG update)
                    next_item = QTableWidgetItem("")

                    # Only insert row if all items were created successfully
                    row = self.channel_list.rowCount()
                    self.channel_list.insertRow(row)

                    # Set all items
                    self.channel_list.setItem(row, 0, number_item)
                    self.channel_list.setItem(row, 1, icon_item)
                    self.channel_list.setItem(row, 2, name_item)
                    self.channel_list.setItem(row, 3, current_item)
                    self.channel_list.setItem(row, 4, next_item)

                    # Try to load channel icon if available (after row is inserted)
                    channel_icon_url = channel['data'].get('icon_public_url') or channel['data'].get('icon')
                    if channel_icon_url:
                        self.load_channel_icon(row, 1, channel_icon_url, server)

                    # Add to verification list
                    channel_verification.append({
                        'row': row,
                        'name': channel['name'],
                        'number': channel['number']
                    })

                    print(f"Debug: Added channel to row {row}: {channel['name']}")

                except Exception as e:
                    print(f"Debug: Error adding channel to table: {str(e)}")
                    traceback.print_exc()
                    continue

            # Restore saved sort order (visual indicator only, channels already sorted manually)
            if 'sort_column' in self.config and 'sort_order' in self.config:
                sort_column = self.config['sort_column']
                sort_order = self.config['sort_order']
                # Update last valid sort
                self.last_valid_sort_column = sort_column
                self.last_valid_sort_order = sort_order
                # Only set visual sort indicator, don't actually sort (already sorted by Python in line 1852)
                self.channel_list.horizontalHeader().setSortIndicator(sort_column, sort_order)

            # Clean up any empty rows (rows without channel name in column 2)
            rows_to_remove = []
            for row in range(self.channel_list.rowCount()):
                name_item = self.channel_list.item(row, 2)
                if name_item is None or not name_item.text():
                    rows_to_remove.append(row)

            # Remove empty rows (in reverse order to avoid index shifting)
            for row in reversed(rows_to_remove):
                print(f"Debug: Removing empty row {row}")
                self.channel_list.removeRow(row)

            # Re-enable sorting after all items are added and cleaned up
            self.channel_list.setSortingEnabled(True)

            # Verify the final table contents
            print("\nDebug: Channel Verification:")
            print(f"Original channel count: {len(channels)}")
            print(f"Added channel count: {len(channel_verification)}")
            print(f"Table row count: {self.channel_list.rowCount()}")

            print("\nDebug: Final Table Contents:")
            for row in range(self.channel_list.rowCount()):
                number_item = self.channel_list.item(row, 0)
                name_item = self.channel_list.item(row, 2)  # Column 2 now contains the name
                if number_item and name_item:
                    number = number_item.data(Qt.DisplayRole)
                    name = name_item.text()
                    print(f"Row {row}: #{number} - {name}")
                else:
                    print(f"Row {row}: Missing items")

            self.statusbar.showMessage("Channels loaded successfully")

            # Start icon download asynchronously (non-blocking)
            QTimer.singleShot(100, self.download_icons_async)

            # Start EPG data fetch for all channels (with delay to ensure table is ready)
            # Note: This makes one API call per channel, so it may take a moment
            QTimer.singleShot(1000, self.update_all_epg_data)

            # Start EPG update timer (only once) - 30 minutes interval instead of 10
            if not hasattr(self, 'epg_update_timer'):
                self.start_epg_update_timer()

            # Start progress bar refresh timer (only updates UI, no API calls)
            if not hasattr(self, 'progress_refresh_timer'):
                self.start_progress_refresh_timer()

        except Exception as e:
            print(f"Debug: Error in fetch_channels: {str(e)}")
            print(f"Debug: Error type: {type(e)}")
            print(f"Debug: Traceback: {traceback.format_exc()}")

            # Show error dialog
            dialog = ConnectionErrorDialog(
                server['name'],
                f"Unexpected error: {str(e)}",
                self
            )
            if dialog.exec_() == QDialog.Accepted:
                print("Debug: Retrying connection...")
                self.fetch_channels()
            else:
                print("Debug: Connection attempt aborted by user")
                self.statusbar.showMessage("Connection aborted")
                self.channel_list.clear()


    def start_recording(self):
        print("Debug: Starting recording")
        try:
            # Get selected channel
            current_channel = self.channel_list.currentItem()
            if not current_channel:
                print("Debug: No channel selected for recording")
                self.statusbar.showMessage("Please select a channel to record")
                return

            # Show duration dialog
            duration_dialog = RecordingDurationDialog(self)
            if duration_dialog.exec_() != QDialog.Accepted:
                print("Debug: Recording cancelled by user")
                return

            duration = duration_dialog.get_duration()
            print(f"Debug: Selected recording duration: {duration} seconds")

            channel_name = current_channel.text()
            print(f"Debug: Attempting to record channel: {channel_name}")

            # Get current server
            server = self.servers[self.server_combo.currentIndex()]
            print(f"Debug: Using server: {server['url']}")

            # Create auth if needed
            auth = None
            if server.get('username') or server.get('password'):
                auth = (server.get('username', ''), server.get('password', ''))
                print(f"Debug: Using authentication with username: {server.get('username', '')}")

            # First, get channel UUID
            api_url = f'{server["url"]}/api/channel/grid?limit=10000'
            print(f"Debug: Getting channel UUID from: {api_url}")

            response = session.get(api_url, auth=auth)
            print(f"Debug: Channel list response status: {response.status_code}")

            channels = response.json()['entries']
            channel_uuid = None
            for channel in channels:
                if channel['name'] == channel_name:
                    channel_uuid = channel['uuid']
                    print(f"Debug: Found channel UUID: {channel_uuid}")
                    break

            if not channel_uuid:
                print(f"Debug: Channel UUID not found for: {channel_name}")
                self.statusbar.showMessage("Channel not found")
                return

            # Prepare recording request
            now = int(datetime.now().timestamp())
            stop_time = now + duration

            # Format exactly as in the working curl command
            conf_data = {
                "start": now,
                "stop": stop_time,
                "channel": channel_uuid,
                "title": {"eng": "Instant Recording"},
                "subtitle": {"eng": "Recorded via TVHplayer"}
            }

            # Convert to string format as expected by the API
            data = {'conf': json.dumps(conf_data)}
            print(f"Debug: Recording data: {data}")

            # Make recording request
            record_url = f'{server["url"]}/api/dvr/entry/create'
            print(f"Debug: Sending recording request to: {record_url}")

            response = requests.post(record_url, data=data, auth=auth)
            print(f"Debug: Recording response status: {response.status_code}")
            print(f"Debug: Recording response: {response.text}")

            if response.status_code == 200:
                duration_minutes = duration // 60
                self.statusbar.showMessage(
                    f"Recording started for: {channel_name} ({duration_minutes} minutes)"
                )
                print("Debug: Recording started successfully")
                self.start_recording_indicator()  # Start the recording indicator
            else:
                self.statusbar.showMessage("Failed to start recording")
                print(f"Debug: Recording failed with status {response.status_code}")

        except Exception as e:
            print(f"Debug: Recording error: {str(e)}")
            print(f"Debug: Error type: {type(e)}")

            print(f"Debug: Traceback: {traceback.format_exc()}")
            self.statusbar.showMessage(f"Recording error: {str(e)}")

    def stop_playback(self):
        print("Debug: Stopping playback")
        """Stop current playback"""
        self.media_player.stop()
        self.statusbar.showMessage("Playback stopped")

                # Create a new fullscreen window
    def toggle_fullscreen(self):
        """Toggle fullscreen mode for VLC player"""
        print(f"Debug: Toggling fullscreen. Current state: {self.is_fullscreen}")

        try:
            if not self.is_fullscreen:
                # Store the video frame's original parent and layout position
                self.original_parent = self.video_frame.parent()
                self.original_layout = self.findChild(QVBoxLayout, "right_layout")

            # Create a new fullscreen window
                self.fullscreen_window = QWidget()
                self.fullscreen_window.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
                self.fullscreen_window.installEventFilter(self)
                layout = QVBoxLayout(self.fullscreen_window)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)  # Remove spacing between widgets

                # Move video frame to fullscreen
                self.video_frame.setParent(self.fullscreen_window)
                layout.addWidget(self.video_frame)

                # Show fullscreen
                QApplication.processEvents()  # Process any pending events
                self.fullscreen_window.showFullScreen()
                self.video_frame.show()

                # Reset VLC window handle for fullscreen
                if sys.platform.startswith('linux'):
                    QApplication.processEvents()  # Give X11 time to update
                    self.media_player.set_xwindow(self.video_frame.winId().__int__())
                elif sys.platform == "win32":
                    self.media_player.set_hwnd(self.video_frame.winId().__int__())
                elif sys.platform == "darwin":
                    self.media_player.set_nsobject(self.video_frame.winId().__int__())
            else:
                # Remove from fullscreen layout
                if self.fullscreen_window and self.fullscreen_window.layout():
                    self.fullscreen_window.layout().removeWidget(self.video_frame)

                # Find the right pane's layout again
                right_layout = self.findChild(QVBoxLayout, "right_layout")
                if right_layout:
                    # Restore to right pane
                    self.video_frame.setParent(self.original_parent)
                    right_layout.insertWidget(0, self.video_frame)
                    QApplication.processEvents()  # Process any pending events
                    self.video_frame.show()

                    # Reset VLC window handle for normal view
                    if sys.platform.startswith('linux'):
                        QApplication.processEvents()  # Give X11 time to update
                        self.media_player.set_xwindow(self.video_frame.winId().__int__())
                    elif sys.platform == "win32":
                        self.media_player.set_hwnd(self.video_frame.winId().__int__())
                    elif sys.platform == "darwin":
                        self.media_player.set_nsobject(self.video_frame.winId().__int__())

                    # Close fullscreen window
                    self.fullscreen_window.close()
                    self.fullscreen_window = None
                else:
                    print("Debug: Could not find right_layout")

            self.is_fullscreen = not self.is_fullscreen
            print(f"Debug: New fullscreen state: {self.is_fullscreen}")

        except Exception as e:
            print(f"Debug: Error in toggle_fullscreen: {str(e)}")
            print(f"Debug: Traceback: {traceback.format_exc()}")

    def load_servers(self):
        """Load TVHeadend server configurations"""
        try:
            with open('servers.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return empty list if no config file exists
            return []
        except json.JSONDecodeError:
            # Return default server if config file is invalid
            return [{
                'name': 'Default Server',
                'url': '127.0.0.1:9981'
            }]

    def manage_servers(self):
        print("Debug: Opening server management dialog")
        dialog = ServerDialog(self)
        dialog.load_servers(self.servers)
        print(f"Debug: Loaded {len(self.servers)} servers into dialog")
        if dialog.exec_() == QDialog.Accepted:
            self.servers = dialog.servers
            print(f"Debug: Updated servers list, now has {len(self.servers)} servers")
            self.save_config()

            # Update server combo
            self.server_combo.clear()
            for server in self.servers:
                print(f"Debug: Adding server to combo: {server['name']}")
                self.server_combo.addItem(server['name'])

            # Refresh channels
            self.fetch_channels()

    def save_config(self):
        """Save current configuration"""
        try:
            # Update window geometry in config
            if not self.is_fullscreen:
                self.config['window_geometry'] = {
                    'x': self.x(),
                    'y': self.y(),
                    'width': self.width(),
                    'height': self.height()
                }

            # Update servers in config
            self.config['servers'] = self.servers

            # Note: last_server is updated in on_server_changed(), not here
            # to avoid overwriting the correct value with stale UI state

            # Save to file
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print("Debug: Configuration saved successfully")
        except Exception as e:
            print(f"Debug: Error saving config: {str(e)}")
            traceback.print_exc()

    def play_channel(self, item):
        """Play the selected channel"""
        try:
            # Get the current row
            current_row = self.channel_list.currentRow()
            if current_row < 0:
                print("Debug: No channel selected")
                self.statusbar.showMessage("Please select a channel to play")
                return

            # Get channel data directly from the table
            name_item = self.channel_list.item(current_row, 2)  # Get the name column item (now column 2)
            if not name_item:
                print("Debug: No channel item found")
                return

            # Get the channel data stored in UserRole
            channel_data = name_item.data(Qt.UserRole)
            if not channel_data:
                print("Debug: No channel data found in item")
                return

            print(f"Debug: Playing channel: {channel_data.get('name', 'Unknown')}")

            # Get current server
            server = self.servers[self.server_combo.currentIndex()]

            # Construct proper URL
            base_url = server['url']
            if not base_url.startswith(('http://', 'https://')):
                base_url = f"http://{base_url}"

            url = f"{base_url}/stream/channel/{channel_data['uuid']}"
            print(f"Debug: Playing URL: {url}")

            # Rest of the play logic...
        except Exception as e:
            print(f"Debug: Error in play_channel: {str(e)}")
            print(f"Debug: Traceback: {traceback.format_exc()}")

    def on_server_changed(self, index):
        """
        Handle when user switches to a different TVHeadend server in the dropdown.
        Updates the config file with the newly selected server index and refreshes channel list.

        Args:
            index (int): Index of the newly selected server in self.servers list
        """
        print(f"Debug: Server changed to index {index}")
        if index >= 0 and index < len(self.servers):  # Valid index selected and server exists
            print(f"Debug: Switching to server: {self.servers[index]['name']}")

            # Stop any running EPG updates immediately
            self.epg_update_stop_requested = True
            if hasattr(self, 'epg_update_queue'):
                self.epg_update_queue = []  # Clear queue

            # Update config with new server selection
            self.config['last_server'] = index

            # Save updated config using central save method
            self.save_config()

            # Load channels from newly selected server
            self.fetch_channels()
        else:
            print(f"Debug: Invalid server index {index} (have {len(self.servers)} servers)")

    def on_volume_changed(self, value):
        print(f"Debug: Volume changed to {value}")
        self.media_player.audio_set_volume(value)

    def eventFilter(self, obj, event):
        """Handle double-click and key events"""
        if obj == self.video_frame:
            if event.type() == event.MouseButtonDblClick:
                self.toggle_fullscreen()
                return True

        # Handle key events for both main window and fullscreen window
        if event.type() == event.KeyPress:
            if event.key() == Qt.Key_Escape and self.is_fullscreen:
                self.toggle_fullscreen()
                return True
            elif event.key() == Qt.Key_F:
                self.toggle_fullscreen()
                return True

        return super().eventFilter(obj, event)

    def toggle_mute(self):
        """Toggle audio mute state"""
        print("Debug: Toggling mute")
        is_muted = self.media_player.audio_get_mute()
        self.media_player.audio_set_mute(not is_muted)

        if not is_muted:  # Switching to muted
            self.mute_btn.setIcon(QIcon(f"{self.icons_dir}/mute.svg"))
            self.mute_btn.setToolTip("Unmute")
            print("Debug: Audio muted")
        else:  # Switching to unmuted
            self.mute_btn.setIcon(QIcon(f"{self.icons_dir}/unmute.svg"))
            self.mute_btn.setToolTip("Mute")
            print("Debug: Audio unmuted")

    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Get new settings (only icon size now)
            icon_size = dialog.get_settings()

            # Apply new settings (will save config internally)
            self.apply_icon_settings(icon_size)

    def apply_icon_settings(self, icon_size):
        """Apply new icon size settings"""
        # IMPORTANT: Save to config FIRST before reloading icons
        # so load_channel_icon() reads the new icon_size from config
        self.config['icon_size'] = icon_size
        self.save_config()

        # Update icon column width (column 1)
        self.channel_list.setColumnWidth(1, icon_size + 10)

        # Update table's icon size (crucial for icon display!)
        self.channel_list.setIconSize(QSize(icon_size, icon_size))

        # Row height stays fixed at 60px for better EPG display
        # (independent of icon size now)

        # Reload all icons with new size

        # Get current server for icon loading
        server = self.servers[self.server_combo.currentIndex()]

        # Reload ALL icons synchronously with new size (now reads from updated config)
        for row in range(self.channel_list.rowCount()):
            icon_item = self.channel_list.item(row, 1)  # Column 1 now has icons
            if icon_item:
                channel_data = icon_item.data(Qt.UserRole)
                if channel_data:
                    icon_url = channel_data.get('icon_public_url') or channel_data.get('icon')
                    if icon_url:
                        self.load_channel_icon(row, 1, icon_url, server, from_cache_only=False)

        self.statusbar.showMessage(f"Icon settings updated ({icon_size}px)")

    def clear_icon_cache(self):
        """Clear all cached channel icons for all servers"""


        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            'Clear Icon Cache',
            'This will delete all cached channel icons for all servers.\n\n'
            'Icons will be downloaded again when you switch to a server.\n\n'
            'Continue?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Delete entire channel_icons directory
                if os.path.exists(self.icon_cache_base_dir):
                    shutil.rmtree(self.icon_cache_base_dir)
                    print(f"Debug: Deleted icon cache directory: {self.icon_cache_base_dir}")

                    # Recreate empty directory
                    os.makedirs(self.icon_cache_base_dir, exist_ok=True)

                    # Clear icons from current channel list
                    for row in range(self.channel_list.rowCount()):
                        icon_item = self.channel_list.item(row, 1)
                        if icon_item:
                            icon_item.setIcon(QIcon())  # Clear icon

                    QMessageBox.information(
                        self,
                        'Cache Cleared',
                        'Icon cache has been cleared successfully.\n\n'
                        'Icons will be downloaded again when needed.'
                    )
                    self.statusbar.showMessage("Icon cache cleared")

                    # Trigger async icon download if on a server
                    if self.servers:
                        QTimer.singleShot(500, self.download_icons_async)
                else:
                    QMessageBox.information(
                        self,
                        'Cache Empty',
                        'Icon cache is already empty.'
                    )
            except Exception as e:
                print(f"Debug: Error clearing icon cache: {str(e)}")
                QMessageBox.warning(
                    self,
                    'Error',
                    f'Failed to clear icon cache:\n{str(e)}'
                )

    def reset_to_defaults(self):
        """Reset all UI settings to factory defaults"""


        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            'Reset to Factory Defaults',
            'This will reset all display settings (column widths, sorting, icon sizes) '
            'AND delete all cached channel icons for all servers.\n\n'
            'Server configurations will NOT be affected.\n\n'
            'Continue?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Remove UI-related config keys
            keys_to_reset = [
                'channel_column_width',
                'current_program_width',
                'icon_size',
                'sort_column',
                'sort_order',
                'column_visibility',
                'window_geometry'
            ]

            for key in keys_to_reset:
                if key in self.config:
                    del self.config[key]

            self.save_config()

            # Delete icon cache for all servers
            try:
                if os.path.exists(self.icon_cache_base_dir):
                    shutil.rmtree(self.icon_cache_base_dir)
                    os.makedirs(self.icon_cache_base_dir, exist_ok=True)
                    print(f"Debug: Deleted icon cache as part of factory reset")
            except Exception as e:
                print(f"Debug: Error deleting icon cache during reset: {str(e)}")

            # Show success message
            QMessageBox.information(
                self,
                'Reset Complete',
                'Settings have been reset to factory defaults and icon cache has been cleared.\n\n'
                'Please restart the application for changes to take effect.'
            )

    def show_about(self):
        """Show the about dialog"""
        print("Debug: Showing about dialog")
        about_text = (
            "<div style='text-align: center;'>"
            "<h2>TVHplayer</h2>"
            "<p>Version 4.0</p>"
            "<p>A powerful and user-friendly TVHeadend client application.</p>"
            "<p style='margin-top: 20px;'><b>Created by:</b><br>mFat</p>"
            "<p style='margin-top: 20px;'><b>Built with:</b><br>"
            "Python, PyQt5, and VLC</p>"
            "<p style='margin-top: 20px;'>"
            "<a href='https://github.com/mfat/tvhplayer'>Project Website</a>"
            "</p>"
            "<p style='margin-top: 20px; font-size: 11px;'>"
            "This program is free software: you can redistribute it and/or modify "
            "it under the terms of the GNU General Public License as published by "
            "the Free Software Foundation, either version 3 of the License, or "
            "(at your option) any later version.<br><br>"
            "This program is distributed in the hope that it will be useful, "
            "but WITHOUT ANY WARRANTY; without even the implied warranty of "
            "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the "
            "GNU General Public License for more details.<br><br>"
            "You should have received a copy of the GNU General Public License "
            "along with this program. If not, see "
            "<a href='https://www.gnu.org/licenses/'>https://www.gnu.org/licenses/</a>."
            "</p>"
            "</div>"
        )
        msg = QMessageBox()
        msg.setWindowTitle("About TVHplayer")
        msg.setText(about_text)
        msg.setTextFormat(Qt.RichText)
        msg.setMinimumWidth(400)  # Make dialog wider to prevent text wrapping
        msg.exec_()

    def show_user_guide(self):
        """Open the user guide documentation"""
        print("Debug: Opening user guide")
        try:
            # Open the GitHub wiki URL in the default web browser
            url = "https://github.com/mfat/tvhplayer/wiki/User-Guide"

            # Open URL in the default web browser based on platform
            if platform.system() == "Linux":
                subprocess.Popen(["xdg-open", url])
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", url])
            elif platform.system() == "Windows":
                os.startfile(url)
            else:
                # Fallback using webbrowser module

                webbrowser.open(url)

            print(f"Opened user guide URL: {url}")

        except Exception as e:
            print(f"Error opening user guide URL: {str(e)}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open user guide: {str(e)}",
                QMessageBox.Ok
            )

    def toggle_recording(self):
        """Toggle between starting and stopping recording"""
        if self.record_btn.isChecked():
            self.start_recording()
        else:
            self.stop_recording()

    def stop_recording(self):
        """Stop active recordings"""
        print("Debug: Attempting to stop recordings")
        try:
            # Get current server
            server = self.servers[self.server_combo.currentIndex()]
            print(f"Debug: Using server: {server['url']}")

            # Create auth if needed
            auth = None
            if server.get('username') or server.get('password'):
                auth = (server.get('username', ''), server.get('password', ''))
                print(f"Debug: Using authentication with username: {server.get('username', '')}")

            # Get list of active recordings
            api_url = f'{server["url"]}/api/dvr/entry/grid'
            print(f"Debug: Getting recordings from: {api_url}")

            response = session.get(api_url, auth=auth)
            print(f"Debug: Recording list response status: {response.status_code}")

            recordings = response.json()['entries']
            print(f"Debug: Total recordings found: {len(recordings)}")

            # Print all recordings and their statuses for debugging
            for recording in recordings:
                print(f"Debug: Recording '{recording.get('disp_title', 'Unknown')}' - Status: {recording.get('status', 'unknown')}")

            # Look for recordings with status 'Running' (this seems to be the actual status used by TVHeadend)
            active_recordings = [r for r in recordings if r['status'] in ['Running', 'recording']]
            if not active_recordings:
                print("Debug: No active recordings found")
                self.statusbar.showMessage("No active recordings to stop")
                self.stop_recording_indicator()  # Make sure to hide indicator
                return

            print(f"Debug: Found {len(active_recordings)} active recordings")

            # Stop each active recording
            for recording in active_recordings:
                stop_url = f'{server["url"]}/api/dvr/entry/stop'
                data = {'uuid': recording['uuid']}

                print(f"Debug: Stopping recording: {recording.get('disp_title', 'Unknown')} ({recording['uuid']})")
                stop_response = requests.post(stop_url, data=data, auth=auth)

                if stop_response.status_code == 200:
                    print(f"Debug: Successfully stopped recording: {recording['uuid']}")
                else:
                    print(f"Debug: Failed to stop recording: {recording['uuid']}")
                    print(f"Debug: Response: {stop_response.text}")

            self.stop_recording_indicator()  # Hide the indicator after stopping recordings
            self.statusbar.showMessage(f"Stopped {len(active_recordings)} recording(s)")

        except Exception as e:
            print(f"Debug: Error stopping recordings: {str(e)}")
            print(f"Debug: Error type: {type(e)}")

            print(f"Debug: Traceback: {traceback.format_exc()}")
            self.statusbar.showMessage(f"Error stopping recordings: {str(e)}")
            self.stop_recording_indicator()  # Make sure to hide indicator even on error

    def start_recording_indicator(self):
        """Start the recording indicator with smooth pulsing animation"""
        print("Debug: Starting recording indicator")
        self.is_recording = True
        self.recording_indicator.setProperty("recording", True)
        self.recording_indicator.style().polish(self.recording_indicator)

        # Create opacity effect
        self.opacity_effect = QGraphicsOpacityEffect(self.recording_indicator)
        self.recording_indicator.setGraphicsEffect(self.opacity_effect)

        # Create and configure the animation
        self.recording_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.recording_animation.setDuration(1000)  # 1 second per pulse
        self.recording_animation.setStartValue(1.0)
        self.recording_animation.setEndValue(0.3)
        self.recording_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.recording_animation.setLoopCount(-1)  # Infinite loop

        # Start the animation
        self.recording_animation.start()

    def stop_recording_indicator(self):
        """Stop the recording indicator and its animation"""
        print("Debug: Stopping recording indicator")
        self.is_recording = False
        if self.recording_animation:
            self.recording_animation.stop()
            self.recording_animation = None
        if hasattr(self, 'opacity_effect'):
            self.recording_indicator.setGraphicsEffect(None)
            self.opacity_effect = None
        self.recording_indicator.setProperty("recording", False)
        self.recording_indicator.style().polish(self.recording_indicator)

    def show_dvr_status(self):
        """Show DVR status dialog"""
        try:
            print("\nDebug: Opening DVR Status Dialog")
            server = self.servers[self.server_combo.currentIndex()]
            print(f"Debug: Using server: {server}")

            # Test connection first
            test_url = f"{server['url']}/api/status/connections"
            auth = None
            if server.get('username') or server.get('password'):
                auth = (server.get('username', ''), server.get('password', ''))
                print(f"Debug: Using authentication with username: {server.get('username', '')}")

            print(f"Debug: Testing connection to: {test_url}")
            try:
                test_response = session.get(test_url, auth=auth, timeout=5)
                print(f"Debug: Connection test response: {test_response.status_code}")
                if test_response.status_code == 200:
                    print("Debug: Server connection successful")
                else:
                    print(f"Debug: Server connection failed with status {test_response.status_code}")
                    self.statusbar.showMessage("Failed to connect to server")
                    return
            except Exception as conn_err:
                print(f"Debug: Connection test failed: {str(conn_err)}")
                self.statusbar.showMessage("Failed to connect to server")
                return

            # Now try to get DVR data
            dvr_url = f"{server['url']}/api/dvr/entry/grid"
            print(f"Debug: Fetching DVR data from: {dvr_url}")
            try:
                dvr_response = session.get(dvr_url, auth=auth, timeout=5)
                print(f"Debug: DVR data response: {dvr_response.status_code}")
                if dvr_response.status_code == 200:
                    dvr_data = dvr_response.json()
                    print(f"Debug: DVR data received: {len(dvr_data.get('entries', []))} entries")
                    # Print first entry as sample if available
                    if dvr_data.get('entries'):
                        print("Debug: Sample DVR entry:")
                        print(dvr_data['entries'][0])
                else:
                    print(f"Debug: Failed to get DVR data: {dvr_response.text}")
                    self.statusbar.showMessage("Failed to get DVR data")
                    return
            except Exception as dvr_err:
                print(f"Debug: DVR data fetch failed: {str(dvr_err)}")
                self.statusbar.showMessage("Failed to get DVR data")
                return

            # If we got here, show the dialog
            dialog = DVRStatusDialog(server, self)
            dialog.show()

        except Exception as e:
            print(f"Debug: Error showing DVR status: {str(e)}")
            print(f"Debug: Traceback: {traceback.format_exc()}")
            self.statusbar.showMessage("Error showing DVR status")

    def play_url(self, url):
        """Play media from URL"""
        try:
            media = self.instance.media_new(url)
            self.media_player.set_media(media)
            self.media_player.play()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to play media: {str(e)}")

    def start_local_recording(self, channel_name):
        """Record channel stream to local disk using ffmpeg"""
        try:
            if not channel_name:
                print("Debug: No channel selected for recording")
                self.statusbar.showMessage("Please select a channel to record")
                return

            print(f"Debug: Starting local recording for channel: {channel_name}")

            # Show file save dialog
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"recording_{channel_name}_{timestamp}.ts"  # Using .ts format initially

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Recording As",
                default_filename,
                "TS Files (*.ts);;MP4 Files (*.mp4);;All Files (*.*)"
            )

            if not file_path:  # User cancelled
                print("Debug: Recording cancelled - no file selected")
                return

            # Get current server and auth info
            server = self.servers[self.server_combo.currentIndex()]

            # Get channel UUID
            api_url = f'{server["url"]}/api/channel/grid?limit=10000'
            auth = None
            if server.get('username') or server.get('password'):
                auth = (server.get('username', ''), server.get('password', ''))

            print(f"Debug: Fetching channel list from: {api_url}")
            response = session.get(api_url, auth=auth)
            channels = response.json()['entries']

            channel_uuid = None
            for channel in channels:
                if channel['name'] == channel_name:
                    channel_uuid = channel['uuid']
                    break

            if not channel_uuid:
                print(f"Debug: Channel UUID not found for: {channel_name}")
                self.statusbar.showMessage("Channel not found")
                return

            # Create stream URL
            server_url = server['url'].rstrip('/')
            if not server_url.startswith(('http://', 'https://')):
                server_url = f'http://{server_url}'

            stream_url = f'{server_url}/stream/channel/{channel_uuid}'

            # Build ffmpeg command
            ffmpeg_cmd = [
                'ffmpeg',
                '-hide_banner',
                '-loglevel', 'warning',
                '-nostats',
                '-y'  # Overwrite output
            ]

            # Add auth headers if needed
            if auth:

                auth_string = f"{auth[0]}:{auth[1]}"
                auth_bytes = auth_string.encode('ascii')
                base64_bytes = base64.b64encode(auth_bytes)
                base64_auth = base64_bytes.decode('ascii')
                ffmpeg_cmd.extend([
                    '-headers', f'Authorization: Basic {base64_auth}\r\n'
                ])

            # Add input options
            ffmpeg_cmd.extend([
                '-i', stream_url,
                '-analyzeduration', '10M',  # Increase analyze duration
                '-probesize', '10M'         # Increase probe size
            ])

            # Add output options based on file extension
            if file_path.lower().endswith('.mp4'):
                ffmpeg_cmd.extend([
                    '-c:v', 'copy',
                    '-c:a', 'aac',          # Transcode audio to AAC
                    '-b:a', '192k',         # Audio bitrate
                    '-movflags', '+faststart',
                    '-f', 'mp4'
                ])
            else:  # Default to .ts
                ffmpeg_cmd.extend([
                    '-c', 'copy',           # Copy both streams without transcoding
                    '-f', 'mpegts'          # Force MPEG-TS format
                ])

            # Add output file
            ffmpeg_cmd.append(file_path)

            print("Debug: Starting ffmpeg with command:")
            # Print command with hidden auth if present
            safe_cmd = ' '.join(ffmpeg_cmd)
            if auth:
                safe_cmd = safe_cmd.replace(base64_auth, "***")
            print(f"Debug: {safe_cmd}")

            # Start ffmpeg process
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10**8
            )

            # Start monitoring process
            self.recording_monitor = QTimer()
            self.recording_monitor.timeout.connect(
                lambda: self.check_recording_status(file_path))  # Close parenthesis here
            self.recording_monitor.start(2000)  # Check every 2 seconds

            self.statusbar.showMessage(f"Local recording started: {file_path}")
            self.start_recording_indicator()

            # After starting ffmpeg process successfully:
            self.recording_status_dialog = RecordingStatusDialog(channel_name, file_path, self)
            self.recording_status_dialog.finished.connect(self.stop_local_recording)
            self.recording_status_dialog.show()

        except Exception as e:
            print(f"Debug: Local recording error: {str(e)}")
            print(f"Debug: Error type: {type(e)}")

            print(f"Debug: Traceback: {traceback.format_exc()}")
            self.statusbar.showMessage(f"Local recording error: {str(e)}")

    def check_recording_status(self, file_path):
        """Check if the recording is actually working"""
        try:

            # Add start time tracking if not exists
            if not hasattr(self, 'recording_start_time'):
                self.recording_start_time = time.time()

            # Calculate elapsed time
            elapsed_time = time.time() - self.recording_start_time

            if not os.path.exists(file_path):
                print("Debug: Recording file does not exist")
                # Only show warning if more than 10 seconds have passed
                if elapsed_time > 10:
                    if hasattr(self, 'recording_status_dialog'):
                        self.recording_status_dialog.close()
                    QMessageBox.warning(self, "Local Recording Status", "Recording file does not exist")
                    return
                else:
                    print(f"Debug: Waiting for file creation ({int(elapsed_time)} seconds elapsed)")
                    return

            file_size = os.path.getsize(file_path)
            print(f"Debug: Current recording file size: {file_size} bytes")

            # Update status dialog if it exists
            if hasattr(self, 'recording_status_dialog'):
                is_stalled = False
                if hasattr(self, 'last_file_size') and file_size == self.last_file_size:
                    is_stalled = True
                self.recording_status_dialog.update_status(file_size, is_stalled)

            if hasattr(self, 'ffmpeg_process'):
                return_code = self.ffmpeg_process.poll()
                if return_code is not None:
                    # Process has ended
                    _, stderr = self.ffmpeg_process.communicate()
                    print(f"Debug: FFmpeg process ended with return code: {return_code}")
                    if stderr:
                        print(f"Debug: FFmpeg error output: {stderr.decode()}")

                    if file_size == 0 or return_code != 0:
                        print("Debug: Recording failed - stopping processes")
                        self.stop_local_recording()
                        error_msg = "Recording failed - check console for errors"
                        QMessageBox.critical(self, "Recording Error", error_msg)
                        return

                # Check if file is growing
                if hasattr(self, 'last_file_size'):
                    if file_size == self.last_file_size:
                        print("Debug: File size not increasing - potential stall")
                        self.stall_count = getattr(self, 'stall_count', 0) + 1
                        if self.stall_count > 5:  # After 10 seconds of no growth
                            print("Debug: Recording stalled - restarting")
                            stall_msg = "Recording stalled - attempting restart"
                            QMessageBox.warning(self, "Recording Status", stall_msg)
                            self.stop_local_recording()
                            self.start_local_recording(self.channel_list.currentItem().text())
                            return
                    else:
                        self.stall_count = 0

                self.last_file_size = file_size

        except Exception as e:
            error_msg = f"Debug: Error checking recording status: {str(e)}"
            print(error_msg)
            QMessageBox.critical(self, "Recording Error", error_msg)

    def stop_local_recording(self):
        """Stop local recording"""
        try:
            # Close status dialog if it exists
            if hasattr(self, 'recording_status_dialog'):
                self.recording_status_dialog.close()
                delattr(self, 'recording_status_dialog')

            print("Debug: Stopping local recording")

            # Stop monitoring
            if hasattr(self, 'recording_monitor') and self.recording_monitor is not None:
                self.recording_monitor.stop()
                self.recording_monitor = None

            # Stop ffmpeg process
            if hasattr(self, 'ffmpeg_process') and self.ffmpeg_process is not None:
                print("Debug: Stopping ffmpeg process")
                self.ffmpeg_process.terminate()
                try:
                    self.ffmpeg_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.ffmpeg_process.kill()
                self.ffmpeg_process = None

            # Clear stall detection variables
            if hasattr(self, 'last_file_size'):
                del self.last_file_size
            if hasattr(self, 'stall_count'):
                del self.stall_count

            self.statusbar.showMessage("Local recording stopped")
            self.stop_recording_indicator()

        except Exception as e:
            print(f"Debug: Error stopping local recording: {str(e)}")
            self.statusbar.showMessage(f"Error stopping local recording: {str(e)}")
            self.stop_recording_indicator()

    def load_config(self):
        """Load application configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            else:
                # Return default configuration
                return {
                    'volume': 50,
                    'last_server': 0,
                    'recording_path': str(Path.home()),
                    'window_geometry': {
                        'x': 100,
                        'y': 100,
                        'width': 1200,
                        'height': 700
                    },
                }
        except Exception as e:
            print(f"Debug: Error loading config: {str(e)}")
            return self.get_default_config()

    def get_default_config(self):
        """Return default configuration"""
        return {
            'volume': 50,
            'last_server': 0,
            'recording_path': str(Path.home()),
            'window_geometry': {
                'x': 100,
                'y': 100,
                'width': 1200,
                'height': 700
            },
        }

    def closeEvent(self, event):
        """Save configuration when closing the application"""
        # Force save pending column resizes before closing (backup for timer)
        if hasattr(self, 'resize_timer'):
            self.resize_timer.stop()  # Stop timer to prevent double-save
        if hasattr(self, 'pending_column_resize') and self.pending_column_resize:
            self.save_all_column_widths()

        # Force save pending splitter changes before closing (backup for timer)
        if hasattr(self, 'splitter_timer'):
            self.splitter_timer.stop()  # Stop timer to prevent double-save
        if hasattr(self, 'pending_splitter_sizes') and self.pending_splitter_sizes:
            self.save_splitter_sizes()

        self.save_config()
        super().closeEvent(event)

    def show_channel_context_menu(self, position):
        """Show context menu for channel list items"""
        menu = QMenu()

        # Get the item at the position
        row = self.channel_list.rowAt(position.y())
        if row >= 0:
            channel_item = self.channel_list.item(row, 2)  # Get name column item (now column 2)
            if channel_item is None:
                # No item at this position, don't show context menu
                return

            channel_data = channel_item.data(Qt.UserRole)
            if channel_data is None:
                # No channel data stored, don't show context menu
                return

            # Add menu actions
            play_action = menu.addAction("Play")
            play_action.triggered.connect(lambda: self.play_channel_by_data(channel_data))
            record_action = menu.addAction("Record")
            record_action.triggered.connect(lambda: self.start_recording())
            local_record_action = menu.addAction("Record Locally")
            local_record_action.triggered.connect(
                lambda: self.start_local_recording(channel_data['name']))

            # Add EPG action
            epg_action = menu.addAction("Show EPG")
            epg_action.triggered.connect(lambda: self.show_channel_epg(channel_data['name']))

            # Show the menu at the cursor position
            menu.exec_(self.channel_list.viewport().mapToGlobal(position))

    def show_channel_epg(self, channel_name):
        """Fetch and show EPG data for the selected channel"""
        try:
            print(f"Debug: Fetching EPG for channel: {channel_name}")

            # Get current server
            server = self.servers[self.server_combo.currentIndex()]
            print(f"Debug: Using server: {server['url']}")

            # Create auth if needed
            auth = None
            if server.get('username') or server.get('password'):
                auth = (server.get('username', ''), server.get('password', ''))
                print(f"Debug: Using authentication with username: {server.get('username', '')}")

            # First get channel UUID
            api_url = f'{server["url"]}/api/channel/grid?limit=10000'
            print(f"Debug: Getting channel UUID from: {api_url}")

            response = session.get(api_url, auth=auth)
            print(f"Debug: Channel list response status: {response.status_code}")

            channels = response.json()['entries']
            print(f"Debug: Found {len(channels)} channels in response")

            channel_uuid = None
            for channel in channels:
                if channel['name'] == channel_name:
                    channel_uuid = channel['uuid']
                    print(f"Debug: Found channel UUID: {channel_uuid}")
                    break

            if not channel_uuid:
                print(f"Debug: Channel UUID not found for: {channel_name}")
                self.statusbar.showMessage("Channel not found")
                return

            # Get EPG data for the channel
            epg_url = f'{server["url"]}/api/epg/events/grid'
            params = {
                'channel': channel_uuid,
                'limit': 24  # Get next 24 events
            }
            print(f"Debug: Fetching EPG data from: {epg_url}")
            print(f"Debug: With parameters: {params}")

            response = session.get(epg_url, params=params, auth=auth)
            print(f"Debug: EPG response status: {response.status_code}")

            if response.status_code == 200:
                epg_data = response.json()['entries']
                if epg_data:
                    dialog = EPGDialog(channel_name, epg_data, server, self)
                    dialog.show()
                else:
                    self.statusbar.showMessage("No EPG data available")
            else:
                self.statusbar.showMessage("Failed to fetch EPG data")

        except Exception as e:
            print(f"Debug: Error fetching EPG: {str(e)}")
            self.statusbar.showMessage(f"Error fetching EPG: {str(e)}")

    def play_channel_from_table(self, item):
        """Play channel from table selection"""
        row = item.row()
        channel_item = self.channel_list.item(row, 2)  # Get name column item (now column 2)
        channel_data = channel_item.data(Qt.UserRole)  # Original data is stored here
        self.play_channel_by_data(channel_data)

    def play_channel_by_data(self, channel_data):
        """Play channel using channel data"""
        try:
            server = self.servers[self.server_combo.currentIndex()]
            server_url = server['url']
            print(f"Debug: Playing channel from server: {server_url}")

            # Create auth string if credentials exist
            auth_string = ''
            auth = None
            if server.get('username') or server.get('password'):
                auth = (server.get('username', ''), server.get('password', ''))
                auth_string = f"{server.get('username', '')}:{server.get('password', '')}@"

            # Use channel UUID directly from stored data
            channel_uuid = channel_data['uuid']

            if channel_uuid:
                # Create media URL with auth if needed
                if auth_string:
                    # Ensure server_url starts with http:// or https://
                    if not server_url.startswith(('http://', 'https://')):
                        server_url = f'http://{server_url}'

                    # Insert auth string after http:// or https://
                    stream_url = server_url.replace('://', f'://{auth_string}')
                    stream_url = f'{stream_url}/stream/channel/{channel_uuid}'

                else:
                    if not server_url.startswith(('http://', 'https://')):
                        server_url = f'http://{server_url}'
                    stream_url = f'{server_url}/stream/channel/{channel_uuid}'
                print(f"Debug: Stream URL: {stream_url}")

                media = self.instance.media_new(stream_url)
                self.media_player.set_media(media)
                self.media_player.play()
                print(f"Debug: Started playback")
                self.statusbar.showMessage(f"Playing: {channel_data['name']}")
            else:
                print(f"Debug: Channel not found: {channel_data['name']}")
                self.statusbar.showMessage("Channel not found")

        except Exception as e:
            print(f"Debug: Error in play_channel: {str(e)}")
            self.statusbar.showMessage(f"Playback error: {str(e)}")

    def show_server_status(self):
        """Show server status dialog"""
        try:
            server = self.servers[self.server_combo.currentIndex()]
            dialog = ServerStatusDialog(server, self)
            dialog.show()
        except Exception as e:
            print(f"Debug: Error showing server status: {str(e)}")
            self.statusbar.showMessage("Error showing server status")

    def filter_channels(self, search_text):
        """Filter channel list based on search text"""
        search_text = search_text.lower()
        for row in range(self.channel_list.rowCount()):
            item = self.channel_list.item(row, 2)  # Get name column item (now column 2)
            if item:
                channel_name = item.text().lower()
                self.channel_list.setRowHidden(row, search_text not in channel_name)

    def check_hardware_acceleration(self):
        """Check and print which hardware acceleration method is being used"""
        if not self.media_player:
            return

        # This only works if a media is playing
        if not self.media_player.is_playing():
            return

        try:
            # Get media statistics - handle different VLC Python binding versions
            media = self.media_player.get_media()
            if not media:
                print("No media currently playing")
                return

            # Different versions of python-vlc have different APIs for get_stats
            try:
                # Newer versions (direct call)
                stats = media.get_stats()
                print("VLC Playback Statistics:")
                print(f"Decoded video blocks: {stats.decoded_video}")
                print(f"Displayed pictures: {stats.displayed_pictures}")
                print(f"Lost pictures: {stats.lost_pictures}")
            except TypeError:
                # Older versions (requiring a stats object parameter)
                stats = vlc.MediaStats()
                media.get_stats(stats)
                print("VLC Playback Statistics:")
                print(f"Decoded video blocks: {stats.decoded_video}")
                print(f"Displayed pictures: {stats.displayed_pictures}")
                print(f"Lost pictures: {stats.lost_pictures}")

            # Check if hardware decoding is enabled
            if hasattr(self.media_player, 'get_role'):
                print(f"Media player role: {self.media_player.get_role()}")

            # Try to get more detailed hardware acceleration info
            print("Hardware acceleration is active if you see 'Using ... for hardware decoding' in the logs above")
            print("For more details, run VLC with the same content and use:")
            print("Tools -> Messages -> Info to see which decoder is being used")

        except Exception as e:
            print(f"Error checking hardware acceleration: {e}")
            print(f"Traceback: {traceback.format_exc()}")

    def show_header_context_menu(self, position):
        """Show context menu for table header to toggle column visibility"""
        menu = QMenu()

        # Column names (updated for 5-column layout)
        column_names = ['#', 'Icon', 'Channel', 'Current Program', 'Next Program']

        # Create checkbox actions for each column
        for col_idx, col_name in enumerate(column_names):
            action = menu.addAction(col_name)
            action.setCheckable(True)
            action.setChecked(not self.channel_list.isColumnHidden(col_idx))
            action.triggered.connect(lambda checked, idx=col_idx: self.toggle_column_visibility(idx, checked))

        # Show menu at cursor position
        menu.exec_(self.channel_list.horizontalHeader().mapToGlobal(position))

    def save_column_width(self, logical_index, old_size, new_size):
        """Debounced save - only saves after resize stops"""
        # Store values but don't save yet
        self.pending_column_resize = (logical_index, new_size)
        # Reset timer - only saves 500ms after last resize event
        self.resize_timer.stop()
        self.resize_timer.start(500)  # 500ms delay

    def save_all_column_widths(self):
        """Actually save column widths after resize finished"""
        if self.pending_column_resize:
            logical_index, new_size = self.pending_column_resize

            if logical_index == 2:  # Channel column
                self.config['channel_column_width'] = new_size
            elif logical_index == 3:  # Current Program column
                self.config['current_program_width'] = new_size
            elif logical_index == 4:  # Next Program column
                self.config['next_program_width'] = new_size

            self.pending_column_resize = None
            self.save_config()

    def save_splitter_position(self, pos, index):
        """Debounced save - only saves after dragging stops"""
        # Store sizes but don't save yet
        self.pending_splitter_sizes = self.splitter.sizes()
        # Reset timer - only saves 500ms after last move event
        self.splitter_timer.stop()
        self.splitter_timer.start(500)  # 500ms delay

    def save_splitter_sizes(self):
        """Actually save splitter sizes after dragging finished"""
        if self.pending_splitter_sizes:
            self.config['splitter_sizes'] = self.pending_splitter_sizes
            self.pending_splitter_sizes = None
            self.save_config()

    def handle_sort_changed(self, logical_index, order):
        """Handle sort indicator changes - block sorting on certain columns"""
        # Columns that should NOT be sortable: Icon (1), Current Program (3), Next Program (4)
        if logical_index in [1, 3, 4]:
            # Block signals to prevent recursive calls
            self.channel_list.horizontalHeader().blockSignals(True)

            # Restore previous valid sort
            self.channel_list.horizontalHeader().setSortIndicator(
                self.last_valid_sort_column,
                self.last_valid_sort_order
            )
            # Re-sort by the last valid column
            self.channel_list.sortByColumn(self.last_valid_sort_column, self.last_valid_sort_order)

            # Unblock signals
            self.channel_list.horizontalHeader().blockSignals(False)
            return

        # Valid sort - save it
        self.last_valid_sort_column = logical_index
        self.last_valid_sort_order = order
        self.save_sort_order(logical_index, order)

    def save_sort_order(self, logical_index, order):
        """Save sort column and order to config"""
        self.config['sort_column'] = logical_index
        self.config['sort_order'] = order  # Qt.AscendingOrder (0) or Qt.DescendingOrder (1)
        self.save_config()

    def toggle_column_visibility(self, column_index, visible):
        """Toggle visibility of a table column"""
        self.channel_list.setColumnHidden(column_index, not visible)

        # Save column visibility to config
        if 'column_visibility' not in self.config:
            self.config['column_visibility'] = {}
        self.config['column_visibility'][str(column_index)] = visible
        self.save_config()

    def update_all_epg_data(self):
        """Start async EPG update for all channels (non-blocking)"""
        if not self.servers:
            return

        total_channels = self.channel_list.rowCount()

        # Stop any currently running EPG update by setting a stop flag
        # The running update will check this flag and stop gracefully
        self.epg_update_stop_requested = True

        # Build queue of channels to update (UUID only, row will be found dynamically)
        self.epg_update_queue = []
        for row in range(total_channels):
            name_item = self.channel_list.item(row, 2)
            if name_item:
                channel_data = name_item.data(Qt.UserRole)
                if channel_data:
                    channel_uuid = channel_data.get('uuid')
                    channel_name = channel_data.get('name', 'Unknown')
                    if channel_uuid:
                        self.epg_update_queue.append((channel_uuid, channel_name))

        # Clear stop flag for this new update
        self.epg_update_stop_requested = False

        # Start async processing
        self.epg_update_index = 0
        self.epg_updated_count = 0
        self.update_next_epg()

    def update_next_epg(self):
        """Update EPG for next channel in queue (async, non-blocking)"""
        # Check if stop was requested (e.g., server changed)
        if hasattr(self, 'epg_update_stop_requested') and self.epg_update_stop_requested:
            print("Debug EPG: Update stopped (server changed)")
            return

        # Check if done (also check for empty queue in case it was cleared)
        if not self.epg_update_queue or self.epg_update_index >= len(self.epg_update_queue):
            if self.epg_updated_count > 0:  # Only show message if we actually updated something
                self.statusbar.showMessage(f"EPG data updated ({self.epg_updated_count} channels)")
            return

        # Get next channel from queue
        channel_uuid, channel_name = self.epg_update_queue[self.epg_update_index]
        self.epg_update_index += 1

        # Find the current row for this channel UUID
        row = None
        for r in range(self.channel_list.rowCount()):
            name_item = self.channel_list.item(r, 2)
            if name_item:
                channel_data = name_item.data(Qt.UserRole)
                if channel_data and channel_data.get('uuid') == channel_uuid:
                    row = r
                    break

        if row is None:
            print(f"Debug EPG: Could not find row for channel '{channel_name}' (UUID: {channel_uuid})")
            # Schedule next channel
            QTimer.singleShot(20, self.update_next_epg)
            return

        # Get server and auth
        try:
            server = self.servers[self.server_combo.currentIndex()]
            auth = None
            if server.get('username') or server.get('password'):
                auth = (server.get('username', ''), server.get('password', ''))

            now = int(time.time())
            epg_url = f'{server["url"]}/api/epg/events/grid'

            # Fetch EPG for this specific channel (same as show_channel_epg)
            params = {
                'channel': channel_uuid,
                'limit': 5  # Only need current + next program
            }

            response = session.get(epg_url, params=params, auth=auth, timeout=5)

            if response.status_code != 200:
                # Schedule next channel
                QTimer.singleShot(20, self.update_next_epg)
                return

            epg_entries = response.json().get('entries', [])

            if not epg_entries:
                # Schedule next channel
                QTimer.singleShot(20, self.update_next_epg)
                return

            # Sort by start time
            epg_entries.sort(key=lambda x: x.get('start', 0))

            # Find current and next program
            current_program = None
            next_program = None

            for entry in epg_entries:
                start_time = entry.get('start', 0)
                stop_time = entry.get('stop', 0)

                if start_time <= now < stop_time:
                    current_program = entry
                elif start_time > now and not next_program:
                    next_program = entry
                    break

            # Update current program column (column 3) with progress bar data
            current_item = self.channel_list.item(row, 3)
            if current_item is None:
                # Fallback: Create item if it doesn't exist (handles edge cases after table operations)
                current_item = QTableWidgetItem("")
                self.channel_list.setItem(row, 3, current_item)

            if current_item:
                if current_program:
                    title = self.get_epg_title(current_program)
                    # Store full data for progress bar delegate
                    current_item.setData(Qt.UserRole, {
                        'title': title,
                        'start': current_program['start'],
                        'stop': current_program['stop']
                    })
                    # IMPORTANT: Set empty text and DisplayRole so Delegate draws everything!
                    # If we set text here, Qt displays the text instead of calling the delegate
                    current_item.setText("")
                    current_item.setData(Qt.DisplayRole, "")  # Force delegate to paint
                    self.epg_updated_count += 1
                else:
                    current_item.setData(Qt.UserRole, None)
                    current_item.setText("")
                    current_item.setData(Qt.DisplayRole, "")

            # Update next program column (column 4) - single-line display (time + title)
            next_item = self.channel_list.item(row, 4)
            if next_item is None:
                # Fallback: Create item if it doesn't exist
                next_item = QTableWidgetItem("")
                self.channel_list.setItem(row, 4, next_item)

            if next_item:
                if next_program:
                    title = self.get_epg_title(next_program)
                    start_str = datetime.fromtimestamp(next_program['start']).strftime('%H:%M')
                    stop_str = datetime.fromtimestamp(next_program['stop']).strftime('%H:%M')
                    next_text = f"{start_str}-{stop_str}  {title}"
                    next_item.setText(next_text)
                else:
                    next_item.setText("")

        except Exception as e:
            # Log exceptions for troubleshooting (essential for development)
            print(f"Debug EPG: Exception for '{channel_name}': {str(e)}")
            import traceback
            traceback.print_exc()

        # Schedule next channel update (non-blocking)
        QTimer.singleShot(20, self.update_next_epg)

    def get_epg_title(self, epg_entry):
        """Extract title from EPG entry (handles both dict and string formats)"""
        title = epg_entry.get('title', 'No title')
        if isinstance(title, dict):
            return title.get('eng', title.get('ger', title.get('deu', 'No title')))
        return str(title)

    def get_server_icon_cache_dir(self, server):
        """Get server-specific icon cache directory"""
        # Create a safe directory name from server name and URL
        server_name = server.get('name', 'default')
        # Remove invalid filename characters and limit length
        safe_name = re.sub(r'[^\w\-_]', '_', server_name)[:50]
        server_dir = os.path.join(self.icon_cache_base_dir, safe_name)
        os.makedirs(server_dir, exist_ok=True)
        return server_dir

    def load_channel_icon(self, row, col, icon_url, server, from_cache_only=True):
        """Load and display channel icon from URL (cache-only by default for performance)"""
        try:
            # If icon_url is relative, make it absolute
            if icon_url.startswith('/'):
                base_url = server['url']
                if not base_url.startswith(('http://', 'https://')):
                    base_url = f"http://{base_url}"
                icon_url = f"{base_url}{icon_url}"

            # Get server-specific cache directory
            icon_cache_dir = self.get_server_icon_cache_dir(server)

            # Check cache first
            icon_filename = icon_url.split('/')[-1].split('?')[0]  # Remove query params
            cache_path = os.path.join(icon_cache_dir, icon_filename)

            # Only load from cache during initial table population
            if from_cache_only and not os.path.exists(cache_path):
                return False  # Icon not in cache, skip for now

            # Download icon if not cached (async mode only)
            if not os.path.exists(cache_path):
                auth = None
                if server.get('username') or server.get('password'):
                    auth = (server.get('username', ''), server.get('password', ''))

                response = session.get(icon_url, auth=auth, timeout=5)
                if response.status_code == 200:
                    with open(cache_path, 'wb') as f:
                        f.write(response.content)
                else:
                    return False

            # Load icon from cache and set it to the table item

            pixmap = QPixmap(cache_path)
            if not pixmap.isNull():
                # Don't pre-scale the pixmap - let QIcon handle it internally for better quality
                # QIcon will automatically scale to the size set via setIconSize()
                icon = QIcon(pixmap)

                # Get the item and set the icon
                item = self.channel_list.item(row, col)
                if item:
                    item.setIcon(icon)
                return True
            return False

        except Exception as e:
            return False

    def download_icons_async(self):
        """Download missing channel icons in the background"""
        if not self.servers:
            return

        server = self.servers[self.server_combo.currentIndex()]
        icons_to_download = []

        # Collect all icon URLs that need downloading
        for row in range(self.channel_list.rowCount()):
            icon_item = self.channel_list.item(row, 1)  # Column 1 now has icons
            if icon_item:
                channel_data = icon_item.data(Qt.UserRole)
                if channel_data:
                    icon_url = channel_data.get('icon_public_url') or channel_data.get('icon')
                    if icon_url:
                        icons_to_download.append((row, 1, icon_url, server))  # Column 1 for icons

        if not icons_to_download:
            return

        # Download icons one by one with small delay to avoid blocking
        self.icon_download_queue = icons_to_download
        self.icon_download_index = 0
        self.download_next_icon()

    def download_next_icon(self):
        """Download next icon from queue"""
        if self.icon_download_index >= len(self.icon_download_queue):
            return

        row, col, icon_url, server = self.icon_download_queue[self.icon_download_index]
        self.icon_download_index += 1

        # Load icon (will download if not cached)
        self.load_channel_icon(row, col, icon_url, server, from_cache_only=False)

        # Schedule next download with small delay (non-blocking)
        QTimer.singleShot(50, self.download_next_icon)

    def start_epg_update_timer(self):
        """Start timer for automatic EPG updates"""
        # Create timer for EPG updates (every 30 minutes - less frequent due to per-channel API calls)
        self.epg_update_timer = QTimer()
        self.epg_update_timer.timeout.connect(self.update_all_epg_data)
        self.epg_update_timer.start(1800000)  # 30 minutes in milliseconds

    def start_progress_refresh_timer(self):
        """Start timer to refresh progress bars (UI only, no API calls)"""
        self.progress_refresh_timer = QTimer()
        self.progress_refresh_timer.timeout.connect(self.refresh_progress_bars)
        self.progress_refresh_timer.start(60000)  # Update every 60 seconds

    def refresh_progress_bars(self):
        """Refresh progress bar display without fetching new data"""
        # Force repaint of column 3 (current program with progress bar)
        for row in range(self.channel_list.rowCount()):
            index = self.channel_list.model().index(row, 3)
            self.channel_list.update(index)


class EPGDialog(QDialog):
    def __init__(self, channel_name, epg_data, server, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"EPG Guide - {channel_name}")
        self.setModal(False)
        self.resize(800, 500)
        self.server = server
        self.channel_name = channel_name
        self.setup_ui(epg_data)

    def setup_ui(self, epg_data):
        layout = QVBoxLayout(self)

        # Create list widget for EPG entries
        self.epg_list = QListWidget()
        layout.addWidget(self.epg_list)

        # Add EPG entries to list with record buttons
        for entry in epg_data:
            # Create widget to hold program info and record button
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 2, 5, 2)
            # Get start and stop times
            start_time = datetime.fromtimestamp(entry['start']).strftime('%H:%M')
            stop_time = datetime.fromtimestamp(entry['stop']).strftime('%H:%M')

            # Get title and description
            if isinstance(entry.get('title'), dict):
                title = entry['title'].get('eng', 'No title')
            else:
                title = str(entry.get('title', 'No title'))

            if isinstance(entry.get('description'), dict):
                description = entry['description'].get('eng', 'No description')
            else:
                description = str(entry.get('description', 'No description'))

            # Create label for program info
            info_text = f"{start_time} - {stop_time}: {title}"
            info_label = QLabel(info_text)

            # Format tooltip with word-wrap and max-width for better readability
            tooltip_html = f'<p style="white-space: pre-wrap; max-width: 400px;">{description}</p>'
            info_label.setToolTip(tooltip_html)
            item_layout.addWidget(info_label, stretch=1)

            # Create record button with unicode icon
            record_btn = QPushButton("⏺")  # Unicode record symbol
            record_btn.setFixedWidth(32)  # Make button smaller since it's just an icon
            record_btn.setFixedHeight(32)  # Make it square
            record_btn.setStyleSheet("""
                QPushButton {
                    color: red;
                    font-size: 16px;
                    border: 1px solid #ccc;
                    border-radius: 16px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #f0f0f0;
                }
                QPushButton:pressed {
                    background-color: #e0e0e0;
                }
            """)
            record_btn.setToolTip("Schedule Recording")
            record_btn.clicked.connect(
                lambda checked, e=entry: self.schedule_recording(e))
            item_layout.addWidget(record_btn)

            # Create list item and set custom widget
            list_item = QListWidgetItem(self.epg_list)
            list_item.setSizeHint(item_widget.sizeHint())
            self.epg_list.addItem(list_item)
            self.epg_list.setItemWidget(list_item, item_widget)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def schedule_recording(self, entry):
        """Schedule a recording for the selected EPG entry"""
        try:
            print(f"Debug: Scheduling recording for: {entry.get('title', 'Unknown')}")

            # Create auth if needed
            auth = None
            if self.server.get('username') or self.server.get('password'):
                auth = (self.server.get('username', ''), self.server.get('password', ''))

            # Prepare recording request with proper language object structure
            conf_data = {
                "start": entry['start'],
                "stop": entry['stop'],
                "channel": entry['channelUuid'],
                "title": {
                    "eng": entry.get('title', 'Scheduled Recording')
                },
                "description": {
                    "eng": entry.get('description', '')
                },
                "comment": "Scheduled via TVHplayer"
            }

            # Convert to string format as expected by the API
            data = {'conf': json.dumps(conf_data)}
            print(f"Debug: Recording data: {data}")

            # Make recording request
            record_url = f'{self.server["url"]}/api/dvr/entry/create'
            print(f"Debug: Sending recording request to: {record_url}")

            response = requests.post(record_url, data=data, auth=auth)
            print(f"Debug: Recording response status: {response.status_code}")
            print(f"Debug: Recording response: {response.text}")

            if response.status_code == 200:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Recording scheduled successfully for {entry.get('title', 'Unknown')}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to schedule recording: {response.text}"
                )

        except Exception as e:
            print(f"Debug: Error scheduling recording: {str(e)}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to schedule recording: {str(e)}"
            )

class RecordingStatusDialog(QDialog):
    def __init__(self, channel_name, file_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recording Status")
        self.setModal(False)  # Allow interaction with main window
        self.resize(400, 200)
        self.setup_ui(channel_name, file_path)

    def setup_ui(self, channel_name, file_path):
        layout = QVBoxLayout(self)

        # Channel name
        channel_label = QLabel(f"Recording: {channel_name}")
        channel_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(channel_label)

        # File path
        path_label = QLabel(f"Saving to: {file_path}")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # Duration
        self.duration_label = QLabel("Duration: 00:00:00")
        layout.addWidget(self.duration_label)

        # File size
        self.size_label = QLabel("File size: 0 MB")
        layout.addWidget(self.size_label)

        # Status message
        self.status_label = QLabel("Status: Recording")
        self.status_label.setStyleSheet("color: green;")
        layout.addWidget(self.status_label)

        # Stop button
        stop_btn = QPushButton("Stop Recording")
        stop_btn.clicked.connect(self.stop_requested)
        layout.addWidget(stop_btn)

        # Start time for duration calculation
        self.start_time = time.time()

    def update_status(self, file_size, is_stalled=False):
        """Update the dialog with current recording status"""
        # Update duration
        duration = int(time.time() - self.start_time)
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        self.duration_label.setText(f"Duration: {hours:02d}:{minutes:02d}:{seconds:02d}")

        # Update file size
        size_mb = file_size / (1024 * 1024)  # Convert to MB
        self.size_label.setText(f"File size: {size_mb:.2f} MB")

        # Update status message
        if is_stalled:
            self.status_label.setText("Status: Stalled - Attempting recovery")
            self.status_label.setStyleSheet("color: orange;")
        else:
            self.status_label.setText("Status: Recording")
            self.status_label.setStyleSheet("color: green;")

    def stop_requested(self):
        """Signal that user wants to stop recording"""
        self.accept()

def main():
    """Main entry point for the application"""
    try:
        # Enable High-DPI scaling for sharp icons and UI
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        # Force the application to use XCB instead of Wayland
        # This helps with VLC integration under Wayland
        QCoreApplication.setAttribute(Qt.AA_X11InitThreads, True)
        os.environ["QT_QPA_PLATFORM"] = "xcb"

        app = QApplication(sys.argv)
        player = TVHeadendClient()
        player.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error starting application: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == '__main__':
    main()
