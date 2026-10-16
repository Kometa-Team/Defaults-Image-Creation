param(
    [Parameter(Mandatory)][string]$Source,
    [Parameter(Mandatory)][string]$Assets,
    [Parameter(Mandatory)][string]$TranslationJson,
    [Parameter(Mandatory)][string]$RowsJson,
    [Parameter(Mandatory)][string]$OutputFile,
    [Parameter(Mandatory)][string]$Magick,
    [switch]$DeferredFitting
)
$ErrorActionPreference = 'Stop'
$Source = [IO.Path]::GetFullPath($Source)
$Assets = [IO.Path]::GetFullPath($Assets)
$OutputFile = [IO.Path]::GetFullPath($OutputFile)
if ($OutputFile.StartsWith($Assets + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Capture output must be outside the production asset directory'
}
if (Test-Path -LiteralPath $OutputFile) { throw 'Capture output already exists' }
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'Bulk source has syntax errors' }
$sourceHash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash.ToLowerInvariant()
$functions = @($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true))
$categories = @($functions | Where-Object { $_.Name -like 'Create*' })
$allowed = @('.\create_poster.ps1', 'ConvertFrom-Csv', 'Copy-Item', 'Find-Path', 'Get-NormalizedFontToken',
    'Get-OptimalPointSize', 'Get-YamlPropertyValue', 'Join-Path', 'LaunchScripts', 'magick', 'MonitorProcess',
    'Move-Item', 'Set-Location', 'Set-TextBetweenDelimiters', 'Start-Sleep', 'Write-Host', 'WriteToLogFile')
foreach ($function in $categories) {
    if ($DeferredFitting) {
        foreach ($variable in $function.FindAll({ param($node) $node -is [System.Management.Automation.Language.VariableExpressionAst] -and $node.VariablePath.UserPath -eq 'optimalFontSize' }, $true)) {
            $parent = $variable.Parent
            while ($parent -and $parent -isnot [System.Management.Automation.Language.AssignmentStatementAst]) { $parent = $parent.Parent }
            if (-not $parent -or ($parent.Left.Extent.Text -ne '$optimalFontSize' -and $parent.Left.Extent.Text -ne '$arr')) {
                throw 'Fitting result influences control flow; deferred capture is not safe'
            }
        }
    }
    foreach ($command in $function.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] }, $true)) {
        if ($command.GetCommandName() -notin $allowed) { throw "Unreviewed category command: $($command.Extent.Text)" }
    }
    foreach ($member in $function.FindAll({ param($node) $node -is [System.Management.Automation.Language.InvokeMemberExpressionAst] }, $true)) {
        if ($member.Member.Extent.Text -notin @('ToString', 'ToUpper', 'ToLower', 'Trim')) {
            throw "Unreviewed category method: $($member.Extent.Text)"
        }
    }
}
$script_path = $Assets
function Convert-TranslationMap($Value) {
    if ($Value -is [Collections.IDictionary]) {
        $result = @{}
        foreach ($key in $Value.Keys) { $result[$key] = Convert-TranslationMap $Value[$key] }
        return $result
    }
    if ($Value -is [array]) { return ,@($Value | ForEach-Object { Convert-TranslationMap $_ }) }
    return $Value
}
$global:ConfigObj = Convert-TranslationMap (Get-Content -LiteralPath $TranslationJson -Raw | ConvertFrom-Json -AsHashtable)
$TranslationFilePath = 'frozen English translation snapshot'
$rows = Get-Content -LiteralPath $RowsJson -Raw | ConvertFrom-Json -AsHashtable
function Row-Key($Category, $Row) {
    $ordered = [ordered]@{}
    foreach ($key in ($Row.Keys | Sort-Object)) { $ordered[$key] = "$($Row[$key])".Trim() }
    return "$Category|$($ordered | ConvertTo-Json -Compress)"
}
$script:rowLookup = @{}
foreach ($row in $rows) {
    $key = Row-Key $row.category $row.row
    if (-not $script:rowLookup.ContainsKey($key)) { $script:rowLookup[$key] = [Collections.Generic.List[int]]::new() }
    $script:rowLookup[$key].Add([int]$row.line)
}
$script:jobs = [Collections.Generic.List[object]]::new()
$script:overlays = [Collections.Generic.List[object]]::new()
$script:operations = [Collections.Generic.List[object]]::new()
$script:queued = [Collections.Generic.List[object]]::new()
$script:fitCache = @{}
$script:virtualFiles = @{}
$script:lastFit = $null
$script:category = ''
$script:virtualRoot = $Assets

# Import only read-only data helpers, never the bulk script's bootstrap or dispatch.
foreach ($name in @('Get-NormalizedFontToken', 'Get-BundledFontPath', 'Get-YamlPropertyValue', 'Set-TextBetweenDelimiters')) {
    $function = @($functions | Where-Object Name -eq $name)
    if ($function.Count -ne 1) { throw "Data helper changed: $name" }
    . ([scriptblock]::Create($function[0].Extent.Text))
}
function WriteToLogFile { }
function Write-Host { }
function Set-Location { }
function Find-Path { }
function Start-Sleep { }
function MonitorProcess { }
function Resolve-ExactFont([string]$Name) {
    $path = Get-BundledFontPath -FontName $Name
    if (-not $path) { throw "No exact bundled font for $Name" }
    return $path.Replace('\', '/')
}
function Get-OptimalPointSize {
    param([string]$text, [string]$font, [int]$box_width, [int]$box_height, [int]$min_pointsize, [int]$max_pointsize)
    $path = Resolve-ExactFont $font
    $key = @($text, $path, $box_width, $box_height, $min_pointsize, $max_pointsize) | ConvertTo-Json -Compress
    if (-not $script:fitCache.ContainsKey($key)) {
        $measured = $null
        if ($DeferredFitting -or [string]::IsNullOrWhiteSpace($text)) { $size = $max_pointsize }
        else {
            $value = & $Magick -size "${box_width}x${box_height}" -font $path -gravity center -fill black "caption:$text" -format '%[caption:pointsize]' info: 2>&1
            if ($LASTEXITCODE -ne 0 -or "$value" -notmatch '^\d+(\.\d+)?$') { throw "Exact fitting failed: $value" }
            $measured = [int][double]"$value"
            $size = [math]::Min($max_pointsize, [math]::Max($min_pointsize, $measured))
        }
        $script:fitCache[$key] = @{ text = $text; font = $font; font_path = $path; box = @($box_width, $box_height);
            minimum = $min_pointsize; maximum = $max_pointsize; measured = $measured; point_size = $size; deferred = [bool]$DeferredFitting }
    }
    $script:lastFit = $script:fitCache[$key]
    return $script:lastFit.point_size
}
function Virtual-Path([string]$Path) {
    $Path = $Path.Replace('\', '/')
    if ([IO.Path]::IsPathRooted($Path)) { $Path = [IO.Path]::GetRelativePath($Assets, $Path).Replace('\', '/') }
    return $Path.TrimStart('/').TrimEnd('/')
}
function Capture-Move {
    param([string[]]$Path, [string]$Destination, [switch]$Force, [int]$CaptureLine)
    foreach ($sourcePath in $Path) {
        $from = Virtual-Path $sourcePath
        $to = Virtual-Path $Destination
        $script:operations.Add(@{ kind = 'move'; source = $from; destination = $to; line = $CaptureLine; category = $script:category })
        foreach ($key in @($script:virtualFiles.Keys)) {
            if ($key -eq $from -or $key.StartsWith($from + '/', [StringComparison]::OrdinalIgnoreCase)) {
                $suffix = $key.Substring($from.Length).TrimStart('/')
                $target = if ($suffix) { "$to/$suffix" } elseif ([IO.Path]::GetExtension($to)) { $to } else { "$to/$([IO.Path]::GetFileName($key))" }
                $entry = $script:virtualFiles[$key]
                $script:virtualFiles.Remove($key)
                $script:virtualFiles[$target] = $entry
            }
        }
    }
}
function Capture-Copy {
    param([string[]]$Path, [string]$Destination, [switch]$Force, [switch]$Recurse, [int]$CaptureLine)
    foreach ($sourcePath in $Path) {
        $from = Virtual-Path $sourcePath
        $to = Virtual-Path $Destination
        $script:operations.Add(@{ kind = 'copy'; source = $from; destination = $to; line = $CaptureLine; category = $script:category })
        foreach ($key in @($script:virtualFiles.Keys)) {
            if ($key -eq $from -or $key.StartsWith($from + '/', [StringComparison]::OrdinalIgnoreCase)) {
                $suffix = $key.Substring($from.Length).TrimStart('/')
                $target = if ($suffix) { "$to/$suffix" } elseif ([IO.Path]::GetExtension($to)) { $to } else { "$to/$([IO.Path]::GetFileName($key))" }
                $script:virtualFiles[$target] = $script:virtualFiles[$key]
            }
        }
    }
}
function Safe-Argument($Node) {
    if ($Node -is [System.Management.Automation.Language.ExpandableStringExpressionAst] -and $Node.NestedExpressions.Count) {
        throw "Unresolved expression in expanded invocation: $($Node.Extent.Text)"
    }
    return $Node.SafeGetValue()
}
function Parse-Invocation([string]$Command) {
    $t = $null; $e = $null
    $parsed = [System.Management.Automation.Language.Parser]::ParseInput($Command, [ref]$t, [ref]$e)
    $commands = @($parsed.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] }, $true))
    if ($e.Count -or $commands.Count -ne 1 -or $commands[0].GetCommandName() -ne '.\create_poster.ps1') { throw "Unsafe queued invocation: $Command" }
    $elements = $commands[0].CommandElements
    $values = [ordered]@{}
    for ($i = 1; $i -lt $elements.Count; $i += 2) {
        if ($elements[$i] -isnot [System.Management.Automation.Language.CommandParameterAst] -or $i + 1 -ge $elements.Count) { throw 'Unexpected invocation argument shape' }
        $name = $elements[$i].ParameterName
        if ($values.Contains($name)) { throw 'Duplicate composer parameter' }
        $values[$name] = Safe-Argument $elements[$i + 1]
    }
    return $values
}
function Register-Queued {
    param([string]$Command, [object]$Row, [int]$Line, [string]$Color)
    $copy = [ordered]@{}
    if ($Row) { foreach ($property in $Row.PSObject.Properties) { $copy[$property.Name.Trim()] = "$($property.Value)".Trim() } }
    $original = if ($script:literalRowCopy) { $script:literalRowCopy } else { $copy }
    $script:queued.Add(@{ command = $Command; row = $original; effective_row = $copy; line = $Line; color = $Color; fitting = $script:lastFit })
}
function Register-LiteralRow($Row) {
    $script:literalRowCopy = [ordered]@{}
    foreach ($property in $Row.PSObject.Properties) { $script:literalRowCopy[$property.Name.Trim()] = "$($property.Value)".Trim() }
}
function Record-Invocation($Values, $Context) {
    if ("$($Values.text)" -like '*TRANSLATION NOT FOUND*') { throw 'Unresolved translation in captured invocation' }
    $sourceLine = $null
    if ($Context.row.Count) {
        $key = Row-Key $script:category $Context.row
        if ($script:rowLookup.ContainsKey($key)) {
            foreach ($line in $script:rowLookup[$key]) { if ($line -lt $Context.line -and ($null -eq $sourceLine -or $line -gt $sourceLine)) { $sourceLine = $line } }
        }
    }
    $fit = $Context.fitting
    if ($fit -and ("$($fit.text)" -ne "$($Values.text)" -or (Get-NormalizedFontToken $fit.font) -ne (Get-NormalizedFontToken $Values.font))) { $fit = $null }
    $index = $script:jobs.Count
    $entry = @{ index = $index; category = $script:category; producer_line = $Context.line; definition_line = $sourceLine;
        source_row = $Context.row; effective_source_row = $Context.effective_row; raw_parameters = $Values; fitting = $fit; dynamic = @{ color_loop = $Context.color } }
    $script:jobs.Add($entry)
    $name = "$($Values.out_name)".Replace('\', '/').TrimStart('/')
    if (-not $name) { $name = [IO.Path]::GetFileNameWithoutExtension("$($Values.logo)") + '-' + "$($Values.base_color)" }
    $script:virtualFiles["output/$name.jpg"] = $index
}
function LaunchScripts {
    param([string[]]$ScriptPaths)
    if ($ScriptPaths.Count -ne $script:queued.Count) { throw 'Queued invocation/context count mismatch' }
    for ($i = 0; $i -lt $ScriptPaths.Count; $i++) {
        if ($ScriptPaths[$i] -ne $script:queued[$i].command) { throw 'Queued command/context mismatch' }
        Record-Invocation (Parse-Invocation $ScriptPaths[$i]) $script:queued[$i]
    }
    $script:queued.Clear()
}
function Capture-Direct {
    param([string]$logo, [string]$logo_offset, [string]$logo_resize, [string]$text, [string]$text_offset,
        [string]$font, [string]$font_size, [string]$font_color, [string]$border, [string]$border_width,
        [string]$border_color, [string]$avg_color_image, [string]$out_name, [string]$base_color,
        [string]$gradient, [string]$avg_color, [string]$clean, [string]$white_wash, [int]$CaptureLine)
    $values = [ordered]@{}
    foreach ($key in $PSBoundParameters.Keys) { if ($key -ne 'CaptureLine') { $values[$key] = $PSBoundParameters[$key] } }
    Record-Invocation $values @{ row = @{}; line = $CaptureLine; color = $null; fitting = $null }
}
function Capture-Overlay {
    param([int]$CaptureLine, [Parameter(ValueFromRemainingArguments)][object[]]$Arguments)
    $script:overlays.Add(@{ category = $script:category; line = $CaptureLine; arguments = $Arguments })
}

# Instrument copies of reviewed category ASTs; originals are never edited or invoked wholesale.
foreach ($function in $categories) {
    $text = $function.Extent.Text
    $edits = [Collections.Generic.List[object]]::new()
    foreach ($loop in $function.FindAll({ param($node) $node -is [System.Management.Automation.Language.ForEachStatementAst] -and $node.Variable.Extent.Text -eq '$item' -and $node.Condition.Extent.Text -eq '$myArray' }, $true)) {
        $edits.Add(@{ start = $loop.Body.Extent.StartOffset + 1 - $function.Extent.StartOffset; length = 0;
            replacement = "`nRegister-LiteralRow `$item`n" })
    }
    foreach ($node in $function.FindAll({ param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and $n.Left.Extent.Text -eq '$arr' -and $n.Operator -eq 'PlusEquals' }, $true)) {
        $replacement = $node.Extent.Text + "`nRegister-Queued -Command `$arr[-1] -Row `$item -Line $($node.Extent.StartLineNumber) -Color `$color"
        $edits.Add(@{ start = $node.Extent.StartOffset - $function.Extent.StartOffset; length = $node.Extent.EndOffset - $node.Extent.StartOffset; replacement = $replacement })
    }
    foreach ($command in $function.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)) {
        $replacement = switch ($command.GetCommandName()) {
            '.\create_poster.ps1' { 'Capture-Direct' }
            'Move-Item' { 'Capture-Move' }
            'Copy-Item' { 'Capture-Copy' }
            'magick' { 'Capture-Overlay' }
            default { $null }
        }
        if ($replacement) {
            $name = $command.CommandElements[0].Extent
            $edits.Add(@{ start = $name.StartOffset - $function.Extent.StartOffset; length = $name.EndOffset - $name.StartOffset;
                replacement = "$replacement -CaptureLine $($command.Extent.StartLineNumber)" })
        }
    }
    foreach ($edit in ($edits | Sort-Object start -Descending)) { $text = $text.Remove($edit.start, $edit.length).Insert($edit.start, $edit.replacement) }
    . ([scriptblock]::Create($text))
}
$captureOrder = @()
foreach ($switch in $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.SwitchStatementAst] }, $true)) {
    foreach ($clause in $switch.Clauses) {
        if ($clause.Item1 -is [System.Management.Automation.Language.StringConstantExpressionAst] -and $clause.Item1.Value -eq 'All') {
            $captureOrder = @($clause.Item2.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] }, $true) | ForEach-Object { $_.GetCommandName() })
        }
    }
}
if ($captureOrder.Count -ne $categories.Count -or @($captureOrder | Sort-Object -Unique).Count -ne $categories.Count) { throw 'All-category dispatch changed' }
foreach ($name in $captureOrder) {
    if ($name -notin $categories.Name) { throw 'Unknown function in All dispatch' }
    $script:category = $name.Substring(6)
    $script:lastFit = $null
    $script:literalRowCopy = $null
    & $name
    if ($script:queued.Count) { throw 'Unflushed command queue' }
    [Console]::Error.WriteLine(("Captured {0}: {1} cumulative composer invocations" -f $script:category, $script:jobs.Count))
}
$targets = @{}
foreach ($key in $script:virtualFiles.Keys) {
    $index = $script:virtualFiles[$key]
    if (-not $targets.ContainsKey($index)) { $targets[$index] = [Collections.Generic.List[string]]::new() }
    $targets[$index].Add($key)
}
foreach ($entry in $script:jobs) { $entry.output_paths = @(if ($targets.ContainsKey($entry.index)) { $targets[$entry.index] | Sort-Object }) }
if ((Get-FileHash -LiteralPath $Source).Hash.ToLowerInvariant() -ne $sourceHash) { throw 'Bulk source changed during capture' }
$result = @{ schema = 1; source_sha256 = $sourceHash; language = 'en'; mode = 'AST-allowlisted capture, no bootstrap, render, file mutation, or publishing';
    jobs = @($script:jobs.ToArray()); overlay_operations = @($script:overlays.ToArray()); file_operations = @($script:operations.ToArray()); fit_count = $script:fitCache.Count }
$result | ConvertTo-Json -Depth 35 | Set-Content -LiteralPath $OutputFile -Encoding utf8NoBOM
