from pathlib import Path

# Caminhos (ajuste)
PDF_DIR = Path(r"C:\Pedro\Python\Read_NFSe_txt\PDF\cwb_pdfs")
OUTPUT_TXT = Path(r"C:\Pedro\Python\Read_NFSe_txt\PDF\saida\notas_cwb.txt")
BLANK_PARTY_FIELDS = True

# Arquivo TXT
FILE_ENCODING = "cp1252"
LINE_ENDING = "\r\n"

# Defaults do layout Domínio
DEFAULTS = {
    "situacao": "0",      # 0 regular
    "acumulador": "1",
    "cfps": "9101",       # pode ajustar
    "aliquota_iss": "0,00",  # será sobrescrita se encontrada
}

# Campos de tomador (cliente) quando não der pra extrair
FALLBACK_CLIENTE = {
    # Preencha se quiser amarrar a um cliente fixo quando o tomador não vier no PDF
    # "cnpj_cpf": "00.000.000/0000-00",
    # "razao_social": "Cliente Padrão",
    # "uf": "SP",
    # "municipio": "São Paulo",
    # "endereco": "Rua ...",
}
