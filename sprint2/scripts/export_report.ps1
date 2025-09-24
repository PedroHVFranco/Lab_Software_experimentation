param(
    [string]$Output='sprint2/docs/RELATORIO.pdf',
    [switch]$TryHtml,
    [ValidateSet('auto','pdflatex','wkhtmltopdf','weasyprint','prince','tectonic')]
    [string]$Engine='auto'
)

$ErrorActionPreference = 'Stop'
# Resolve sprint2 directory (parent of scripts dir)
$scriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sprint2Dir = Split-Path -Parent $scriptsDir
$md = Join-Path $sprint2Dir 'docs/RELATORIO.md'

if (-not (Test-Path $md)) { throw "Report not found: $md" }

function Test-Command($name) {
    $old = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    $ErrorActionPreference = $old
    return $cmd -ne $null
}

# Helper: locate Edge (headless) if needed
function Find-Edge {
    if (Test-Command 'msedge') { return 'msedge' }
    $paths = @(
        "$env:ProgramFiles\\Microsoft\\Edge\\Application\\msedge.exe",
        "$env:ProgramFiles(x86)\\Microsoft\\Edge\\Application\\msedge.exe"
    )
    foreach ($p in $paths) { if (Test-Path $p) { return $p } }
    return $null
}

function Ensure-PdfGenerated($path) {
    return (Test-Path $path) -and ((Get-Item $path).Length -gt 1024)
}

$pdfOk = $false

# Prefer Pandoc (with chosen engine) → Pandoc+wkhtmltopdf → Edge headless → HTML fallback
if (Test-Command 'pandoc') {
    $engineToUse = $Engine
    if ($Engine -eq 'auto') {
        if (Test-Command 'pdflatex')      { $engineToUse = 'pdflatex' }
        elseif (Test-Command 'wkhtmltopdf') { $engineToUse = 'wkhtmltopdf' }
        elseif (Test-Command 'weasyprint')  { $engineToUse = 'weasyprint' }
        elseif (Test-Command 'prince')      { $engineToUse = 'prince' }
        elseif (Test-Command 'tectonic')    { $engineToUse = 'tectonic' }
        else { $engineToUse = '' }
    }

    try {
        if ([string]::IsNullOrEmpty($engineToUse)) {
            Write-Host 'Pandoc found but no PDF engine detected; creating HTML first...' -ForegroundColor Cyan
            $tmpHtml = [System.IO.Path]::ChangeExtension($Output, '.tmp.html')
            pandoc "$md" -t html5 -s -o "$tmpHtml"
            $edge = Find-Edge
            if ($edge) {
                Write-Host "Printing HTML to PDF via Edge: $edge" -ForegroundColor Cyan
                & $edge --headless --disable-gpu --print-to-pdf="$Output" "$tmpHtml"
                Remove-Item $tmpHtml -ErrorAction SilentlyContinue
                if (Ensure-PdfGenerated $Output) {
                    $pdfOk = $true
                }
            }
        } else {
            Write-Host "Using pandoc with --pdf-engine=$engineToUse ..." -ForegroundColor Cyan
            pandoc "$md" -o "$Output" --pdf-engine=$engineToUse
            if (Ensure-PdfGenerated $Output) { $pdfOk = $true }
        }
    } catch {
        Write-Warning "Pandoc export failed: $($_.Exception.Message)"
    }
}

if (-not $pdfOk -and (Test-Command 'wkhtmltopdf' -and $TryHtml)) {
    Write-Host 'Using wkhtmltopdf via intermediate HTML...' -ForegroundColor Cyan
    $tmpHtml = [System.IO.Path]::ChangeExtension($Output, '.html')
    # Minimal HTML from Markdown (no pandoc): wrap MD as preformatted if pandoc not available
    if (Test-Command 'pandoc') {
        pandoc "$md" -t html5 -s -o "$tmpHtml"
    } else {
        $body = Get-Content -Raw "$md"
        "<html><meta charset='utf-8'><body><pre>" + [System.Web.HttpUtility]::HtmlEncode($body) + "</pre></body></html>" | Out-File -Encoding utf8 "$tmpHtml"
    }
    wkhtmltopdf "$tmpHtml" "$Output"
    Remove-Item $tmpHtml -ErrorAction SilentlyContinue
    if (Ensure-PdfGenerated $Output) { $pdfOk = $true }
}

if ($pdfOk) {
    Write-Host "PDF generated: $Output" -ForegroundColor Green
} else {
    Write-Warning 'Could not generate PDF automatically. Install Pandoc (and optionally wkhtmltopdf) for best results.'
    Write-Host 'Saving a HTML copy next to the report as fallback.' -ForegroundColor Yellow
    $htmlOut = [System.IO.Path]::ChangeExtension($Output, '.html')
    if (Test-Command 'pandoc') {
        pandoc "$md" -t html5 -s -o "$htmlOut"
    } else {
        Copy-Item "$md" $htmlOut
    }
    Write-Host "HTML copy saved: $htmlOut" -ForegroundColor Green
}
