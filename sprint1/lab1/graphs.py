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
def grafico_boxplot(df,col, title, name):
    plt.figure(figsize=(8, 5))
    # sns.boxplot(x=col, y=line, data=df)
    sns.boxplot(x=df[col])
    plt.xscale("log")
    plt.title(title)
    plt.xticks(rotation=45)
    plt.tight_layout()
    salvar_grafico(name)
    # plt.show()
    
def grafico_violin(df):
    plt.figure(figsize=(8, 5))
    sns.violinplot(x=df["prsMerged"])
    plt.title('Distribuição dos Lucros por Produto (Violin Plot)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    salvar_grafico("grafico_violin")
    # plt.show()
    


def main():
    df = pd.read_csv('data/top100.csv')#retorna um dataframe
    #RQ01
    grafico_histograma(df, 10, 'idade_dias', 'Idade', "RQ1")
    
    #RQ02 --- melhores a exibição dps
    grafico_violin(df)
    grafico_boxplot(df, "prsMerged", "RQ02 - PRs aceitos (log)", "RQ02")

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

    #gerar graficos

if __name__ == "__main__":
    main()

    #graphs
    
