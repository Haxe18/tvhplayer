# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TVHplayer is a cross-platform desktop client for TVHeadend servers, built with PyQt6 and python-vlc. It allows users to watch live TV, browse EPG, schedule recordings, and record locally to their computer.

## Running and Development

### Run from source
```bash
pip install -r requirements.txt
python3 tvhplayer/tvhplayer.py
```

### Build executable with PyInstaller
```bash
pyinstaller --name=tvhplayer --windowed tvhplayer/tvhplayer.py
```

### Flatpak build
Uses `io.github.mfat.tvhplayer.yml` manifest with dependencies defined in `pypi-dependencies.yaml`

## Architecture

### Main Application Structure

**Single-file architecture**: The entire application is in `tvhplayer/tvhplayer.py` (~3300+ lines). This monolithic structure means:
- All UI, API logic, playback, and recording features are in one file
- No separation between components - changes require careful review of the entire context
- Main entry point is the `main()` function at the end of the file

### Key Classes and Functions

- **`natural_sort_key(channel_name)`** (line ~853): Natural/human sorting for channel names
  - Extracts base name and number from channel names using regex pattern `r'\s(\d+)\s'`
  - Returns tuple: `(base_name.lower(), number)` for proper sorting
  - Channels without numbers use -1 to sort before numbered variants
  - Examples:
    - "Sky Sport Bundesliga HD" → `("sky sport bundesliga hd", -1)` - comes first
    - "Sky Sport Bundesliga 1 HD" → `("sky sport bundesliga hd", 1)`
    - "Sky Sport Bundesliga 10 HD" → `("sky sport bundesliga hd", 10)`
  - Ensures "Sky Sport 1" < "Sky Sport 2" < "Sky Sport 10" (not "1, 10, 2")
  - Ensures "Sky Sport Bundesliga HD" < "Sky Sport Bundesliga 1 HD" (no number before numbers)

- **`ProgressBarDelegate(QStyledItemDelegate)`** (line ~863): Custom delegate for EPG progress bars
  - Draws program title, time range, and animated progress bar in table cells
  - Color-coded progress: Green (0-25%), Blue (25-75%), Orange (75-100%)
  - Auto-refreshes every 60 seconds for live progress updates

- **`SettingsDialog(QDialog)`** (line ~978): User preferences dialog
  - Icon size presets: Small (48px), Medium (64px), Large (80px), Extra Large (100px), Custom
  - Settings persist to config file
  - Accessible via Settings → Channel Icons menu

- **`TVHeadendClient(QMainWindow)`** (line ~1088): Main application window and controller
  - Handles all UI, server connections, playback, and recordings
  - Initializes VLC with hardware acceleration support
  - Platform-specific configuration paths (macOS: ~/Library/Application Support, Windows: %APPDATA%, Linux: ~/.config)
  - Implements persistent UI state (column widths, splitter position, sort order)

- **`Logger`** (line 38): Application logging system
  - Logs to `~/.tvhplayer/logs/tvhplayer_<timestamp>.log`
  - Captures system info at startup
  - Redacts sensitive environment variables

- **Other Dialog Classes**:
  - `DVRStatusDialog`: Display DVR status and scheduled recordings
  - `RecordingDurationDialog`: Set custom recording duration
  - `ServerDialog`: Quick server connection setup
  - `ServerConfigDialog`: Detailed server configuration
  - `ServerStatusDialog`: Display server status, signal strength, connections
  - `EPGDialog`: Browse Electronic Program Guide
    - Displays EPG entries with time, title, and description
    - HTML-formatted tooltips with word-wrap and max-width (400px) for better readability
    - Prevents long descriptions from spanning entire screen
  - `RecordingStatusDialog`: Monitor active recordings

### TVHeadend API Integration

The app communicates with TVHeadend via HTTP REST API (no HTSP support). Common endpoints:
- `/api/channel/grid?limit=10000` - Fetch channel list
- `/api/epg/events/grid?channel=<uuid>&limit=5` - Fetch EPG data **per channel** (channel UUID required!)
- `/api/dvr/entry/grid` - Fetch DVR recordings
- `/api/dvr/entry/create` - Schedule recording
- `/api/dvr/entry/stop` - Stop recording
- `/api/status/inputs` - Server input status
- `/api/status/connections` - Active connections
- `/api/status/subscriptions` - Active subscriptions
- `/api/serverinfo` - Server version info

**HTTP Session & User-Agent:**
- Uses a global `requests.Session()` object for all HTTP requests (lines 41-42)
- User-Agent: `TVHplayer/4.0 (https://github.com/mfat/tvhplayer)`
- Connection pooling enabled for better performance
- All API calls use `session.get()` instead of `requests.get()`

**Important EPG Notes:**
- EPG API requires `channel: uuid` parameter - time-based filtering alone doesn't work
- EPG updates are done **per-channel** (one API call per channel) to ensure data is returned
- Updates are **asynchronous** using `QTimer.singleShot()` to avoid UI blocking
  - Processes one channel at a time with 20ms delays between requests
  - For 72 channels: ~1.4s overhead but UI stays responsive
  - Uses queue-based approach: `update_all_epg_data()` → `update_next_epg()` loop
  - **UUID-based row lookup**: Queue stores `(uuid, name)` instead of row numbers
    - Row is found dynamically via UUID search in `update_next_epg()`
    - Prevents issues when table is sorted during EPG updates
    - More robust against table mutations
- **Fallback item creation**: If TableWidget items in columns 3/4 don't exist, they are automatically created
  - Handles edge cases where items might be missing after table operations (sorting, column visibility changes)
  - Ensures EPG data is always displayed even if table structure is inconsistent
- Auto-refresh interval is 30 minutes due to per-channel overhead

**Authentication:**
- Uses both digest and plain auth (both must be enabled on server)
- Handles 401 errors gracefully with user-friendly error messages

### Video Playback

- **VLC integration**: Uses `python-vlc` bindings with hardware acceleration
- **Platform-specific window handles**:
  - Linux: `set_xwindow()`
  - Windows: `set_hwnd()`
  - macOS: `set_nsobject()`
- Hardware decoding configured with `--avcodec-hw=any` flag

### Local Recording

Uses FFMPEG subprocess for local recording feature. Requires ffmpeg in PATH or same directory on Windows.

### Configuration

- Stored in JSON format at platform-specific paths
- File: `tvhplayer.conf`
- Contains: server list, window geometry, last selected server, UI state
- Server configs include: name, URL, username, password
- **Configuration saving**:
  - Centralized via `save_config()` method - all config changes should use this
  - Server selection: Updated in `on_server_changed()` via `save_config()`
  - Avoids redundant saves by not re-reading UI state in `save_config()`
  - Config dict is "single source of truth", not the UI controls
- UI state persistence:
  - `icon_size`: Channel icon size (48-100px)
  - `channel_column_width`: Width of channel name column (default: 80px)
  - `current_program_width`: Width of current program column (default: 300px)
  - `next_program_width`: Width of next program column (default: 300px)
  - `splitter_sizes`: Left/right panel sizes (default: [300, 900]) - debounced
  - `sort_column`: Last sorted column index
  - `sort_order`: Qt.AscendingOrder (0) or Qt.DescendingOrder (1)
  - `column_visibility`: Dict of column visibility states
  - `last_server`: Index of currently selected server (persists between sessions)
- Reset to factory defaults via Settings → Reset to Factory Defaults

### Resources

- Qt resources compiled in `resources_rc.py` from `resources.qrc`
- Icons stored in `icons/` directory
- Flexible import handling for both package and direct source execution
- **Channel icons cached per-server** in `~/.config/tvhplayer/channel_icons/<server_name>/` (or platform-specific config dir)
  - Server-specific subdirectories prevent icon mixing between servers
  - Downloaded once from TVHeadend server
  - Stored in original size
  - Rescaled on-the-fly when displayed based on user settings
  - Can be cleared via Settings → Clear Icon Cache

### Channel List Features

The main channel list (`QTableWidget`) has **5 columns**:

| Column | Content | Resize Mode | Notes |
|--------|---------|-------------|-------|
| 0 | **# (Number)** | ResizeToContents | Channel number from TVHeadend |
| 1 | **Icon** | Fixed | User-configurable size (48-100px) |
| 2 | **Channel Name** | Interactive | User resizable, persists to config (default: 80px) |
| 3 | **Current Program** | Interactive | Custom delegate with progress bar, persists (default: 300px) |
| 4 | **Next Program** | Interactive | Simple text display, persists (default: 300px) |

**Key Features:**

1. **Natural Sorting**: Channel names sorted intelligently
   - "Sky Sport Bundesliga 1" comes before "Sky Sport Bundesliga 10"
   - "Sky Sport Bundesliga HD" (no number) comes before "Sky Sport Bundesliga 1 HD"
   - Uses `natural_sort_key()` function that extracts base name and number
   - Algorithm:
     1. Search for number pattern `r'\s(\d+)\s'` (number surrounded by spaces)
     2. If found: Extract base name (remove number) and number as integer
     3. If not found: Use full name and -1 (sorts before all positive numbers)
     4. Return tuple `(base_name.lower(), number)` for alphabetical then numerical sorting
   - Used in `NaturalSortTableWidgetItem.__lt__()` for Qt table sorting
   - Initial load: sorted by channel number, then natural-sorted by name
   - User can click column headers to re-sort (# and Channel Name columns only)
   - Icon, Current Program, and Next Program columns are **not sortable** (blocked via `handle_sort_changed()`)

2. **Live Progress Bars** (Column 3):
   - Custom `ProgressBarDelegate` draws program title, time range, and progress bar
   - Progress calculated from program start/stop times
   - Color-coded: Green → Blue → Orange as program progresses
   - Auto-refreshes every 60 seconds without API calls

3. **Icon Management**:
   - Configurable size via Settings → Channel Icons menu
   - Presets: Small (48px), Medium (64px), Large (80px), Extra Large (100px), Custom
   - `QTableWidget.setIconSize()` controls display size (critical for proper rendering!)
   - Icons cached locally and rescaled on-demand

4. **EPG Updates**:
   - Initial load when channels are fetched
   - Auto-refresh every 30 minutes via QTimer
   - Per-channel API calls to `/api/epg/events/grid?channel=<uuid>`
   - Data stored in `Qt.UserRole` for delegate access

5. **Column Visibility**:
   - Right-click on table header to show/hide columns
   - Settings saved to config file (`column_visibility` key)
   - Restored on application restart

**Important Implementation Details:**

- **Progress Bar Delegate**: Column 3 uses custom delegate, so `setText("")` must be used (not actual text)
  - If text is set via `setText()`, Qt displays the text instead of calling the delegate
  - Data is stored in `Qt.UserRole` as dict: `{'title': str, 'start': int, 'stop': int}`
  - Delegate draws: time range (9pt), title (9pt normal weight), and color-coded progress bar (10px height)
  - Text wrapping: Single-line uses VCenter alignment, multi-line uses AlignTop + TextWordWrap
  - Fixed row height: 60px (independent of icon size)

- **Icon Column Sizing**: When changing icon size in settings:
  1. Update config FIRST (before reloading icons)
  2. Set `QTableWidget.setIconSize(QSize(size, size))` - **CRITICAL** for proper icon display!
  3. Set column 1 width: `icon_size + 10`
  4. Reload all icons from cache with new size

- **Channel Data Storage**: Full channel data (`Qt.UserRole`) stored on:
  - Column 1 (icon item) - for icon loading
  - Column 2 (name item) - for playback/filtering/context menus

- **Async Operations**: Both icon downloads and EPG updates use async patterns to avoid UI blocking
  - Pattern: Build queue → Process one item → `QTimer.singleShot(delay, next_callback)`
  - Icon downloads: 50ms delays between downloads
  - EPG updates: 20ms delays between channel updates
  - Never block the main thread with long-running operations!

- **Column Width Persistence**: Debounced saving prevents excessive disk writes
  - Uses QTimer with 500ms delay after resize events
  - Saves only after user stops resizing (releases mouse)
  - Backup save in `closeEvent()` to catch any pending changes
  - All three resizable columns (2, 3, 4) persist independently

- **Splitter Position**: Main window horizontal splitter position persists with debouncing
  - Left panel (channel list) and right panel (video/controls)
  - Uses same debouncing pattern as column widths (500ms delay)
  - Timer: `splitter_timer` with `pending_splitter_sizes` state
  - Backup save in `closeEvent()` to catch pending changes before app closes
  - Default: [300, 900] pixels

- **Sort Order**: Table sort state persists across sessions
  - Saves column index and sort direction (ascending/descending)
  - Restored automatically on channel list load

- **Robust Error Handling**: Multiple layers of defensive programming
  - **Empty row cleanup**: After sorting, any rows without channel name in column 2 are automatically removed
  - **Preventive item creation**: All table items are created in local variables first, row only inserted if all items succeed
  - **Fallback item creation**: Missing items in columns 3/4 (EPG) are created on-demand during updates
  - **Null-safe context menu**: Checks if `channel_item` and `channel_data` exist before showing context menu
  - **EPG queue management**: When switching servers, EPG update queue is cleared and stop flag is set
    - Prevents "Could not find row" errors from old server's channels
    - Queue check is robust: `if not self.epg_update_queue or self.epg_update_index >= len(...)`
    - Handles cleared queues gracefully without magic numbers
  - **Sorting control during batch operations**:
    - `setSortingEnabled(False)` during channel list loading prevents Qt auto-sorting
    - Visual sort indicator set with `setSortIndicator()` after Python pre-sorting
    - Sorting re-enabled after empty row cleanup completes
    - Prevents items from being separated across columns during insertion
  - **Exception logging**: All exceptions include full traceback for troubleshooting
  - Pattern: Check → Create if missing → Proceed, never assume items exist

## Dependencies

Core runtime dependencies:
- PyQt6 >= 6.0.0
- python-vlc >= 3.0.12122
- requests >= 2.28.0
- python-dateutil >= 2.8.2

External dependencies:
- VLC media player (libvlc)
- FFMPEG (for local recording feature)

## Platform Support

Cross-platform with platform-specific handling for:
- Configuration paths (XDG on Linux, Application Support on macOS, APPDATA on Windows)
- VLC window integration
- PyInstaller bundling paths
