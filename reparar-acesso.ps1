[CmdletBinding()]
param(
    [string]$PastaJogo,
    [string]$SidUsuario,
    [string]$CacheAutorizado,
    [switch]$EtapaElevada
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Texto-Literal([string]$Texto) { return "'" + $Texto.Replace("'", "''") + "'" }
function Conferir-Caminho([string]$Caminho, [bool]$VerificarHardLinks = $true) {
    $item = Get-Item -LiteralPath $Caminho -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Reparo recusado em link/juncao: $Caminho"
    }
    # Query hard-link metadata only after UAC for the previously unreadable payloads.
    if ($VerificarHardLinks -and !$item.PSIsContainer) {
        $link = $item.PSObject.Properties['LinkType']
        if ($null -ne $link -and $link.Value) {
            throw "Reparo recusado em arquivo com links: $Caminho"
        }
    }
    $parent = if ($item.PSIsContainer) { $item.Parent } else { $item.Directory }
    while ($null -ne $parent) {
        if (($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Reparo recusado: ha uma juncao no caminho $($parent.FullName)"
        }
        $parent = $parent.Parent
    }
    return $item
}

function Conferir-Cache([string]$Caminho, [string]$Romfs, [bool]$SomenteFormato = $false) {
    if ([string]::IsNullOrEmpty($Caminho)) { return }
    $cache = [IO.Path]::GetFullPath($Caminho).TrimEnd('\')
    $inputs = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'work\inputs')).TrimEnd('\')
    if ((Split-Path $cache -Leaf) -notmatch '^[0-9a-fA-F]{64}$' -or
        !(Split-Path $cache -Parent).Equals($inputs, [StringComparison]::OrdinalIgnoreCase) -or
        !([IO.Path]::GetFullPath($Romfs).TrimEnd('\')).Equals((Join-Path $cache 'romfs'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'A entrada autorizada deve ser somente o cache hash/romfs registrado nesta instalacao.'
    }
    if (!$SomenteFormato) { $null = Conferir-Caminho $cache }
}

function Testar-Leitura-Pastas([string]$Romfs) {
    foreach ($nome in @('System', 'Pack')) {
        try {
            $iterator = [IO.Directory]::EnumerateFileSystemEntries((Join-Path $Romfs $nome)).GetEnumerator()
            try { $null = $iterator.MoveNext() } finally {
                if ($iterator -is [IDisposable]) { $iterator.Dispose() }
            }
        } catch {
            $cause = $_.Exception
            while ($null -ne $cause.InnerException) { $cause = $cause.InnerException }
            if ($cause -is [UnauthorizedAccessException]) { return $false }
            # Missing resources are not fixed by changing permissions.
            throw
        }
    }
    return $true
}

function Chamar-Ferramenta([string]$Executavel, [string[]]$Argumentos) {
    $ErrorActionPreference = 'Continue'
    $texto = & $Executavel @Argumentos 2>&1
    $codigo = $LASTEXITCODE
    return [pscustomobject]@{ code = $codigo; output = ($texto | Out-String) }
}

try {
    if ([string]::IsNullOrEmpty($PastaJogo)) { $PastaJogo = Join-Path $PSScriptRoot 'jogo' }
    $PastaJogo = [IO.Path]::GetFullPath($PastaJogo).TrimEnd('\')
    if ($PastaJogo -notmatch '^[A-Za-z]:\\') { throw 'Use uma pasta local do jogo.' }
    $null = Conferir-Caminho $PastaJogo
    $manifestPath = Join-Path $PastaJogo 'AkynoLeyend-build.json'
    $expectedProject = 'AkynoLeyend'
    $nomes = @('AkynoLeyend.exe', 'AkynoLeyend.dll', 'image.bin')
    # Fixed legacy names are needed to repair access before identity migration can read its inputs.
    if (![IO.File]::Exists($manifestPath) -and [IO.File]::Exists((Join-Path $PastaJogo 'ocarina-build.json'))) {
        $manifestPath = Join-Path $PastaJogo 'ocarina-build.json'
        $expectedProject = 'ocarina-hookshot'
        $nomes = @('hookshot.exe', 'hookshot_vk.dll', 'image.bin')
    }
    $null = Conferir-Caminho $manifestPath
    $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json
    if ($manifest.schema -ne 1 -or $manifest.project -ne $expectedProject) {
        throw 'Esta pasta nao contem um manifesto AkynoLeyend reconhecido.'
    }
    foreach ($nome in $nomes) {
        if ($manifest.files.$nome -notmatch '^[0-9a-fA-F]{64}$') { throw "Hash ausente/invalido: $nome" }
        $item = Conferir-Caminho (Join-Path $PastaJogo $nome) $false
        if ($item.PSIsContainer) { throw "O caminho deveria ser um arquivo: $nome" }
    }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    $admin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if ([string]::IsNullOrEmpty($SidUsuario)) { $SidUsuario = $identity.User.Value }
    if ($SidUsuario -notmatch '^S-1-(?:[0-9]+-)*[0-9]+$') { throw 'SID de usuario invalido.' }

    if (!$EtapaElevada -and !$admin) {
        # Discover a blocked private input as the normal user, never by guessing after elevation.
        $CacheAutorizado = ''
        try {
            if (!(Testar-Leitura-Pastas ([string]$manifest.romfs))) {
                $candidate = Split-Path ([IO.Path]::GetFullPath([string]$manifest.romfs)) -Parent
                Conferir-Cache $candidate ([string]$manifest.romfs) $true
                $CacheAutorizado = $candidate
            }
        } catch {
            Write-Host "A verificacao da entrada nao terminou: $($_.Exception.Message)"
            Write-Host 'O reparo abaixo continuara restrito aos tres arquivos do jogo.'
            $CacheAutorizado = ''
        }
        Write-Host ('Reparo de acesso: ' + ($nomes -join ', ') + '.')
        if ($CacheAutorizado) { Write-Host "Entrada privada bloqueada, tambem autorizada: $CacheAutorizado" }
        Write-Host 'O Windows pedira permissao de administrador para ajustar estes acessos.'
        $command = '& ' + (Texto-Literal $PSCommandPath) + ' -EtapaElevada -PastaJogo ' +
            (Texto-Literal $PastaJogo) + ' -SidUsuario ' + (Texto-Literal $SidUsuario)
        if ($CacheAutorizado) { $command += ' -CacheAutorizado ' + (Texto-Literal $CacheAutorizado) }
        $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
        $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $child = Start-Process -FilePath $powershell -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-EncodedCommand', $encoded) -Verb RunAs -Wait -PassThru
        if ($child.ExitCode -ne 0) { throw "O reparo terminou com codigo $($child.ExitCode). Veja diagnosticos-acesso." }
        # Back in the original, unelevated process. The game is not executed here.
        $python = Join-Path $PSScriptRoot 'ferramentas\python\python.exe'
        & $python -I -X utf8 (Join-Path $PSScriptRoot 'manage.py') audit-access --out $PastaJogo
        if ($LASTEXITCODE -ne 0) { throw 'A leitura ainda falhou no usuario normal. Envie o novo diagnostico.' }
        & $python -I -X utf8 (Join-Path $PSScriptRoot 'manage.py') run --out $PastaJogo --dry-run
        if ($LASTEXITCODE -ne 0) { throw 'A leitura foi reparada, mas a verificacao completa mostrou outro erro acima.' }
        Write-Host 'Acesso e hashes conferidos no usuario normal. Abra AkynoLeyendBuilder normalmente.'
        exit 0
    }
    if (!$admin) { throw 'A etapa de reparo precisa da elevacao solicitada pelo Windows.' }
    Conferir-Cache $CacheAutorizado ([string]$manifest.romfs)
    $logRoot = Join-Path $PSScriptRoot 'diagnosticos-acesso'
    $null = [IO.Directory]::CreateDirectory($logRoot)
    $logFile = Join-Path $logRoot ('reparo-' + (Get-Date -Format 'yyyyMMdd-HHmmss-ffff') + '.json')
    $registro = [ordered]@{ time = (Get-Date).ToString('o'); game_folder = $PastaJogo; user_sid = $SidUsuario;
        elevated = $admin; files = @(); input_cache = $CacheAutorizado; actions = @(); success = $false }
    $icacls = Join-Path $env:SystemRoot 'System32\icacls.exe'
    $takeown = Join-Path $env:SystemRoot 'System32\takeown.exe'
    try {
        foreach ($nome in $nomes) {
            $path = Join-Path $PastaJogo $nome
            $null = Conferir-Caminho $path
            try {
                $before = Get-Acl -LiteralPath $path
                $registro.files += [ordered]@{ name = $nome; owner_before = $before.Owner; sddl_before = $before.Sddl }
            } catch {
                $registro.files += [ordered]@{ name = $nome; acl_before_error = $_.Exception.Message }
            }
            $result = Chamar-Ferramenta $icacls @($path, '/reset')
            $output = $result.output; $code = $result.code
            $registro.actions += [ordered]@{ path = $path; operation = 'reset'; code = $code; output = ($output | Out-String) }
            if ($code -ne 0) {
                $result = Chamar-Ferramenta $takeown @('/f', $path, '/a')
                $output = $result.output; $code = $result.code
                $registro.actions += [ordered]@{ path = $path; operation = 'takeown-file-only'; code = $code; output = ($output | Out-String) }
                if ($code -ne 0) { throw "O Windows continuou negando o reparo de $nome" }
                $result = Chamar-Ferramenta $icacls @($path, '/reset')
                if ($result.code -ne 0) { throw "Nao foi possivel restaurar a heranca de $nome" }
            }
            $result = Chamar-Ferramenta $icacls @($path, '/grant:r', ('*' + $SidUsuario + ':(M)'))
            $output = $result.output; $code = $result.code
            $registro.actions += [ordered]@{ path = $path; operation = 'grant-user-modify'; code = $code; output = ($output | Out-String) }
            if ($code -ne 0) { throw "Nao foi possivel conceder acesso ao usuario em $nome" }
            $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
            if ($actual -ne $manifest.files.$nome) { throw "Hash divergente em $nome; nao execute o jogo antes de conferir o build." }
            $after = Get-Acl -LiteralPath $path
            $registro.files[-1]['sddl_after'] = $after.Sddl
            $registro.files[-1]['sha256'] = $actual
        }
        if ($CacheAutorizado) {
            $null = Conferir-Caminho $CacheAutorizado
            $before = Get-Acl -LiteralPath $CacheAutorizado
            $registro['input_sddl_before'] = $before.Sddl
            # One exact private input root, no drive/profile/work reset and no /T or /R.
            $result = Chamar-Ferramenta $icacls @($CacheAutorizado, '/grant:r', ('*' + $SidUsuario + ':(OI)(CI)(M)'))
            $output = $result.output; $code = $result.code
            $registro.actions += [ordered]@{ path = $CacheAutorizado; operation = 'grant-input-user-inheritable'; code = $code; output = ($output | Out-String) }
            if ($code -ne 0) { throw 'Nao foi possivel recuperar a entrada privada autorizada.' }
        }
        $registro.success = $true
        Write-Host 'Permissoes ajustadas e arquivos conferidos, sem recompilar ou executar o jogo.'
    } catch {
        $registro['error'] = $_.Exception.Message
        throw
    } finally {
        [IO.File]::WriteAllText($logFile, ($registro | ConvertTo-Json -Depth 8), (New-Object Text.UTF8Encoding($false)))
        Write-Host "Registro do reparo: $logFile"
    }
    exit 0
} catch {
    Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
