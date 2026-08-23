# Check current VS installation state
$vsInstaller = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vs_installer.exe"
& $vsInstaller list --installPath "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools" --format json
