$Action = New-ScheduledTaskAction -Execute "c:\data\project\robobtc\venv\Scripts\pythonw.exe" -Argument "main.py" -WorkingDirectory "c:\data\project\robobtc"

$TriggerStartup = New-ScheduledTaskTrigger -AtStartup
$TriggerHourly = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)
$TriggerHourly.Repetition.Duration = "P3650D"

$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit 0 -MultipleInstances IgnoreNew

try {
    Register-ScheduledTask -TaskName "RoboBTC_Harvester" -Action $Action -Trigger @($TriggerStartup, $TriggerHourly) -Settings $Settings -User "SYSTEM" -RunLevel Highest -Force
    Write-Host "Task successfully registered!" -ForegroundColor Green
} catch {
    Write-Host "Failed to register task: $($_.Exception.Message)" -ForegroundColor Red
}
