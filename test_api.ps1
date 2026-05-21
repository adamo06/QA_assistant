param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$ApiKey = "dev-business-key",
    [string]$OAuthClientId = "qa-assistant",
    [string]$OAuthClientSecret = "dev-oauth-secret"
)

$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
chcp 65001 | Out-Null
try {
    [System.Console]::TreatControlCAsInput = $false
} catch {
}

function Write-Step {
    param(
        [int]$Number,
        [string]$Title
    )

    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor DarkGray
    Write-Host ("Étape {0} : {1}" -f $Number, $Title) -ForegroundColor Cyan
    Write-Host ("=" * 72) -ForegroundColor DarkGray
}

function Write-JsonBlock {
    param(
        [object]$Value
    )

    $Value | ConvertTo-Json -Depth 8 | Write-Host
}

function Invoke-ApiGet {
    param(
        [string]$Path,
        [hashtable]$Headers = @{}
    )

    $uri = ($BaseUrl.TrimEnd('/') + $Path)
    return Invoke-RestMethod -Uri $uri -Method Get -Headers $Headers
}

function Invoke-Section {
    param(
        [scriptblock]$Action,
        [string]$FailureHint
    )

    try {
        return & $Action
    }
    catch {
        Write-Host "Erreur : $($_.Exception.Message)" -ForegroundColor Red
        if ($FailureHint) {
            Write-Host $FailureHint -ForegroundColor Yellow
        }
        throw
    }
}

Write-Host "Test de l'API métier" -ForegroundColor Green
Write-Host ("Base URL : {0}" -f $BaseUrl)

Write-Step -Number 1 -Title "Vérifier que l'API répond"
Write-Host 'Réponse attendue : {"status":"ok"}'
$health = Invoke-Section -FailureHint 'Conseil : lance d''abord `uv run uvicorn api.server:app --reload` dans un autre terminal.' -Action {
    Invoke-ApiGet -Path "/health"
}
Write-Host "Réponse reçue :"
Write-JsonBlock -Value $health

Write-Step -Number 2 -Title "Tester l'authentification par clé API"
$apiHeaders = @{ "X-API-Key" = $ApiKey }
$summaryByKey = Invoke-Section -FailureHint "Vérifie BUSINESS_API_KEY si l'API refuse la requête." -Action {
    Invoke-ApiGet -Path "/v1/business/summary" -Headers $apiHeaders
}
Write-Host "Réponse reçue :"
Write-JsonBlock -Value $summaryByKey

Write-Step -Number 3 -Title "Tester la recherche métier avec la clé API"
$searchByKey = Invoke-Section -FailureHint "Vérifie l'index Chroma et la clé API si la recherche échoue." -Action {
    Invoke-ApiGet -Path "/v1/business/search?q=Small%20Basic&k=3" -Headers $apiHeaders
}
Write-Host "Réponse reçue :"
Write-JsonBlock -Value $searchByKey

Write-Step -Number 4 -Title "Obtenir un jeton OAuth"
$tokenResponse = Invoke-Section -FailureHint "Vérifie BUSINESS_OAUTH_CLIENT_ID et BUSINESS_OAUTH_CLIENT_SECRET si le jeton OAuth échoue." -Action {
    Invoke-RestMethod `
    -Uri ($BaseUrl.TrimEnd('/') + "/oauth/token") `
    -Method Post `
    -ContentType "application/json" `
    -Body (@{
        grant_type = "client_credentials"
        client_id = $OAuthClientId
        client_secret = $OAuthClientSecret
    } | ConvertTo-Json)
}

Write-Host "Réponse reçue :"
Write-JsonBlock -Value $tokenResponse

Write-Step -Number 5 -Title "Tester l'authentification OAuth"
$oauthHeaders = @{ "Authorization" = "Bearer $($tokenResponse.access_token)" }
$summaryByOAuth = Invoke-Section -FailureHint "Le token OAuth a peut-être expiré ou le service est indisponible." -Action {
    Invoke-ApiGet -Path "/v1/business/summary" -Headers $oauthHeaders
}
Write-Host "Réponse reçue :"
Write-JsonBlock -Value $summaryByOAuth

Write-Step -Number 6 -Title "Tester la recherche métier avec OAuth"
$searchByOAuth = Invoke-Section -FailureHint "Vérifie le token OAuth et l'index Chroma si la recherche échoue." -Action {
    Invoke-ApiGet -Path "/v1/business/search?q=programmation&k=3" -Headers $oauthHeaders
}
Write-Host "Réponse reçue :"
Write-JsonBlock -Value $searchByOAuth

Write-Step -Number 7 -Title "Vérifier le chemin agent"
$agentResult = Invoke-Section -FailureHint 'Vérifie OPENAI_API_KEY si l''appel agent échoue.' -Action {
    uv run python -c "from agents.rag import build_rag_agent; agent = build_rag_agent(); result = agent.invoke({'messages':[{'role':'user','content':'Donne-moi un résumé du corpus indexé et le nombre de chunks disponibles.'}]}); last = result['messages'][-1]; print(getattr(last, 'content', getattr(last, 'content_blocks', last)))"
}
Write-Host "Résultat de l'agent :"
Write-Host ([string]$agentResult)

Write-Host ""
Write-Host "Tous les tests ont été exécutés." -ForegroundColor Green
