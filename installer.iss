; installer.iss — Inno Setup 6 para o Limpa PDF (MPSC)
; Build: ISCC.exe installer.iss
; Instalação silenciosa (ZenWorks): LimpaPDF_setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART

[Setup]
AppName=Limpa PDF — MPSC
AppVersion=2.9.0
AppPublisher=MPSC
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=
AppId={{A3F2E1D0-8B7C-4F5A-9E6D-2C1B0A3F4E5D}
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
; Se o Limpa PDF estiver aberto durante a instalação, pede/força o fechamento
; (no modo silencioso do ZenWorks, fecha sozinho).
CloseApplications=yes
RestartApplications=no

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

[Code]
// ── Atualização limpa: desinstala QUALQUER versão anterior antes de copiar ──
// O AppId é fixo, então o Windows já trata como o mesmo programa; mas o
// bundle do PyInstaller muda de arquivos a cada versão — instalar por cima
// deixaria DLLs órfãs da versão antiga em {app}. Rodar o desinstalador
// anterior (silencioso) garante pasta limpa. Funciona também no modo
// silencioso do ZenWorks (/VERYSILENT).

function CaminhoDesinstaladorAnterior(): String;
var
  chave, valor: String;
begin
  // Chave que o próprio Inno Setup grava: <AppId>_is1
  chave := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\'
           + '{A3F2E1D0-8B7C-4F5A-9E6D-2C1B0A3F4E5D}_is1';
  valor := '';
  if not RegQueryStringValue(HKLM, chave, 'UninstallString', valor) then
    RegQueryStringValue(HKCU, chave, 'UninstallString', valor);
  Result := RemoveQuotes(valor);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  desinst: String;
  cod, espera: Integer;
begin
  Result := '';
  desinst := CaminhoDesinstaladorAnterior();
  if (desinst <> '') and FileExists(desinst) then
  begin
    Log('Versao anterior encontrada; desinstalando: ' + desinst);
    if Exec(desinst, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '',
            SW_HIDE, ewWaitUntilTerminated, cod) then
    begin
      // O unins000.exe se copia para %TEMP% e devolve o controle antes de
      // terminar de apagar os arquivos; aguardar ele sumir (máx. 30 s).
      espera := 0;
      while FileExists(desinst) and (espera < 60) do
      begin
        Sleep(500);
        espera := espera + 1;
      end;
      Log('Desinstalacao da versao anterior concluida (cod ' + IntToStr(cod) + ').');
    end
    else
      Log('Falha ao executar o desinstalador anterior (cod ' + IntToStr(cod) + '); '
          + 'a instalacao segue por cima (mesmo AppId).');
  end;
end;
