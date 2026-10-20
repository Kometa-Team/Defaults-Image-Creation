"""Optional development reference probe; the Python runtime never invokes PowerShell."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from create_defaults.bulk.translations import key_token, legacy_case, replace_placeholders


@pytest.mark.skipif(not shutil.which("pwsh"), reason="Optional legacy-reference tool is not installed")
def test_value_case_and_replacement_semantics_against_original_helpers(tmp_path):
    source = Path(__file__).resolve().parents[2] / "create_default_posters.ps1"
    cases = {"case": [{"text": text, "mode": mode} for text in ("Mixed Case", "Stra\u00dfe", "\u0130\u0131iI", "\u1f80\u01f0\ufb03") for mode in ("upper", "lower", "exact")],
             "replace": [{"text": text, "replacement": replacement} for text in ("A<<x>>B<<y>>C", "<<x\ny>>") for replacement in
                         ("literal", "$$", "$&", "$0", "$00", "$000", "$01", "$1", "${0}", "$_", "$`", "$'", "$+", "\\$0")]}
    data = tmp_path / "cases.json"
    cases["keys"] = [[first, second] for first, second in [("action", "ACTION"), ("Stra\u00dfe", "STRASSE"), ("\u00df", "\u1e9e"), ("I", "\u0131"), ("i", "\u0130"), ("\u00c9", "\u00e9"), ("\u03c2", "\u03c3"), ("s", "\u017f")]]
    data.write_text(json.dumps(cases), encoding="utf-8")
    script = tmp_path / "probe.ps1"
    script.write_text("""param([string]$Source, [string]$Cases)
$ErrorActionPreference = 'Stop'
[System.Globalization.CultureInfo]::CurrentCulture = [System.Globalization.CultureInfo]::GetCultureInfo('en-US')
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source, [ref]$null, [ref]$null)
$functions = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in @('Get-YamlPropertyValue', 'Set-TextBetweenDelimiters') }, $true)
function WriteToLogFile { param([string]$Text) }
foreach ($f in $functions) { . ([scriptblock]::Create($f.Extent.Text)) }
$data = Get-Content -LiteralPath $Cases -Raw -Encoding UTF8 | ConvertFrom-Json
$case = @($data.case | ForEach-Object { Get-YamlPropertyValue -PropertyPath 'key' -ConfigObject @{ key = $_.text } -CaseSensitivity $_.mode })
$replace = @($data.replace | ForEach-Object { Set-TextBetweenDelimiters -InputString $_.text -ReplacementString $_.replacement })
$keys = @($data.keys | ForEach-Object { $hash = @{}; $hash[$_[0]] = 'value'; $hash.ContainsKey($_[1]) })
@{ case = $case; replace = $replace; keys = $keys } | ConvertTo-Json -Depth 8 -Compress
""", encoding="utf-8")
    result = subprocess.run([shutil.which("pwsh"), "-NoLogo", "-NoProfile", "-File", str(script), str(source), str(data)], capture_output=True, text=True, encoding="utf-8-sig", timeout=30, check=True)
    actual = json.loads(result.stdout)
    mismatches = [(case, expected, legacy_case(case["text"], case["mode"])) for case, expected in zip(cases["case"], actual["case"]) if legacy_case(case["text"], case["mode"]) != expected]
    mismatches.extend((case, expected, replace_placeholders(case["text"], case["replacement"])) for case, expected in zip(cases["replace"], actual["replace"]) if replace_placeholders(case["text"], case["replacement"]) != expected)
    mismatches.extend((case, expected, key_token(case[0]) == key_token(case[1])) for case, expected in zip(cases["keys"], actual["keys"]) if (key_token(case[0]) == key_token(case[1])) != expected)
    assert not mismatches
