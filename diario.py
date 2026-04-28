#Pega os dados do seges
from request_seges import Seges as sg
from request_seges import Login
from urllib.parse import urlparse
import urllib3

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()
usuario = '10631094776'
etapa = 0 # significa que é o trimestre (0-1ºTrimestre, 1-2ºTrimestre...)
senha = usuario


login = Login("https://seges.sedu.es.gov.br")

session_logada, base_url = login.autenticar(usuario, senha)
seges = sg(session_logada, etapa, base_url)

# pega links das turmas
url = 'https://seges.sedu.es.gov.br/avaliacao_modo_avancados/turmas'
lancar_notas = seges.get_minhas_turmas(url)

# pega minhas notas
listagem_avaliacao = seges.get_links_minhas_notas(lancar_notas['href'])
listagem_avaliacao.tail()
'''
output
classroom é a turma
discipline_id é o tipo de diciplina
stage_id é o código do trimestre
'''

minhas_turmas = (listagem_avaliacao.drop_duplicates(subset='classroom_id').reset_index(drop=True)) # só serve para pegar o nome dos alunos e fim
meus_alunos = seges.get_alunos_por_turma(listagem_avaliacao['href'].to_list())
minhas_avaliacoes = seges.get_avaliacoes(listagem_avaliacao['href'])
listagem_avaliacao["classroom_id"] = listagem_avaliacao["classroom_id"].astype(int)

notas = seges.get_notas(listagem_avaliacao['href'])

df = notas.copy()

df = df.merge(
    meus_alunos,
    on=["turma", "classroom_id", "aluno_id", "classroom_evaluation_id"],
    how="left"
)

df = df.merge(
    minhas_avaliacoes,
    on=["turma", "classroom_evaluation_id"],
    how="left"
)

df["discipline_id"] = df["discipline_id"].astype(int)
listagem_avaliacao["discipline_id"] = listagem_avaliacao["discipline_id"].astype(int)

df = df.merge(
    listagem_avaliacao,
    on=["turma", "classroom_id", "discipline_id"],
    how="left"
)


df['result']= df[['number', 'recovery']].max(axis=1)

import os
import pandas as pd
with pd.ExcelWriter("output/diario.xlsx", engine="xlsxwriter") as writer:

    for turma in df["turma"].dropna().unique():

        df_turma = df[df["turma"] == turma].copy()

        # garante nomes limpos de sheet (limite Excel = 31 chars)
        sheet_name = str(turma)[:31]

        # =========================
        # pivot: aluno x avaliação
        # =========================
        df_turma["atividade_coluna"] = (
            df_turma["avaliacao_nome"].astype(str) +
            " - " +
            df_turma["disciplina"].astype(str)
        )

        df_pivot = df_turma.pivot_table(
            index=["numero", "nome"],
            columns="atividade_coluna",
            values="result",
            aggfunc="max"
        ).reset_index()

        # remove colunas vazias
        df_pivot = df_pivot.dropna(axis=1, how="all")

        # ordena colunas
        fixas = ["numero", "nome"]
        cols = [c for c in df_pivot.columns if c not in fixas]

        df_pivot = df_pivot[fixas + sorted(cols)]

        # exporta
        df_pivot.to_excel(writer, sheet_name=sheet_name, index=False)

        # ajuste automático de largura
        worksheet = writer.sheets[sheet_name]
        worksheet.freeze_panes(1, 2)

        for i, col in enumerate(df_pivot.columns):
            max_len = max(df_pivot[col].fillna("").astype(str).str.len().max(), len(str(col)))
            worksheet.set_column(i, i, max_len + 2)