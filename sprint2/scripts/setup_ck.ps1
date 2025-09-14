# Baixa e compila o CK (Java code metrics)
# Pré-requisitos: Git, Maven, Java 11+ disponíveis no PATH
param(
    [string]$RepoUrl = "https://github.com/mauricioaniche/ck.git",
    [string]$TargetDir = "$PSScriptRoot/../tools/ck",
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$target = Resolve-Path -LiteralPath $TargetDir -ErrorAction SilentlyContinue
if (-not $target) {
    New-Item -ItemType Directory -Path $TargetDir | Out-Null
    $target = Resolve-Path -LiteralPath $TargetDir
}

Write-Host "[CK] Target: $target"

# Verificações básicas
function Assert-Tool($name, $check) {
  try { iex $check | Out-Null } catch { throw "Ferramenta necessária não encontrada: $name" }
}
Assert-Tool 'git' 'git --version'
Assert-Tool 'mvn' 'mvn -v'
Assert-Tool 'java' 'java -version'

$srcDir = Join-Path $target 'src'
# Em PowerShell, use -and dentro de parênteses na condição
if ((Test-Path -LiteralPath $srcDir) -and (-not $Force.IsPresent)) {
  Write-Host "[CK] Repositório já existe em $srcDir. Use -Force para atualizar."
} else {
  if (Test-Path -LiteralPath $srcDir) { Remove-Item -Recurse -Force -LiteralPath $srcDir }
  git clone --depth=1 $RepoUrl $srcDir
}

Push-Location $srcDir
try {
  Write-Host "[CK] Build via Maven..."
  mvn -q -DskipTests clean package
} finally {
  Pop-Location
}

$jar = Get-ChildItem -Path (Join-Path $srcDir 'target') -Filter '*jar-with-dependencies.jar' -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $jar) { throw "[CK] JAR with dependencies não encontrado em target/." }

# Copia para tools/ck
$destJar = Join-Path $target $jar.Name
Copy-Item $jar.FullName $destJar -Force

# Cria um marker/manifesto simples
$manifest = @{
  repo = $RepoUrl
  built_at = (Get-Date).ToString('s')
  jar = (Split-Path -Leaf $destJar)
}
$manifest | ConvertTo-Json | Set-Content (Join-Path $target 'ck_build.json')

Write-Host "[CK] Pronto: $destJar"
