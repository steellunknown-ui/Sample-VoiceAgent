# setup.ps1 — One-click setup script for Voice Agent
# Run this in PowerShell: .\setup.ps1

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   🎙️  Voice Agent — Setup Script          ║" -ForegroundColor Cyan
Write-Host "║   EN + Hinglish + Marathi                ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create .env from example
if (-not (Test-Path ".env")) {
    Write-Host "📄 Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "   ✓ .env created. Please add your OpenRouter API key!" -ForegroundColor Green
    Write-Host "   → Get a free key at: https://openrouter.ai" -ForegroundColor Cyan
} else {
    Write-Host "   ✓ .env already exists" -ForegroundColor Green
}

# Step 2: Install dependencies
Write-Host ""
Write-Host "📦 Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
Write-Host "   ✓ Dependencies installed" -ForegroundColor Green

# Step 3: Done
Write-Host ""
Write-Host "══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit .env and add your OPENROUTER_API_KEY" -ForegroundColor White
Write-Host "  2. Run: python app.py" -ForegroundColor White
Write-Host "  3. Open: http://localhost:5000" -ForegroundColor White
Write-Host ""
