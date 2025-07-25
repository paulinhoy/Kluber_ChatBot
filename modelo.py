#import os
import pandas as pd
import numpy as np
import json
import datetime
import traceback
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO

from langchain.tools import Tool
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_community.callbacks import get_openai_callback
#from langchain_core.messages import AIMessage, HumanMessage

#from dotenv import load_dotenv
#from pathlib import Path

ultimo_grafico_base64 = None # Guarda imagem

api_key = st.secrets["OPENAI_API_KEY"]

# --- CONFIGURAÇÃO INICIAL ---

# Carregar variáveis de ambiente
#dotenv_path = Path(__file__).resolve().parent / '.env'
#load_dotenv(dotenv_path)
#api_key = os.getenv("OPENAI_API_KEY")

# Arquivo json
LOG_FILE = "log_interacoes.jsonl"

# Carregar DataFrame
try:
    df = pd.read_excel("data/VENT_EXEMPLO_ANONIMIZADO.xlsx", sheet_name="Planilha2")
    df_exemplo = df.head(3).to_string()

except Exception as e:
    print(f"Erro ao carregar o banco de dados: {e}")
    exit(1)

# --- FERRAMENTA DE CONSULTA (sem alterações) ---

def query_dataframe(query: str) -> str:
    try:
        safe_env = {
            'df': df,
            'pd': pd,
            'np': np,
            'result': None
        }
        if '\n' in query:
            lines = query.strip().split('\n')
            last_line = lines[-1].strip()
            if '=' not in last_line and not last_line.startswith('print'):
                lines[-1] = f"result = {last_line}"
            elif last_line.startswith('print'):
                lines[-1] = f"result = {last_line[6:-1]}"
            exec('\n'.join(lines), safe_env)
            result = safe_env.get('result')
            if result is None:
                for line in reversed(lines):
                    if '=' in line:
                        var_name = line.split('=')[0].strip()
                        if var_name in safe_env:
                            result = safe_env[var_name]
                            break
        else:
            result = eval(query, {}, safe_env)
        if result is None:
            return "Operação executada (sem retorno)"
        if isinstance(result, (pd.DataFrame, pd.Series)):
            # MUDANÇA: Limitar ainda mais para evitar spam no terminal
            if len(result) > 10:
                return (
                    f"Resultado truncado (10 de {len(result)} linhas):\n"
                    f"{result.head(10).to_string()}"
                )
            return f"Resultado:\n{result.to_string()}"
        if isinstance(result, (list, dict, set)):
            # MUDANÇA: Limitar listas/dicts grandes
            result_str = str(result)
            if len(result_str) > 300:
                return f"Resultado ({type(result).__name__}) truncado:\n{result_str[:300]}..."
            return f"Resultado ({type(result).__name__}):\n{result_str}"
        # MUDANÇA: Limitar strings muito grandes
        result_str = str(result)
        if len(result_str) > 200:
            return f"Resultado truncado: {result_str[:200]}..."
        return f"Resultado: {result_str}"
    except Exception as e:
        return f"ERRO: {str(e)}\nDica: Use 'df' para referenciar o DataFrame principal"

def plot_chart(query: str) -> str:
    """
    Executa código para criar gráficos usando matplotlib/seaborn
    """
    try:
        # Configurar o ambiente seguro
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(10, 6))
        
        safe_env = {
            'df': df,
            'pd': pd,
            'np': np,
            'plt': plt,
            'sns': sns,
            'fig': fig,
            'ax': ax
        }
        
        # Executar o código
        exec(query, safe_env)
        
        # Salvar o gráfico em base64 para o Streamlit
        buffer = BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        
        # Converter para base64
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close()
        
        # IMPORTANTE: Salvar o gráfico em uma variável global para o Streamlit
        # e retornar apenas uma mensagem curta para o LLM
        global ultimo_grafico_base64
        ultimo_grafico_base64 = img_base64
        
        return "GRAFICO_CRIADO_COM_SUCESSO"
        
    except Exception as e:
        plt.close()
        return f"ERRO ao criar gráfico: {str(e)}"

# --- CONFIGURAÇÃO DO AGENTE ---

tools = [
    Tool(
        name="dataframe_query",
        func=query_dataframe,
        description="""Ferramenta para consultar o DataFrame 'doencas' já carregado.
       Use essa ferramenta para fazer consultas usando pandas no dataframe"""
    ),
    Tool(
        name="plot_chart",
        func=plot_chart,
        description="""Ferramenta para criar gráficos usando matplotlib/seaborn.
        Use 'df' para o DataFrame, 'plt' para matplotlib, 'sns' para seaborn.
        Sempre use plt.title(), plt.xlabel(), plt.ylabel() para rotular o gráfico.
        Exemplo: plt.bar(df['coluna'].value_counts().index, df['coluna'].value_counts().values)"""
    )
]

llm = ChatOpenAI(
    model="gpt-4.1-mini-2025-04-14",     #"gpt-4.1-mini-2025-04-14"
    openai_api_key=api_key,
    temperature=0.1,
)

prompt = ChatPromptTemplate.from_messages([
    ("system",f"""
Você tem acesso às funções dataframe_query e plot_chart.
SEMPRE que precisar executar qualquer operação no dataframe, invoque dataframe_query.
SEMPRE que precisar criar gráficos, invoque plot_chart.

Para gráficos:
- Use matplotlib (plt) ou seaborn (sns)
- Sempre adicione título, rótulos dos eixos
- Use plt.title(), plt.xlabel(), plt.ylabel()
- O DataFrame está disponível como 'df'

Para análise de performance de vendedores:
- Use 'Valor Total' para calcular vendas totais
- Use 'Nome Vendedor' para identificar vendedores
- Sempre agrupe os dados antes de plotar (ex: df.groupby('Nome Vendedor')['Valor Total'].sum())
- Limite a 10-15 vendedores no gráfico para melhor visualização

Você está trabalhando com um dataframe Pandas chamado `df, o nome das colunas são:
    
Ano, Mês, Tipo Nota, Nota Fiscal, Codigo, Descricao, Codigo.1, Estado, Nome, Loja, Cidade, Grupo de venda, Grupo Economico, Maior Compra, Media de Atraso, Status, Tipo Cliente, Tipo Pessoa, Tipo Pessoa Juridica, Vendedor, Nome Filial, Nome Operacao Dahuer, Operacao Dahuer, Tipo Produto, Unidade Medida, Grupo Produto, Nome Transportadora, Cod Gerente, Cod. Supervisor, Codigo Vendedor, Nome Gerente, Nome Supervisor, Nome Vendedor, Quantidade, Valor Unitario, Valor Total, Valor ICMS, Valor ICMS ST, Valor IPI, Valor Pis, Valor Cofins, Valor Desconto.
Aqui estão as primeiras linhas do dataframe para referência
     {df_exemplo}
     
IMPORTANTE:
- Só faça gráficos se for solicitado pelo usuário
- Sempre utilize o dataframe `df`.
- Sempre explique o resultado de forma clara e objetiva em português.
- Para gráficos, descreva o que o gráfico mostra após criá-lo.
- Não é necessário se oferecer para fazer gráficos
- Evite exibir dados brutos muito grandes - sempre agregue ou limite os resultados.

"""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

agent = create_openai_functions_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True,
    # ALTERAÇÃO: Habilitar o retorno dos passos intermediários
    return_intermediate_steps=True
)

# --- FUNÇÃO PRINCIPAL DE PROCESSAMENTO E LOG ---

def processar_pergunta(pergunta: str, chat_history: list = None) -> str:
    """
    Recebe uma pergunta, executa o agente, salva um log detalhado em JSON
    e retorna a resposta final para o usuário.
    """
    global ultimo_grafico_base64
    ultimo_grafico_base64 = None  # IMPORTANTE: Limpar antes de processar
    
    entrada = {"input": pergunta}
    if chat_history:
        entrada["chat_history"] = chat_history

    log_data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "pergunta_usuario": pergunta,
        "historico_usado": [
            {"type": msg.type, "content": msg.content} for msg in (chat_history or [])
        ],
    }
    
    resposta_para_usuario = ""

    try:
        # Usar o callback para capturar custos e tokens 
        with get_openai_callback():
            resposta_agente = agent_executor.invoke(entrada)

        # Formatar os passos intermediários para o log
        passos_formatados = []
        for step in resposta_agente.get("intermediate_steps", []):
            action, observation = step
            passos_formatados.append({
                "ferramenta": action.tool,
                "input_ferramenta": action.tool_input,
                "log_agente": action.log,
                "output_ferramenta": observation,
            })

        # Preencher o resto do log com dados de sucesso
        log_data.update({
            "status": "sucesso",
            "resposta_final_agente": resposta_agente.get("output"),
            "passos_intermediarios": passos_formatados,
        })
        resposta_para_usuario = resposta_agente.get("output")
        
        # Se foi criado um gráfico, adicionar o base64 na resposta
        if ultimo_grafico_base64:
            resposta_para_usuario += f"\nGRAFICO_BASE64:{ultimo_grafico_base64}"
            ultimo_grafico_base64 = None  # Limpar após usar

    except Exception as e:
        ultimo_grafico_base64 = None  # Limpar em caso de erro também
        # Guarda erro
        log_data.update({
            "status": "erro",
            "erro_mensagem": str(e),
            "erro_traceback": traceback.format_exc(),
        })
        resposta_para_usuario = "Ocorreu um erro ao processar sua solicitação."
        print(f"ERRO NO AGENTE: {e}") 

    finally:
        # Escrever o log 
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_data, ensure_ascii=False, indent=2) + "\n")

    return resposta_para_usuario