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

### Build executables with PyInstaller

Each platform has its own `.spec` file for consistent, reproducible builds:

**Windows:**
```bash
pyinstaller windows/tvhplayer.spec
```
- Creates `dist/tvhplayer/` directory with all files (--onedir mode)
- Inno Setup installer with modern UI creates final .exe installer
- Filtered Qt6 DLLs to reduce size (excludes unused modules like QML, QtQuick, OpenGL SW renderer)
- Bundles Qt platform plugins to prevent "Qt platform plugin could not be initialised" error
- Uses system-installed VLC (not bundled) to save ~133 MB
- Icon: `icons/tvhplayer.ico`

**macOS:**
```bash
pyinstaller macos/tvhplayer.spec
```
- Creates `dist/TVHplayer.app` bundle
- DMG installers for Intel (macos-14, x86_64) and Apple Silicon (macos-15, arm64)
- Includes VLC plugins from `/Applications/VLC.app` or Homebrew installation
- Icon: `icons/tvhplayer.png` (modern PNG format, .icns deprecated)

**Linux:**
Use the existing debian/ configuration:
```bash
dpkg-buildpackage -us -uc -b
```
- Creates `.deb` package with dynamic version handling
- Requires: `build-essential`, `debhelper`, `dh-python`, `python3-all`, `python3-setuptools`

### Flatpak build
Uses `io.github.mfat.tvhplayer.yml` manifest with dependencies defined in `pypi-dependencies.yaml`

### GitHub Actions Build Pipeline

Automated builds run via `.github/workflows/build.yml`:

**Trigger:** Push tags or manual workflow_dispatch

**Build Matrix:**
- **Windows** (windows-latest): `.exe` installer via Inno Setup
- **macOS Intel** (macos-14): `.dmg` for x86_64
- **macOS Apple Silicon** (macos-15): `.dmg` for arm64
- **Linux** (ubuntu-latest): `.deb` package

**Key Configuration:**
- Python 3.13 used across all platforms
- `fail-fast: false` - all platforms build in parallel even if one fails
- Parallel execution for faster builds
- Dynamic version management from Git workflow
- Automatic GitHub Release upload on tag push

**Build Optimizations:**
- **Caching enabled** for faster builds:
  - Python pip dependencies (`cache: 'pip'`)
  - Homebrew packages (macOS: `~/Library/Caches/Homebrew`)
  - Chocolatey packages (Windows: `~\AppData\Local\Temp\chocolatey`)
- Cache keys based on OS + workflow hash for consistency
- Note: APT package caching is not used on Linux due to permission issues with `/var/cache/apt/archives`

**Artifact Naming:**
- `tvhplayer-windows-{version}-setup.exe`
- `tvhplayer-macos-intel-{version}.dmg`
- `tvhplayer-macos-silicon-{version}.dmg`
- `tvhplayer-linux-{version}.deb`

### Build Troubleshooting

**Common Build Issues:**

1. **Windows: "Qt platform plugin could not be initialised"**
   - **Cause**: Qt platform plugins not bundled correctly
   - **Fix**: Use `windows/tvhplayer.spec` with COLLECT mode (not onefile)
   - The spec file ensures `qwindows.dll` is placed in `platforms/` subdirectory

2. **Windows/macOS: "script 'tvhplayer/tvhplayer.py' not found"**
   - **Cause**: Incorrect path resolution in `.spec` file (using `os.getcwd()` instead of `SPECPATH`)
   - **Fix**: Use `SPECPATH` variable to locate repository root
   - Example: `repo_root = os.path.dirname(SPECPATH)`
   - Both `windows/tvhplayer.spec` and `macos/tvhplayer.spec` now use this correct pattern

3. **Linux: "can't parse dependency" or "parsing package Depends field"**
   - **Cause**: Missing commas or incorrect formatting in `debian/control`
   - **Fix**: Ensure all dependencies are comma-separated on single lines
   - **Required dependencies**: `python3-pyqt6`, `python3-vlc`, `python3-requests`, `python3-dateutil`, `vlc`

4. **Linux: "Unmet build dependencies: build-essential"**
   - **Cause**: Missing build tools for dpkg-buildpackage
   - **Fix**: Install `build-essential` before running dpkg-buildpackage
   - Full list: `build-essential`, `debhelper`, `dh-python`, `python3-all`, `python3-setuptools`

5. **All platforms: "no files found matching 'icons/*'"**
   - **Cause**: Incorrect path in `MANIFEST.in`
   - **Fix**: Icons are in `icons/` not `tvhplayer/icons/`
   - Correct: `include icons/*`

**Debugging Tips:**
- Check PyInstaller build logs for missing modules or plugins
- Verify `.spec` file paths are relative to repository root, not spec file location
- Test installers on clean systems without development dependencies
- Use `fail-fast: false` in CI to get build logs from all platforms

## Architecture

### Main Application Structure

**Single-file architecture**: The entire application is in `tvhplayer/tvhplayer.py` (~4500+ lines). This monolithic structure means:
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

- **`AppearanceDialog(QDialog)`** (line ~1420): Theme/appearance settings dialog
  - Theme mode options: Auto (Follow System), Light Mode, Dark Mode
  - Accessible via Settings → Appearance menu
  - Returns selected theme via `get_theme_mode()`: 'auto', 'light', or 'dark'

- **`SettingsDialog(QDialog)`** (line ~1485): Channel icon preferences dialog
  - Icon size presets: Small (48px), Medium (64px), Large (80px), Extra Large (100px), Custom
  - Settings persist to config file
  - Accessible via Settings → Channel Icons menu
  - Returns icon size as integer (not dict)

- **`TVHeadendClient(QMainWindow)`** (line ~1585): Main application window and controller
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

### Dark Mode & Theme System

TVHplayer includes a comprehensive dark mode system with automatic OS detection and manual override:

**Theme Functions** (lines 35-446):
- **`create_dark_palette()`**: Creates QPalette with lighter gray tones
  - Window/Button: #424242, Base: #3d3d3d, AlternateBase: #484848
  - Mid: #555555 (used for progress bar backgrounds)
  - Includes disabled state colors for accessibility
- **`create_light_palette()`**: Creates QPalette for light mode with standard Qt colors
- **`is_system_dark_mode()`**: Detects OS dark mode preference using native APIs (no subprocess)
  - **Linux**: Checks environment variables (`GTK_THEME`, `QT_QPA_PLATFORMTHEME`, `XDG_CURRENT_DESKTOP`)
  - **All platforms**: Uses Qt 6.5+ `styleHints().colorScheme()` when available
  - **Fallback**: Improved palette analysis - averages lightness of Window, Base, and Button colors (<128 = dark)
  - **No external commands**: Uses only `os.environ` and Qt APIs for better performance and reliability
- **`get_dark_mode_stylesheet()`**: Comprehensive QSS stylesheet for dark mode
  - Fixes Windows native widgets (QHeaderView, QComboBox, labels)
  - Styles all UI components: tables, menus, buttons, inputs, tabs
  - Ensures readability on Windows where QPalette alone is insufficient
- **`get_light_mode_stylesheet()`**: QSS stylesheet for light mode consistency

**Theme Application** (`TVHeadendClient.apply_theme()`, line ~2950):
- Reads `theme_mode` from config: 'auto' (default), 'light', or 'dark'
- For 'auto': calls `is_system_dark_mode()` to detect OS preference
- Applies **both** QPalette and QSS stylesheet (critical for Windows compatibility)
- Updates status bar with current theme

**Theme-Aware Components**:
- **ProgressBarDelegate**: EPG text and progress bar backgrounds use palette colors
  - Text: `option.palette.color(QPalette.ColorRole.Text)` (was hardcoded black)
  - Bar background: `option.palette.color(QPalette.ColorRole.Mid)` (was hardcoded gray)
  - Automatically adapts to light/dark themes without manual intervention

**Config Persistence**:
- `theme_mode` key stores user preference ('auto'/'light'/'dark')
- Applied automatically on application startup (after UI setup)
- Changed via Settings → Appearance dialog

**Why Both QPalette + QSS**:
- QPalette: Base colors for Qt widgets, cross-platform compatibility
- QSS: Necessary for Windows native widgets (headers, combo boxes) that ignore QPalette
- QSS also provides hover states and fine-grained control unavailable in QPalette

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
- Contains: server list, window geometry, last selected server, UI state, recording path
- Server configs include: name, URL, username, password

**Config Locations:**
- macOS: `~/Library/Application Support/TVHplayer/tvhplayer.conf`
- Windows: `%APPDATA%\TVHplayer\tvhplayer.conf`
- Linux: `~/.config/tvhplayer/tvhplayer.conf`

**Migration from v3.5 (Windows):**
- Old location: `%USERPROFILE%\.tvhplayer.conf`
- Automatically migrated to: `%APPDATA%\TVHplayer\tvhplayer.conf`
- Backup created: `%APPDATA%\TVHplayer\.tvhplayer.conf.v35.backup`
- Old file removed from home directory after migration
- Migration runs once on first start of v4.0+

**Default Recording Paths:**
- Windows: `%USERPROFILE%\Videos`
- macOS/Linux: `~` (Home directory)
- **Configuration saving**:
  - Centralized via `save_config()` method - all config changes should use this
  - Server selection: Updated in `on_server_changed()` via `save_config()`
  - Avoids redundant saves by not re-reading UI state in `save_config()`
  - Config dict is "single source of truth", not the UI controls
- UI state persistence:
  - `theme_mode`: Theme preference ('auto', 'light', 'dark') - default: 'auto'
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
