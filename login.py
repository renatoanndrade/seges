from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

class Login:
    def __init__(self, nami, login, senha, escola=None):  # escola é opcional
        self.nami = nami
        self.senha = senha
        self.login = login
        self.escola = escola.lower() if escola else None
        self.logar()
    
    def logar(self):
        # Vai para página de login
        seges = "https://seges.sedu.es.gov.br/"
        self.nami.get(seges)
        
        # Preenche login
        WebDriverWait(self.nami, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[class="input_login"]'))
        ).send_keys(self.login)
        
        # Preenche senha
        self.nami.find_element(By.CSS_SELECTOR, 'input[class="input_senha"]').send_keys(self.senha)
        
        # Clica no botão entrar
        self.nami.find_element(By.CSS_SELECTOR, 'div[class="botao-entrar"]').click()
        
        # Aguarda o login ser processado
        WebDriverWait(self.nami, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#main-menu'))
        )
        
        # Se foi passada uma escola, seleciona
        if self.escola:
            self.selecionar_escola()
    
    def selecionar_escola(self):
        # Vai para página de seleção de escolas
        self.nami.get("https://seges.sedu.es.gov.br/context/schools")
        
        # Aguarda a tabela de escolas carregar
        WebDriverWait(self.nami, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#schools'))
        )
        
        # Mapeamento dos nomes das escolas
        escolas_validas = {
            "adolfina": "EEEFM ADOLFINA ZAMPROGNO",
            "gaudino": "CEEFMTI GALDINO ANTONIO VIEIRA",
            "godofredo": "EEEM GODOFREDO SCHNEIDER"
        }
        
        if self.escola not in escolas_validas:
            print(f"✗ Escola '{self.escola}' não é válida!")
            return
        
        # Encontra todas as linhas da tabela
        linhas = self.nami.find_elements(By.CSS_SELECTOR, '#schools tbody tr')
        
        escola_encontrada = False
        nome_procurado = escolas_validas[self.escola]
        
        for linha in linhas:
            nome_escola = linha.find_element(By.CSS_SELECTOR, 'td:first-child').text
            
            if nome_procurado in nome_escola:
                botao = linha.find_element(By.CSS_SELECTOR, 'a.btn-success')
                botao.click()
                print(f"✓ Escola selecionada: {nome_escola}")
                escola_encontrada = True
                break
        
        if not escola_encontrada:
            print(f"✗ Escola '{nome_procurado}' não encontrada!")