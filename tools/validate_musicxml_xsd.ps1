param(
    [string]$CacheDirectory = (Join-Path $env:TEMP "TimbreScribe-MusicXML40-XSD")
)

$ErrorActionPreference = "Stop"
$validationRoot = [System.IO.Path]::GetFullPath($CacheDirectory)
New-Item -ItemType Directory -Path $validationRoot -Force | Out-Null

$schemaFiles = @(
    @{
        Name = "musicxml.xsd"
        Url = "https://raw.githubusercontent.com/w3c/musicxml/v4.0/schema/musicxml.xsd"
        Sha256 = "bfe37ed25a9ec00e6f2591d53df260b84efe12aed209ba3ac0a76f9287665a99"
    },
    @{
        Name = "xml.xsd"
        Url = "https://raw.githubusercontent.com/w3c/musicxml/v4.0/schema/xml.xsd"
        Sha256 = "616a3077df5cfc954ac74a75abe9697b95eef7a85dbe09367d995a483e840eb5"
    },
    @{
        Name = "xlink.xsd"
        Url = "https://raw.githubusercontent.com/w3c/musicxml/v4.0/schema/xlink.xsd"
        Sha256 = "6e601f8eeb41618b50e4c7f944dff754e57ea43b602755470dda24c9c2f6df92"
    }
)

foreach ($schemaFile in $schemaFiles) {
    $schemaPath = Join-Path $validationRoot $schemaFile.Name
    $valid = (Test-Path -LiteralPath $schemaPath -PathType Leaf) -and
        ((Get-FileHash -Algorithm SHA256 -LiteralPath $schemaPath).Hash.ToLowerInvariant() -eq $schemaFile.Sha256)
    if (-not $valid) {
        Invoke-WebRequest -Uri $schemaFile.Url -OutFile $schemaPath -UseBasicParsing
    }
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $schemaPath).Hash.ToLowerInvariant()
    if ($actualHash -ne $schemaFile.Sha256) {
        throw "MusicXML schema hash mismatch for $($schemaFile.Name)"
    }
}

$fixtureRoot = Join-Path $validationRoot "generated"
New-Item -ItemType Directory -Path $fixtureRoot -Force | Out-Null
$env:TIMBRESCRIBE_XSD_FIXTURES = $fixtureRoot
@'
import os
from pathlib import Path

from tests.factories import make_raw_transcription
from timbrescribe.domain.notation import NotationSettings, build_notation
from timbrescribe.infrastructure.exporting import MusicXmlExporter

output = Path(os.environ["TIMBRESCRIBE_XSD_FIXTURES"])
raw = make_raw_transcription(
    note_specs=((60, 1.75, 2.75), (64, 0.0, 1.0), (67, 0.0, 0.5))
)
for profile_id in ("piano", "clarinet-bb", "alto-sax-eb", "horn-f"):
    score = build_notation(
        raw,
        NotationSettings(instrument_profile_id=profile_id),
    ).score
    MusicXmlExporter().export(score, output / f"{profile_id}.musicxml")
'@ | uv run python -
if ($LASTEXITCODE -ne 0) {
    throw "Could not generate MusicXML XSD fixtures"
}

$schemas = [System.Xml.Schema.XmlSchemaSet]::new()
$schemas.XmlResolver = [System.Xml.XmlUrlResolver]::new()
[void]$schemas.Add(
    "http://www.w3.org/XML/1998/namespace",
    (Join-Path $validationRoot "xml.xsd")
)
[void]$schemas.Add(
    "http://www.w3.org/1999/xlink",
    (Join-Path $validationRoot "xlink.xsd")
)
[void]$schemas.Add("", (Join-Path $validationRoot "musicxml.xsd"))
$schemas.Compile()

$script:validationFailures = @()
Get-ChildItem -LiteralPath $fixtureRoot -Filter *.musicxml | ForEach-Object {
    $settings = [System.Xml.XmlReaderSettings]::new()
    $settings.Schemas = $schemas
    $settings.ValidationType = [System.Xml.ValidationType]::Schema
    $fixture = $_.FullName
    $settings.add_ValidationEventHandler({
        param($sender, $event)
        $script:validationFailures += "${fixture}: $($event.Message)"
    })
    $reader = [System.Xml.XmlReader]::Create($fixture, $settings)
    try {
        while ($reader.Read()) {}
    }
    finally {
        $reader.Dispose()
    }
}
if ($script:validationFailures.Count) {
    throw ($script:validationFailures -join "`n")
}

Write-Output "W3C MusicXML 4.0 XSD validation passed for piano, B-flat, E-flat, and F fixtures"
