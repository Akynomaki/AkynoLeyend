[CmdletBinding()]
param(
    [string]$Jogo,
    [string]$Exefs,
    [string]$Romfs,
    [string]$Destino,
    [string]$Trabalho,
    [string]$Idioma = 'pt-BR',
    [ValidateRange(1, 64)][int]$Jobs,
    [switch]$RenderizadorDosFontes,
    [ValidateSet(0, 3, 6, 12, 24)][int]$BlocoMiB = 0
)
$ErrorActionPreference = 'Stop'
try {
    # Resolve defaults in the script body, after parameter binding.
    $scriptFile = $PSCommandPath
    if ([string]::IsNullOrWhiteSpace($scriptFile)) {
        $scriptFile = $MyInvocation.MyCommand.Path
    }
    if ([string]::IsNullOrWhiteSpace($scriptFile)) {
        throw 'Nao foi possivel identificar a pasta deste script. Abra Compilar.cmd na pasta extraida.'
    }
    $projectRoot = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($scriptFile))
    if ([string]::IsNullOrWhiteSpace($Destino)) {
        $Destino = Join-Path $projectRoot 'jogo'
    }
    if ([string]::IsNullOrWhiteSpace($Trabalho)) {
        $Trabalho = Join-Path $projectRoot 'work'
    }
    $python = Join-Path $projectRoot 'ferramentas\python\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Extraia o pacote completo; a pasta ferramentas deve ficar ao lado deste arquivo.'
    }
    $arguments = @('-I', (Join-Path $projectRoot 'manage.py'), 'build',
        '--out', $Destino, '--work', $Trabalho, '--language', $Idioma)
    if ($BlocoMiB -gt 0) { $arguments += @('--chunk-mib', [string]$BlocoMiB) }
    if ($Exefs -or $Romfs) {
        if ($Jogo -or -not $Exefs -or -not $Romfs) {
            throw 'Use -Jogo ARQUIVO ou o par -Exefs PASTA -Romfs PASTA.'
        }
        $arguments += @('--exefs', $Exefs, '--romfs', $Romfs)
    } else {
        if (-not $Jogo) {
            Add-Type -AssemblyName System.Windows.Forms
            $dialog = New-Object System.Windows.Forms.OpenFileDialog
            try {
                $dialog.Title = 'Selecione sua copia local do jogo (.nup)'
                $dialog.Filter = 'Arquivo NUP (*.nup)|*.nup'
                if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 2 }
                $Jogo = $dialog.FileName
            } finally { $dialog.Dispose() }
        }
        $arguments += @('--nup', $Jogo)
    }
    if ($PSBoundParameters.ContainsKey('Jobs')) { $arguments += @('--jobs', [string]$Jobs) }
    if ($RenderizadorDosFontes) { $arguments += '--renderer-source' }
    & $python @arguments
    exit $LASTEXITCODE
} catch {
    Write-Host ('Falha: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
