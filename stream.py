import streamlit as st
import base64
import re
#from io import BytesIO
from modelo import processar_pergunta

st.set_page_config(page_title="Chatbot com IA")
st.title("Chatbot com IA")
st.caption("Faça perguntas sobre o banco de dados")

# Adicionando a barra lateral
with st.sidebar:
    st.header("Bem-vindo ao Chatbot de Vendas!")
    st.markdown("""
    Este é o seu assistente inteligente para explorar os dados de vendas da nossa empresa.
    Sinta-se à vontade para fazer qualquer tipo de pergunta sobre:

    *   **Desempenho de vendas:** Quais são os melhores vendedores ? Quais são os produtos mais vendido ?
    *   **Gráficos:** Faça um gráfico com os produtos mais vendidos
    *   **Comparativos:** Como as vendas do mês de janeiro se comparam ao do mês de fevereiro?
    *   **E muito mais!**

    Além de responder às suas perguntas, este chatbot pode **gerar gráficos** para visualizar os dados de forma clara e intuitiva. Experimente pedir algo como: "Mostre um gráfico das vendas por mês".

    """)
    st.info("Dica: Quanto mais específica for sua pergunta, melhor será a resposta!")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "Como posso ajudar você?"}]
if "processing" not in st.session_state:
    st.session_state["processing"] = False

# Função para exibir uma mensagem
def corrigir_formatacao_moeda(texto):  
    # Corrige padrões como "R25,56" para "R$ 25,56"  
    texto = re.sub(r'R(\d+,\d+)', r'R$ \1', texto)  
    # Corrige padrões como "R 64,63" para "R$ 64,63"  
    texto = re.sub(r'R (\d+,\d+)', r'R$ \1', texto)  
    return texto  
  
# Modifique a função exibir_mensagem:  
def exibir_mensagem(content):  
    if "GRAFICO_BASE64:" in content:  
        partes = content.split("GRAFICO_BASE64:")  
        texto = partes[0].strip()  
          
        if texto:  
            texto_corrigido = corrigir_formatacao_moeda(texto)  
            st.write(texto_corrigido)  
          
        try:  
            base64_data = partes[1].strip()  
            img_data = base64.b64decode(base64_data)  
            st.image(img_data, use_container_width=True)  
        except Exception as e:  
            st.error(f"Erro ao exibir gráfico: {e}")  
    else:  
        content_corrigido = corrigir_formatacao_moeda(content)  
        st.write(content_corrigido)
# IMPORTANTE Exibe mensagens só se não tiver processando
if not st.session_state.processing:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            exibir_mensagem(msg["content"])

if st.session_state.processing:
    with st.spinner("Pensando..."):
        st.empty()

if prompt := st.chat_input("Digite sua pergunta..."):
    st.session_state.processing = True
    
    # Adicionar pergunta do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Processar resposta
    resposta = processar_pergunta(prompt)
    
    # Adicionar resposta ao histórico
    st.session_state.messages.append({"role": "assistant", "content": resposta})
    
    # Marcar como não processando
    st.session_state.processing = False
    
    # Forçar re-renderização
    st.rerun()