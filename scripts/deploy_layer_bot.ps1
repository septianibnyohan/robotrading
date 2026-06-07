$TaskName = "RoboBTC_Layer_Bot"
$PythonW = "c:\data\project\robobtc\venv\Scripts\pythonw.exe"
$Script = "btc_layer_bot.py"
$Arguments = "btc_layer_bot.py --symbol all"
$WorkDir = "c:\data\project\robobtc"

# Stop existing task if running
Write-Host "Stopping existing task $TaskName (if running)..."
try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task -and $task.State -ne "Ready") {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
} catch {
    Write-Host "Failed to check/stop task: $($_.Exception.Message)"
}

# Clean up any leftover processes running btc_layer_bot.py to be safe
Write-Host "Cleaning up any leftover processes..."
try {
    Get-CimInstance Win32_Process -Filter "name = 'pythonw.exe' or name = 'python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*btc_layer_bot.py*" } | ForEach-Object {
        Write-Host "Stopping process: $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
} catch {
    Write-Host "Failed to cleanup processes: $($_.Exception.Message)"
}

# Define actions, triggers and settings
$Action = New-ScheduledTaskAction -Execute $PythonW -Argument $Arguments -WorkingDirectory $WorkDir
$TriggerStartup = New-ScheduledTaskTrigger -AtStartup
$TriggerHourly = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)
$TriggerHourly.Repetition.Duration = "P3650D"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit 0 -MultipleInstances IgnoreNew

# Register the task
Write-Host "Registering task $TaskName..."
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($TriggerStartup, $TriggerHourly) -Settings $Settings -User "SYSTEM" -RunLevel Highest -Force
    Write-Host "Task successfully registered!" -ForegroundColor Green
    
    # Start the task
    Write-Host "Starting task $TaskName..."
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Task started successfully!" -ForegroundColor Green
} catch {
    Write-Host "Failed to register or start task: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
