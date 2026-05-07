$ErrorActionPreference = 'Stop'

function Write-Allow([string]$message = $null) {
    $result = @{
        hookSpecificOutput = @{
            hookEventName = 'PreToolUse'
            permissionDecision = 'allow'
        }
    }

    if ($message) {
        $result.systemMessage = $message
    }

    $result | ConvertTo-Json -Depth 8 -Compress
    exit 0
}

function Write-Deny([string]$reason, [string]$context = $null) {
    $result = @{
        hookSpecificOutput = @{
            hookEventName = 'PreToolUse'
            permissionDecision = 'deny'
            permissionDecisionReason = $reason
        }
    }

    if ($context) {
        $result.hookSpecificOutput.additionalContext = $context
    }

    $result | ConvertTo-Json -Depth 8 -Compress
    exit 0
}

function Get-ImagePaths([string]$commandText) {
    $pattern = '(?i)(?:"(?<quoted>[^"]+\.(png|jpe?g|webp|gif|bmp|tiff?|svg))"|''(?<single>[^'']+\.(png|jpe?g|webp|gif|bmp|tiff?|svg))''|(?<bare>[^\s]+\.(png|jpe?g|webp|gif|bmp|tiff?|svg)))'
    $matches = [regex]::Matches($commandText, $pattern)
    $paths = New-Object System.Collections.Generic.List[string]

    foreach ($match in $matches) {
        foreach ($groupName in @('quoted', 'single', 'bare')) {
            $value = $match.Groups[$groupName].Value
            if ($value) {
                $paths.Add($value)
                break
            }
        }
    }

    return $paths
}

function Normalize-PathToken([string]$pathToken) {
    return ($pathToken -replace '/', '\').Trim().Trim('"', '''').ToLowerInvariant()
}

$rawInput = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($rawInput)) {
    Write-Allow
}

try {
    $payload = $rawInput | ConvertFrom-Json
} catch {
    Write-Allow "Image safety hook skipped because the hook payload could not be parsed."
}

if ($null -eq $payload.tool_name) {
    Write-Allow
}

$toolName = [string]$payload.tool_name
$commandText = $null
if ($payload.tool_input -and $payload.tool_input.PSObject.Properties.Name -contains 'command') {
    $commandText = [string]$payload.tool_input.command
}

if ([string]::IsNullOrWhiteSpace($commandText)) {
    Write-Allow
}

if ($toolName -notin @('run_in_terminal', 'send_to_terminal')) {
    Write-Allow
}

$normalizedCommand = $commandText.ToLowerInvariant()
if ($normalizedCommand -match '\bmogrify\b' -or $normalizedCommand -match 'overwrite[_-]?original') {
    Write-Deny 'In-place image modification is blocked.' 'Write outputs to a derived file such as product-cutout.png or banner-hero.webp.'
}

$imagePaths = Get-ImagePaths $commandText
if ($imagePaths.Count -eq 0) {
    Write-Allow
}

$imageProcessorHints = @('magick', 'imagemagick', 'ffmpeg', 'sharp', 'cwebp', 'vips', 'rembg', 'backgroundremover', 'opencv', 'pillow', 'pil', 'python')
$looksLikeImageEdit = $false
foreach ($hint in $imageProcessorHints) {
    if ($normalizedCommand.Contains($hint)) {
        $looksLikeImageEdit = $true
        break
    }
}

if (-not $looksLikeImageEdit -and $imagePaths.Count -lt 2) {
    Write-Allow
}

if ($imagePaths.Count -eq 1) {
    Write-Deny 'Image commands must write to an explicit derived output path.' 'Add a separate output filename such as shot-retouched.png or card-thumb.webp.'
}

$inputPath = Normalize-PathToken $imagePaths[0]
$outputPath = Normalize-PathToken $imagePaths[$imagePaths.Count - 1]

if ($inputPath -eq $outputPath) {
    Write-Deny 'Overwriting the source image is blocked.' 'Use a new output filename with a task suffix such as -edit, -hero, or -cutout.'
}

if ($outputPath -match '(^|\\)(raw|source|sources|original|originals|input|inputs)(\\|$)') {
    Write-Deny 'Derived image outputs cannot be written into source asset folders.' 'Write outputs to a derived or output directory instead.'
}

$outputFileName = [System.IO.Path]::GetFileNameWithoutExtension($outputPath)
if ($outputFileName -notmatch '^[a-z0-9]+(?:-[a-z0-9]+)*-(thumb|hero|cutout|bg|edit|retouched|masked|export|variant[0-9]*|v[0-9]+)$') {
    Write-Deny 'Derived image filenames must be lowercase kebab-case and include an approved task suffix.' 'Examples: product-cutout.png, homepage-hero.webp, speaker-retouched.jpg.'
}

Write-Allow
