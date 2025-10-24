# parser_sp.py
import re
from dateutil import parser as dtp
from settings import DEFAULTS, FALLBACK_CLIENTE

def _m(rx, text, flags=re.I):
    m = re.search(rx, text, flags)
    return (m.group(1) or "").strip() if m else ""

def _first_line(s: str) -> str:
    s = (s or "").strip()
    return s.splitlines()[0].strip() if s else ""

def _money(s):
    s = (s or "").strip()
    if not s:
        return "0,00"
    s = s.replace(".", "").replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        v = 0.0
    return f"{v:.2f}".replace(".", ",")

def _date_any(s):
    s = (s or "").strip()
    if not s:
        return s
    try:
        d = dtp.parse(s, dayfirst=True, fuzzy=True)
        return d.strftime("%d/%m/%Y")
    except Exception:
        return s

def can_parse_sp(text: str) -> bool:
    t = text.upper()
    # marcadores comuns na Nota Paulistana
    return (
        "PREFEITURA DO MUNICÍPIO DE SÃO PAULO" in t
        or "PREFEITURA MUNICIPAL DE SÃO PAULO" in t
        or "NOTA FISCAL DE SERVIÇOS ELETRÔNICA" in t and "SÃO PAULO" in t
        or "NOTA PAULISTANA" in t
    )

def parse_sp(text: str) -> dict:
    d = {}

    # Documento
    d["numero_documento"] = _m(r"(?:N[oº]?\s*da\s*NFS-?e|N[oº]?\s*Nota|NFS-?e)\s*[:\-]?\s*([0-9]{1,10})", text)
    if not d["numero_documento"]:
        d["numero_documento"] = _m(r"\bNota\s*N[ºo]\s*([0-9]+)", text)
    d["serie"] = _m(r"S[ée]rie\s*[:\-]?\s*([A-Za-z0-9\-]+)", text)
    d["data"]  = _date_any(_m(r"(?:Data\s*da\s*Emiss[aã]o|emitid[ao]\s*em)\s*[:\-]?\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", text))

    # PRESTADOR (cliente no layout Domínio)
    # tenta bloco formal
    m_prest = re.search(
        r"PRESTADOR(?:\s+DE\s+SERVI[ÇC]OS)?(.*?)(?:TOMADOR|DISCRIMINA[ÇC][AÃ]O|DESCRI[ÇC][AÃ]O|VALOR\s+DOS\s+SERVI[ÇC]OS)",
        text, re.I | re.S
    )
    prest_bloco = m_prest.group(1) if m_prest else ""

    cnpj_prest  = _m(r"\bCNPJ\s*[:\-]?\s*([\d\.\-\/]{14,18})", prest_bloco) or _m(r"\bCNPJ\s*[:\-]?\s*([\d\.\-\/]{14,18})", text)
    razao_prest = _first_line(_m(r"Raz[aã]o\s*Social\s*[:\-]?\s*(.+)", prest_bloco)) or _first_line(_m(r"Nome\s*[:\-]?\s*(.+)", prest_bloco))
    if not razao_prest:
        # fallback: linhas “Prestador: NOME ... CNPJ: ...”
        razao_prest = _first_line(_m(r"Prestador\s*[:\-]?\s*([^C\n\r]+)", text))

    end_prest   = _first_line(_m(r"Endere[cç]o\s*[:\-]?\s*(.+)", prest_bloco)) or _first_line(_m(r"Endere[cç]o\s*[:\-]?\s*(.+)", text))
    mun_line    = _m(r"Munic[ií]pio\s*[:\-]?\s*(.+)", prest_bloco) or _m(r"Munic[ií]pio\s*[:\-]?\s*(.+)", text)
    mun_prest   = (mun_line.split("UF:")[0].strip() if mun_line else "")
    uf_prest    = _m(r"\bUF\s*[:\-]?\s*([A-Z]{2})\b", prest_bloco) or _m(r"\bUF\s*[:\-]?\s*([A-Z]{2})\b", text)

    d["cnpj_cpf"]     = cnpj_prest or FALLBACK_CLIENTE.get("cnpj_cpf","")
    d["razao_social"] = razao_prest or FALLBACK_CLIENTE.get("razao_social","")
    d["endereco"]     = end_prest or FALLBACK_CLIENTE.get("endereco","")
    d["municipio"]    = mun_prest or "São Paulo"
    d["uf"]           = uf_prest or "SP"

    # ---- Valores: procura rótulo → pega 1º R$ logo depois
    def find_money_after(label_rx: str, text: str, lookahead: int = 200) -> str:
        m = re.search(label_rx, text, re.I)
        if not m:
            return "0,00"
        sub = text[m.end(): m.end() + lookahead]
        m2 = re.search(r"R\$\s*([\d\.\,]+)", sub)
        return _money(m2.group(1)) if m2 else "0,00"

    def find_money_within(label_rx: str, text: str, window: int = 250):
        m = re.search(label_rx, text, re.I)
        if not m:
            return "0,00", "0,00"
        sub = text[m.end(): m.end() + window]
        m_val = re.search(r"R\$\s*([\d\.\,]+)", sub)
        m_pct = re.search(r"\(([\d\.\,]+)\s*%\)", sub)
        return (_money(m_val.group(1)) if m_val else "0,00", _money(m_pct.group(1)) if m_pct else "0,00")

    d["valor_deducao"]   = find_money_after(r"DEDU[CÇ][ÕO]ES?", text)
    d["valor_descontos"] = find_money_after(r"DESCONTOS?", text)
    d["base_calculo"]    = find_money_after(r"BASE\s+DE\s+C[ÁA]LCULO|B\.\s*C[ÁA]LCULO", text)

    iss_val, iss_pct     = find_money_within(r"\bISS\b", text)
    d["aliquota_iss"]    = iss_pct

    iss_ret_txt = (_m(r"ISS\s*RETIDO\s*[:\-]?\s*([A-ZÇÃÕ]+)", text) or "").upper()
    if iss_ret_txt.startswith("S"):
        d["valor_iss_retido"] = iss_val
        d["valor_iss_normal"] = "0,00"
    elif iss_ret_txt.startswith("N"):
        d["valor_iss_retido"] = "0,00"
        d["valor_iss_normal"] = iss_val
    else:
        d["valor_iss_retido"] = "0,00"; d["valor_iss_normal"] = "0,00"

    d["valor_cofins"] = find_money_after(r"COFINS?", text)
    d["valor_pis"]    = find_money_after(r"\bPIS\b", text)
    d["valor_csll"]   = find_money_after(r"\bCSLL\b", text)
    d["valor_irrf"]   = find_money_after(r"\bIRRF?\b|\bIMPOSTO\s+DE\s+RENDA\b", text)
    d["valor_inss"]   = find_money_after(r"\bINSS\b", text)
    d["valor_servicos"] = find_money_after(r"VALOR\s+DOS\s+SERVI[ÇC]OS|VALOR\s+TOTAL\s+DOS\s+SERVI[ÇC]OS", text)

    # Valor contábil
    try:
        vs  = float(d["valor_servicos"].replace(".","").replace(",","."))
        vd  = float(d["valor_descontos"].replace(".","").replace(",","."))
        vdd = float(d["valor_deducao"].replace(".","").replace(",","."))
        d["valor_contabil"] = f"{(vs - vd - vdd):.2f}".replace(".", ",")
    except:
        d["valor_contabil"] = d["valor_servicos"]

    # Defaults Domínio + Itens
    d["situacao"]   = DEFAULTS["situacao"]
    d["acumulador"] = DEFAULTS["acumulador"]
    d["cfps"]       = DEFAULTS["cfps"]
    d["codigo_item"] = ""; d["quantidade"] = ""; d["valor_unitario"] = ""

    return d

PARSER = {
    "name": "São Paulo (SP)",
    "can_parse": can_parse_sp,
    "parse": parse_sp,
}
