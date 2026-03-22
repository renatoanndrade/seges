import requests
from selenium.webdriver.common.by import By
import pandas as pd

class AlunosEmCurso:
    def __init__(self, nami, trimestre):
        self.nami = nami
        self.trimestre = trimestre
        
    def get_links_avaliacao_turma(self):
        self.nami.get('https://seges.sedu.es.gov.br/avaliacao_modo_avancados/turmas')
        a = self.nami.find_element(By.CSS_SELECTOR, 'tbody')
        linhas_tabela = a.find_elements(By.CSS_SELECTOR, 'tr[valign = "top"]')
        linhas_tabela[7].text
        
        links_avaliacao_turmas = []
        for linha_tabela in linhas_tabela:
            d = linha_tabela.find_element(By.CSS_SELECTOR, f'td[title="{self.trimestre}"]')
            links_avaliacao_turmas.append(d.find_element(By.CSS_SELECTOR, f'a[class="botao_transferir"]').get_attribute("href"))
        return links_avaliacao_turmas
    
    def pega_links_notas(self):
        links_avaliacao_turmas = self.get_links_avaliacao_turma()
        links_notas = []

        for link in links_avaliacao_turmas:
            self.nami.get(link)

            botoes = self.nami.find_elements(
                By.CSS_SELECTOR, 'a[title*="Lançar notas para"]'
            )

            for botao in botoes:
                lk = botao.get_attribute("href")
                links_notas.append(lk)

        urls_data = [url.replace('/grades?', '/grades/data?') for url in links_notas]

        return urls_data
    