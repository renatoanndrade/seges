from request_seges import Seges as sg
from request_seges import Login
from urllib.parse import urlparse
import urllib3

from getpass import getpass

import requests
import pandas as pd
import os


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

usuario = '10631094776'
senha = '10631094776'


etapa = 0 # significa que é o trimestre (0 = 1ºTrimestre, 1 = 2ºTrimestre e 2 = 3º Trimestre)

# urls digitadas
login = Login("https://seges.sedu.es.gov.br")
url_avaliacoes = 'https://seges.sedu.es.gov.br/avaliacao_modo_avancados/turmas'

session = requests.Session()

session_logada, base_url = login.autenticar(usuario, senha)
resp = session_logada.get(url_avaliacoes, verify=False)

if "sign_in" in resp.url.lower():
    print("❌ Não logado")
    print('Errou a senha ou o login, tente de novo.')
else:
    print("✅ Logado")
    
    

seges = sg(session_logada, etapa, base_url)

# pega links das turmas
url = 'https://seges.sedu.es.gov.br/avaliacao_modo_avancados/turmas'
lancar_notas = seges.get_minhas_turmas(url_avaliacoes)

# pega minhas notas
listagem_avaliacao = seges.get_links_minhas_notas(lancar_notas['href'])
listagem_avaliacao.tail()

'''
output
classroom é a turma
discipline_id é o tipo de diciplina
stage_id é o código do trimestre
'''

minhas_turmas = (listagem_avaliacao.drop_duplicates(subset='classroom_id').reset_index(drop=True))
meus_alunos = seges.get_alunos_por_turma(minhas_turmas['href'].to_list())
minhas_avaliacoes = seges.get_avaliacoes(listagem_avaliacao['href'])
listagem_avaliacao["classroom_id"] = listagem_avaliacao["classroom_id"].astype(int)

notas = seges.get_notas(listagem_avaliacao['href'])

df1 = []
df_notas = notas.copy()
df1 = df_notas.merge(
    meus_alunos,
    on=["turma", "classroom_id", "aluno_id"],
    how="left"
)
df1 = df1.merge(
    listagem_avaliacao,
    on=["turma", "classroom_id"],
    how="left"
)

df1 = df1.merge(
    minhas_avaliacoes,
    on=["classroom_evaluation_id" ,'turma'],
    how="left"
)

df1 = df1[df1["disciplina"] != "ELETIVAS"]

df1["result"] = df1[["number", "recovery"]].max(axis=1)


turmas = df1['turma'].unique()

import pandas as pd
import os

caminho_saida = 'output/diario.xlsx'

pasta = os.path.dirname(caminho_saida)
os.makedirs(pasta, exist_ok=True)

with pd.ExcelWriter(caminho_saida, engine='xlsxwriter') as w:

    for turma in turmas:
        # =========================
        # FILTRA A TURMA
        # =========================
        df_turma = df1[df1['turma'] == turma].copy()

        # =========================
        # CRIA CHAVE DA COLUNA (ANTI-CONFLITO)
        # =========================
        df_turma["atividade_coluna"] = (
            df_turma["atividade_nome"].astype(str) +
            " - " +
            df_turma["disciplina"].astype(str)
        )

        # =========================
        # PIVOT (ATIVIDADES → COLUNAS)
        # =========================
        df_pivot = df_turma.pivot_table(
            index=["numero", "nome"],
            columns="atividade_coluna",
            values="result",
            aggfunc="max"
        ).reset_index()

        # =========================
        # REMOVE COLUNAS VAZIAS
        # =========================
        df_pivot = df_pivot.dropna(axis=1, how="all")

        # =========================
        # ORGANIZAR COLUNAS
        # =========================
        colunas_fixas = ["numero", "nome"]
        colunas_atividades = [c for c in df_pivot.columns if c not in colunas_fixas]

        df_pivot = df_pivot[colunas_fixas + sorted(colunas_atividades)]

        # =========================
        # EXPORTA
        # =========================
        sheet_name = turma[:31]

        df_pivot.to_excel(
            w,
            sheet_name=sheet_name,
            index=False
        )

        worksheet = w.sheets[sheet_name]

        # =========================
        # AUTOFIT (SEGURO)
        # =========================
        for col_num in range(len(df_pivot.columns)):
            col_data = df_pivot.iloc[:, col_num]

            max_len = max(
                col_data.astype(str).map(len).max(),
                len(str(df_pivot.columns[col_num]))
            )

            worksheet.set_column(col_num, col_num, max_len + 2)