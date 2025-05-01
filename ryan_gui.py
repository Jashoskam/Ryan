import sys
import requests
import json
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QTextEdit, QComboBox,
                               QLabel, QFileDialog, QSplitter, QFrame, QSizePolicy,
                               QMessageBox, QInputDialog, QLineEdit, QStackedWidget,
                               QListWidget, QListWidgetItem, QDialog, QDialogButtonBox)
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QTextDocument, QIcon, QTextCursor # Import QTextCursor
from PySide6.QtCore import Qt, QRegularExpression, QThread, Signal, QTimer, QObject
import traceback

# Base URL for your local FastAPI backend
# Make sure your ryan.py script is running (e.g., `uvicorn ryan:app --reload`)
API_BASE_URL = "http://127.0.0.1:8000"

# --- Worker Thread for API Requests ---
# This class does NOT need to be indented under RyanCodingApp
class ApiWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, endpoint, data=None, method='POST'):
        super().__init__()
        self.endpoint = endpoint
        self.data = data
        self.method = method
        self._is_running = True

    def run(self):
        url = f"{API_BASE_URL}/{self.endpoint}"
        # print(f"DEBUG: ApiWorker: Sending {self.method} request to {url}") # DEBUG PRINT
        try:
            if self.method == 'POST':
                response = requests.post(url, json=self.data)
            elif self.method == 'GET':
                response = requests.get(url)
            elif self.method == 'PUT':
                 response = requests.put(url, json=self.data)
            elif self.method == 'DELETE':
                 response = requests.delete(url)
            else:
                 # This error should now be caught before reaching requests.post
                 raise ValueError(f"Unsupported HTTP method: {self.method}")

            # print(f"DEBUG: ApiWorker: Received response with status code {response.status_code}") # DEBUG PRINT
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            result = response.json()
            # print(f"DEBUG: ApiWorker: Successfully parsed JSON response.") # DEBUG PRINT
            if self._is_running:
                self.finished.emit(result)
        except requests.exceptions.RequestException as e:
            # print(f"DEBUG: ApiWorker: RequestException caught: {e}") # DEBUG PRINT
            if self._is_running:
                error_message = f"API Request Error to /{self.endpoint} ({self.method}): {e}"
                if e.response is not None:
                     try:
                          error_details = e.response.json()
                          if "detail" in error_details:
                               detail_content = error_details["detail"]
                               if isinstance(detail_content, dict) and 'content' in detail_content:
                                    error_message += f"\nBackend Detail: {detail_content['content']}"
                               elif isinstance(detail_content, str):
                                    error_message += f"\nBackend Detail: {detail_content}"
                               else:
                                     error_message += f"\nBackend returned status code {e.response.status_code} with unstructured detail."
                          else:
                               error_message += f"\nBackend returned status code {e.response.status_code} with no detail."
                     except json.JSONDecodeError:
                          error_message += f"\nBackend returned status code {e.response.status_code} with non-JSON error."
                self.error.emit(error_message)
        except Exception as e:
            # print(f"DEBUG: ApiWorker: Unexpected exception caught: {e}") # DEBUG PRINT
            if self._is_running:
                self.error.emit(f"An unexpected error occurred: {e}")

    def stop(self):
        self._is_running = False
        self.wait()


# --- Simple Syntax Highlighter ---
# This class does NOT need to be indented under RyanCodingApp
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Using Atom One Dark colors
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#c678dd")) # Purple
        keyword_patterns = ["\\bFalse\\b", "\\bNone\\b", "\\bTrue\\b", "\\band\\b", "\\bas\\b", "\\bassert\\b",
                            "\\basync\\b", "\\bawait\\b", "\\bbreak\\b", "\\bclass\\b", "\\bcontinue\\b",
                            "\\bdef\\b", "\\bdel\\b", "\\belif\\b", "\\belse\\b", "\\bexcept\\b", "\\bfinally\\b",
                            "\\bfor\\b", "\\bfrom\\b", "\\bglobal\\b", "\\bif\\b", "\\bin\\b", "\\bis\\b",
                            "\\blambda\\b", "\\bnonlocal\\b", "\\bnot\\b", "\\bor\\b", "\\bpass\\b",
                            "\\braise\\b", "\\breturn\\b", "\\btry\\b", "\\bwhile\\b", "\\bwith\\b", "\\byield\\b"]

        self.highlighting_rules = [(QRegularExpression(pattern), keyword_format)
                                   for pattern in keyword_patterns]

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#98c379")) # Green
        self.highlighting_rules.append((QRegularExpression("\"(?:\\\\[^\n]|[^\"\n])*\""), string_format))
        self.highlighting_rules.append((QRegularExpression("'[^'\n]*'"), string_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#5c6370")) # Grey
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((QRegularExpression("#[^\n]*"), comment_format))

        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#61afef")) # Blue
        self.highlighting_rules.append((QRegularExpression("\\b[A-Za-z0-9_]+(?=\\()"), function_format))

        # Add number highlighting
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#d19a66")) # Orange
        self.highlighting_rules.append((QRegularExpression("\\b[0-9]+\\.?[0-9]*\\b"), number_format))


    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

# --- Main Application Window ---
# >>> Start of RyanCodingApp class definition <<<
# This line should be at the very left margin (no indentation)
class RyanCodingApp(QMainWindow):
    # >>> Start of __init__ method <<<
    # This line should be indented 4 spaces (or 1 tab) from the 'class' line
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Ryan - Coding Genius")
        self.setGeometry(100, 100, 1200, 800)

        # Apply dark theme background to the main window
        self.setStyleSheet("QMainWindow { background-color: #0d0d0d; color: #e0e0e0; }")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- Sidebar ---
        self.sidebar = QFrame()
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 15, 10, 15)
        self.sidebar_layout.setSpacing(15)
        self.sidebar.setFixedWidth(60)
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a; /* Dark sidebar background */
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                box-shadow: 2px 0 15px rgba(0, 0, 0, 0.6);
            }
            QPushButton {
                background: none;
                border: none;
                color: #e0e0e0; /* Light text */
                font-size: 1.2em;
                padding: 10px 0px;
                border-radius: 8px;
                text-align: left;
            }
            QPushButton:hover {
                background: #3a3a3a; /* Darker hover */
                color: #ffffff; /* White text on hover */
            }
        """)
        self.main_layout.addWidget(self.sidebar)

        # AI Orb Placeholder (using a simple colored circle)
        self.ai_orb_placeholder = QFrame()
        self.ai_orb_placeholder.setFixedSize(50, 50)
        # Using the vibrant blue from the HTML orb
        self.ai_orb_placeholder.setStyleSheet("QFrame { background-color: #0077ff; border-radius: 25px; }")
        self.sidebar_layout.addWidget(self.ai_orb_placeholder, alignment=Qt.AlignCenter)

        self.chat_button = QPushButton(QIcon.fromTheme("mail-message-new"), "")
        self.chat_button.setToolTip("Chat")
        self.chat_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.sidebar_layout.addWidget(self.chat_button)

        self.code_button = QPushButton(QIcon.fromTheme("applications-development"), "")
        self.code_button.setToolTip("Code Editor")
        self.code_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        self.sidebar_layout.addWidget(self.code_button)

        self.memory_button = QPushButton(QIcon.fromTheme("document-properties"), "")
        self.memory_button.setToolTip("Memory")
        self.memory_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        self.memory_button.clicked.connect(self.load_memory)
        self.sidebar_layout.addWidget(self.memory_button)

        self.logs_button = QPushButton(QIcon.fromTheme("utilities-terminal"), "")
        self.logs_button.setToolTip("Logs")
        self.logs_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(3))
        self.logs_button.clicked.connect(self.load_logs)
        self.sidebar_layout.addWidget(self.logs_button)

        self.settings_button = QPushButton(QIcon.fromTheme("preferences-system"), "")
        self.settings_button.setToolTip("Settings")
        self.settings_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(4))
        self.sidebar_layout.addWidget(self.settings_button)

        self.sidebar_layout.addStretch()

        # --- Main Content Area (Stacked Widget) ---
        self.main_content_frame = QFrame()
        self.main_content_layout = QVBoxLayout(self.main_content_frame)
        self.main_content_layout.setContentsMargins(10, 10, 10, 10)
        self.main_content_layout.setSpacing(10)
        # Using the main background color from HTML
        self.main_content_frame.setStyleSheet("QFrame { background-color: #0d0d0d; }")

        self.stacked_widget = QStackedWidget()
        self.main_content_layout.addWidget(self.stacked_widget)
        self.main_layout.addWidget(self.main_content_frame)

        # --- Pages for the Stacked Widget ---

        # 0: Chat Page
        self.chat_page = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_page)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(10)

        self.chat_history_display = QTextEdit()
        self.chat_history_display.setReadOnly(True)
        self.chat_history_display.setFont(QFont("Inter", 10))
        self.chat_history_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e; /* Darker background for chat history */
                color: #e0e0e0; /* Light text */
                border: none;
                padding: 10px;
                border-radius: 8px;
            }
        """)
        self.chat_layout.addWidget(self.chat_history_display)

        self.chat_input_frame_page = QFrame()
        self.chat_input_layout_page = QHBoxLayout(self.chat_input_frame_page)
        self.chat_input_layout_page.setContentsMargins(5, 5, 5, 5)
        self.chat_input_layout_page.setSpacing(5)
        # Using a slightly different background for the input frame
        self.chat_input_frame_page.setStyleSheet("QFrame { background-color: #3a404a; border-radius: 8px; }")

        self.chat_input_line_page = QLineEdit()
        self.chat_input_line_page.setPlaceholderText("Type a message...")
        self.chat_input_line_page.setFont(QFont("Inter", 10))
        self.chat_input_line_page.setStyleSheet("""
            QLineEdit {
                background-color: #1e2127; /* Input field background */
                color: #abb2bf; /* Text color */
                selection-background-color: #4e5a65;
                border: none;
                padding: 5px;
                border-radius: 4px;
            }
        """)
        # Connect returnPressed signal to send_chat_instruction
        self.chat_input_line_page.returnPressed.connect(self.send_chat_instruction)
        self.chat_input_layout_page.addWidget(self.chat_input_line_page)

        self.send_chat_button_page = QPushButton("Send")
        # Connect clicked signal to send_chat_instruction
        self.send_chat_button_page.clicked.connect(self.send_chat_instruction)
        self.send_chat_button_page.setStyleSheet("""
            QPushButton {
                background-color: #0077ff; /* Blue button */
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0055cc; /* Darker blue on hover */
            }
            QPushButton:pressed {
                background-color: #0077ff;
            }
            QPushButton:disabled {
                background-color: #5c6370; /* Grey when disabled */
                color: #abb2bf; /* Lighter grey text when disabled */
            }
        """)
        self.chat_input_layout_page.addWidget(self.send_chat_button_page)

        self.chat_layout.addWidget(self.chat_input_frame_page)
        self.stacked_widget.addWidget(self.chat_page)

        # 1: Code Editor Page
        self.code_page = QWidget()
        self.code_page_layout = QVBoxLayout(self.code_page)
        self.code_page_layout.setContentsMargins(0, 0, 0, 0)
        self.code_page_layout.setSpacing(10)

        # --- Splitter for Code and Results Areas ---
        self.splitter = QSplitter(Qt.Vertical)

        # --- Code Area Frame ---
        self.code_frame = QFrame()
        self.code_layout = QVBoxLayout(self.code_frame)
        self.code_layout.setContentsMargins(0, 0, 0, 0)
        self.code_layout.setSpacing(5)
        # Using a dark background for the code area frame
        self.code_frame.setStyleSheet("QFrame { background-color: #282c34; border-radius: 8px; }")

        # Controls Frame (matching chat input frame style)
        self.controls_frame = QFrame()
        self.controls_layout = QHBoxLayout(self.controls_frame)
        self.controls_layout.setContentsMargins(10, 5, 10, 5)
        self.controls_layout.setSpacing(10)
        self.controls_frame.setStyleSheet("QFrame { background-color: #3a404a; border-top-left-radius: 8px; border-top-right-radius: 8px; }")

        self.language_combo = QComboBox()
        self.language_combo.addItems(["python", "javascript", "java", "cpp", "c", "ruby", "go", "unknown"])
        self.language_combo.setStyleSheet("""
            QComboBox {
                background-color: #5c6370; /* Grey background */
                color: #abb2bf; /* Light grey text */
                padding: 5px;
                border-radius: 4px;
                border: 1px solid #5c6370;
            }
            QComboBox::drop-down { border: 0px; }
            QComboBox QAbstractItemView {
                background-color: #5c6370;
                color: #abb2bf;
                selection-background-color: #636b78;
            }
        """)
        self.controls_layout.addWidget(self.language_combo)

        self.load_button = QPushButton("Load File")
        self.load_button.clicked.connect(self.load_code_file)
        self.load_button.setStyleSheet("""
            QPushButton {
                background-color: #5c6370; /* Grey button */
                color: #abb2bf; /* Light grey text */
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #636b78; } /* Darker grey on hover */
            QPushButton:pressed { background-color: #5c6370; }
        """)
        self.controls_layout.addWidget(self.load_button)

        self.save_button = QPushButton("Save Code")
        self.save_button.clicked.connect(self.save_code_file)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #5c6370; /* Grey button */
                color: #abb2bf; /* Light grey text */
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #636b78; } /* Darker grey on hover */
            QPushButton:pressed { background-color: #5c6370; }
        """)
        self.controls_layout.addWidget(self.save_button)

        self.clear_button = QPushButton("Clear Code")
        self.clear_button.clicked.connect(self.clear_code_area)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #5c6370; /* Grey button */
                color: #abb2bf; /* Light grey text */
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #636b78; } /* Darker grey on hover */
            QPushButton:pressed { background-color: #5c6370; }
        """)
        self.controls_layout.addWidget(self.clear_button)
        self.controls_layout.addStretch()

        self.code_layout.addWidget(self.controls_frame)

        self.code_input = QTextEdit()
        self.code_input.setFont(QFont("Consolas", 12)) # Consolas is a good coding font
        self.code_input.setStyleSheet("""
            QTextEdit {
                background-color: #1e2127; /* Dark background */
                color: #abb2bf; /* Light grey text */
                selection-background-color: #4e5a65;
                border: none;
                padding: 10px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        self.code_highlighter = PythonHighlighter(self.code_input.document()) # Apply highlighter
        self.code_layout.addWidget(self.code_input)
        self.splitter.addWidget(self.code_frame)

        # --- Results Area Frame ---
        self.results_frame = QFrame()
        self.results_layout = QVBoxLayout(self.results_frame)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(5)
        # Using a dark background for the results area frame
        self.results_frame.setStyleSheet("QFrame { background-color: #282c34; border-radius: 8px; }")

        self.results_header = QLabel("Results")
        # Matching controls frame header style
        self.results_header.setStyleSheet("""
            QLabel {
                background-color: #3a404a; /* Dark header background */
                color: #abb2bf; /* Light grey text */
                padding: 5px 10px;
                font-weight: bold;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
        """)
        self.results_layout.addWidget(self.results_header)

        self.results_display = QTextEdit()
        self.results_display.setFont(QFont("Consolas", 10))
        self.results_display.setReadOnly(True)
        self.results_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e2127; /* Dark background */
                color: #abb2bf; /* Light grey text */
                border: none;
                padding: 10px;
                 border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        self.results_highlighter = PythonHighlighter(self.results_display.document()) # Apply highlighter
        self.results_layout.addWidget(self.results_display)
        self.splitter.addWidget(self.results_frame)
        self.splitter.setSizes([500, 300]) # Set initial sizes for splitter panes

        self.code_page_layout.addWidget(self.splitter)

        # --- Actions Frame (matching code area frame style) ---
        self.actions_frame = QFrame()
        self.actions_layout = QHBoxLayout(self.actions_frame)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(10)
        self.actions_frame.setStyleSheet("QFrame { background-color: #282c34; padding: 10px; border-radius: 8px; }")

        # Buttons with colors matching Atom One Dark theme
        self.run_button = QPushButton("Run Code")
        self.run_button.clicked.connect(self.run_code)
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #61afef; /* Blue */
                color: #282c34; /* Dark text */
                padding: 8px 15px;
                border-radius: 4px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #52a2e0; } /* Darker blue on hover */
            QPushButton:pressed { background-color: #61afef; }
        """)
        self.actions_layout.addWidget(self.run_button)

        self.debug_button = QPushButton("Debug Code")
        self.debug_button.clicked.connect(self.debug_code)
        self.debug_button.setStyleSheet("""
            QPushButton {
                background-color: #e5c07b; /* Yellow */
                color: #282c34; /* Dark text */
                padding: 8px 15px;
                border-radius: 4px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d9b672; } /* Darker yellow on hover */
            QPushButton:pressed { background-color: #e5c07b; }
        """)
        self.actions_layout.addWidget(self.debug_button)

        self.analyze_button = QPushButton("Analyze Code")
        self.analyze_button.clicked.connect(self.analyze_code)
        self.analyze_button.setStyleSheet("""
            QPushButton {
                background-color: #98c379; /* Green */
                color: #282c34; /* Dark text */
                padding: 8px 15px;
                border-radius: 4px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #8acb6d; } /* Darker green on hover */
            QPushButton:pressed { background-color: #98c379; }
        """)
        self.actions_layout.addWidget(self.analyze_button)

        self.fix_button = QPushButton("Fix Code")
        self.fix_button.clicked.connect(self.fix_code)
        self.fix_button.setStyleSheet("""
            QPushButton {
                background-color: #c678dd; /* Purple */
                color: #282c34; /* Dark text */
                padding: 8px 15px;
                border-radius: 4px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #b96ac0; } /* Darker purple on hover */
            QPushButton:pressed { background-color: #c678dd; }
        """)
        self.actions_layout.addWidget(self.fix_button)
        self.actions_layout.addStretch()

        self.code_page_layout.addWidget(self.actions_frame)
        self.stacked_widget.addWidget(self.code_page)

        # 2: Memory Page
        self.memory_page = QWidget()
        self.memory_layout = QVBoxLayout(self.memory_page)
        self.memory_layout.setContentsMargins(10, 10, 10, 10)
        self.memory_layout.setSpacing(10)

        self.memory_list_widget = QListWidget()
        self.memory_list_widget.setFont(QFont("Inter", 10))
        self.memory_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e; /* Dark background */
                color: #e0e0e0; /* Light text */
                border: none;
                padding: 10px;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 8px;
                margin-bottom: 5px;
                border-bottom: 1px solid #333; /* Dark border between items */
            }
            QListWidget::item:selected {
                 background-color: #3a3a3a; /* Darker background for selected item */
                 color: #ffffff; /* White text for selected item */
            }
        """)
        self.memory_list_widget.itemDoubleClicked.connect(self.edit_memory_item)
        self.memory_layout.addWidget(self.memory_list_widget)

        # Memory Actions Frame (matching code area frame style)
        self.memory_actions_frame = QFrame()
        self.memory_actions_layout = QHBoxLayout(self.memory_actions_frame)
        self.memory_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.memory_actions_layout.setSpacing(10)
        self.memory_actions_frame.setStyleSheet("QFrame { background-color: #282c34; padding: 10px; border-radius: 8px; }")

        self.refresh_memory_button = QPushButton("Refresh Memory")
        self.refresh_memory_button.clicked.connect(self.load_memory)
        self.refresh_memory_button.setStyleSheet("""
            QPushButton {
                background-color: #5c6370; /* Grey button */
                color: #abb2bf; /* Light grey text */
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #636b78; } /* Darker grey on hover */
        """)
        self.memory_actions_layout.addWidget(self.refresh_memory_button)

        self.delete_memory_button = QPushButton("Delete Selected")
        self.delete_memory_button.clicked.connect(self.delete_memory_item)
        self.delete_memory_button.setStyleSheet("""
            QPushButton {
                background-color: #e06c75; /* Red */
                color: #282c34; /* Dark text */
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #c05a65; } /* Darker red on hover */
        """)
        self.memory_actions_layout.addWidget(self.delete_memory_button)
        self.memory_actions_layout.addStretch()
        self.memory_layout.addWidget(self.memory_actions_frame)
        self.stacked_widget.addWidget(self.memory_page)

        # 3: Logs Page
        self.logs_page = QWidget()
        self.logs_layout = QVBoxLayout(self.logs_page)
        self.logs_layout.setContentsMargins(10, 10, 10, 10)
        self.logs_layout.setSpacing(10)

        self.logs_display = QTextEdit()
        self.logs_display.setReadOnly(True)
        self.logs_display.setFont(QFont("Consolas", 10))
        self.logs_display.setStyleSheet("""
            QTextEdit {
                background-color: #1c1c1c; /* Very dark background for logs */
                color: #b0b0b0; /* Lighter grey text */
                border: none;
                padding: 10px;
                border-radius: 8px;
            }
        """)
        self.logs_layout.addWidget(self.logs_display)

        # Logs Actions Frame (matching code area frame style)
        self.logs_actions_frame = QFrame()
        self.logs_actions_layout = QHBoxLayout(self.logs_actions_frame)
        self.logs_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.logs_actions_layout.setSpacing(10)
        self.logs_actions_frame.setStyleSheet("QFrame { background-color: #282c34; padding: 10px; border-radius: 8px; }")

        self.refresh_logs_button = QPushButton("Refresh Logs")
        self.refresh_logs_button.clicked.connect(self.load_logs)
        self.refresh_logs_button.setStyleSheet("""
            QPushButton {
                background-color: #5c6370; /* Grey button */
                color: #abb2bf; /* Light grey text */
                padding: 5px 10px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #636b78; } /* Darker grey on hover */
        """)
        self.logs_actions_layout.addWidget(self.refresh_logs_button)
        self.logs_actions_layout.addStretch()
        self.logs_layout.addWidget(self.logs_actions_frame)
        self.stacked_widget.addWidget(self.logs_page)

        # 4: Settings Page
        self.settings_page = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_page)
        self.settings_layout.setContentsMargins(10, 10, 10, 10)
        self.settings_layout.setSpacing(10)

        self.settings_label = QLabel("Settings (Placeholder)")
        self.settings_label.setStyleSheet("QLabel { color: #abb2bf; font-size: 1.2em; }")
        self.settings_layout.addWidget(self.settings_label)
        self.settings_layout.addStretch()

        self.stacked_widget.addWidget(self.settings_page)

        # --- Status Bar ---
        self.statusBar = self.statusBar()
        self.statusBar.setStyleSheet("QStatusBar { background-color: #3a404a; color: #abb2bf; }")
        self.statusBar.showMessage("Ready")

        # --- Worker Thread Instance ---
        self.api_worker = None

        # --- Typing Animation Variables ---
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self.type_next_char)
        self.current_typing_text = ""
        self.typing_index = 0
        self.typing_target_text_edit = None # Reference to the QTextEdit being typed into

        # Set initial page to Code Editor
        self.stacked_widget.setCurrentIndex(1)

    # >>> Start of Helper and Interaction Methods <<<
    # These methods MUST be indented at the same level as __init__

    # Start of update_results method
    def update_results(self, message, message_type="info"):
        """Appends a message to the results/chat display with basic styling."""
        # Stop typing animation if a new message is being added directly
        self.stop_typing_animation()

        if message_type == "info":
            color = "#abb2bf" # Light grey
        elif message_type == "success":
            color = "#98c379" # Green
        elif message_type == "error":
            color = "#e06c75" # Red
        elif message_type == "code":
             # For code, just append directly without typing effect
             self.results_display.append(f"<pre>{message}</pre>")
             self.results_display.verticalScrollBar().setValue(self.results_display.verticalScrollBar().maximum())
             return
        elif message_type == "user_chat":
             # User messages in chat history
             self.chat_history_display.append(f"<p style='color: #61afef; margin: 5px 0;'><b>You:</b> {message}</p>")
             self.chat_history_display.verticalScrollBar().setValue(self.chat_history_display.verticalScrollBar().maximum())
             return
        elif message_type == "ryan_chat":
             # Ryan's messages in chat history - start typing animation
             # We don't append the message here, the typing animation will do it
             self.start_typing_animation(self.chat_history_display, message)
             return

        # Default behavior for messages in the results area (Code page)
        self.results_display.append(f"<span style='color: {color};'>{message}</span>")
        self.results_display.verticalScrollBar().setValue(self.results_display.verticalScrollBar().maximum())
    # End of update_results method

    # Start of typing animation methods
    def start_typing_animation(self, text_edit_widget, text):
        """Starts the typing animation in the specified QTextEdit."""
        self.stop_typing_animation() # Stop any existing animation

        self.typing_target_text_edit = text_edit_widget
        self.current_typing_text = text
        self.typing_index = 0

        # Append the 'Ryan:' prefix immediately
        self.typing_target_text_edit.append(f"<p style='color: #c678dd; margin: 5px 0;'><b>Ryan:</b> ")
        self.typing_target_text_edit.verticalScrollBar().setValue(self.typing_target_text_edit.verticalScrollBar().maximum())

        # Start the timer to type character by character
        # Adjust the interval (milliseconds) for typing speed
        self.typing_timer.start(20) # Type a character every 20ms (adjust as needed)

    def type_next_char(self):
        """Types the next character of the current_typing_text."""
        if self.typing_index < len(self.current_typing_text):
            next_char = self.current_typing_text[self.typing_index]
            # Use insertHtml to append the character within the current paragraph
            # This is a bit tricky with HTML formatting, simple text is easier.
            # For simplicity, let's just append text for now.
            # A more robust solution would parse the text for HTML tags.

            # Get the current cursor position
            cursor = self.typing_target_text_edit.textCursor()
            # Move to the end of the document using QTextCursor.End (CORRECTED)
            cursor.movePosition(QTextCursor.End)
            # Insert the next character
            cursor.insertText(next_char)
            # Set the updated cursor back to the text edit
            self.typing_target_text_edit.setTextCursor(cursor)


            self.typing_index += 1
            # Ensure the scrollbar follows the typing
            self.typing_target_text_edit.verticalScrollBar().setValue(self.typing_target_text_edit.verticalScrollBar().maximum())
        else:
            # Animation finished, stop the timer and add closing paragraph tag
            self.stop_typing_animation()
            cursor = self.typing_target_text_edit.textCursor()
            cursor.movePosition(QTextCursor.End) # Use QTextCursor.End (CORRECTED)
            cursor.insertHtml("</p>") # Close the paragraph tag
            self.typing_target_text_edit.setTextCursor(cursor)
            self.typing_target_text_edit.verticalScrollBar().setValue(self.typing_target_text_edit.verticalScrollBar().maximum())


    def stop_typing_animation(self):
        """Stops the current typing animation."""
        if self.typing_timer.isActive():
            self.typing_timer.stop()
            # Ensure any remaining text is displayed if animation was interrupted
            if self.typing_index < len(self.current_typing_text) and self.typing_target_text_edit:
                 remaining_text = self.current_typing_text[self.typing_index:]
                 cursor = self.typing_target_text_edit.textCursor()
                 cursor.movePosition(QTextCursor.End) # Use QTextCursor.End (CORRECTED)
                 cursor.insertText(remaining_text)
                 cursor.insertHtml("</p>") # Add closing paragraph tag
                 self.typing_target_text_edit.setTextCursor(cursor)
                 self.typing_target_text_edit.verticalScrollBar().setValue(self.typing_target_text_edit.verticalScrollBar().maximum())

            self.current_typing_text = ""
            self.typing_index = 0
            self.typing_target_text_edit = None
    # End of typing animation methods


    # Start of load_code_file method
    def load_code_file(self):
        """Opens a file dialog and loads the selected file's content into the code editor."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Code File", "",
            "Code Files (*.py *.js *.java *.cpp *.c *.rb *.go *.txt);;All Files (*)"
        )
        if not filepath:
            return

        try:
            with open(filepath, "r") as file:
                code_content = file.read()
            self.code_input.setPlainText(code_content)
            self.update_results(f"Loaded file: {os.path.basename(filepath)}", "success")

            file_extension = os.path.splitext(filepath)[1].lower()
            language_map = {
                ".py": "python", ".js": "javascript", ".java": "java",
                ".cpp": "cpp", ".c": "c", ".rb": "ruby", ".go": "go"
            }
            guessed_language = language_map.get(file_extension, "unknown")
            self.language_combo.setCurrentText(guessed_language)
            self.update_results(f"Guessed language: {guessed_language}", "info")

        except Exception as e:
            self.update_results(f"Error loading file: {e}", "error")
            QMessageBox.critical(self, "Error Loading File", f"Failed to load file:\n{e}")
    # End of load_code_file method

    # Start of save_code_file method
    def save_code_file(self):
        """Opens a file dialog and saves the current code editor content to a file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Code", "",
            "Code Files (*.py *.js *.java *.cpp *.c *.rb *.go *.txt);;All Files (*)"
        )
        if not filepath:
            return

        try:
            code_content = self.code_input.toPlainText()
            with open(filepath, "w") as file:
                file.write(code_content)
            self.update_results(f"Saved code to: {os.path.basename(filepath)}", "success")
        except Exception as e:
            self.update_results(f"Error saving file: {e}", "error")
            QMessageBox.critical(self, "Error Saving File", f"Failed to save file:\n{e}")
    # End of save_code_file method

    # Start of clear_code_area method
    def clear_code_area(self):
        self.code_input.clear()
        self.update_results("Code area cleared.", "info")
    # End of clear_code_area method


    # --- Backend Interaction Functions ---
    # Start of send_request method
    def send_request(self, endpoint, data=None, method='POST', result_callback=None, error_callback=None):
        # Stop typing animation if a new request is sent (e.g., user sends another message)
        self.stop_typing_animation()

        if self.api_worker and self.api_worker.isRunning():
            self.update_results("A request is already in progress. Please wait.", "info")
            return

        self.statusBar.showMessage(f"Sending request to /{endpoint}...")
        self.set_input_enabled(False)

        # print(f"DEBUG: send_request: Received method: {method} (Type: {type(method)})") # DEBUG PRINT

        self.api_worker = ApiWorker(endpoint, data, method)
        if result_callback:
            self.api_worker.finished.connect(result_callback)
            # print(f"DEBUG: send_request: Connected finished signal to {result_callback.__name__}") # DEBUG PRINT
        if error_callback:
             self.api_worker.error.connect(error_callback)
             # print(f"DEBUG: send_request: Connected error signal to {error_callback.__name__}") # DEBUG PRINT
        else:
             # Default error handling if no specific callback is provided
             self.api_worker.error.connect(lambda msg: self.update_results(msg, "error"))
             # print("DEBUG: send_request: Connected error signal to default handler") # DEBUG PRINT


        # Connect a slot to update status bar and re-enable input on completion/error
        self.api_worker.finished.connect(lambda: self.statusBar.showMessage("Request completed."))
        self.api_worker.error.connect(lambda: self.statusBar.showMessage("Request failed."))
        self.api_worker.finished.connect(lambda: self.set_input_enabled(True)) # Re-enable on finish
        self.api_worker.error.connect(lambda: self.set_input_enabled(True))   # Re-enable on error

        # print(f"DEBUG: send_request: Starting ApiWorker thread for endpoint /{endpoint}") # DEBUG PRINT
        self.api_worker.start()
    # End of send_request method

    # Start of set_input_enabled method
    def set_input_enabled(self, enabled):
        self.chat_input_line_page.setEnabled(enabled)
        self.send_chat_button_page.setEnabled(enabled)
        self.run_button.setEnabled(enabled)
        self.debug_button.setEnabled(enabled)
        self.analyze_button.setEnabled(enabled)
        self.fix_button.setEnabled(enabled)
        self.refresh_memory_button.setEnabled(enabled)
        self.delete_memory_button.setEnabled(enabled)
        self.refresh_logs_button.setEnabled(enabled)
    # End of set_input_enabled method

    # Start of run_code method
    def run_code(self):
        """Gets code and language, sends to backend /execute_code endpoint, displays results."""
        code_string = self.code_input.toPlainText().strip()
        language = self.language_combo.currentText()

        if not code_string:
            self.update_results("Please enter code to run.", "info")
            return

        data = {"code": code_string, "language": language}
        self.send_request("execute_code", data, self.handle_code_execution_result)
    # End of run_code method


    # Start of handle_code_execution_result method
    def handle_code_execution_result(self, response):
        # print(f"DEBUG: handle_code_execution_result called with response: {response}") # DEBUG PRINT
        self.update_results("--- Code Execution Result ---", "info")
        if response.get("type") == "code_execution_result":
            success = response.get("success")
            output = response.get("output", "")
            error = response.get("error", "")
            return_code = response.get("return_code")

            self.update_results(f"Success: {success}", "success" if success else "error")
            self.update_results(f"Return Code: {return_code}", "info")
            if output:
                self.update_results("--- STDOUT ---", "info")
                self.update_results(output, "code")
            if error:
                self.update_results("--- STDERR ---", "error")
                self.update_results(error, "error")
        elif response.get("type") == "error":
             pass # Error handled by default error callback
        else:
            self.update_results(f"Received unexpected response type: {response.get('type')}", "error")
            self.update_results(json.dumps(response, indent=2), "error")
    # End of handle_code_execution_result method

    # Start of debug_code method
    def debug_code(self):
        """Gets code and language, prompts for error, sends to /debug_code, displays suggestion."""
        code_string = self.code_input.toPlainText().strip()
        language = self.language_combo.currentText()

        if not code_string:
            self.update_results("Please enter code to debug.", "info")
            return

        error_output, ok = QInputDialog.getMultiLineText(
            self, "Enter Error Output", "Paste the error output from your code execution:"
        )

        if not ok or not error_output:
            self.update_results("No error output provided for debugging.", "info")
            return

        data = {"code": code_string, "error_output": error_output, "language": language}
        self.send_request("debug_code", data, self.handle_debug_result)
    # End of debug_code method

    # Start of handle_debug_result method
    def handle_debug_result(self, response):
        # print(f"DEBUG: handle_debug_result called with response: {response}") # DEBUG PRINT
        self.update_results("--- AI Debug Suggestion ---", "info")
        if response.get("type") == "ai_debug_result":
            suggestion = response.get("suggestion", "No suggestion provided.")
            corrected_code = response.get("corrected_code")

            self.update_results(f"Suggestion: {suggestion}", "info")
            if corrected_code:
                self.update_results("--- Corrected Code ---", "info")
                self.update_results(corrected_code, "code")
        elif response.get("type") == "error":
             pass # Error handled by default error callback
        else:
            self.update_results(f"Received unexpected response type: {response.get('type')}", "error")
            self.update_results(json.dumps(response, indent=2), "error")
    # End of handle_debug_result method

    # Start of analyze_code method
    def analyze_code(self):
        """Gets code and language, optionally prompts for task, sends to /analyze_code, displays analysis."""
        code_string = self.code_input.toPlainText().strip()
        language = self.language_combo.currentText()

        if not code_string:
            self.update_results("Please enter code to analyze.", "info")
            return

        task_description, ok = QInputDialog.getText(
            self, "Analysis Task", "Enter analysis task (optional, e.g., 'Explain this function'):"
        )

        if not ok:
            task_description = ""

        data = {"code": code_string, "task_description": task_description}
        self.send_request("analyze_code", data, self.handle_analyze_result)
    # End of analyze_code method

    # Start of handle_analyze_result method
    def handle_analyze_result(self, response):
        # print(f"DEBUG: handle_analyze_result called with response: {response}") # DEBUG PRINT
        self.update_results("--- AI Analysis Result ---", "info")
        if response.get("type") == "ai_analysis_result":
            analysis = response.get("analysis", "No analysis provided.")
            self.update_results(analysis, "info")
        elif response.get("type") == "error":
             pass # Error handled by default error callback
        else:
            self.update_results(f"Received unexpected response type: {response.get('type')}", "error")
            self.update_results(json.dumps(response, indent=2), "error")
    # End of handle_analyze_result method

    # Start of fix_code method
    def fix_code(self):
        """Gets code and language, prompts for suggested fix, sends to /fix_code, displays fixed code."""
        original_code = self.code_input.toPlainText().strip()
        language = self.language_combo.currentText()

        if not original_code:
            self.update_results("Please enter code to fix.", "info")
            return

        suggested_fix, ok = QInputDialog.getMultiLineText(
            self, "Apply Fix", "Paste suggested fix (text or code block):"
        )

        if not ok or not suggested_fix:
            self.update_results("No suggested fix provided.", "info")
            return

        data = {"original_code": original_code, "suggested_fix": suggested_fix, "language": language}
        self.send_request("fix_code", data, self.handle_fix_result)
    # End of fix_code method

    # Start of handle_fix_result method
    def handle_fix_result(self, response):
        # print(f"DEBUG: handle_fix_result called with response: {response}") # DEBUG PRINT
        self.update_results("--- Code Fix Result ---", "info")
        if response.get("type") == "code_fix_result":
            success = response.get("success")
            fixed_code = response.get("fixed_code")
            message = response.get("message", "Operation completed.")

            self.update_results(f"Success: {success}", "success" if success else "error")
            self.update_results(f"Message: {message}", "info")
            if fixed_code:
                self.update_results("--- Fixed Code ---", "info")
                self.update_results(fixed_code, "code")
                # Optionally, replace the code in the editor with the fixed code
                # response = QMessageBox.question(self, "Apply Fix", "Do you want to replace the current code with the fixed code?",
                #                                QMessageBox.Yes | QMessageBox.No)
                # if response == QMessageBox.Yes:
                #     self.code_input.setPlainText(fixed_code)

        elif response.get("type") == "error":
             pass # Error handled by default error callback
        else:
            self.update_results(f"Received unexpected response type: {response.get('type')}", "error")
            self.update_results(json.dumps(response, indent=2), "error")
    # End of handle_fix_result method

    # Start of handle_chat_result method
    def handle_chat_result(self, response):
        # print(f"DEBUG: handle_chat_result called with response: {response}") # DEBUG PRINT
        # Display the chat response in the chat history area using typing animation
        ryan_response_content = response.get('content', 'Empty response')

        if response.get("type") == "code":
            # If Ryan provides code, put it in the code editor and add a chat message
            code_content = response.get("content", "").strip()
            if code_content:
                self.code_input.setPlainText(code_content)
                # Add a chat message indicating code was generated
                chat_message = ryan_response_content # Use the chat content from the response
                self.update_results(f"Ryan generated code and placed it in the editor.", "info")
                # Switch to the code page if not already there
                self.stacked_widget.setCurrentIndex(1)
                # Now, start typing the chat message in the chat history
                self.start_typing_animation(self.chat_history_display, chat_message)
            else:
                # If code response is empty, just display the chat content
                self.update_results("Ryan generated an empty code response.", "info")
                self.start_typing_animation(self.chat_history_display, ryan_response_content)

        elif response.get("type") == "error":
             pass # Error handled by default error callback
        else:
            # For text or other types, just start the typing animation in chat history
            self.start_typing_animation(self.chat_history_display, ryan_response_content)

    # End of handle_chat_result method

    # --- Functions for Other Sections ---
    # Start of load_memory method
    def load_memory(self):
        self.memory_list_widget.clear()
        self.update_results("Loading memory...", "info")
        self.send_request("memory", method='GET', result_callback=self.handle_memory_result)
    # End of load_memory method

    # Start of handle_memory_result method
    def handle_memory_result(self, response):
        # print(f"DEBUG: handle_memory_result called with response: {response}") # DEBUG PRINT
        if isinstance(response, list):
            if response:
                for item in response:
                    key = item.get('key', 'N/A')
                    value = item.get('value', 'N/A')
                    list_item = QListWidgetItem(f"Key: {key}\nValue: {value}")
                    list_item.setData(Qt.UserRole, key)
                    self.memory_list_widget.addItem(list_item)
                self.update_results(f"Loaded {len(response)} memory entries.", "success")
            else:
                self.update_results("Memory is empty.", "info")
        elif response.get("type") == "error":
             pass # Error handled by default error callback
        else:
            self.update_results(f"Received unexpected memory response type: {response.get('type')}", "error")
            self.update_results(json.dumps(response, indent=2), "error")
    # End of handle_memory_result method

    # Start of edit_memory_item method
    def edit_memory_item(self, item):
        """Opens a dialog to edit a selected memory item."""
        key = item.data(Qt.UserRole)
        # Extract current value, handling potential missing "Value: " prefix
        item_text = item.text()
        if "Value: " in item_text:
            current_value = item_text.split("Value: ", 1)[-1]
        else:
            current_value = item_text # Use full text if prefix not found

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Memory: {key}")
        dialog_layout = QVBoxLayout(dialog)

        value_edit = QTextEdit()
        value_edit.setPlainText(current_value)
        dialog_layout.addWidget(value_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)

        if dialog.exec() == QDialog.Accepted:
            new_value = value_edit.toPlainText().strip()
            if new_value != current_value:
                self.update_results(f"Updating memory key: {key}...", "info")
                data = {"value": new_value}
                # Send PUT request to update memory
                self.send_request(f"memory/{key}", data=data, method='PUT', result_callback=self.handle_memory_update_result)
            else:
                self.update_results("No changes made to memory item.", "info")
    # End of edit_memory_item method

    # Start of handle_memory_update_result method
    def handle_memory_update_result(self, response):
         # print(f"DEBUG: handle_memory_update_result called with response: {response}") # DEBUG PRINT
         if response.get("type") == "success":
              self.update_results(response.get("content", "Memory updated successfully."), "success")
              self.load_memory() # Refresh the list after update
         elif response.get("type") == "error":
              pass # Error handled by default error callback
         else:
              self.update_results(f"Received unexpected memory update response type: {response.get('type')}", "error")
              self.update_results(json.dumps(response, indent=2), "error")
    # End of handle_memory_update_result method

    # Start of delete_memory_item method
    def delete_memory_item(self):
        """Deletes the selected memory item."""
        selected_items = self.memory_list_widget.selectedItems()
        if not selected_items:
            self.update_results("No memory item selected for deletion.", "info")
            return

        item_to_delete = selected_items[0]
        key = item_to_delete.data(Qt.UserRole)

        reply = QMessageBox.question(self, "Delete Memory", f"Are you sure you want to delete memory key: {key}?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.update_results(f"Deleting memory key: {key}...", "info")
            # Send DELETE request to delete memory
            self.send_request(f"memory/{key}", method='DELETE', result_callback=self.handle_memory_delete_result)
    # End of delete_memory_item method

    # Start of handle_memory_delete_result method
    def handle_memory_delete_result(self, response):
         # print(f"DEBUG: handle_memory_delete_result called with response: {response}") # DEBUG PRINT
         if response.get("type") == "success":
              self.update_results(response.get("content", "Memory deleted successfully."), "success")
              self.load_memory() # Refresh the list after deletion
         elif response.get("type") == "error":
              pass # Error handled by default error callback
         else:
              self.update_results(f"Received unexpected memory delete response type: {response.get('type')}", "error")
              self.update_results(json.dumps(response, indent=2), "error")
    # End of handle_memory_delete_result method

    # Start of load_logs method
    def load_logs(self):
        """Fetches logs from the backend and displays them."""
        self.logs_display.clear() # Clear current logs
        self.update_results("Loading logs...", "info")
        # For simplicity, fetching all logs at once for now. Pagination can be added later.
        self.send_request("logs", method='GET', result_callback=self.handle_logs_result)
    # End of load_logs method

    # Start of handle_logs_result method
    def handle_logs_result(self, response):
        # print(f"DEBUG: handle_logs_result called with response: {response}") # DEBUG PRINT
        if response.get("type") == "logs":
            logs_content = response.get("content", "No logs available.")
            self.logs_display.setPlainText(logs_content)
            self.update_results("Logs loaded.", "success")
        elif response.get("type") == "error":
             pass # Error handled by default error callback
        else:
            self.update_results(f"Received unexpected logs response type: {response.get('type')}", "error")
            self.update_results(json.dumps(response, indent=2), "error")
    # End of handle_logs_result method

    # --- Chat Instruction Function ---
    # Start of send_chat_instruction method
    def send_chat_instruction(self):
        """Gets text from chat input, sends to backend /chat endpoint, handles response."""
        # print("DEBUG: send_chat_instruction called") # DEBUG PRINT
        current_index = self.stacked_widget.currentIndex()
        if current_index == 0: # Chat page is active
             user_instruction = self.chat_input_line_page.text().strip()
             chat_input_widget = self.chat_input_line_page
             # print(f"DEBUG: send_chat_instruction: User input from chat page: '{user_instruction}'") # DEBUG PRINT
        else:
             # No chat input on other pages
             # print("DEBUG: send_chat_instruction: Called on non-chat page, returning.") # DEBUG PRINT
             return

        if not user_instruction:
            self.update_results("Please enter an instruction for Ryan.", "info")
            # print("DEBUG: send_chat_instruction: No user input, showing info message.") # DEBUG PRINT
            return

        # Display user's instruction in the chat history area immediately
        self.update_results(user_instruction, "user_chat")
        chat_input_widget.clear() # Clear the input field
        # print("DEBUG: send_chat_instruction: User input displayed, input cleared.") # DEBUG PRINT

        # We don't have creative_context in this simple GUI, so send None
        data = {"message": user_instruction, "creative_context": None}
        # print(f"DEBUG: send_chat_instruction: Sending data to /chat: {data}") # DEBUG PRINT
        # Corrected call: Pass method='POST' and result_callback=self.handle_chat_result
        self.send_request("chat", data=data, method='POST', result_callback=self.handle_chat_result)
    # End of send_chat_instruction method

    # --- Override closeEvent ---
    # Start of closeEvent method
    def closeEvent(self, event):
        # print("DEBUG: closeEvent called") # DEBUG PRINT
        # Stop typing animation when closing
        self.stop_typing_animation()
        if self.api_worker and self.api_worker.isRunning():
            # print("DEBUG: closeEvent: Stopping ApiWorker thread.") # DEBUG PRINT
            self.api_worker.stop()
        super().closeEvent(event)
    # End of closeEvent method

    # >>> End of Helper and Interaction Methods <<<

# >>> End of RyanCodingApp class definition <<<


# --- Main application setup ---
# This block MUST be at the very left margin (no indentation)
if __name__ == "__main__":
    try:
        # Check if the backend is likely running
        response = requests.get(f"{API_BASE_URL}/docs")
        if response.status_code == 200:
            print("Backend is running. Starting GUI...")
        else:
            print(f"Warning: Could not connect to backend at {API_BASE_URL}. Status code: {response.status_code}")
            print("Please ensure your ryan.py script is running (e.g., `uvicorn ryan:app --reload`)")
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to backend at {API_BASE_URL}.")
        print("Please ensure your ryan.py script is running (e.g., `uvicorn ryan:app --reload`)")
    except Exception as e:
        print(f"An unexpected error occurred while checking backend: {e}")

    app = QApplication(sys.argv)
    window = RyanCodingApp()
    window.show()
    sys.exit(app.exec())
