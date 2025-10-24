import io
import streamlit as st
import pandas as pd

from extractor import extract_text_bytes
from parser_router import select_parser
from excel_writer import DOMINIO_COLUMNS, record_to_row

st.set_page_config(page_title="Importador NFS-e (Domínio)", layout="wide")

st.title("📥 Importador NFS-e → Planilha Domínio")
st.caption("Envie PDFs de diferentes prefeituras. O sistema detecta automaticamente o layout e gera um XLSX no padrão do Domínio.")

uploaded_files = st.file_uploader(
    "Selecione um ou mais PDFs de NFS-e",
    type=["pdf"],
    accept_multiple_files=True
)

processar = st.button("🔎 Processar PDFs")

def make_dataframe(registros: list) -> pd.DataFrame:
    rows = [record_to_row(r) for r in registros]
    return pd.DataFrame(rows, columns=DOMINIO_COLUMNS)

if processar:
    if not uploaded_files:
        st.warning("Envie pelo menos um PDF.")
        st.stop()

    registros = []
    logs = []

    with st.spinner("Lendo e extraindo dados..."):
        for f in uploaded_files:
            try:
                raw = f.read()
                text = extract_text_bytes(raw)
                parser_name, parser_fn = select_parser(text)
                parsed = parser_fn(text)
                parsed["origem_parser"] = parser_name
                registros.append(parsed)
                logs.append(f"{f.name}: OK ({parser_name})")
            except Exception as e:
                logs.append(f"{f.name}: ERRO - {e}")

    # Cria DataFrame no layout Domínio
    df = make_dataframe(registros)

    st.subheader("Pré-visualização (layout Domínio)")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Gera Excel em memória
    xlsx_buf = io.BytesIO()
    with pd.ExcelWriter(xlsx_buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Notas")
    xlsx_buf.seek(0)

    st.download_button(
        label="⬇️ Baixar XLSX (Domínio)",
        data=xlsx_buf,
        file_name="nfse_dominio.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.success("Processamento concluído!")
    if logs:
        st.caption("Arquivos processados:")
        for line in logs:
            st.text(line)

else:
    st.markdown("Faça upload de PDFs e clique em **Processar PDFs**.")
