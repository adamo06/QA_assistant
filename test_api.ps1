param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
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

Write-Step -Number 2 -Title "Tester le résumé du corpus"
$summaryByKey = Invoke-Section -FailureHint "Vérifie que l'index Chroma existe et que l'API est lancée." -Action {
    Invoke-ApiGet -Path "/v1/business/summary"
}
Write-Host "Réponse reçue :"
Write-JsonBlock -Value $summaryByKey

Write-Step -Number 3 -Title "Tester la recherche métier"
$searchByKey = Invoke-Section -FailureHint "Vérifie l'index Chroma si la recherche échoue." -Action {
    Invoke-ApiGet -Path "/v1/business/search?q=Small%20Basic&k=3"
}
Write-Host "Réponse reçue :"
Write-JsonBlock -Value $searchByKey

Write-Step -Number 4 -Title "Vérifier le chemin agent"
$agentResult = Invoke-Section -FailureHint 'Vérifie OPENAI_API_KEY si l''appel agent échoue.' -Action {
    uv run python -c "from agents.rag import build_rag_agent; agent = build_rag_agent(); result = agent.invoke({'messages':[{'role':'user','content':'Donne-moi un résumé du corpus indexé et le nombre de chunks disponibles.'}]}); last = result['messages'][-1]; print(getattr(last, 'content', getattr(last, 'content_blocks', last)))"
}
Write-Host "Résultat de l'agent :"
Write-Host ([string]$agentResult)

Write-Host ""
Write-Host "Tous les tests ont été exécutés." -ForegroundColor Green
