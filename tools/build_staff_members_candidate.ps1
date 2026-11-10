param(
    [string]$GameRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)

$ErrorActionPreference = 'Stop'
$root = $GameRoot
$srcJson = Join-Path $root 'CHS_Project\outputs\credits_inspect\title_staff.psb.m.json'
$outDir = Join-Path $root 'CHS_Project\outputs\credits_inspect\staff_members_candidate'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$j = Get-Content -Raw -Encoding UTF8 $srcJson | ConvertFrom-Json
$items = [System.Collections.ArrayList]@($j.param.item)
$insertAt = [Math]::Min(40, $items.Count)

function Item([int]$font, [int]$space, [string[]]$text, [bool]$staff = $false, [bool]$hasStaff = $false) {
    $o = [ordered]@{}
    if ($PSBoundParameters.ContainsKey('font')) { $o.font = $font }
    if ($PSBoundParameters.ContainsKey('space')) { $o.space = $space }
    if ($hasStaff) { $o.staff = $staff }
    if ($null -ne $text) { $o.text = $text }
    return [pscustomobject]$o
}

$newItems = @(
    (Item 2 55 @('合金装备 大师合集 2 特典包汉化成员')),
    (Item 2 25 @('汉化成员')),
    (Item 0 80 @(
        '程序/汉化移植','Aphelion0728',
        '启动器翻译','Aphelion0728',
        '启动器中文文本图集制作','格序设计（闲鱼）',
        '测试','Aphelion0728'
    ) $false $true),
    (Item 2 55 @('《合金装备：幽灵通天塔》')),
    (Item 2 25 @('GBC版汉化成员')),
    (Item 0 80 @(
        '程序','Stephen',
        '翻译','完美无缺加油、Kiostar Land、Stephen'
    ) $false $true),
    (Item 2 55 @('特别感谢')),
    (Item 0 80 @('幽涧翠草、格序设计（闲鱼）、GBC版全体汉化成员。'))
)
for ($i = $newItems.Count - 1; $i -ge 0; $i--) { [void]$items.Insert($insertAt, $newItems[$i]) }
$j.param.item = $items
$outJson = Join-Path $outDir 'title_staff.psb.m.json'
$j | ConvertTo-Json -Depth 30 | Set-Content -Encoding UTF8 $outJson

# Preserve the existing atlas characters and append every character used by the added credits.
$charFile = Join-Path $outDir 'staff_font_chars.txt'
$oldChars = (Get-Content -Raw -Encoding UTF8 (Join-Path $root 'CHS_Project\outputs\credits_inspect\staff_import_candidate\staff_font_chars.txt')).TrimEnd("`r", "`n")
$addedText = (($items | ForEach-Object { $_.text }) -join '')
$allChars = [System.Collections.Generic.HashSet[string]]::new()
foreach ($c in ($oldChars.ToCharArray() + $addedText.ToCharArray())) { [void]$allChars.Add([string]$c) }
$ordered = [System.Text.StringBuilder]::new()
foreach ($c in $oldChars.ToCharArray()) { if ($allChars.Contains([string]$c)) { [void]$ordered.Append($c); [void]$allChars.Remove([string]$c) } }
foreach ($c in ($addedText.ToCharArray() | Sort-Object)) { if ($allChars.Contains([string]$c)) { [void]$ordered.Append($c); [void]$allChars.Remove([string]$c) } }
$ordered.ToString() | Set-Content -Encoding UTF8 -NoNewline $charFile
Write-Host "Wrote $outJson"
Write-Host "Wrote $charFile ($($ordered.Length) characters)"
