import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import sys
import subprocess
import os
import tempfile
from fpdf import FPDF

def processar_ensaio(dados_curva, w0, t0, L0, wf, tf, Lf):
    A0 = w0 * t0
    Af = wf * tf

    alongamento_pct = ((Lf - L0) / L0) * 100
    estriccao_pct = ((A0 - Af) / A0) * 100

    carga_max_n = 0.0
    desloc_max = 0.0
    
    historico_tensoes = []
    historico_deformacoes = []

    for carga_kn, desloc_mm in dados_curva:
        carga_n = carga_kn * 1000
        tensao_n_mm2 = carga_n / A0
        deformacao_pct = (desloc_mm / L0) * 100
        
        historico_tensoes.append(tensao_n_mm2)
        historico_deformacoes.append(deformacao_pct)

        if carga_n > carga_max_n:
            carga_max_n = carga_n
        if desloc_mm > desloc_max:
            desloc_max = desloc_mm

    sigma_max = carga_max_n / A0

    tensao_escoamento = 0.0
    deformacao_escoamento = 0.0
    if len(historico_tensoes) > 5:
        delta_sigma = historico_tensoes[5] - historico_tensoes[1]
        delta_eps = (historico_deformacoes[5] - historico_deformacoes[1]) / 100
        E = delta_sigma / delta_eps if delta_eps != 0 else 0

        for eps_pct, sigma in zip(historico_deformacoes, historico_tensoes):
            eps_abs = eps_pct / 100
            sigma_reta = E * (eps_abs - 0.002) 
            if sigma_reta >= sigma and eps_abs > 0.002:
                tensao_escoamento = sigma
                deformacao_escoamento = eps_pct
                break
                
    if tensao_escoamento == 0.0:
        tensao_escoamento = sigma_max 
        deformacao_escoamento = historico_deformacoes[historico_tensoes.index(sigma_max)]

    carga_escoamento_n = tensao_escoamento * A0
    razao_elastica = tensao_escoamento / sigma_max if sigma_max > 0 else 0

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(historico_deformacoes, historico_tensoes, color='b', linewidth=2, label='Curva de Tração')
    
    idx_max = historico_tensoes.index(sigma_max)
    ax.scatter(historico_deformacoes[idx_max], sigma_max, color='red', zorder=5, 
               label=f'Tensão Máxima ({sigma_max:.1f} N/mm²)')
    ax.scatter(deformacao_escoamento, tensao_escoamento, color='orange', zorder=5, 
               label=f'Escoamento 0.2% ({tensao_escoamento:.1f} N/mm²)')

    ax.set_title('Curva Tensão-Deformação de Engenharia', fontsize=14, fontweight='bold')
    ax.set_xlabel('Deformação (%)', fontsize=12)
    ax.set_ylabel('Tensão (N/mm²)', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.legend(loc='lower right')
    fig.tight_layout()

    resultados = {
        "A0": A0, "Af": Af,
        "carga_max_n": carga_max_n,
        "carga_escoamento_n": carga_escoamento_n,
        "sigma_max": sigma_max,
        "tensao_escoamento": tensao_escoamento,
        "razao_elastica": razao_elastica,
        "desloc_max": desloc_max,
        "alongamento_pct": alongamento_pct,
        "estriccao_pct": estriccao_pct
    }
    
    return resultados, fig


def gerar_relatorio_pdf(resultados, w0, t0, L0, wf, tf, Lf, fig):
    """Gera um PDF com os resultados e o gráfico, retornando os bytes do arquivo."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Titulo
    pdf.cell(0, 10, txt="Relatorio de Ensaio de Tracao (ASTM E8M)", ln=True, align='C')
    pdf.ln(5)
    
    # Secao de Geometria
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt="1. Geometria do Corpo de Prova", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"Inicial: Largura (w0) = {w0:.2f} mm | Espessura (t0) = {t0:.2f} mm | L0 = {L0:.2f} mm", ln=True)
    pdf.cell(0, 6, txt=f"Final: Largura (wf) = {wf:.2f} mm | Espessura (tf) = {tf:.2f} mm | Lf = {Lf:.2f} mm", ln=True)
    pdf.ln(5)
    
    # Secao de Propriedades
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt="2. Propriedades Mecanicas", ln=True)
    pdf.set_font("Arial", '', 11)
    
    # Lista de propriedades SEM ACENTOS para evitar erros no FPDF
    propriedades = [
        ("Area Inicial (A0)", f"{resultados['A0']:.2f}", "mm2"),
        ("Carga de Escoamento (Fe)", f"{resultados['carga_escoamento_n']:.1f}", "N"),
        ("Carga Maxima (Fmax)", f"{resultados['carga_max_n']:.1f}", "N"),
        ("Tensao de Escoamento (0,2%)", f"{resultados['tensao_escoamento']:.1f}", "MPa"),
        ("Tensao Maxima (UTS)", f"{resultados['sigma_max']:.1f}", "MPa"),
        ("Razao Elastica", f"{resultados['razao_elastica']:.2f}", "-"),
        ("Alongamento Final (EL)", f"{resultados['alongamento_pct']:.1f}", "%"),
        ("Estriccao / Reducao de Area (RA)", f"{resultados['estriccao_pct']:.1f}", "%")
    ]
    
    # Criando a tabela no PDF
    for prop, valor, unid in propriedades:
        pdf.cell(85, 8, txt=prop, border=1)
        pdf.cell(40, 8, txt=valor, border=1, align='C')
        pdf.cell(40, 8, txt=unid, border=1, align='C', ln=True)
        
    pdf.ln(5)
    
    # Secao do Grafico
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt="3. Curva Tensao-Deformacao", ln=True)
    
    # Salva a figura temporariamente para inserir no PDF
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
        fig.savefig(tmp_img.name, format="png", bbox_inches="tight")
        pdf.image(tmp_img.name, x=10, w=190)
    
    # Salva o PDF e lê em formato de bytes para o Streamlit
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        pdf.output(tmp_pdf.name)
        with open(tmp_pdf.name, "rb") as f:
            pdf_bytes = f.read()
            
    return pdf_bytes


# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Análise de Ensaio de Tração", layout="wide")

st.title("📈 Análise de Ensaio de Tração Retangular (ASTM E8M)")

st.sidebar.header("Parâmetros Iniciais e Finais")
w0 = st.sidebar.number_input("Largura Inicial - w0 (mm)", value=6.00, step=0.01)
t0 = st.sidebar.number_input("Espessura Inicial - t0 (mm)", value=3.00, step=0.01)
L0 = st.sidebar.number_input("Comprimento Útil Inicial - L0 (mm)", value=37.10, step=0.10)
st.sidebar.divider()
wf = st.sidebar.number_input("Largura Final - wf (mm)", value=5.60, step=0.01)
tf = st.sidebar.number_input("Espessura Final - tf (mm)", value=2.70, step=0.01)
Lf = st.sidebar.number_input("Comprimento Útil Final - Lf (mm)", value=38.20, step=0.10)

col_input, col_btn = st.columns([2, 1])

with col_input:
    st.subheader("Dados Brutos")
    dados_input = st.text_area(
        "Cole as colunas de Carga (kN) e Deslocamento (mm) separadas por espaço ou tabulação:",
        value="0.264  0.004\n0.613  0.010\n0.932  0.016\n1.251  0.022\n1.566  0.027", 
        height=200
    )

with col_btn:
    st.write("") 
    st.write("") 
    processar = st.button("Processar Ensaio", type="primary", use_container_width=True)

st.divider()

if processar and dados_input:
    dados_ensaio = []
    for linha in dados_input.strip().split("\n"):
        valores = linha.split()
        if len(valores) == 2:
            try:
                dados_ensaio.append((float(valores[0]), float(valores[1])))
            except ValueError:
                continue
    
    if len(dados_ensaio) > 0:
        resultados, fig = processar_ensaio(dados_ensaio, w0, t0, L0, wf, tf, Lf)
        
        col_grafico, col_res1, col_res2 = st.columns([2, 1, 1])
        
        with col_grafico:
            st.pyplot(fig)
            
        with col_res1:
            st.subheader("Resultados Gerais")
            st.metric("Área Inicial (A0)", f"{resultados['A0']:.2f} mm²")
            st.metric("Carga Máxima", f"{resultados['carga_max_n']:.1f} N")
            st.metric("Tensão Máxima (UTS)", f"{resultados['sigma_max']:.1f} N/mm²")
            
        with col_res2:
            st.subheader("Escoamento e Fratura")
            st.metric("Carga Escoamento", f"{resultados['carga_escoamento_n']:.1f} N")
            st.metric("Tensão Escoamento", f"{resultados['tensao_escoamento']:.1f} N/mm²")
            st.metric("Razão Elástica", f"{resultados['razao_elastica']:.2f}")
            st.metric("Estricção (RA)", f"{resultados['estriccao_pct']:.1f} %")
            
        st.subheader("📋 Tabela Resumo")
        
        tabela_resultados = pd.DataFrame({
            "Propriedade Analisada": [
                "Área Inicial (A0)", 
                "Carga de Escoamento (Fe)",
                "Carga Máxima (Fmax)", 
                "Tensão de Escoamento (0,2%)", 
                "Tensão Máxima (UTS)", 
                "Razão Elástica", 
                "Alongamento Final (EL)",
                "Estricção / Redução de Área (RA)"
            ],
            "Valor Obtido": [
                f"{resultados['A0']:.2f}", 
                f"{resultados['carga_escoamento_n']:.1f}",
                f"{resultados['carga_max_n']:.1f}", 
                f"{resultados['tensao_escoamento']:.1f}", 
                f"{resultados['sigma_max']:.1f}", 
                f"{resultados['razao_elastica']:.2f}", 
                f"{resultados['alongamento_pct']:.1f}",
                f"{resultados['estriccao_pct']:.1f}"
            ],
            "Unidade de Medida": ["mm²", "N", "N", "N/mm²", "N/mm²", "-", "%", "%"]
        })
        
        st.table(tabela_resultados)
        
        # --- GERAÇÃO E BOTÃO DO PDF ---
        pdf_bytes = gerar_relatorio_pdf(resultados, w0, t0, L0, wf, tf, Lf, fig)
        
        st.markdown("---")
        st.subheader("📥 Exportar Resultados")
        st.download_button(
            label="📄 Baixar Relatório em PDF",
            data=pdf_bytes,
            file_name="Relatorio_Tracao.pdf",
            mime="application/pdf",
            type="primary"
        )
            
    else:
        st.error("Formato de dados inválido. Certifique-se de usar números separados por espaço.")

# --- EXECUÇÃO SEGURA PELO PLAY DO VS CODE ---
if __name__ == "__main__":
    if os.environ.get("STREAMLIT_RODANDO") != "true":
        os.environ["STREAMLIT_RODANDO"] = "true"
        subprocess.run([sys.executable, "-m", "streamlit", "run", sys.argv[0]])
        sys.exit()