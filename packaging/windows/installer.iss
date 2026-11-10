; Inno Setup 安装包脚本（封装 PyInstaller onedir 产物：GUI + CLI）
; 构建示例：
;   iscc /DMyAppVersion=0.1.0 /DMyAppArch=x64 packaging\windows\installer.iss
;   iscc /DMyAppVersion=0.1.0 /DMyAppArch=arm64 packaging\windows\installer.iss

#ifndef MyAppName
  #define MyAppName "m3u8-downloader"
#endif
#ifndef MyAppDisplayName
  #define MyAppDisplayName "m3u8 视频下载器"
#endif
#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#ifndef MyAppArch
  #define MyAppArch "x64"
#endif
#ifndef MyAppPublisher
  #define MyAppPublisher "Xinghao Zuo"
#endif
#ifndef MyAppURL
  #define MyAppURL "https://github.com/LinusAuditore/m3u8-downloader-py"
#endif
#ifndef MySourceDir
  #define MySourceDir "..\..\dist\m3u8-downloader"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\..\dist"
#endif

[Setup]
AppId={{8D6E48B4-5C9A-4E2F-9B6A-2A74D9C10388}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppDisplayName} {#MyAppVersion} ({#MyAppArch})
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppDisplayName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyAppName}-{#MyAppVersion}-windows-{#MyAppArch}-setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\m3u8-downloader.exe
#if MyAppArch == "arm64"
ArchitecturesAllowed=arm64
ArchitecturesInstallIn64BitMode=arm64
#else
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppDisplayName}"; Filename: "{app}\m3u8-downloader.exe"
Name: "{autodesktop}\{#MyAppDisplayName}"; Filename: "{app}\m3u8-downloader.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\m3u8-downloader.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppDisplayName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
