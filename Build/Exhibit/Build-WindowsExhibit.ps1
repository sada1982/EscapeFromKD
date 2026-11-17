param(
    [Parameter(Mandatory=$true)] [string]$ProjectRoot,
    [Parameter(Mandatory=$true)] [string]$BuildCopy,
    [Parameter(Mandatory=$true)] [string]$ArchiveDir,
    [string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8'
)
$ErrorActionPreference='Stop'
$ProjectRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path
if (!(Test-Path -LiteralPath (Join-Path $ProjectRoot 'myProject.uproject'))) { throw 'Expected myProject.uproject.' }
if (Test-Path -LiteralPath $BuildCopy) { throw 'Choose an unused directory for the isolated build copy.' }
New-Item -ItemType Directory -Path $BuildCopy | Out-Null
$BuildCopy=(Resolve-Path -LiteralPath $BuildCopy).Path
foreach ($group in 'Config','Content') {
    robocopy (Join-Path $ProjectRoot $group) (Join-Path $BuildCopy $group) /E /XJ /COPY:DT /DCOPY:T /R:1 /W:1 /NP /NDL /NFL /NJH /NJS
    if ($LASTEXITCODE -gt 7) { throw "robocopy failed ($LASTEXITCODE)." }
}
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'myProject.uproject') -Destination $BuildCopy
New-Item -ItemType Directory -Path (Join-Path $BuildCopy 'Config/Windows') -Force | Out-Null
foreach ($file in 'Config/Windows/WindowsEngine.ini','Config/DefaultGameUserSettings.ini') {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $BuildCopy $file) -Force
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Source') -Destination $BuildCopy -Recurse -Force
$projectFile=Join-Path $BuildCopy 'myProject.uproject'
$descriptor=Get-Content -Raw -LiteralPath $projectFile | ConvertFrom-Json
$descriptor | Add-Member -NotePropertyName Modules -NotePropertyValue @([ordered]@{Name='myProject';Type='Runtime';LoadingPhase='Default';TargetAllowList=@('Game')}) -Force
[System.IO.File]::WriteAllText($projectFile,($descriptor|ConvertTo-Json -Depth 10),[System.Text.UTF8Encoding]::new($false))
$cmdlet=Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
$uat=Join-Path $EngineRoot 'Engine/Build/BatchFiles/RunUAT.bat'
$projectFile=Join-Path $BuildCopy 'myProject.uproject'
& $uat BuildCookRun "-project=$projectFile" -nop4 -utf8output -platform=Win64 -clientconfig=Shipping -build -cook -map=/Game/Main/Stage/KDStage -stage -pak -iostore -package -archive "-archivedirectory=$ArchiveDir" -nodebuginfo -nocompileeditor "-unrealexe=$cmdlet" -installed -unattended -UbtArgs=-WaitMutex
exit $LASTEXITCODE

