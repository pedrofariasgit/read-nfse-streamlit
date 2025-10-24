# excel_writer.py
from datetime import datetime
import pandas as pd
from settings import BLANK_PARTY_FIELDS  # ← adiciona o flag

# Cabeçalho EXATO do Excel do Domínio (28 colunas)
DOMINIO_COLUMNS = [
    "CPF/CNPJ","Razão Social","UF","Município","Endereço","Número Documento","Série","Data",
    "Situação (0- Regular / 2- Cancelada)","Acumulador","CFPS","Valor Serviços","Valor Descontos",
    "Valor Dedução","Valor Contábil","Base de Calculo","Alíquota ISS","Valor ISS Normal",
    "Valor ISS Retido","Valor IRRF","Valor PIS","Valor COFINS","Valor CSLL","Valo CRF",
    "Valor INSS","Código do Item","Quantidade","Valor Unitário"
]

def br_money(v):
    s = str(v or "").strip()
    if not s:
        return "0,00"
    s = s.replace(".", "").replace(",", ".")
    try:
        num = float(s)
    except ValueError:
        num = 0.0
    inteiro, dec = f"{num:.2f}".split(".")
    return f"{inteiro},{dec}"

def br_date(s):
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return s  # deixa como veio se não couber

def record_to_row(n: dict) -> list:
    # aplica o flag: se BLANK_PARTY_FIELDS for True, deixa campos em branco
    razao_social = "" if BLANK_PARTY_FIELDS else n.get("razao_social","")
    uf = "" if BLANK_PARTY_FIELDS else n.get("uf","")
    municipio = "" if BLANK_PARTY_FIELDS else n.get("municipio","")
    endereco = "" if BLANK_PARTY_FIELDS else n.get("endereco","")

    # mapeia o dict padronizado -> ordem do Excel
    return [
        n.get("cnpj_cpf",""),
        razao_social,
        uf,
        municipio,
        endereco,
        str(n.get("numero_documento","")).strip(),
        str(n.get("serie","")).strip(),
        br_date(n.get("data")),
        str(n.get("situacao","0")).strip(),
        str(n.get("acumulador","")).strip(),
        str(n.get("cfps","")).strip(),
        br_money(n.get("valor_servicos")),
        br_money(n.get("valor_descontos")),
        br_money(n.get("valor_deducao")),
        br_money(n.get("valor_contabil")),
        br_money(n.get("base_calculo")),
        br_money(n.get("aliquota_iss")),
        br_money(n.get("valor_iss_normal")),
        br_money(n.get("valor_iss_retido")),
        br_money(n.get("valor_irrf")),
        br_money(n.get("valor_pis")),
        br_money(n.get("valor_cofins")),
        br_money(n.get("valor_csll")),
        br_money(n.get("valor_crf")),
        br_money(n.get("valor_inss")),
        n.get("codigo_item","") or "",
        (str(n.get("quantidade","")).replace(".", ",") if n.get("quantidade") not in (None,"") else ""),
        (str(n.get("valor_unitario","")).replace(".", ",") if n.get("valor_unitario") not in (None,"") else ""),
    ]

def write_xlsx(registros: list, xlsx_path: str):
    rows = [record_to_row(r) for r in registros]
    df = pd.DataFrame(rows, columns=DOMINIO_COLUMNS)
    # mantém tudo como texto (não perde zeros nem vírgulas)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Notas")

def write_csv_semicolon(registros: list, csv_path: str):
    rows = [record_to_row(r) for r in registros]
    df = pd.DataFrame(rows, columns=DOMINIO_COLUMNS)
    df.to_csv(csv_path, index=False, sep=";", encoding="utf-8-sig")
