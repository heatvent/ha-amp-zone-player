# Release a new HACS version
#
# Usage (from repo root):
#   .\tools\release.ps1 0.1.1
#   .\tools\release.ps1 0.2.0 -Notes "Add browse_media passthrough"
#
# HACS only sees GitHub Releases (hacs.json hide_default_branch).
# Tag must be vX.Y.Z and match custom_components/amp_zone_player/manifest.json "version".

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [string]$Notes = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$manifestPath = Join-Path $root "custom_components\amp_zone_player\manifest.json"
$changelogPath = Join-Path $root "CHANGELOG.md"
$tag = "v$Version"

if (-not (Test-Path $manifestPath)) {
    throw "Run from repo root; missing manifest.json"
}

$dirty = git status --porcelain
if ($dirty) {
    throw "Working tree is dirty. Commit or stash first.`n$dirty"
}

$raw = Get-Content -LiteralPath $manifestPath -Raw
if ($raw -notmatch '"version"\s*:\s*"([^"]+)"') {
    throw "Could not find version in manifest.json"
}
$old = $Matches[1]
if ($old -ne $Version) {
    $raw = [regex]::Replace($raw, '"version"\s*:\s*"[^"]+"', "`"version`": `"$Version`"")
    [System.IO.File]::WriteAllText($manifestPath, $raw)
    Write-Host "manifest.json: $old -> $Version"
} else {
    Write-Host "manifest.json already at $Version"
}

$date = Get-Date -Format "yyyy-MM-dd"
$bullet = if ($Notes) { $Notes } else { "See commit history." }
$changelog = Get-Content -LiteralPath $changelogPath -Raw
if ($changelog -notmatch [regex]::Escape("## $Version")) {
    $entry = "## $Version - $date`r`n`r`n- $bullet`r`n`r`n"
    if ($changelog -match '(?s)^(# Changelog\s*)') {
        $changelog = $changelog -replace '(# Changelog\s*)', "`$1`r`n$entry"
    } else {
        $changelog = "# Changelog`r`n`r`n$entry$changelog"
    }
    [System.IO.File]::WriteAllText($changelogPath, $changelog)
    Write-Host "CHANGELOG.md: added $Version"
}

git add -- "custom_components/amp_zone_player/manifest.json" "CHANGELOG.md"
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "Release $Version"
} else {
    Write-Host "No version file changes to commit"
}

git push origin HEAD

$existingTag = git tag -l $tag
if ($existingTag) {
    throw "Tag $tag already exists"
}

git tag -a $tag -m "Release $Version"
git push origin $tag

$releaseNotes = if ($Notes) { $Notes } else { "Music Assistant Amp Zone Player $Version" }
gh release create $tag --title $Version --notes $releaseNotes --latest

Write-Host ""
Write-Host "Published https://github.com/heatvent/ha-amp-zone-player/releases/tag/$tag"
Write-Host "In HACS: update Music Assistant Amp Zone Player to $Version, then restart HA."
