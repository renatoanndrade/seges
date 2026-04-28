
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

            turma = data.get("classroom", {})
            disciplina = data.get("curriculum_discipline", {})

            alunos = data.get("group_students", [])
            avaliacoes = data.get("classroom_evaluations", [])

            # 🔥 aluno × avaliação (ESSA É A CHAVE)
            for aluno in alunos:
                for av in avaliacoes:

                    resultados.append({
                        "turma": turma.get("name"),
                        "classroom_id": turma.get("id"),
                        "discipline_id": disciplina.get("id"),

                        "aluno_id": aluno.get("id"),
                        "numero": aluno.get("number"),
                        "nome": aluno.get("name"),
                        "condicao": aluno.get("status"),
                        "classroom_evaluation_id": av.get("id"),   # ✅ sempre existe
                        "avaliacao_nome": av.get("name")           # ✅ sempre existe
                    })

        df = pd.DataFrame(resultados)

        return df.drop_duplicates(
            subset=[
                "classroom_id",
                "aluno_id",
                "discipline_id",
                "classroom_evaluation_id"
            ]
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


    def alterar_notas(self, payloads):
        respostas = []

        for payload in payloads:

            # 🔹 GERAR REFERER
            def gerar_referer(p):
                return (
                    f"{self.base_url}/grades?"
                    f"classroom_id={p['classroom_id']}"
                    f"&curriculum_discipline_id={p['curriculum_discipline_id']}"
                    f"&stage_id={p['stage_id']}"
                )

            referer = gerar_referer(payload)

            # 🔹 CSRF
            csrf = self._get_csrf_token(referer)

            # 🔹 HEADERS
            headers = {
                "Content-Type": "application/json",
                "Origin": self.base_url,
                "Referer": referer,
                "X-CSRF-Token": csrf,
                "User-Agent": "Mozilla/5.0"
            }

            try:
                # 🔹 REQUEST
                resp = self.session.post(
                    f"{self.base_url}/grades/grade.json",
                    json=payload,
                    headers=headers,
                    verify=False
                )

                if resp.status_code != 200:
                    raise Exception(resp.text)

                respostas.append({
                    "student_id": payload["group_student_id"],
                    "status": resp.status_code
                })

            except Exception as e:
                respostas.append({
                    "student_id": payload.get("group_student_id"),
                    "error": str(e)
                })

        #return respostas
    

    # limpeza dos nomes
    def get_nome_limpo(caminho):
        import pandas as pd
        import unicodedata
        # ========= FUNÇÃO PRA LIMPAR NOME =========
        def limpar_nome(nome):
            if pd.isna(nome):
                return None
            nome = str(nome).strip().upper()
            return unicodedata.normalize('NFKD', nome).encode('ASCII', 'ignore').decode('ASCII')


        # ========= CAMINHO DO ARQUIVO =========
        

        # ========= LER TODAS AS SHEETS =========
        dfs = pd.read_excel(caminho, sheet_name=None)

        lista_dfs = []

        # ========= LOOP NAS ABAS =========
        for nome_aba, df in dfs.items():
            try:
                # Garantir cópia
                df = df.copy()

                # Pegar até 4 colunas
                df = df.iloc[:, :4]

                # Detectar número de colunas
                n_cols = df.shape[1]

                if n_cols == 4:
                    df.columns = ["id", "nome", "nota_1", "nota_2"]
                elif n_cols == 3:
                    df.columns = ["id", "nome", "nota_1"]
                    df["nota_2"] = None
                else:
                    print(f"Aba {nome_aba} ignorada (colunas insuficientes)")
                    continue

                # ========= LIMPEZA =========
                df["nome"] = df["nome"].apply(limpar_nome)

                df["nota_1"] = pd.to_numeric(df["nota_1"], errors="coerce")
                df["nota_2"] = pd.to_numeric(df["nota_2"], errors="coerce")

                # ========= REGRA DE NEGÓCIO =========
                df["nota_final"] = df[["nota_1", "nota_2"]].max(axis=1)

                # ========= GUARDAR TURMA DA SHEET =========
                df["turma_sheet"] = nome_aba

                # ========= LIMPEZA FINAL =========
                df = df.dropna(subset=["nome"])

                # ========= SELECIONAR COLUNAS =========
                lista_dfs.append(df[["nome", "nota_final", "turma_sheet"]])

            except Exception as e:
                print(f"Erro na aba {nome_aba}: {e}")


        # ========= CONCATENAR =========
        if lista_dfs:
            df_suja = pd.concat(lista_dfs, ignore_index=True)
        else:
            df_suja = pd.DataFrame(columns=["nome", "nota_final", "turma_sheet"])
            
        return df_suja
    
    def escolher_atividade(lista_atividades):
        import tkinter as tk
        opcoes = sorted(lista_atividades['atividade_nome'].dropna().unique())
        root = tk.Tk()
        # 🔥 força ficar na frente
        root.lift()
        root.attributes("-topmost", True)
        root.after(100, lambda: root.attributes("-topmost", False))
        var = tk.StringVar(value=opcoes[0] if opcoes else "")
        def confirmar():
            root.destroy()
        for opcao in opcoes:
            tk.Radiobutton(root, text=opcao, variable=var, value=opcao).pack(anchor="w")
        tk.Button(root, text="OK", command=confirmar).pack(pady=10)
        root.mainloop()        
        return var.get()
    
    def set_payloads(stage_id, dataframe):
        payloads = []
        for _, row in dataframe.iterrows():

            nota = row["nota_final"]

            # 🔥 regra principal
            if pd.isna(nota):
                number = None
                unevaluated = True
            else:
                number = float(nota)
                unevaluated = False

            payload = {
                "classroom_evaluation_id": int(row["classroom_evaluation_id"]),
                "classroom_id": int(row["classroom_id"]),
                "curriculum_discipline_id": int(row["discipline_id"]),
                "group_student_id": int(row["aluno_id"]),

                "letter_id": None,

                "number": number,
                "recovery": None,

                "recovery_unevaluated": False,
                "stage_id": stage_id,  # ⚠️ ajuste se precisar (ou puxa do dataset)
                "unevaluated": unevaluated
            }

            payloads.append(payload)
        return payloads