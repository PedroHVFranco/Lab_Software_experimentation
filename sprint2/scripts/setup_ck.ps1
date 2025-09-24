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

# Helpers: tentar localizar ferramentas comuns e ajustar PATH da sessão
function Add-ToPathIfExists {
  param([string]$path)
  if ([string]::IsNullOrWhiteSpace($path)) { return $false }
  if (Test-Path -LiteralPath $path) {
    if (-not ($env:Path -split ';' | Where-Object { $_ -eq $path })) {
      $env:Path = "$path;" + $env:Path
    }
    return $true
  }
  return $false
}

function Ensure-Tool {
  param(
    [string]$name,
    [string]$exe,
    [string[]]$candidateDirs
  )
  $found = $false
  try {
    $null = Get-Command $exe -ErrorAction Stop
    $found = $true
  } catch {
    foreach ($d in $candidateDirs) {
      if (Add-ToPathIfExists $d) {
        try { $null = Get-Command $exe -ErrorAction Stop; $found = $true; break } catch { }
      }
    }
  }
  if (-not $found) { throw "Ferramenta necessária não encontrada: $name ($exe)" }
}

# Candidatos comuns
$gitCandidates = @(
  "$env:ProgramFiles\Git\cmd",
  "$env:ProgramFiles\Git\bin",
  "${env:ProgramFiles(x86)}\Git\cmd",
  "${env:ProgramFiles(x86)}\Git\bin"
)
$mvnCandidates = @(
  "$env:ProgramData\chocolatey\bin",
  "$env:ProgramData\chocolatey\lib\maven\apache-maven-3.9.11\bin",
  "$env:ProgramFiles\Apache\maven\bin"
)
$javaCandidates = @()
if ($env:JAVA_HOME) { $javaCandidates += (Join-Path $env:JAVA_HOME 'bin') }
$javaCandidates += @(
  "$env:ProgramFiles\Eclipse Adoptium\jdk-17.0.16.8-hotspot\bin",
  "$env:ProgramFiles\Eclipse Adoptium\jdk-17\bin",
  "$env:ProgramFiles\Java\jdk-17\bin",
  "$env:ProgramFiles\Java\jdk-11\bin"
)

Ensure-Tool -name 'git' -exe 'git' -candidateDirs $gitCandidates
Ensure-Tool -name 'maven' -exe 'mvn' -candidateDirs $mvnCandidates
Ensure-Tool -name 'java' -exe 'java' -candidateDirs $javaCandidates

# Se já houver um JAR válido no diretório alvo e não for Force, reutilize
$existingJar = Get-ChildItem -Path $target -Filter '*jar-with-dependencies.jar' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($existingJar -and (-not $Force.IsPresent)) {
  Write-Host "[CK] JAR já encontrado em $($existingJar.FullName). Usando existente (use -Force para rebuild)."
  # Atualiza manifesto simples e sai
  $manifest = @{
    repo = $RepoUrl
    built_at = (Get-Date).ToString('s')
    jar = (Split-Path -Leaf $existingJar.FullName)
    reused = $true
  }
  $manifest | ConvertTo-Json | Set-Content (Join-Path $target 'ck_build.json')
  exit 0
}

$srcDir = Join-Path $target 'src'

# Se src existe mas não contém pom.xml e não for Force, vamos forçar reclone
$needsClone = $true
if (Test-Path -LiteralPath $srcDir) {
  if (Test-Path -LiteralPath (Join-Path $srcDir 'pom.xml')) {
    $needsClone = $false
    if ($Force.IsPresent) { $needsClone = $true }
  } else {
    $needsClone = $true
  }
}
if ($needsClone) {
  if (Test-Path -LiteralPath $srcDir) { Remove-Item -Recurse -Force -LiteralPath $srcDir }
  Write-Host "[CK] Clonando repositório CK em $srcDir ..."
  git clone --depth=1 $RepoUrl $srcDir
} else {
  Write-Host "[CK] Repositório já existe em $srcDir. (Use -Force para atualizar)"
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
