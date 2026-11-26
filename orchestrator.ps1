# Orchestrator: Micro-batch dbt runs
Write-Host "Starting dbt Micro-batch Orchestrator..." -ForegroundColor Cyan

while ($true) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Triggering dbt run for Silver & Gold..." -ForegroundColor Yellow
    
    # Navigate into the dbt project folder
    cd manufacturing_dbt
    
    # Run dbt (silver and gold only to save time)
    dbt run --select silver gold
    
    # Check if the command failed (exit code != 0)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "dbt run failed! Check the logs above." -ForegroundColor Red
    } else {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] dbt run completed successfully." -ForegroundColor Green
    }
    
    # Navigate back to the root folder
    cd ..
    
    # Wait for 60 seconds before the next run
    Write-Host "Sleeping for 60 seconds..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 60
}