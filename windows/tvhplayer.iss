; Inno Setup Script for TVHplayer
; https://jrsoftware.org/isinfo.php

#define MyAppName "TVHplayer"
#define MyAppVersion GetEnv("VERSION")
#if MyAppVersion == ""
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "mFat"
#define MyAppURL "https://github.com/mfat/tvhplayer"
#define MyAppExeName "tvhplayer.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; This MUST match the AppId from v3.5 for proper updates
AppId={{44F47025-9814-4F1C-86E8-4A190FD4FDC9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=tvhplayer-windows-{#MyAppVersion}-setup
; SetupIconFile=..\icons\tvhplayer.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Modern UI settings
WizardStyle=modern
WizardResizable=yes
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Package the entire PyInstaller --onedir output
Source: "..\dist\tvhplayer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
