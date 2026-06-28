; installer.iss — Inno Setup 6 para o Limpa PDF (MPSC)
; Build: ISCC.exe installer.iss
; Instalação silenciosa (ZenWorks): LimpaPDF_setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART

[Setup]
AppName=Limpa PDF — MPSC
AppVersion=2.6.0
AppPublisher=MPSC
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=
DefaultDirName={commonpf64}\LimpaPDF
DefaultGroupName=Limpa PDF
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=LimpaPDF_setup
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\LimpaPDF.exe
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: checkedonce

[Files]
Source: "dist\LimpaPDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Limpa PDF — MPSC"; Filename: "{app}\LimpaPDF.exe"
Name: "{group}\Desinstalar Limpa PDF"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Limpa PDF — MPSC"; Filename: "{app}\LimpaPDF.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LimpaPDF.exe"; Description: "Iniciar Limpa PDF — MPSC"; Flags: nowait postinstall skipifsilent
