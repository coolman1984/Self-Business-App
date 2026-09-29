; Inno Setup script of Self Business OS (built by tools/build_windows.py).
; The same SBO-Setup.exe installs the program on a new PC and updates it on a PC that already has it:
; only the program in Program Files is replaced, the data in %ProgramData%\SelfBusinessOS is never touched.
; The visible product name is a working name; the technical folder names below do not change with the brand.

#define MyAppName "Self Business OS"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef AppPublisher
  #define AppPublisher "Mohamed Fawzy"
#endif
#ifndef AppCopyright
  #define AppCopyright "(c) 2026 Mohamed Fawzy"
#endif

[Setup]
AppId={{3C9A5E12-7B4D-4F86-A0C3-5E2D9B71F6A8}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright={#AppCopyright}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\SelfBusinessOS
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
DisableDirPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=SBO-Setup-{#AppVersion}
SetupIconFile=..\build\sbo.ico
UninstallDisplayIcon={app}\SBO.exe
UninstallDisplayName={#MyAppName}
LicenseFile=..\LICENSE.txt
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Put an icon on the desktop"
Name: "autostart"; Description: "Start with Windows (recommended - keeps this PC in sync with the others)"

[Dirs]
; data, backups and settings: writable for everybody who uses this PC, kept when the program is updated or removed
Name: "{commonappdata}\SelfBusinessOS"; Flags: uninsneveruninstall

[Files]
Source: "..\build\sbo_main.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\SBO.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\SBO.exe"; Tasks: desktopicon
Name: "{commonstartup}\{#MyAppName}"; Filename: "{app}\SBO.exe"; Parameters: "--background"; Tasks: autostart

[Run]
; the data folder holds the keys and the databases: only Administrators, the system and the person who installed the program may use it
Filename: "{sys}\icacls.exe"; Parameters: """{commonappdata}\SelfBusinessOS"" /inheritance:r /grant:r *S-1-5-18:(OI)(CI)F *S-1-5-32-544:(OI)(CI)F ""{username}"":(OI)(CI)M"; Flags: runhidden; StatusMsg: "Protecting your data folder..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#MyAppName}"""; Flags: runhidden; StatusMsg: "Allowing the other PCs to connect..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#MyAppName}"" dir=in action=allow program=""{app}\SBO.exe"" enable=yes profile=private,domain"; Flags: runhidden
Filename: "{app}\SBO.exe"; Description: "Open {#MyAppName} now"; Flags: nowait postinstall skipifsilent runasoriginaluser
Filename: "{app}\SBO.exe"; Parameters: "--background"; Flags: nowait runasoriginaluser; Check: WizardSilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM SBO.exe"; Flags: runhidden; RunOnceId: "StopSBO"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#MyAppName}"""; Flags: runhidden; RunOnceId: "FirewallRule"

[Messages]
FinishedLabel=The program is installed. Your data is kept in %ProgramData%\SelfBusinessOS (also after updates).

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  { stop the running program (it is safe to stop at any moment), so its files can be replaced }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM SBO.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(1000);
  Result := '';
end;
