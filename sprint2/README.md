# Sprint 2 – Preparação de Ambiente

## Estrutura de Pastas
```
sprint2/
  README.md
  tools/
    ck/                           # CK construído (JARs) 
  scripts/
    fetch_repos_graphql.py        # Coleta top-N Java via GraphQL
    analyze_rqs.py                # consolida dados e calcula correlações (plots opcionais)
    process_streaming.py          # processamento streaming: clona, mede, salva sumários e apaga o repo
    process_local.py              # processa um repositório já baixado (sem clonar)
    merge_summaries.py            # une shards/repairs e deduplica por repo (canônicos)
    check_missing.py              # identifica faltantes e gera CSV para reprocesso
    review_outputs.py             # resumo rápido de saídas e verificação de plots
    setup_ck.ps1                  # Script para obter/compilar CK
    setup_cloc.ps1                # Script para instalar cloc
  data/
    repos_list.csv                # Lista dos repositórios coletados (GraphQL)
    _stream_tmp/                  # Pasta temporária para o modo streaming (ignorada pelo git)
    processed/                    # Dados consolidados para análise (apenas artefatos canônicos)
      cloc_summary.csv
      ck_summary.csv
      analysis_summary.csv
      correlations.csv
      plots/
```

## Requisitos de Software
- **Java 11+** (para rodar CK)
- **Maven** (para build do CK)
- **Python 3.10+**
  - pandas, requests, tqdm, seaborn, scipy, numpy
- **Git**
- **cloc** (contagem de linhas de código/comentários)

## Instalação rápida (Windows/PowerShell)

### Java & Maven
Se tiver Chocolatey:
```powershell
choco install temurin11 -y
choco install maven -y
```

### Python (crie um ambiente virtual)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pandas requests tqdm seaborn scipy numpy
```

### cloc
Baixe o executável em https://github.com/AlDanial/cloc/releases ou instale via Chocolatey:
```powershell
choco install cloc -y
```
Ou use o instalador automatizado:
```powershell
powershell -ExecutionPolicy Bypass -File sprint2\scripts\setup_cloc.ps1
```

### Git
Instale via https://git-scm.com/download/win ou Chocolatey:
```powershell
choco install git -y
```

## Próximos passos
- Obter CK (clonar e buildar JAR ou baixar pronto)
- Coletar lista dos 1.000 repositórios Java
- Automatizar clone e coleta de métricas
- Sumarizar e analisar dados

## Obter o CK (automático via script)
Use o script abaixo para clonar e compilar o CK. Ele salvará o JAR em `sprint2/tools/ck/`.

```powershell
# a partir da raiz do repositório
cd sprint2\scripts
PowerShell -ExecutionPolicy Bypass -File .\setup_ck.ps1
# Se já existir e quiser forçar atualização:
PowerShell -ExecutionPolicy Bypass -File .\setup_ck.ps1 -Force
```

Após a execução, o JAR ficará em algo como:
`sprint2/tools/ck/ck-<versao>-jar-with-dependencies.jar`

## Coletar os 1.000 repositórios Java (GraphQL)
Defina o token do GitHub e execute o script:

```powershell
# defina seu token
$env:GITHUB_TOKEN = "<seu_token>"

# opcional: ative a venv
if (Test-Path .\.venv\Scripts\Activate.ps1) { . .\.venv\Scripts\Activate.ps1 }

# execute a coleta (gera sprint2/data/repos_list.csv)
python sprint2\scripts\fetch_repos_graphql.py --max 1000 --out sprint2\data\repos_list.csv --verbose
```

O arquivo `sprint2/data/repos_list.csv` conterá: repo, url, stars, created_at, releases, age_years.

## Artefatos de dados esperados
- `sprint2/data/repos_list.csv` — lista dos 1.000 repositórios com: repo, url, stars, created_at, releases, age_years
- `sprint2/data/processed/cloc_summary.csv` — LOC e comentários por repositório (totais)
- `sprint2/data/processed/ck_summary.csv` — resumo por repo de CBO/DIT/LCOM
- `sprint2/data/processed/analysis_summary.csv` — tabela mesclada para análise
- `sprint2/data/processed/correlations.csv` — correlações (Spearman e Pearson)
- `sprint2/data/processed/plots/*.png` — visualizações (bônus)

Limpeza e versionamento:
- Apenas os artefatos canônicos ficam versionados em `processed/` (as quatro CSVs + `plots/`).
- Artefatos temporários/diagnósticos (ex.: `cloc_summary_*repair*.csv`, `cloc_summary_debug*.csv`, suspeitos) são ignorados via `.gitignore`.
- A pasta temporária `data/_stream_tmp/` é ignorada e removida após cada execução streaming.

## Modo Streaming (não armazena repositórios)
Fluxo recomendado: para cada repo, o script clona shallow, mede CLOC e CK, grava os sumários e apaga a pasta.

```powershell
# Processa em modo streaming os primeiros 100 repositórios da lista
python sprint2\scripts\process_streaming.py `
  --csv sprint2\data\repos_list.csv `
  --work_dir sprint2\data\_stream_tmp `
  --out_dir sprint2\data\processed `
  --max 100 `
  --ck_jar sprint2\tools\ck\ck-0.7.1-SNAPSHOT-jar-with-dependencies.jar

# Opcional: rodar apenas um subconjunto por regex (ex.: apenas repos do owner 'apache')
python sprint2\scripts\process_streaming.py --filter_regex "^apache/" --max 50

# Dica (Windows): se git, cloc ou java não estiverem no PATH, informe explicitamente
python sprint2\scripts\process_streaming.py `
  --csv sprint2\data\repos_list.csv `
  --max 5 `
  --work_dir sprint2\data\_stream_tmp `
  --out_dir sprint2\data\processed `
  --git_exe "C:\\Program Files\\Git\\bin\\git.exe" `
  --cloc_exe "C:\\ProgramData\\chocolatey\\bin\\cloc.exe" `
  --java_exe "C:\\Program Files\\Eclipse Adoptium\\jdk-17.0.16.8-hotspot\\bin\\java.exe"
```

Saídas (mesmas dos modos anteriores, porém sem salvar JSONs/CSVs brutos por repo):
- `sprint2/data/processed/cloc_summary.csv`
- `sprint2/data/processed/ck_summary.csv`

Notas técnicas (robustez do CLOC/CK):
- O `process_streaming.py` implementa estratégias de fallback para o CLOC: varredura do working tree, modo `--vcs=git`, lista de arquivos `.java`, varredura por sub-raiz (match `--match-f=.java`), passagem Java-only pela árvore completa e, para repositórios muito grandes, agregação em blocos (chunked list-file) — mitigando erros de I/O do Perl em árvores enormes.
- Para CK, o script usa JAR com caminho absoluto, flags de memória da JVM e caminho(s) de fonte de fallback (ex.: `src/main/java`).
- Flags úteis: `--skip_cloc`, `--skip_ck`, `--workers`, `--cloc_extended`, `--keep_temp` (para inspeção pontual).

## Perguntas de pesquisa (RQs) e como medir
- RQ01 Popularidade vs Qualidade: usar `stars` versus CBO/DIT/LCOM
- RQ02 Maturidade vs Qualidade: usar `age_years` versus CBO/DIT/LCOM
- RQ03 Atividade vs Qualidade: usar `releases` (contagem) versus CBO/DIT/LCOM
- RQ04 Tamanho vs Qualidade: usar `code` e `comment` (cloc) versus CBO/DIT/LCOM

Para cada RQ, sumarizar por repositório usando medidas de tendência central (mediana, média) e dispersão (desvio padrão), e discutir achados versus hipóteses.

Gere as tabelas e correlações com:

```powershell
# Após gerar repos_list.csv, cloc_summary.csv e ck_summary.csv
python sprint2\scripts\analyze_rqs.py --plots
```

Os gráficos serão salvos em `sprint2/data/processed/plots/*.png`.

## Troubleshooting
- Erro “Filename too long” (Windows): habilite caminhos longos (ver seção de clone) e use o script de clone fornecido, que já força `core.longpaths=true` por invocação.
- `cloc` falha por falta de `unzip`: nossos scripts usam varredura do working tree (evita dependências externas). Garanta que o `cloc` está instalado e acessível no PATH.
- Rate limit no GitHub GraphQL: defina corretamente o `GITHUB_TOKEN` e, se necessário, reduza a taxa (o script já pagina em lotes e dorme entre chamadas).

## Status atual (resumo)
- Lista dos 1.000 repositórios: ok (GraphQL)
- Clone em paralelo com suporte a caminhos longos: ok
- Coleta e processamento streaming (CLOC e CK) → `cloc_summary.csv` e `ck_summary.csv`: ok
- Merge/dedup (canônicos) → `merge_summaries.py`: ok
- Análise RQs + correlações + gráficos → `analyze_rqs.py`: ok

Observação: após múltiplas rodadas de validação e reparo direcionado, restou uma fração pequena (~1%) de casos anômalos tolerados (p.ex., `CK>0` e `CLOC==0` em árvores peculiares). Esses casos não alteram as conclusões principais e podem ser revisitados com inspeções pontuais, se necessário.
