$vsInstaller = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vs_installer.exe"
Write-Host "Running VS installer modify..."
& $vsInstaller modify `
    --installPath "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools" `
    --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
    --add Microsoft.VisualStudio.Component.VC.CMake.Project `
    --add Microsoft.VisualStudio.Component.Windows10SDK `
    --add Microsoft.VisualStudio.ComponentGroup.NativeDesktop.Core `
    --passive `
    --wait
exit $LASTEXITCODE
