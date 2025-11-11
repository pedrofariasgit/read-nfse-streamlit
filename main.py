# main.py (substituir o conteúdo atual por este)
import os
import re
from pathlib import Path
from settings import PDF_DIR, OUTPUT_TXT
from extractor import extract_text  # sua função existente (pdfplumber)
from parser_router import select_parser
from writer import write_txt
from excel_writer import write_xlsx, write_csv_semicolon

# ---------- Helpers ----------
def is_valid_cnpj(s: str) -> bool:
    if not s:
        return False
    digits = re.sub(r"\D", "", s)
    return len(digits) == 14

def parse_result_status(parse_res: dict, require_serie: bool = True):
    """
    Retorna (is_valid: bool, missing: list)
    """
    missing = []
    if not isinstance(parse_res, dict):
        return False, ["PARSE_FAIL"]
    c = parse_res.get("cnpj_cpf", "") or ""
    n = str(parse_res.get("numero_documento", "") or "").strip()
    s = str(parse_res.get("serie", "") or "").strip()
    if not is_valid_cnpj(c):
        missing.append("CNPJ")
    if not n or not re.search(r"\d", n):
        missing.append("NÚMERO")
    if require_serie and not s:
        missing.append("SÉRIE")
    return (len(missing) == 0), missing

# ---------- Main ----------
def run():
    registros = []
    # lista arquivos no PDF_DIR (PDF_DIR já vem do settings como Path)
    for fname in sorted(os.listdir(PDF_DIR)):
        if not fname.lower().endswith(".pdf"):
            continue
        path = PDF_DIR / fname
        filename = fname

        # 1) extrair texto com pdfplumber via extractor.extract_text
        text = extract_text(str(path)) or ""
        # heurística simples: se pouco ou nada de texto, considerar imagem/scan
        if len(text.strip()) < 40:
            print(f"{filename}: IMAGEM")
            # opcional: pode salvar um registro com erro ou ignorar completamente
            continue

        # 2) selecionar parser e rodar
        parser_name, parse_fn = select_parser(text)
        try:
            parsed = parse_fn(text)  # parsed deve ser dict
        except Exception as e:
            print(f"{filename}: ERRO (parse exception)")
            # opcional: log de exceção
            # import traceback; traceback.print_exc()
            continue

        # 3) validar campos essenciais
        ok, missing = parse_result_status(parsed, require_serie=True)
        if ok:
            print(f"{filename}: OK")
        else:
            print(f"{filename}: ERRO ({', '.join(missing)})")

        # 4) armazenar o parsed (mantive o comportamento original)
        registros.append(parsed)

    # após processar todos, gravar outputs (mesmo se alguns foram IMAGEM/ERRO)
    write_txt(registros, OUTPUT_TXT)
    xlsx_path = str(OUTPUT_TXT).replace(".txt", "_preview.xlsx")
    csv_path  = str(OUTPUT_TXT).replace(".txt", "_preview.csv")
    write_xlsx(registros, xlsx_path)
    write_csv_semicolon(registros, csv_path)

    print(f"Gerado TXT:   {OUTPUT_TXT}")
    print(f"Gerado XLSX:  {xlsx_path}")
    print(f"Gerado CSV ;: {csv_path}")

if __name__ == "__main__":
    run()
