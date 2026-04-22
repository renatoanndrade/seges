
import requests
import urllib3 #isso serve para mecher nos arquivos SSL
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np

from urllib.parse import urljoin, urlparse, parse_qs

import requests
import urllib3 #isso serve para mecher nos arquivos SSL
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np

from urllib.parse import urljoin, urlparse, parse_qs

class Login:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()

    def _pega_token(self):
        resp = self.session.get(f"{self.base_url}/users/sign_in", verify=False)
        soup = BeautifulSoup(resp.text, "html.parser")

        token_input = soup.select_one('input[name="authenticity_token"]')

        if not token_input:
            raise ValueError("Token não encontrado na página")

        return token_input["value"]

    def autenticar(self, usuario, senha):
        token = self._pega_token()

        payload = {
            "utf8": "✓",
            "authenticity_token": token,
            "user[login]": usuario,
            "user[password]": senha,
            "commit": "Entrar"
        }

        resp = self.session.post(
            f"{self.base_url}/users/sign_in",
            data=payload,
            verify=False
        )
        
        parsed = urlparse(resp.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        return self.session, base_url
       

class Seges:
    def __init__(self, session, etapa, base_url):
        self.session = session
        self.etapa = etapa  
        self.base_url = base_url

        # headers padrão
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*"
        })

    # =========================
    # 🔗 UTILS
    # =========================
    def _to_data_url(self, url):
        if "/grades?" in url:
            return url.replace("/grades?", "/grades/data?")
        return None

    def _gerar_referer(self, classroom_id, discipline_id, stage_id):
        return (
            f"{self.base_url}/grades?"
            f"classroom_id={classroom_id}"
            f"&curriculum_discipline_id={discipline_id}"
            f"&stage_id={stage_id}"
        )

    def _get_csrf_token(self, url):
        resp = self.session.get(url, verify=False)

        if resp.status_code != 200:
            raise Exception("Erro ao obter CSRF")

        soup = BeautifulSoup(resp.text, "html.parser")

        token = soup.select_one('meta[name="csrf-token"]')

        if not token:
            raise Exception("CSRF token não encontrado")

        return token["content"]

    # =========================
    # 📚 TURMAS
    # =========================
    def get_minhas_turmas(self, url):
        resp = self.session.get(url, verify=False)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        dados = []

        for a in soup.select("a.botao_transferir"):
            href = a.get("href")
            if not href:
                continue

            tr = a.find_parent("tr")
            nome_turma = tr.select_one("td").get_text(strip=True)

            query = urlparse(href).query
            params = parse_qs(query)

            dados.append({
                "turma": nome_turma,
                "turma_id": params.get("turma_id", [None])[0],
                "etapa_id": params.get("etapa_id", [None])[0],
                "href": href
            })
            
        df = pd.DataFrame(dados)

        etapas = np.sort(df['etapa_id'].dropna().unique())
        return df[df['etapa_id'] == etapas[self.etapa]].reset_index(drop=True)

    # =========================
    # 📌 DISCIPLINAS
    # =========================
    def get_links_minhas_notas(self, hrefs):
        dfs = []

        for href in hrefs:
            url = urljoin(self.base_url, href)

            resp = self.session.get(url, verify=False)
            soup = BeautifulSoup(resp.text, "html.parser")

            info = {}

            for p in soup.select("fieldset .destaque_informacoes p"):
                texto = p.get_text(strip=True)

                if "Turma:" in texto:
                    info["turma"] = texto.replace("Turma:", "").strip()

                elif "Etapa:" in texto:
                    info["etapa"] = texto.replace("Etapa:", "").strip()

            dados = []

            for tr in soup.select("tr.tabela1, tr.tabela2"):
                a = tr.select_one("a.botao_transferir")
                if not a:
                    continue

                disciplina = tr.select_one("td").contents[0].strip()
                href_full = urljoin(self.base_url, a["href"])
                params = parse_qs(urlparse(href_full).query)

                dados.append({
                    "turma": info.get("turma"),
                    "etapa": self.etapa,
                    "disciplina": disciplina,
                    "classroom_id": params.get("classroom_id", [None])[0],
                    "discipline_id": params.get("curriculum_discipline_id", [None])[0],
                    "stage_id": params.get("stage_id", [None])[0],
                    "href": href_full
                })

            dfs.append(pd.DataFrame(dados))

        return pd.concat(dfs, ignore_index=True)

    # =========================
    # 👨‍🎓 ALUNOS
    # =========================
    def get_alunos_por_turma(self, links):
        resultados = []

        for url in links:
            url_data = self._to_data_url(url)
            if not url_data:
                continue

            resp = self.session.get(url_data, verify=False)

            if "application/json" not in resp.headers.get("Content-Type", ""):
                print(f"⚠️ Não é JSON: {url}")
                continue

            data = resp.json()

            for aluno in data["group_students"]:

                resultados.append({
                    "turma": data["classroom"]["name"],
                    "classroom_id": data["classroom"]["id"],
                    "aluno_id": aluno.get("id"),
                    "numero": aluno.get("number"),
                    "nome": aluno.get("name"),
                    "condicao": aluno.get("status")
                })

        df = pd.DataFrame(resultados)

        return df.drop_duplicates(
            subset=["classroom_id", "aluno_id"]
        ).reset_index(drop=True)

    def get_notas(self, links):
        resultados = []

        for url in links:
            url_data = self._to_data_url(url)
            if not url_data:
                continue

            resp = self.session.get(url_data, verify=False)

            if "application/json" not in resp.headers.get("Content-Type", ""):
                print(f"⚠️ Não é JSON: {url}")
                continue

            data = resp.json()

            turma = data["classroom"]["name"]
            classroom_id = data["classroom"]["id"]

            for nota in data.get("grades", []):
                resultados.append({
                    "turma": turma,
                    "classroom_id": classroom_id,
                    "aluno_id": nota["group_student_id"],
                    "classroom_evaluation_id": nota["classroom_evaluation_id"],
                    "number": nota.get("number"),
                    "recovery": nota.get("recovery")
                })

        return pd.DataFrame(resultados)


    # =========================
    # 📝 AVALIAÇÕES
    # =========================
    def get_avaliacoes(self, links_notas):
        resultados = []

        for url in links_notas:
            url_data = self._to_data_url(url)
            if not url_data:
                continue

            resp = self.session.get(url_data, verify=False)

            try:
                data = resp.json()
            except:
                print(f"⚠️ Não é JSON: {url}")
                continue

            for av in data["classroom_evaluations"]:
                resultados.append({
                    "turma": data["classroom"]["name"],
                    "classroom_evaluation_id": av["id"],
                    "atividade_nome": av["name"]
                })

        return pd.DataFrame(resultados)

    def montar_payload_nota(self, meus_alunos, listagem_avaliacao, minhas_avaliacoes, notas, numero_aluno, turma, disciplina_nome, atividade_nome):

        # =========================
        # 🔹 ALUNO
        # =========================
        aluno = meus_alunos[
            (meus_alunos["numero"] == numero_aluno) &
            (meus_alunos["turma"] == turma)
        ]

        if aluno.empty:
            raise ValueError("Aluno não encontrado")

        aluno = aluno.iloc[0]
        aluno_id = int(aluno["aluno_id"])
        classroom_id = int(aluno["classroom_id"])

        # =========================
        # 🔹 DISCIPLINA
        # =========================
        df_disciplina = listagem_avaliacao[
            (listagem_avaliacao["classroom_id"].astype(int) == classroom_id) &
            (listagem_avaliacao["disciplina"].str.strip().str.upper()
            == disciplina_nome.strip().upper())
        ]

        if df_disciplina.empty:
            raise ValueError("Disciplina não encontrada")

        df_disciplina = df_disciplina.iloc[0]
        discipline_id = int(df_disciplina["discipline_id"])
        stage_id = int(df_disciplina["stage_id"])

        # =========================
        # 🔹 AVALIAÇÃO
        # =========================
        avaliacao = minhas_avaliacoes[
            (minhas_avaliacoes["turma"] == turma) &
            (minhas_avaliacoes["atividade_nome"].str.strip().str.upper()
            == atividade_nome.strip().upper())
        ]

        if avaliacao.empty:
            raise ValueError("Atividade não encontrada")

        avaliacao = avaliacao.iloc[0]
        classroom_evaluation_id = int(avaliacao["classroom_evaluation_id"])

        # =========================
        # 🔹 NOTAS (AQUI É A MUDANÇA IMPORTANTE)
        # =========================
        nota_row = notas[
            (notas["classroom_id"].astype(int) == classroom_id) &
            (notas["aluno_id"].astype(int) == aluno_id) &
            (notas["classroom_evaluation_id"].astype(int) == classroom_evaluation_id)
        ]

        if nota_row.empty:
            number = None
            recovery = None       
            
        else:
            number = nota_row.iloc[0]["number"]
            recovery = nota_row.iloc[0]["recovery"]
            # 🔥 caso exista linha mas venha NaN
            if pd.isna(number):
                number = None

            if pd.isna(recovery):
                recovery = None

        # =========================
        # 🔥 PAYLOAD FINAL
        # =========================
        payload = {
            "classroom_evaluation_id": classroom_evaluation_id,
            "classroom_id": classroom_id,
            "curriculum_discipline_id": discipline_id,
            "group_student_id": aluno_id,

            "letter_id": None,

            # 🔥 vindo do DATASET NOTAS
            "number": number,
            "recovery": recovery,

            "recovery_unevaluated": False,
            "stage_id": stage_id,
            "unevaluated": False
        }

        return payload


    def alterar_nota(self, payload):

        # =========================
        # 🔹 GERAR REFERER (interno)
        # =========================
        def gerar_referer():
            return (
                f"{self.base_url}/grades?"
                f"classroom_id={payload['classroom_id']}"
                f"&curriculum_discipline_id={payload['curriculum_discipline_id']}"
                f"&stage_id={payload['stage_id']}"
            )

        referer = gerar_referer()

        # =========================
        # 🔹 CSRF
        # =========================
        csrf = self._get_csrf_token(referer)

        # =========================
        # 🔹 HEADERS
        # =========================
        headers = {
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": referer,
            "X-CSRF-Token": csrf,
            "User-Agent": "Mozilla/5.0"
        }

        # =========================
        # 🔹 REQUEST
        # =========================
        resp = self.session.post(
            f"{self.base_url}/grades/grade.json",
            json=payload,
            headers=headers,
            verify=False
        )

        # =========================
        # 🔥 TRATAMENTO
        # =========================
        if resp.status_code != 200:
            raise Exception(f"Erro ao enviar nota: {resp.status_code} - {resp.text}")

        print(f"Aluno ID: {payload['group_student_id']}")
        print("Status:", resp.status_code)

        return resp
    
    
    
    
    
    def exportar_alunos_ativos(self, links_turmas, caminho_saida):
        urllib3.disable_warnings()

        with pd.ExcelWriter(caminho_saida) as w:

            for url in links_turmas:   

                cookies = {
                    c['name']: c['value'] 
                    for c in self.nami.get_cookies()
                }

                data = requests.get(
                    url, 
                    cookies=cookies, 
                    verify=False
                ).json()

                sheet = data["classroom"]["name"]

                df = pd.DataFrame(data["group_students"])

                df = df[df["status_humanize"] == "Em curso"][["number", "name"]]
                df.columns = ['numero', 'NOME']

                df.to_excel(
                    w, 
                    sheet_name=sheet, 
                    freeze_panes=(1, 2), 
                    index=False
                )

                worksheet = w.sheets[sheet]
                worksheet.autofit()