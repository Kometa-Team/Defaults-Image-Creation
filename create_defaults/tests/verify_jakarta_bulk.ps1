$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '../create_default_posters.ps1'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $source), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Bulk script has syntax errors' }
$normalizer = $ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-NormalizedFontToken'
}, $true)
. ([scriptblock]::Create($normalizer[0].Extent.Text))
function Get-OptimalPointSize { $script:fitCalls++; return 321 }
$script_path = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$approved = @()
foreach ($category in @('CreateDecade', 'CreateYear')) {
    $function = $ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $category
    }, $true)[0]
    # Execute only the actual literal table and command-building loop, never the bulk workflow.
    $tables = @($function.Body.EndBlock.Statements | Where-Object {
        $_ -is [System.Management.Automation.Language.AssignmentStatementAst] -and
        $_.Left.Extent.Text -eq '$myArray' -and $_.Right.Extent.Text -like '*Plus Jakarta Sans Bold*'
    })
    $loops = @($function.Body.EndBlock.Statements | Where-Object {
        $_ -is [System.Management.Automation.Language.ForEachStatementAst] -and
        $_.Condition.Extent.Text -eq '$myArray' -and $_.Extent.StartOffset -gt $tables[0].Extent.EndOffset
    } | Select-Object -First 1)
    if ($tables.Count -ne 1 -or $loops.Count -ne 1) { throw 'Bulk table/loop isolation changed' }
    $arr = @()
    $script:fitCalls = 0
    . ([scriptblock]::Create($tables[0].Extent.Text))
    . ([scriptblock]::Create($loops[0].Extent.Text))
    $jakarta = @($arr | Where-Object { $_ -like '*Plus Jakarta Sans Bold*' })
    $others = @($arr | Where-Object { $_ -notlike '*Plus Jakarta Sans Bold*' })
    foreach ($command in $jakarta) {
        if ($command -notmatch '-font_size\s+409(?:\s|$)') { throw 'Approved Jakarta size was auto-fitted' }
    }
    foreach ($command in $others) {
        if ($command -notmatch '-font_size\s+321(?:\s|$)') { throw 'Unrelated style bypassed the existing fitter' }
    }
    if ($script:fitCalls -ne $others.Count) { throw 'Unexpected fitter routing' }
    $approved += $jakarta
}
if ($approved.Count -ne 11) { throw 'Expected exactly 11 fixed-size Jakarta commands' }
Write-Output 'PASS: all 11 real Jakarta commands use 409 points; unrelated styles retain auto-fitting; no bootstrap or publishing executed.'
