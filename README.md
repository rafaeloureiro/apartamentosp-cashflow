# 🏠 apartamentosp-cashflow

Painel de fluxo de caixa pessoal alimentado pelo Trello.  
Lê cards de um quadro no padrão `DD/MM/AA - R$ valor - descrição` e calcula automaticamente a **minha parte** nas contas compartilhadas com a esposa.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://apartamentosp-cashflow.streamlit.app)

---

## ✨ Funcionalidades

- **Divisão automática 50/50** — cards com o label `Apartamento SP` têm o valor dividido por 2
- **Seletor de período** — analise qualquer intervalo de datas dos últimos 2 anos
- **KPIs com comparativo YoY** — gasto acumulado no mês, total do período e maior gasto individual
- **Gráfico de fluxo diário** — barras de saídas + linha de saldo acumulado (eixo duplo)
- **Ranking de categorias** — top 12 fornecedores/categorias em barras horizontais
- **Pizza de composição** — proporção entre gastos próprios e gastos compartilhados
- **Tabela detalhada** — valor original, minha parte e indicação do label
- **Filtro de exclusão** — remove categorias dos cálculos diretamente pela sidebar
- **Cache de 10 minutos** — evita chamadas desnecessárias à API do Trello

---

## 🗂️ Estrutura do repositório

```
apartamentosp-cashflow/
├── contas_pessoais.py      # App principal
├── requirements.txt        # Dependências Python
├── .streamlit/
│   └── secrets.toml        # Credenciais (não versionar — ver .gitignore)
└── .gitignore
```

---

## ⚙️ Configuração local

### 1. Clone o repositório

```bash
git clone https://github.com/<seu-usuario>/apartamentosp-cashflow.git
cd apartamentosp-cashflow
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as credenciais do Trello

Crie o arquivo `.streamlit/secrets.toml` (nunca suba este arquivo para o GitHub):

```toml
TRELLO_API_KEY = "sua_api_key_aqui"
TRELLO_TOKEN   = "seu_token_aqui"
```

> **Como obter as credenciais:**  
> Acesse [https://trello.com/app-key](https://trello.com/app-key), copie a **API Key** e gere um **Token** com permissão de leitura.

### 5. Execute o app

```bash
streamlit run contas_pessoais.py
```

Acesse `http://localhost:8501` no navegador.

---

## 🚀 Deploy no Streamlit Community Cloud

1. Faça push do repositório para o GitHub (sem o `secrets.toml`)
2. Acesse [share.streamlit.io](https://share.streamlit.io) e clique em **New app**
3. Selecione o repositório, branch `main` e arquivo `contas_pessoais.py`
4. Em **Advanced settings → Secrets**, cole:

```toml
TRELLO_API_KEY = "sua_api_key_aqui"
TRELLO_TOKEN   = "seu_token_aqui"
```

5. Clique em **Deploy** — pronto!

---

## 📋 Padrão dos cards no Trello

Cada card do quadro deve seguir o formato:

```
DD/MM/AA - R$ valor - descrição
```

**Exemplos válidos:**
```
05/06/25 - R$ 350,00 - Condomínio
12/06/25 - R$ 1.200,00 - Aluguel
```

Cards fora do padrão são listados na seção **"Cards com formato inválido"** no rodapé do app.

### Label de divisão

Cards com o label **`Apartamento SP`** têm o valor automaticamente dividido por 2.  
O valor original é preservado na tabela para referência.

---

## 🔗 Projeto relacionado

Este app é derivado do [trello-cashflow](https://github.com/<seu-usuario>/trello-cashflow), painel de contas a pagar do negócio.
