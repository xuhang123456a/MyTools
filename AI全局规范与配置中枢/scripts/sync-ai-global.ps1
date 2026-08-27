# sync-ai-global.ps1
# Automates distributing and symlinking ~/.ai rules, skills, and MCP configs to all AI tools

$ErrorActionPreference = 'Continue'
$aiHome = "C:\Users\Administrator\.ai"
$agentsMd = "$aiHome\AGENTS.md"
$mcpJson = "$aiHome\mcp\mcp-servers.json"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Starting sync of ~/.ai global rules & skills..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Helper: Create directory junction
function New-DirJunction($target, $linkPath) {
    if (Test-Path $linkPath) {
        $item = Get-Item $linkPath -Force
        if ($item.Attributes -match "ReparsePoint") {
            cmd /c rmdir "$linkPath" 2>$null
        } else {
            Remove-Item -LiteralPath $linkPath -Recurse -Force
        }
    }
    $parent = Split-Path -Parent $linkPath
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    
    cmd /c mklink /J "$linkPath" "$target" | Out-Null
    if (Test-Path $linkPath) {
        Write-Host "  [Junction OK] $linkPath -> $target" -ForegroundColor Green
    } else {
        Write-Host "  [Junction FAIL] $linkPath" -ForegroundColor Red
    }
}

# Helper: Create file hardlink or copy fallback
function Sync-RuleFile($sourceFile, $destFile) {
    $parent = Split-Path -Parent $destFile
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    if (Test-Path $destFile) {
        Remove-Item -LiteralPath $destFile -Force -ErrorAction SilentlyContinue
    }
    cmd /c mklink /H "$destFile" "$sourceFile" 2>$null | Out-Null
    if (-not (Test-Path $destFile)) {
        Copy-Item -LiteralPath $sourceFile -Destination $destFile -Force
        Write-Host "  [File Copy] $destFile" -ForegroundColor Yellow
    } else {
        Write-Host "  [Hardlink OK] $destFile" -ForegroundColor Green
    }
}

# 1. Antigravity / Gemini CLI
Write-Host "`n[1/5] Syncing Antigravity / Gemini CLI..." -ForegroundColor Yellow
Sync-RuleFile -sourceFile $agentsMd -destFile "C:\Users\Administrator\.gemini\config\GEMINI.md"
New-DirJunction -target "$aiHome\skills\unity-engineering" -linkPath "C:\Users\Administrator\.gemini\antigravity\skills\unity-engineering"
Copy-Item "$mcpJson" "C:\Users\Administrator\.gemini\config\mcp_config.json" -Force
Write-Host "  Antigravity done." -ForegroundColor Green

# 2. OpenAI Codex
Write-Host "`n[2/5] Syncing OpenAI Codex..." -ForegroundColor Yellow
if (Test-Path "C:\Users\Administrator\.codex\skills\unity-engineering") {
    $item = Get-Item "C:\Users\Administrator\.codex\skills\unity-engineering" -Force
    if (-not ($item.Attributes -match "ReparsePoint")) {
        Move-Item "C:\Users\Administrator\.codex\skills\unity-engineering" "C:\Users\Administrator\.codex\skills\unity-engineering.bak" -Force -ErrorAction SilentlyContinue
    }
}
New-DirJunction -target "$aiHome\skills\unity-engineering" -linkPath "C:\Users\Administrator\.codex\skills\unity-engineering"
Write-Host "  Codex done." -ForegroundColor Green

# 3. Claude Code & Desktop
Write-Host "`n[3/5] Syncing Claude Code & Claude Desktop..." -ForegroundColor Yellow
Sync-RuleFile -sourceFile $agentsMd -destFile "C:\Users\Administrator\CLAUDE.md"
Sync-RuleFile -sourceFile $agentsMd -destFile "C:\Users\Administrator\.claude\CLAUDE.md"
if (Test-Path "C:\Users\Administrator\AppData\Roaming\Claude") {
    Copy-Item "$mcpJson" "C:\Users\Administrator\AppData\Roaming\Claude\claude_desktop_config.json" -Force
}
Write-Host "  Claude done." -ForegroundColor Green

# 4. GitHub Copilot
Write-Host "`n[4/5] Syncing GitHub Copilot..." -ForegroundColor Yellow
Sync-RuleFile -sourceFile $agentsMd -destFile "C:\Users\Administrator\.copilot\copilot-instructions.md"
Copy-Item "$mcpJson" "C:\Users\Administrator\.copilot\mcp-config.json" -Force
Write-Host "  Copilot done." -ForegroundColor Green

# 5. Cline / Roo-Code / Cursor / Windsurf Global Rules
Write-Host "`n[5/5] Configuring Cline, Cursor, Windsurf global files..." -ForegroundColor Yellow
Sync-RuleFile -sourceFile $agentsMd -destFile "C:\Users\Administrator\.clinerules"
Sync-RuleFile -sourceFile $agentsMd -destFile "C:\Users\Administrator\.windsurfrules"
Sync-RuleFile -sourceFile $agentsMd -destFile "C:\Users\Administrator\.cursorrules"

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "SUCCESS: Global AI rules and skills synced!" -ForegroundColor Green
Write-Host "You now only need to maintain C:\Users\Administrator\.ai" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan