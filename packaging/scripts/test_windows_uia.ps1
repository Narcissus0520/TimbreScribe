[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Application,
    [string]$Output
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Find-UiaWindow {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,
        [int]$TimeoutSeconds = 30
    )

    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty,
        $ProcessId
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $window = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
            [System.Windows.Automation.TreeScope]::Children,
            $condition
        )
        if ($null -ne $window) {
            return $window
        }
        Start-Sleep -Milliseconds 250
    }
    throw "The packaged application did not expose a Windows UI Automation root window."
}

function Add-CurrentUiaNames {
    param(
        [Parameter(Mandatory = $true)]
        [System.Windows.Automation.AutomationElement]$Root,
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.HashSet[string]]$Names
    )

    $elements = $Root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition
    )
    for ($index = 0; $index -lt $elements.Count; $index++) {
        try {
            $name = [string]$elements.Item($index).Current.Name
            if (-not [string]::IsNullOrWhiteSpace($name)) {
                $null = $Names.Add($name)
            }
        }
        catch [System.Windows.Automation.ElementNotAvailableException] {
            continue
        }
    }
    return $elements.Count
}

function Select-UiaTabs {
    param(
        [Parameter(Mandatory = $true)]
        [System.Windows.Automation.AutomationElement]$Root,
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.HashSet[string]]$Names
    )

    $tabCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::TabItem
    )
    $tabs = $Root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        $tabCondition
    )
    for ($index = 0; $index -lt $tabs.Count; $index++) {
        $tab = $tabs.Item($index)
        $pattern = $null
        $selectionSupported = $tab.TryGetCurrentPattern(
            [System.Windows.Automation.SelectionItemPattern]::Pattern,
            [ref]$pattern
        )
        $selected = $false
        $errorText = ""
        try {
            if ($selectionSupported) {
                ([System.Windows.Automation.SelectionItemPattern]$pattern).Select()
                Start-Sleep -Milliseconds 150
                $null = Add-CurrentUiaNames -Root $Root -Names $Names
                $selected = $true
            }
        }
        catch {
            $errorText = $_.Exception.Message
        }
        [pscustomobject]@{
            name = [string]$tab.Current.Name
            keyboard_focusable = [bool]$tab.Current.IsKeyboardFocusable
            selection_supported = [bool]$selectionSupported
            selected = $selected
            error = $errorText
        }
    }
}

function Test-ExpectedTabs {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Tabs,
        [Parameter(Mandatory = $true)]
        [string[]]$ExpectedNames,
        [int]$ExpectedCount = 12
    )

    if ($Tabs.Count -ne $ExpectedCount) {
        return $false
    }
    $actualNames = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::Ordinal
    )
    foreach ($tab in $Tabs) {
        $name = [string]$tab.name
        if ([string]::IsNullOrWhiteSpace($name)) {
            return $false
        }
        $null = $actualNames.Add($name)
    }
    foreach ($name in $ExpectedNames) {
        if (-not $actualNames.Contains($name)) {
            return $false
        }
    }
    return $true
}

function Write-UiaEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Json,
        [string]$Destination
    )

    if ([string]::IsNullOrWhiteSpace($Destination)) {
        [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
        Write-Output $Json
        return
    }
    $resolved = [System.IO.Path]::GetFullPath($Destination)
    $parent = Split-Path -Parent $resolved
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $temporary = "$resolved.tmp.$([guid]::NewGuid().ToString('N'))"
    try {
        [System.IO.File]::WriteAllText(
            $temporary,
            $Json + [Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false)
        )
        if (Test-Path -LiteralPath $resolved -PathType Leaf) {
            [System.IO.File]::Replace($temporary, $resolved, $null)
        }
        else {
            [System.IO.File]::Move($temporary, $resolved)
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$applicationPath = [System.IO.Path]::GetFullPath($Application)
if (-not (Test-Path -LiteralPath $applicationPath -PathType Leaf)) {
    throw "Packaged application not found: $applicationPath"
}
$temporaryRoot = Join-Path (
    [System.IO.Path]::GetTempPath()
) ("TimbreScribe-uia-" + [guid]::NewGuid().ToString("N"))
$safeTemporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$resolvedTemporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot)
$originalLocalAppData = $env:LOCALAPPDATA
$process = $null

try {
    New-Item -ItemType Directory -Path $resolvedTemporaryRoot -Force | Out-Null
    $env:LOCALAPPDATA = Join-Path $resolvedTemporaryRoot "local-app-data"
    $process = Start-Process -FilePath $applicationPath -PassThru -WindowStyle Minimized
    try {
        $null = $process.WaitForInputIdle(30000)
    }
    catch [System.InvalidOperationException] {
        throw "The packaged GUI process exited before becoming ready for UI Automation."
    }

    $window = Find-UiaWindow -ProcessId $process.Id
    $allNames = [System.Collections.Generic.HashSet[string]]::new(
        [System.StringComparer]::Ordinal
    )
    $elementCount = Add-CurrentUiaNames -Root $window -Names $allNames
    $tabRecords = @(Select-UiaTabs -Root $window -Names $allNames)
    $expectedTabNames = @("Mock", "Basic", "MuScriptor", "MusicXML", "Score assistant")
    $expectedNames = @(
        "TimbreScribe workspaces",
        "Engraved score view",
        "Compact score preview",
        "Generated MusicXML source preview",
        "Source waveform",
        "Raw transcription piano roll",
        "Editable score workspace",
        "Score assistant workspace",
        "Job and diagnostic messages",
        "Current job progress"
    )
    $semanticResults = @(
        foreach ($name in $expectedNames) {
            [pscustomobject]@{name = $name; present = $allNames.Contains($name)}
        }
    )
    $tabsComplete = Test-ExpectedTabs -Tabs $tabRecords -ExpectedNames $expectedTabNames
    $tabsOperable = @(
        $tabRecords | Where-Object {
            -not $_.keyboard_focusable -or -not $_.selection_supported -or -not $_.selected
        }
    ).Count -eq 0
    $semanticsComplete = @($semanticResults | Where-Object { -not $_.present }).Count -eq 0
    $windowNamed = ([string]$window.Current.Name).StartsWith(
        "TimbreScribe",
        [System.StringComparison]::Ordinal
    )
    $allPassed = $windowNamed -and $tabsComplete -and $tabsOperable -and $semanticsComplete
    $os = Get-CimInstance Win32_OperatingSystem
    $evidence = [ordered]@{
        schema_version = 1
        application = "TimbreScribe"
        executable_name = Split-Path -Leaf $applicationPath
        executable_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $applicationPath).Hash.ToLowerInvariant()
        operating_system = [ordered]@{
            caption = [string]$os.Caption
            version = [string]$os.Version
            build = [string]$os.BuildNumber
            architecture = [string]$os.OSArchitecture
        }
        provider = "Windows UI Automation"
        window_name = [string]$window.Current.Name
        descendant_element_count = $elementCount
        unique_named_element_count = $allNames.Count
        tab_items = $tabRecords
        expected_semantic_names = $semanticResults
        checks = [ordered]@{
            window_named = $windowNamed
            tabs_complete = $tabsComplete
            tabs_keyboard_focusable_and_selectable = $tabsOperable
            semantic_names_present_after_tab_activation = $semanticsComplete
        }
        passed = $allPassed
    }
    $json = $evidence | ConvertTo-Json -Depth 8
    Write-UiaEvidence -Json $json -Destination $Output
    if (-not $allPassed) {
        throw "Packaged Windows UI Automation acceptance failed; inspect the JSON evidence."
    }
    Write-Output "Packaged Windows UI Automation acceptance passed."
}
finally {
    $env:LOCALAPPDATA = $originalLocalAppData
    if ($null -ne $process -and -not $process.HasExited) {
        $process.CloseMainWindow() | Out-Null
        if (-not $process.WaitForExit(5000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
    if (
        $resolvedTemporaryRoot.StartsWith(
            $safeTemporaryRoot,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -and (Test-Path -LiteralPath $resolvedTemporaryRoot)
    ) {
        Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
