# Sprint 2 – Preparação de Ambiente

## Estrutura de Pastas
```
sprint2/
  scripts/         # Scripts Python para coleta, análise e automação
  data/
    raw_ck/        # Saídas brutas do CK (métricas de qualidade)
    raw_cloc/      # Saídas brutas do cloc (LOC, comentários)
    processed/     # Dados consolidados para análise
  figures/         # Gráficos gerados
  reports/         # Relatórios, hipóteses, PDFs
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
