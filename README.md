
<a href='https://flathub.org/apps/io.github.mfat.tvhplayer'>
    <img width='240' alt='Get it on Flathub' src='https://flathub.org/api/badge?locale=en'/>
  </a>

# TVHplayer
A TVheadend client for watching and recording live TV on PC

![Screenshot_6](Screenshots/Screenshot_6.png)




## Features:

With TVHplayer you can:
- Play live TV & radio channels
- Browse EPG with live progress bars showing current and upcoming programs
  - Robust EPG handling with automatic recovery for missing UI elements
  - Asynchronous updates keep UI responsive even with many channels
  - Word-wrapped tooltips with max-width for better readability
- Schedule recordings
- Initiate instant recordings with custom duration
- Record live TV locally on your computer
- Monitor your server status, signal strength and DVR
- Customize channel icon sizes (48px - 100px)
- Persistent UI state - your column widths, sort order, and window layout are remembered
  - Debounced saving prevents excessive disk writes during resizing operations
  - Server selection persists between sessions
- Natural/human sorting for channel names (e.g., "Channel 1, 2, 10" not "1, 10, 2")
  - Channels without numbers sort before numbered variants (e.g., "Channel HD" before "Channel 1 HD")
- Per-server icon caching for fast switching between multiple TVHeadend servers
- Column visibility control - show/hide columns via right-click on table header
- TVHplayer is cross-platform - runs on linux, macOS and Windows

## Download
- Head to [releases](https://github.com/mfat/tvhplayer/releases) section to download the app for your operating system (Linux, MacOS or Windows)
- Linux users can also install the app from [Flathub](https://flathub.org/apps/io.github.mfat.tvhplayer)

<a href='https://flathub.org/apps/io.github.mfat.tvhplayer'>
    <img width='240' alt='Get it on Flathub' src='https://flathub.org/api/badge?locale=en'/>
  </a>


## Requirements
- Make sure both digest and plain authentication are enabled in your server
- See requirements.txt for required python modules (python3 -m pip install python-vlc
- python3 -m pip install python-vlc
- VLC 
- FFMPEG (used for local recording feature if you need it)
  - On Windows follow [this guide](https://phoenixnap.com/kb/ffmpeg-windows) to add ffmpeg to windows PATH. You can also put ffmpeg.exe in the same directory as tvhplayer.
 
## Help and Support
- Refer to the [User Guide](https://github.com/mfat/tvhplayer/wiki/User-Guide) for more information about using the app. 
- If you encounter any problems [open a bug report](https://github.com/user/repository/issues/new)

## Run the app from source 
- You can run the code directly with python. You may want to do this if you don't want to download an executable.
To do this:
- install python
- download the [requirements.txt](https://github.com/mfat/tvhplayer/blob/main/requirements.txt) and run this command:
  `pip install -r requirements.txt`
- Download the tvhplayer zip file from the latest release and extract to a folder or clone using git:
  `git clone https://github.com/mfat/tvhplayer.git`
- cd into the folder
- Run the app with:
  `python3 tvhplayer/tvhplayer.py`

## Technical information
- TVHplayer uses Tvheadend's HTTP REST API (no HTSP support yet)
- For playback, it uses libvlc with hardware acceleration support
- Optimized HTTP requests with connection pooling and custom User-Agent
- Per-server icon caching in `~/.config/tvhplayer/channel_icons/` (Linux/macOS) or `%APPDATA%/tvhplayer/channel_icons/` (Windows)
- Custom natural sorting algorithm for channel names:
  - Extracts base name and number from channel names
  - Sorts alphabetically by base name, then numerically
  - Channels without numbers (e.g., "HD") sort before numbered variants (e.g., "1 HD")
- Robust error handling with automatic recovery:
  - Empty table rows are automatically cleaned up after sorting
  - Missing UI elements are created on-demand during EPG updates
  - Graceful handling of incomplete data structures
  - Proper EPG queue cleanup when switching servers (prevents stale data requests)
  
## Support development
Bitcoin: `bc1qqtsyf0ft85zshsnw25jgsxnqy45rfa867zqk4t`

Doge:  `DRzNb8DycFD65H6oHNLuzyTzY1S5avPHHx`
