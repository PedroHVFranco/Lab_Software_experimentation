# Sprint 2 – Preparação de Ambiente

## Estrutura de Pastas
```
sprint2/
  README.md
  tools/
    ck/                           # CK construído (JARs) 
  scripts/
    fetch_repos_graphql.py        # Coleta top-N Java via GraphQL
    clone_repos.py                # Clone paralelo com suporte a long paths
    run_cloc.py                   # cloc em lote + CSV agregado
    run_cloc_one.py               # cloc por repositório (CSV simples)
    setup_ck.ps1                  # Script para obter/compilar CK
    setup_cloc.ps1                # Script para instalar cloc
  data/
    repos/                        # Repositórios clonados: <owner>/<repo>
    repos_list.csv                # Lista dos repositórios coletados (GraphQL)
    raw_ck/                       # Saídas brutas do CK (métricas de qualidade)
    raw_cloc/                     # Saídas brutas do cloc (LOC, comentários)
      00-Evan__shattered-pixel-dungeon.all_langs.json
    processed/                    # Dados consolidados para análise
      00-Evan_cloc.csv            # Exemplo de CSV individual (cloc)
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

## Clonar os repositórios (com suporte a caminhos longos)
Para clonar os repositórios listados no CSV em paralelo:

```powershell
# clona para sprint2/data/repos/<owner>/<repo>
python sprint2\scripts\clone_repos.py --csv sprint2\data\repos_list.csv --out sprint2\data\repos --workers 6
```

Observações (Windows):
- O script força `git -c core.longpaths=true` por invocação para mitigar erros de “Filename too long”.
- Opcionalmente, habilite caminhos longos no sistema e no Git para uso geral:
  - Registro do Windows (requer admin): HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled = 1
  - Git (requer admin para nível system): `git config --system core.longpaths true`

As falhas de clone são registradas em `sprint2/data/clone_failures.log`.

## Medir tamanho (LOC e comentários) com cloc
Instale o cloc (veja acima). Depois, rode em lote para todos os repositórios clonados:

```powershell
python sprint2\scripts\run_cloc.py --repos_dir sprint2\data\repos --out_json_dir sprint2\data\raw_cloc --out_csv sprint2\data\processed\cloc_summary.csv --workers 6
```

Saídas:
- JSON por repositório em `sprint2/data/raw_cloc/<owner>__<repo>.json`
- CSV agregado em `sprint2/data/processed/cloc_summary.csv` com colunas: repo, files, code, comment, blank

Gerar CSV para um repositório específico (ex.: 00-Evan/shattered-pixel-dungeon):
```powershell
python sprint2\scripts\run_cloc_one.py --repo_dir sprint2\data\repos\00-Evan\shattered-pixel-dungeon --out_csv sprint2\data\processed\00-Evan_cloc.csv --name 00-Evan/shattered-pixel-dungeon
```

Exemplo de saída (já gerado):
```
repo,files,code,comment,blank
00-Evan/shattered-pixel-dungeon,1554,273423,33108,57435
```

## Métricas de qualidade (CK)
O CK já é obtido/compilado via `setup_ck.ps1`. Próximo passo: automatizar a execução do JAR do CK para cada repositório e sumarizar CBO, DIT e LCOM por repositório (os CSVs do CK são gerados por nível — classe/método/etc.).

Notas:
- O JAR ficará em `sprint2/tools/ck/ck-<versao>-jar-with-dependencies.jar`.
- Em breve será adicionado um script para executar o CK em lote e consolidar as métricas por repositório.

## Artefatos de dados esperados
- `sprint2/data/repos_list.csv` — lista dos 1.000 repositórios com: repo, url, stars, created_at, releases, age_years
- `sprint2/data/processed/cloc_summary.csv` — LOC e comentários por repositório (totais)
- `sprint2/data/raw_cloc/*.json` — saídas brutas do cloc por repositório
- `sprint2/data/raw_ck/*.csv` — saídas do CK (por nível); será sumarizado para CBO, DIT, LCOM por repositório

## Perguntas de pesquisa (RQs) e como medir
- RQ01 Popularidade vs Qualidade: usar `stars` versus CBO/DIT/LCOM
- RQ02 Maturidade vs Qualidade: usar `age_years` versus CBO/DIT/LCOM
- RQ03 Atividade vs Qualidade: usar `releases` (contagem) versus CBO/DIT/LCOM
- RQ04 Tamanho vs Qualidade: usar `code` e `comment` (cloc) versus CBO/DIT/LCOM

Para cada RQ, sumarizar por repositório usando medidas de tendência central (mediana, média) e dispersão (desvio padrão), e discutir achados versus hipóteses.

## Troubleshooting
- Erro “Filename too long” (Windows): habilite caminhos longos (ver seção de clone) e use o script de clone fornecido, que já força `core.longpaths=true` por invocação.
- `cloc` falha por falta de `unzip`: nossos scripts usam varredura do working tree (evita dependências externas). Garanta que o `cloc` está instalado e acessível no PATH.
- Rate limit no GitHub GraphQL: defina corretamente o `GITHUB_TOKEN` e, se necessário, reduza a taxa (o script já pagina em lotes e dorme entre chamadas).

## Status atual (resumo)
- Lista dos 1.000 repositórios: ok (GraphQL)
- Clone em paralelo com suporte a caminhos longos: ok
- cloc em repositório individual (ex.: 00-Evan): ok (`00-Evan_cloc.csv` gerado)
- cloc em lote e consolidação (`cloc_summary.csv`): pendente de execução
- CK (CBO, DIT, LCOM) e sumarização por repositório: pendente (script em desenvolvimento)
