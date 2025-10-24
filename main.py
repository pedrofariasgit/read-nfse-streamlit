import os
from settings import PDF_DIR, OUTPUT_TXT
from extractor import extract_text
from parser_cwb import parse_cwb
from writer import write_txt
from excel_writer import write_xlsx, write_csv_semicolon

def run():
    registros = []
    for fname in os.listdir(PDF_DIR):
        if not fname.lower().endswith(".pdf"):
            continue
        path = PDF_DIR / fname
        text = extract_text(str(path))
        parsed = parse_cwb(text)
        registros.append(parsed)

    # 1) TXT (automatização direta)
    write_txt(registros, OUTPUT_TXT)

    # 2) XLSX/CSV (plano B para conferência/colagem no Excel do Domínio)
    xlsx_path = str(OUTPUT_TXT).replace(".txt", "_preview.xlsx")
    csv_path  = str(OUTPUT_TXT).replace(".txt", "_preview.csv")
    write_xlsx(registros, xlsx_path)
    write_csv_semicolon(registros, csv_path)

    print(f"Gerado TXT:   {OUTPUT_TXT}")
    print(f"Gerado XLSX:  {xlsx_path}")
    print(f"Gerado CSV ;: {csv_path}")

if __name__ == "__main__":
    run()
