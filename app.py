import io
import re
import streamlit as st
import pandas as pd
from io import BytesIO
from PyPDF2 import PdfReader

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


# ---------- Helpers específicos ----------
def pdf_has_text_bytes(file_bytes: bytes, min_chars: int = 50) -> bool:
    """
    Detecta se o PDF (bytes) contém camada de texto pesquisável.
    Retorna True se acumulou ao menos `min_chars` caracteres de texto.
    """
    try:
        reader = PdfReader(BytesIO(file_bytes))
        total_chars = 0
        for page in reader.pages:
            txt = page.extract_text() or ""
            total_chars += len(txt.strip())
            if total_chars >= min_chars:
                return True
        return False
    except Exception:
        return False


def is_valid_cnpj(cnpj: str) -> bool:
    if not cnpj:
        return False
    digits = re.sub(r"\D", "", cnpj)
    return len(digits) == 14


def parse_result_status(res: dict, require_serie: bool = True):
    """
    Valida campos essenciais do parse.
    Retorna (ok: bool, missing: list)
    """
    missing = []
    if not isinstance(res, dict):
        return False, ["PARSE_FAIL"]
    cnpj = res.get("cnpj_cpf", "") or ""
    numero = str(res.get("numero_documento", "") or "").strip()
    serie = str(res.get("serie", "") or "").strip()
    if not is_valid_cnpj(cnpj):
        missing.append("CNPJ")
    if not numero or not re.search(r"\d", numero):
        missing.append("NÚMERO")
    if require_serie and not serie:
        missing.append("SÉRIE")
    return len(missing) == 0, missing


# ---------- Main UI flow ----------
if processar:
    if not uploaded_files:
        st.warning("Envie pelo menos um PDF.")
        st.stop()

    registros = []
    logs = []

    with st.spinner("Lendo e extraindo dados..."):
        for f in uploaded_files:
            try:
                raw = f.read()  # bytes
                # 1) se for PDF sem texto suficiente -> considerar IMAGEM/SCAN
                if not pdf_has_text_bytes(raw):
                    logs.append(f"{f.name}: IMAGEM")
                    continue

                # 2) extrai texto (sua função já usa pdfplumber internamente)
                text = extract_text_bytes(raw)
                parser_name, parser_fn = select_parser(text)

                # 3) rodar parser
                try:
                    parsed = parser_fn(text)
                except Exception as e:
                    logs.append(f"{f.name}: ERRO (parse exception) - {parser_name}")
                    # opcional: registrar traceback em logs detalhados
                    continue

                # marca origem
                parsed["origem_parser"] = parser_name

                # 4) validação e logs curtos
                ok, missing = parse_result_status(parsed, require_serie=True)
                if ok:
                    logs.append(f"{f.name}: OK")
                else:
                    # inclua parser_name no log de erro para facilitar triagem
                    logs.append(f"{f.name}: ERRO ({', '.join(missing)}) - {parser_name}")

                # 5) armazenar registro (mantive o comportamento anterior)
                registros.append(parsed)

            except Exception as e:
                # erro inesperado na leitura/fluxo
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
