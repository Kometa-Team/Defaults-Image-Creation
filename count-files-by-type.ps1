[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Path = ".",

    [switch]$IncludeHidden,

    [switch]$IncludeNoExtension
)

$resolvedPath = (Resolve-Path -LiteralPath $Path).Path

$items = Get-ChildItem -LiteralPath $resolvedPath -File -Recurse -Force -ErrorAction SilentlyContinue

if (-not $IncludeHidden) {
    $items = $items | Where-Object {
        -not ($_.Attributes -band [IO.FileAttributes]::Hidden) -and
        -not ($_.Attributes -band [IO.FileAttributes]::System)
    }
}

$results = $items |
    Group-Object {
        if ([string]::IsNullOrWhiteSpace($_.Extension)) {
            "[no extension]"
        }
        else {
            $_.Extension.ToLowerInvariant()
        }
    } |
    Where-Object { $IncludeNoExtension -or $_.Name -ne "[no extension]" } |
    Sort-Object @{ Expression = "Count"; Descending = $true }, @{ Expression = "Name"; Descending = $false } |
    Select-Object @{ Name = "FileType"; Expression = { $_.Name } }, @{ Name = "Count"; Expression = { $_.Count } }

if (-not $results) {
    Write-Host "No matching files found under $resolvedPath"
    exit 0
}

$results | Format-Table -AutoSize
