<#
 Instala o cloc no Windows via winget (preferencial) ou choco (fallback).
 Também verifica a instalação ao final.

 Uso (PowerShell):
   powershell -ExecutionPolicy Bypass -File sprint2/scripts/setup_cloc.ps1
#>

Write-Host "[cloc] Verificando instalação..."
$clocCmd = Get-Command cloc -ErrorAction SilentlyContinue
if ($null -ne $clocCmd) {
    cloc --version
    Write-Host "[cloc] Já instalado."
    exit 0
}

Write-Host "[cloc] Tentando instalar com winget..."
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($null -ne $winget) {
    try {
        winget install --id AlDanial.cloc --accept-source-agreements --accept-package-agreements -e
    } catch {
        Write-Warning "[cloc] Falha no winget: $_"
    }
}

$clocCmd = Get-Command cloc -ErrorAction SilentlyContinue
if ($null -eq $clocCmd) {
    Write-Host "[cloc] Tentando instalar com chocolatey..."
    $choco = Get-Command choco -ErrorAction SilentlyContinue
    if ($null -ne $choco) {
        try {
            choco install cloc -y
        } catch {
            Write-Warning "[cloc] Falha no chocolatey: $_"
        }
    } else {
        Write-Warning "[cloc] Nem winget nem choco encontrados. Instale cloc manualmente: https://github.com/AlDanial/cloc"
    }
}

$clocCmd = Get-Command cloc -ErrorAction SilentlyContinue
if ($null -ne $clocCmd) {
    Write-Host "[cloc] Instalação OK:"
    cloc --version
    exit 0
} else {
    Write-Error "[cloc] Não foi possível instalar o cloc automaticamente."
    exit 1
}
