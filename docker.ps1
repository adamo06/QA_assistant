param(
    [ValidateSet("build", "up", "ingest", "down", "logs")]
    [string]$Action = "up"
)

$ErrorActionPreference = "Stop"

function Invoke-DockerCompose {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose a échoué avec le code $LASTEXITCODE"
    }
}

switch ($Action) {
    "build" {
        Invoke-DockerCompose -Arguments @("build")
    }
    "up" {
        Invoke-DockerCompose -Arguments @("up", "--build")
    }
    "ingest" {
        Invoke-DockerCompose -Arguments @("run", "--rm", "ingest")
    }
    "down" {
        Invoke-DockerCompose -Arguments @("down")
    }
    "logs" {
        Invoke-DockerCompose -Arguments @("logs", "-f", "qa-assistant")
    }
}
