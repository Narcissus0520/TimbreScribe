#define AppName "TimbreScribe"
#define AppPublisher "TimbreScribe contributors"
#define AppUrl "https://github.com/Narcissus0520/TimbreScribe"
#ifndef AppVersion
  #define AppVersion "0.9.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\work\release\dist\TimbreScribe"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\work\release\artifacts"
#endif

[Setup]
AppId={{8B343F14-A56E-4918-BED3-BD33950EC866}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
DefaultDirName={localappdata}\Programs\TimbreScribe
DefaultGroupName=TimbreScribe
DisableProgramGroupPage=auto
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no
Uninstallable=yes
UninstallDisplayIcon={app}\TimbreScribe.exe
LicenseFile={#SourceDir}\licenses\LICENSE
OutputDir={#OutputDir}
OutputBaseFilename=TimbreScribe-{#AppVersion}-windows-x64-setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=TimbreScribe per-user Windows installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startmenuicon"; Description: "Create a Start menu shortcut"; GroupDescription: "Shortcuts:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TimbreScribe"; Filename: "{app}\TimbreScribe.exe"; Tasks: startmenuicon
Name: "{autodesktop}\TimbreScribe"; Filename: "{app}\TimbreScribe.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\.timbrescribe"; ValueType: string; ValueName: ""; ValueData: "TimbreScribe.Project"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\TimbreScribe.Project"; ValueType: string; ValueName: ""; ValueData: "TimbreScribe project"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\TimbreScribe.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\TimbreScribe.exe,0"
Root: HKCU; Subkey: "Software\Classes\TimbreScribe.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\TimbreScribe.exe"" ""%1"""

[Run]
Filename: "{app}\TimbreScribe.exe"; Description: "Launch TimbreScribe"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  RemoveManagedData: Integer;
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
  begin
    RemoveManagedData := MsgBox(
      'Remove downloaded models, generated cache, and diagnostic logs? ' +
      'Settings, recovery data, credentials, and user project files will be preserved.',
      mbConfirmation,
      MB_YESNO
    );
    if RemoveManagedData = IDYES then
    begin
      DelTree(ExpandConstant('{localappdata}\TimbreScribe\models'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\TimbreScribe\cache'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\TimbreScribe\logs'), True, True, True);
    end;
  end;
end;
