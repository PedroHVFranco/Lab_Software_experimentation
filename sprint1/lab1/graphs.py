import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import random
from datetime import datetime, timedelta
import os

def salvar_grafico(nome_arquivo):
    """Salva o gráfico atual em PNG na pasta 'graficos'."""
    pasta = 'graficos'
    os.makedirs(pasta, exist_ok=True)  # Cria a pasta se não existir
    caminho = os.path.join(pasta, f'{nome_arquivo}.png')
    plt.savefig(caminho, bbox_inches='tight')
    plt.close()  # Fecha a figura atual para liberar memória
    print(f'Gráfico salvo em: {caminho}')

def grafico_barra(df, col, line, title, name):
    plt.figure(figsize=(8, 5))
    sns.barplot(x=col, y=line, data=df, estimator="median", errorbar=None)
    plt.title(title)
    plt.xticks(rotation=45)
    plt.tight_layout()
    salvar_grafico(name)
    plt.show()
    
def grafico_barra1(contagem, title, name):
    plt.figure(figsize=(8, 6))
    sns.barplot(x=contagem.values, y=contagem.index, palette="viridis")
    plt.title(title)
    plt.xlabel("Número de repositórios")
    plt.ylabel("Linguagem")
    plt.tight_layout()
    salvar_grafico(name)
    
def grafico_histograma(df,bin, col, title, name, log=False, eixo="x"):
    #obs o pls.figure cria uma figura vazia, ent qualquer imagem criada cai la dentro, por isso o plt n usa sns e msm tem img do sns dentro dele
    plt.figure(figsize=(8, 5))
    sns.histplot(df[col], bins=bin, kde=True)
    plt.title(title)
    if log:
       if eixo == "x":
            plt.xscale("log")   
       elif eixo == "y":
            plt.yscale("log")
            
    plt.tight_layout()
    salvar_grafico(name)
    
        
def grafico_histograma_rq1(df,bin, col, title, name, log=False, eixo="x"):
    #obs o pls.figure cria uma figura vazia, ent qualquer imagem criada cai la dentro, por isso o plt n usa sns e msm tem img do sns dentro dele
    plt.figure(figsize=(8, 5))
    sns.histplot(df[col]/365, bins=bin, kde=True)
    plt.title(title)
    if log:
       if eixo == "x":
            plt.xscale("log")   
       elif eixo == "y":
            plt.yscale("log")
            
    plt.tight_layout()
    salvar_grafico(name)
    
    #col = categoria e line = variavel numerica
def grafico_RQ2(df,col, title, name):
   plt.figure(figsize=(8,5))
   sns.histplot(df["prsMerged"], bins=50, log_scale=True, kde=True)
   plt.title("Distribuição de PRs aceitos (log)")
   plt.xlabel("PRs aceitos (log)")
   plt.ylabel("Quantidade de repositórios")
   plt.tight_layout()
   salvar_grafico("RQ2")
    # plt.show()
    
def grafico_violin(df):
    plt.figure(figsize=(8, 5))
    sns.violinplot(x=df["prsMerged"])
    plt.title('Distribuição dos Lucros por Produto (Violin Plot)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    salvar_grafico("grafico_violin")
    # plt.show()
   
# rq7 Contribuições externas 
def grafico_rq7_prs(df):
    plt.figure(figsize=(10,6))
    sns.barplot(x="primaryLanguage", y="prsMerged", data=df, estimator="median")
    plt.title("RQ7 - PRs aceitos por linguagem")
    plt.ylabel("Mediana de PRs aceitos")
    plt.xticks(rotation=45)
    plt.tight_layout()
    salvar_grafico("RQ7_CONT_EXT")

# rq70 releses por linguagem
def grafico_rq7_releases(df):
    plt.figure(figsize=(10,6))
    sns.barplot(x="primaryLanguage", y="releases", data=df, estimator="median")
    plt.title("RQ7 - Releases por linguagem")
    plt.ylabel("Mediana de releases")
    plt.xticks(rotation=45)
    plt.tight_layout()
    salvar_grafico("RQ7_RELEASE_L")
    
# rq7 atualização recente / linguagem
def grafico_rq7_atualizacao(df):
    plt.figure(figsize=(10,6))
    sns.barplot(x="primaryLanguage", y="dias_desde_ultima_atualizacao", 
            data=df, estimator="mean")
    plt.title("RQ7 - Atualização recente por linguagem")
    plt.ylabel("Media (dias)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    salvar_grafico("RQ7_ATT_L")

    


def main():
    df = pd.read_csv('data/top100.csv')#retorna um dataframe
    #RQ01
    grafico_histograma_rq1(df, 10, 'idade_dias', 'Idade', "RQ1")
    
    #RQ02 --- melhores a exibição dps
    grafico_RQ2(df, "prsMerged", "RQ02 - PRs aceitos (log)", "RQ02")

    #RQ03
    grafico_histograma(df, 15, 'releases', 'releases', "RQ3")
    
    #RQ04
    grafico_histograma(df, 30, 'dias_desde_ultima_atualizacao', 'dias desde ultima atualizacao', "RQ4")
    
    #RQ05
    contagem = df["primaryLanguage"].fillna("Sem linguagem").value_counts()
    contagem.head
    grafico_barra1(contagem, 'linguaguens mais usadas', "RQ5")
    
    #RQ06
    grafico_histograma(df, 15, 'closedRatio', 'total issues / issues fechadas', "RQ6")

    #RQ07
    grafico_rq7_atualizacao(df)
    grafico_rq7_prs(df)
    grafico_rq7_releases(df)


if __name__ == "__main__":
    main()

    
