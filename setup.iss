#define MyAppName "YKS-LGS Odev Takip"
#define MyAppVersion "3.5.0"
#define MyAppPublisher "Osman Kutukcu"
#define MyAppExeName "OdevTakip_v2.exe"

[Setup]
AppId={{C7A9F521-8F3D-4A73-9C1D-8942A8C162DE}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=OdevTakip_v2_Kurulum
Compression=lzma2/max
SolidCompression=yes
SetupIconFile=assets\app_icon.ico
UninstallDisplayIcon={app}\app_icon.ico
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "assets\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
; Mevcut veritabanı ve lisans dosyalarını koru (asla ezme)
Source: "dist\OdevTakip_v2\*.db"; DestDir: "{app}"; Flags: onlyifdoesntexist recursesubdirs skipifsourcedoesntexist
Source: "dist\OdevTakip_v2\*.sqlite"; DestDir: "{app}"; Flags: onlyifdoesntexist recursesubdirs skipifsourcedoesntexist
Source: "dist\OdevTakip_v2\license.json"; DestDir: "{app}"; Flags: onlyifdoesntexist recursesubdirs skipifsourcedoesntexist
; Diğer tüm uygulama dosyalarını güncelle
Source: "dist\OdevTakip_v2\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\Kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
