import pdfplumber
from pathlib import Path

# Caminho do PDF de teste
PDF_FILE = Path(r"C:\Pedro\Python\Read_NFSe_txt\PDF\cwb_pdfs\NFSe_Curitiba.pdf")

def extract_text(pdf_path: str) -> str:
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            texts.append(t)
    return "\n".join(texts).strip()

if __name__ == "__main__":
    text = extract_text(PDF_FILE)
    print(text)   # Mostra tudo no console
    
    # opcional: salvar em arquivo para analisar melhor
    with open("saida_bruta.txt", "w", encoding="utf-8") as f:
        f.write(text)

# extractor.py (adicionar)
from io import BytesIO
import pdfplumber

def extract_text_bytes(file_bytes: bytes) -> str:
    texts = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            texts.append(t)
    return "\n".join(texts).strip()
