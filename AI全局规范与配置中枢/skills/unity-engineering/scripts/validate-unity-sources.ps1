[CmdletBinding()]
param(
    [string]$ProjectRoot = (Get-Location).Path,
    [string]$AssemblyProject = 'Assembly-CSharp.csproj',
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    [string]$Exclude = '',
    [string]$AdditionalSource = '',
    [string]$OutputPath = 'Temp\CodexValidation\UnitySourceValidation.dll'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$projectPath = Join-Path $ProjectRoot $AssemblyProject
if (-not (Test-Path -LiteralPath $projectPath)) {
    throw "Unity-generated project was not found: $projectPath"
}

[xml]$project = Get-Content -Raw -Encoding UTF8 -LiteralPath $projectPath
$hintPaths = @($project.Project.ItemGroup.Reference |
    ForEach-Object { $_.HintPath } |
    Where-Object { $_ })
$unityEngineHint = $hintPaths |
    Where-Object { $_.Replace('/', '\') -like '*\Managed\UnityEngine\UnityEngine.dll' } |
    Select-Object -First 1
if (-not $unityEngineHint) {
    throw "Could not discover the Unity installation from $AssemblyProject."
}

if (-not [IO.Path]::IsPathRooted($unityEngineHint)) {
    $unityEngineHint = Join-Path $ProjectRoot $unityEngineHint
}
$unityEngineDirectory = Split-Path -Parent $unityEngineHint
$unityDataDirectory = Split-Path -Parent (Split-Path -Parent $unityEngineDirectory)
$unityDotnet = Join-Path $unityDataDirectory 'NetCoreRuntime\dotnet.exe'
$unityCompiler = Join-Path $unityDataDirectory 'DotNetSdkRoslyn\csc.dll'
foreach ($requiredPath in @($unityDotnet, $unityCompiler)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Unity compiler input was not found: $requiredPath"
    }
}

$references = foreach ($hintPath in $hintPaths) {
    $candidate = if ([IO.Path]::IsPathRooted($hintPath)) { $hintPath } else { Join-Path $ProjectRoot $hintPath }
    if (Test-Path -LiteralPath $candidate) { (Resolve-Path -LiteralPath $candidate).Path }
}

$projectReferences = @($project.Project.ItemGroup.ProjectReference | Where-Object { $_.Include })
foreach ($projectReference in $projectReferences) {
    $referencedProjectPath = Join-Path $ProjectRoot $projectReference.Include
    if (-not (Test-Path -LiteralPath $referencedProjectPath)) { continue }
    [xml]$referencedProject = Get-Content -Raw -Encoding UTF8 -LiteralPath $referencedProjectPath
    $assemblyName = $referencedProject.Project.PropertyGroup.AssemblyName |
        Where-Object { $_ } |
        Select-Object -First 1
    if (-not $assemblyName) { $assemblyName = [IO.Path]::GetFileNameWithoutExtension($referencedProjectPath) }
    $assemblyPath = Join-Path $ProjectRoot "Library\ScriptAssemblies\$assemblyName.dll"
    if (Test-Path -LiteralPath $assemblyPath) { $references += (Resolve-Path -LiteralPath $assemblyPath).Path }
}
$references = @($references | Sort-Object -Unique)

$sourceRoots = @($SourceRoot -split ';' | Where-Object { $_ })
$excludePatterns = @($Exclude -split ';' | Where-Object { $_ })
$sources = foreach ($sourceRootItem in $sourceRoots) {
    $sourcePath = if ([IO.Path]::IsPathRooted($sourceRootItem)) { $sourceRootItem } else { Join-Path $ProjectRoot $sourceRootItem }
    if (-not (Test-Path -LiteralPath $sourcePath)) { throw "Source root was not found: $sourcePath" }
    Get-ChildItem -LiteralPath $sourcePath -Recurse -Filter '*.cs' | Where-Object {
        $fileName = $_.Name
        $relativePath = $_.FullName.Substring($ProjectRoot.Length).TrimStart([char[]]@('\', '/')).Replace('\', '/')
        -not ($excludePatterns | Where-Object { $fileName -like $_ -or $relativePath -like $_ })
    } | ForEach-Object { $_.FullName }
}

foreach ($additionalSourceItem in @($AdditionalSource -split ';' | Where-Object { $_ })) {
    $additionalPath = if ([IO.Path]::IsPathRooted($additionalSourceItem)) { $additionalSourceItem } else { Join-Path $ProjectRoot $additionalSourceItem }
    if (-not (Test-Path -LiteralPath $additionalPath)) { throw "Additional source was not found: $additionalPath" }
    $sources += (Resolve-Path -LiteralPath $additionalPath).Path
}
$sources = @($sources | Sort-Object -Unique)
if ($sources.Count -eq 0) { throw 'No C# sources were selected.' }

$defines = $project.Project.PropertyGroup.DefineConstants | Where-Object { $_ } | Select-Object -First 1
$languageVersion = $project.Project.PropertyGroup.LangVersion | Where-Object { $_ } | Select-Object -First 1
if (-not $languageVersion) { $languageVersion = '9.0' }

$absoluteOutputPath = if ([IO.Path]::IsPathRooted($OutputPath)) { $OutputPath } else { Join-Path $ProjectRoot $OutputPath }
$outputDirectory = Split-Path -Parent $absoluteOutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$responsePath = Join-Path $outputDirectory 'UnitySourceValidation.rsp'

$responseLines = @(
    '/nologo',
    '/nostdlib+',
    '/target:library',
    "/langversion:$languageVersion",
    "/out:`"$absoluteOutputPath`""
)
if ($defines) { $responseLines += "/define:$defines" }
if (($project.Project.PropertyGroup.AllowUnsafeBlocks | Where-Object { $_ -eq 'true' } | Select-Object -First 1)) {
    $responseLines += '/unsafe+'
}
foreach ($reference in $references) { $responseLines += "/reference:`"$reference`"" }
foreach ($source in $sources) { $responseLines += "`"$source`"" }
[IO.File]::WriteAllLines($responsePath, $responseLines, (New-Object Text.UTF8Encoding($false)))

try {
    & $unityDotnet $unityCompiler '/noconfig' ('@' + $responsePath)
    if ($LASTEXITCODE -ne 0) { throw "Unity source validation failed with exit code $LASTEXITCODE." }
}
finally {
    if (Test-Path -LiteralPath $responsePath) { Remove-Item -LiteralPath $responsePath -Force }
}

Write-Host "Unity source validation succeeded: $($sources.Count) files -> $absoluteOutputPath" -ForegroundColor Green
