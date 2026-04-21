from request_seges import Seges as sg
from request_seges import Login
from urllib.parse import urlparse
import urllib3

from getpass import getpass

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

usuario = input("Usuário: ")
senha = getpass("Senha: ")

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
    
etapa = 0 # significa que é o trimestre (0-1ºTrimestre, 1-2ºTrimestre...)
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

turmas = meus_alunos['turma'].unique()

import pandas as pd
import os

caminho_saida = 'output/alunos_ativos.xlsx'
# pega só a pasta
pasta = os.path.dirname(caminho_saida)
# cria se não existir
os.makedirs(pasta, exist_ok=True)

with pd.ExcelWriter(caminho_saida) as w:
    for turma in turmas:
        df_saida = meus_alunos[meus_alunos['turma'] == turma]
        df_saida = df_saida[['numero', 'nome']]
        
        df_saida.to_excel(
            w, 
            sheet_name=turma, 
            freeze_panes=(1, 2), 
            index=False
            )

        worksheet = w.sheets[turma]
        worksheet.autofit()