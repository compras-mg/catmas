# Corrige os nomes das variaveis nos extratores instalados.
# Nao exibe credenciais, inicia extracoes ou altera agendamentos.
param(
    [string]$Catalogo = "$env:USERPROFILE\Documents\CATMAS-Extracao-Python-v3\extrair_catmas.py",
    [string]$Historico = "$env:USERPROFILE\Documents\CATMAS-Historico-Python-v1\historico_catmas.py"
)
$ErrorActionPreference = 'Stop'
$arquivos = @($Catalogo, $Historico)

foreach ($nome in 'impala_user', 'impala_user_senha') {
    $usuario = [Environment]::GetEnvironmentVariable($nome, 'User')
    $sistema = [Environment]::GetEnvironmentVariable($nome, 'Machine')
    if ([string]::IsNullOrWhiteSpace($usuario) -and
        [string]::IsNullOrWhiteSpace($sistema)) {
        throw "Variavel persistente ausente: $nome. Nenhum arquivo alterado."
    }
}

$alteracoes = foreach ($arquivo in $arquivos) {
    if (-not (Test-Path -LiteralPath $arquivo -PathType Leaf)) {
        throw "Arquivo nao encontrado: $arquivo. Nenhum arquivo alterado."
    }
    $texto = [IO.File]::ReadAllText($arquivo)
    $novo = $texto.Replace('impala-password', 'impala_user_senha').
                   Replace('impala-user', 'impala_user')
    if (-not $novo.Contains('impala_user_senha') -or
        -not $novo.Contains('impala_user')) {
        throw "Formato inesperado em $arquivo. Nenhum arquivo alterado."
    }
    [pscustomobject]@{
        Arquivo = $arquivo
        Novo = $novo
    }
}

$sufixo = '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$utf8 = New-Object System.Text.UTF8Encoding($false)
foreach ($item in $alteracoes) {
    Copy-Item -LiteralPath $item.Arquivo -Destination ($item.Arquivo + $sufixo)
}
try {
    foreach ($item in $alteracoes) {
        [IO.File]::WriteAllText($item.Arquivo, $item.Novo, $utf8)
        if ([IO.File]::ReadAllText($item.Arquivo) -cne $item.Novo) {
            throw "Falha ao conferir arquivo gravado."
        }
    }
} catch {
    foreach ($item in $alteracoes) {
        Copy-Item -LiteralPath ($item.Arquivo + $sufixo) -Destination $item.Arquivo -Force
    }
    throw
}
"Correcao aplicada e conferida nos dois extratores. Backups: $sufixo"
