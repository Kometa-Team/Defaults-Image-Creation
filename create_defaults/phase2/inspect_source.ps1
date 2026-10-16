# Development audit only. Parse source ASTs; never execute the generator/bootstrap.
param(
    [Parameter(Mandatory)][string]$Source,
    [Parameter(Mandatory)][string]$OutputFile
)
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $Source), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Source parse failed; audit not written' }
$functions = @($ast.FindAll({ param($n)
    $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -cmatch '^Create\w+$'
}, $true))
$inventory = @($functions | ForEach-Object {
    $function = $_
    $calls = @($function.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.CommandAst] -and $n.GetCommandName() -eq 'Get-YamlPropertyValue'
    }, $true) | ForEach-Object { @{ line = $_.Extent.StartLineNumber; expression = $_.Extent.Text } })
    $loops = @($function.FindAll({ param($n)
        $n -is [System.Management.Automation.Language.ForEachStatementAst] -or $n -is [System.Management.Automation.Language.ForStatementAst]
    }, $true) | ForEach-Object { @{ line = $_.Extent.StartLineNumber; kind = $_.GetType().Name } })
    @{ category = $function.Name.Substring(6); line = $function.Extent.StartLineNumber;
       end_line = $function.Extent.EndLineNumber; translation_calls = $calls; loops = $loops }
})
$aliases = @{}
$all = @()
foreach ($switch in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.SwitchStatementAst] }, $true)) {
    foreach ($clause in $switch.Clauses) {
        if ($clause.Item1 -isnot [System.Management.Automation.Language.StringConstantExpressionAst]) { continue }
        $commands = @($clause.Item2.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true) | ForEach-Object { $_.GetCommandName() })
        if ($clause.Item1.Value -eq 'All') { $all = $commands; continue }
        if ($commands.Count -eq 1 -and $commands[0] -cin $functions.Name) {
            $aliases[$clause.Item1.Value] = $commands[0].Substring(6)
        }
    }
}
$languageAssignments = @($ast.FindAll({ param($n)
    $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and $n.Left.Extent.Text -eq '$LanguageCodes'
}, $true))
if ($languageAssignments.Count -ne 1) { throw 'Ambiguous supported-language assignment' }
$languages = @($languageAssignments[0].Right.FindAll({ param($n)
    $n -is [System.Management.Automation.Language.StringConstantExpressionAst]
}, $true) | ForEach-Object { $_.Value })
if ($all.Count -ne $functions.Count -or -not $languages.Count) { throw 'Incomplete source inspection' }
$result = @{ schema_version = 1; source_sha256 = (Get-FileHash -LiteralPath $Source).Hash.ToLowerInvariant();
    scope = 'Parser AST only; no source execution'; functions = $inventory; aliases = $aliases;
    all_dispatch = @($all | ForEach-Object { $_.Substring(6) }); supported_languages = $languages }
if (Test-Path -LiteralPath $OutputFile) { throw 'Refusing to overwrite an existing structural audit' }
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputFile -Encoding utf8NoBOM
