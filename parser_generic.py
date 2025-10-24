# parser_generic.py
import re
from dateutil import parser as dtp
from settings import DEFAULTS, FALLBACK_CLIENTE
import unicodedata


# ----------------------- Helpers -----------------------

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
    except Exception:
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

# Rótulos tolerantes
LABELS_VALOR_SERVICOS = r"(VALOR\s+TOTAL\s+DOS\s+SERVI[ÇC]OS|VALOR\s+DOS\s+SERVI[ÇC]OS|VALOR\s+SERVI[ÇC]OS|VALOR\s+DO\s+SERVI[ÇC]O)"
LABELS_BASE_CALCULO   = r"(BASE\s+DE\s+C[ÁA]LCULO|B\.\s*C[ÁA]LCULO|BASE\s+C[ÁA]LCULO|BASE\s+CALCULO)"
LABELS_ISS            = r"\b(ISS|ISSQN)\b"
LABELS_ISS_RETIDO     = r"(ISS(?:QN)?\s*RETID[OA])"
LABELS_DEDUCOES       = r"(DEDU[CÇ][ÕO]ES?)"
LABELS_DESCONTOS      = r"(DESCONTOS?)"
LABELS_PIS            = r"\bPIS\b"
LABELS_COFINS         = r"COFINS?"
LABELS_CSLL           = r"\bCSLL\b"
LABELS_IR             = r"\bIRRF?\b|\bIMPOSTO\s+DE\s+RENDA\b"
LABELS_INSS           = r"\bINSS\b"

# Bloco do Prestador pode aparecer como Prestador/Emitente/Fornecedor
PRESTADOR_BLOCK       = r"(PRESTADOR|EMITENTE|FORNECEDOR)(?:\s+DE\s+SERVI[ÇC]OS)?"

def _find_money_after(label_rx: str, text: str, lookahead: int = 350) -> str:
    m = re.search(label_rx, text, re.I)
    if not m:
        return "0,00"
    sub = text[m.end(): m.end() + lookahead]
    m2 = re.search(r"(?:R\$)?\s*([\d\.\,]+)", sub)
    return _money(m2.group(1)) if m2 else "0,00"

def _find_money_within(label_rx: str, text: str, window: int = 400):
    m = re.search(label_rx, text, re.I)
    if not m:
        return "0,00", "0,00"
    sub = text[m.end(): m.end() + window]
    m_val = re.search(r"(?:R\$)?\s*([\d\.\,]+)", sub)
    m_pct = re.search(r"\(([\d\.\,]+)\s*%\)", sub)
    val = _money(m_val.group(1)) if m_val else "0,00"
    pct = _money(m_pct.group(1)) if m_pct else "0,00"
    return val, pct

def _extract_aliquota(text: str) -> str:
    m = re.search(r"Al[ií]quota\s*(?:do\s*ISS|%)\s*[:\(\)]?\s*([\d\.\,]+)", text, re.I)
    return _money(m.group(1)) if m else "0,00"

def _extract_retencao_inline(text: str, campo: str) -> str:
    rx = fr"{campo}\s*[:\-]?\s*\(?R\$?\)?\s*([\d\.\,]+)"
    m = re.search(rx, text, re.I)
    return _money(m.group(1)) if m else "0,00"

def _norm(s: str) -> str:
    s = s or ""
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    s = s.upper().replace("—", "-").replace("–", "-").replace("°", "O")
    return s

def _pick_first_number_token(s: str) -> str:
    if not s: return ""
    for tok in re.findall(r"[A-Z0-9./-]+", s):
        if not re.search(r"\d", tok):            # precisa ter dígito
            continue
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", tok):  # data
            continue
        if re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", tok):  # CNPJ
            continue
        if re.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}", tok):        # CPF
            continue
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{2})?", tok):   # dinheiro
            continue
        if tok in {"ELETR","ELETRONICA","NFSE","NFS-E","DOC"}:
            continue
        if 3 <= len(tok) <= 20:
            return tok
    return ""

def _slice_near(label_rx: str, text: str, window: int = 240) -> str:
    m = re.search(label_rx, text, re.I)
    if not m: return ""
    a = max(0, m.start() - window)
    b = min(len(text), m.end() + window)
    return text[a:b]

# ----------------------- Parser -----------------------

def parse_generic(text: str) -> dict:
    d = {}
    T = text
    U = text.upper()


    # ---------- Documento (cobre Eusébio, Curitiba, SJP + fallback por proximidade)
    def _clean(s):
        s = (s or "").strip()
        s = re.sub(r'^[\s:–—\-]+', '', s)
        s = re.sub(r'[\s:–—\-]+$', '', s)
        return s

    def _pick_first_number(s):
        if not s:
            return ""
        # pega primeiro token com dígitos (3 a 15), ignorando datas/CNPJ/CPF/valores
        for tok in re.findall(r"[A-Za-z0-9./\-]+", s):
            if not re.search(r"\d", tok):
                continue
            if re.fullmatch(r"\d{2}/\d{2}/\d{4}", tok):  # data
                continue
            if re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", tok):  # CNPJ
                continue
            if re.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}", tok):  # CPF
                continue
            if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{2})?", tok):  # dinheiro
                continue
            T0 = tok.upper()
            if T0 in {"ELETR", "ELETRONICA", "ELETRÔNICA", "DOC", "NFSE", "NFS-E"}:
                continue
            if 3 <= len(tok) <= 15:
                return tok
        return ""

    def _near(label_rx, text, window=140):
        m = re.search(label_rx, text, re.I)
        if not m:
            return ""
        a = max(0, m.start() - window)
        b = min(len(text), m.end() + window)
        return text[a:b]

    numero_documento = ""
    serie = ""

    # ---- Matches diretos mais flexíveis (acentos e hífens diferentes)
    padroes_numero = [
        r'Nota\s*N[ºo°]?\s*[:–—\-]?\s*([0-9]{1,15})',
        r'N[úu]mero\s+da\s+nota\s*[:–—\-]?\s*([0-9]{1,15})',
        r'N[úu]mero\s+da\s+NFS[–—\-\s]?e\s*[:–—\-]?\s*([0-9]{1,15})',
        r'NFS[–—\-\s]?e\s*[:–—\-]?\s*([0-9]{1,15})',
    ]
    for pat in padroes_numero:
        m = re.search(pat, T, flags=re.IGNORECASE)
        if m:
            cand = _clean(m.group(1))
            if re.search(r'\d', cand):
                numero_documento = cand
                break

    # ---- Série
    for pat in [r'(?:S[ÉE]RIE|SERIE)\s*[:–—\-]?\s*([A-Za-z0-9\-]+)']:
        m = re.search(pat, T, flags=re.IGNORECASE)
        if m:
            serie = _clean(m.group(1))
            break

    # ---- Fallback por proximidade do rótulo, caso o número ainda esteja vazio
    if not numero_documento:
        # Perto de "Nota", "Número da nota", "Número da NFS-e", "NFS-e"
        for label in [
            r'Nota\s*N[ºo°]?', r'N[úu]mero\s+da\s+nota', r'N[úu]mero\s+da\s+NFS[–—\-\s]?e', r'\bNFS[–—\-\s]?e\b'
        ]:
            bloco = _near(label, T, window=180)
            cand = _pick_first_number(bloco)
            if cand:
                numero_documento = cand
                break

    d["numero_documento"] = numero_documento
    d["serie"] = serie

    # --- Fallback universal (só roda se ainda faltou algo; não altera o que já deu certo)
    if not d["numero_documento"] or not d["serie"]:
        TN = _norm(T)

        # número da nota
        if not d["numero_documento"]:
            aliases = [
                r"NOTA\s*N[O0]?",          # NOTA Nº/NO
                r"NUMERO\s+DA\s+NOTA",
                r"NUMERO\s+DA\s+NFS-?E",
                r"\bNFS-?E\b",
            ]
            # 1) match direto label:valor
            for label in aliases:
                m = re.search(label + r"\s*[:\-]?\s*([A-Z0-9./-]{3,20})", TN, re.I)
                if m and re.search(r"\d", m.group(1)):
                    d["numero_documento"] = m.group(1).strip()
                    break
            # 2) proximidade
            if not d["numero_documento"]:
                for label in aliases:
                    bloco = _slice_near(label, TN, window=240)
                    cand = _pick_first_number_token(bloco)
                    if cand:
                        d["numero_documento"] = cand
                        break
            # 3) cabeçalho da 1ª página
            if not d["numero_documento"]:
                d["numero_documento"] = _pick_first_number_token(TN[:2000])

        # série (se houver)
        if not d["serie"]:
            mserie = re.search(r"\bSERIE\b\s*[:\-]?\s*([A-Z0-9-]{1,10})", TN, re.I)
            if mserie:
                d["serie"] = mserie.group(1).strip()


    # ---- Data (mantém sua lógica)
    d["data"]  = _date_any(
        _m(r"(?:Data\s*(?:da)?\s*Emiss[aã]o|emitid[ao]\s*em)\s*[:\-]?\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", T)
        or _m(r"([0-9]{2}/[0-9]{2}/[0-9]{4})", T)
    )



    # ---------- Prestador (mapeado para as colunas 'CLIENTE' do Domínio)
    # Tenta isolar bloco do prestador. Se não achar, usa o texto inteiro (fallback).
    m_prest = re.search(
        PRESTADOR_BLOCK + r"(.*?)(?:TOMADOR|DESTINAT[ÁA]RIO|DISCRIM|DESCRI|VALOR\s+DOS\s+SERVI)",
        T, re.I | re.S
    )
    prest_bloco = m_prest.group(1) if m_prest else T

    # heurística para achar a razão social sem pegar "de Serviços"
    def _guess_razao(prest_text: str, full_text: str) -> str:
        # 1) Padrões explícitos
        for rx in [
            r"Raz[aã]o\s*Social\s*(?:do\s*Prestador)?\s*[:\-]?\s*(.+)",
            r"Nome\s*(?:\/\s*Raz[aã]o\s*Social)?\s*(?:do\s*Prestador)?\s*[:\-]?\s*(.+)",
            r"Denomina[cç][aã]o\s*Social\s*[:\-]?\s*(.+)",
        ]:
            v = _m(rx, prest_text)
            if v:
                return _first_line(v)

        # 2) Linha imediatamente ANTES do CNPJ dentro do bloco (evita rótulos)
        mcn = re.search(r"\bCNPJ\s*[:\-]?\s*[\d\.\-\/]{14,18}", prest_text, re.I)
        context = prest_text[:mcn.start()] if mcn else prest_text
        lines = [ln.strip() for ln in context.splitlines() if ln.strip()]

        def is_label(s: str) -> bool:
            return bool(re.search(r"(PRESTADOR|EMITENTE|FORNECEDOR|SERVI[ÇC]OS|RAZ|NOME|CNPJ|ENDERE|MUNIC|UF|CEP|INSCRI)", s, re.I))

        for ln in reversed(lines):
            if not is_label(ln):
                return _first_line(ln)
        return ""

    # CNPJ sempre por rótulo
    cnpj_prest  = _m(r"\bCNPJ\s*[:\-]?\s*([\d\.\-\/]{14,18})", prest_bloco) or _m(r"\bCNPJ\s*[:\-]?\s*([\d\.\-\/]{14,18})", T)
    # Razão social robusta (evita pegar "de Serviços")
    razao_prest = _guess_razao(prest_bloco, T)

    # Endereço: apenas a 1ª linha após "Endereço:", sem puxar CEP/Município
    end_prest   = _m(r"Endere[cç]o\s*[:\-]?\s*([^\r\n]+)", prest_bloco) or _m(r"Endere[cç]o\s*[:\-]?\s*([^\r\n]+)", T)
    if end_prest:
        # corta qualquer coisa depois de "CEP", "Município", "UF"
        end_prest = re.split(r"\b(CEP|Munic[ií]pio|UF)\b", end_prest)[0].strip()

    # Município/UF: pode vir como "Município: CIDADE - UF" na mesma linha
    mun_line    = _m(r"Munic[ií]pio\s*[:\-]?\s*([^\r\n]+)", prest_bloco) or _m(r"Munic[ií]pio\s*[:\-]?\s*([^\r\n]+)", T)
    uf_prest    = _m(r"\bUF\s*[:\-]?\s*([A-Z]{2})\b", prest_bloco) or _m(r"\bUF\s*[:\-]?\s*([A-Z]{2})\b", T)

    municipio_prest = ""
    if mun_line:
        # remove trechos que não são parte do município
        mun_core = re.split(r"\b(Endere[cç]o|CEP|E-?MAIL|INSCRI[ÇC][AÃ]O|TOMADOR)\b", mun_line)[0].strip()
        # tenta extrair UF a partir de " - UF" (ex.: "SÃO JOSÉ DOS PINHAIS - PR")
        mhy = re.search(r"(.*?)[\s\-\/]+([A-Z]{2})\b", mun_core)
        if mhy:
            municipio_prest = mhy.group(1).strip()
            uf_prest = uf_prest or mhy.group(2).strip()
        else:
            municipio_prest = mun_core

    d["cnpj_cpf"]     = cnpj_prest or FALLBACK_CLIENTE.get("cnpj_cpf","")
    d["razao_social"] = razao_prest or FALLBACK_CLIENTE.get("razao_social","")
    d["endereco"]     = end_prest or FALLBACK_CLIENTE.get("endereco","")
    d["municipio"]    = (municipio_prest or FALLBACK_CLIENTE.get("municipio","")).strip()
    d["uf"]           = uf_prest or FALLBACK_CLIENTE.get("uf","")

    # ---------- Valores (label -> valor próximo)
    d["valor_deducao"]    = _find_money_after(LABELS_DEDUCOES, T)
    d["valor_descontos"]  = _find_money_after(LABELS_DESCONTOS, T)
    d["base_calculo"]     = _find_money_after(LABELS_BASE_CALCULO, T)

    iss_val, iss_pct      = _find_money_within(LABELS_ISS, T)
    d["aliquota_iss"]     = _extract_aliquota(T) if iss_pct == "0,00" else iss_pct
    d["valor_iss_normal"] = "0,00"
    d["valor_iss_retido"] = "0,00"

    # Alguns layouts trazem explicitamente "Valor do ISS"
    valor_iss_direct      = _find_money_after(r"(VALOR\s+DO\s+ISS|ISS\s*[:\-])", T)
    if valor_iss_direct != "0,00" and iss_val == "0,00":
        iss_val = valor_iss_direct

    # ISS retido SIM/NÃO (se não houver, assume normal)
    iss_ret_txt = (_m(LABELS_ISS_RETIDO + r"\s*[:\-]?\s*([A-ZÇÃÕ]+)", T) or "").upper()
    if iss_ret_txt.startswith("S"):
        d["valor_iss_retido"] = iss_val
    elif iss_ret_txt.startswith("N"):
        d["valor_iss_normal"] = iss_val
    else:
        d["valor_iss_normal"] = iss_val

    # Retenções inline (PIS/COFINS/IR/INSS/CSLL)
    d["valor_pis"]       = _extract_retencao_inline(T, "PIS")
    d["valor_cofins"]    = _extract_retencao_inline(T, "COFINS?")
    d["valor_irrf"]      = _extract_retencao_inline(T, "IR")
    d["valor_inss"]      = _extract_retencao_inline(T, "INSS")
    d["valor_csll"]      = _extract_retencao_inline(T, "CSLL")

    # Valor dos serviços – aceita várias grafias/posições
    d["valor_servicos"]  = _find_money_after(LABELS_VALOR_SERVICOS, T)
    if d["valor_servicos"] == "0,00":
        # Alguns layouts repetem totais no fim
        tail = T[-1200:]
        alt = _find_money_after(LABELS_VALOR_SERVICOS, tail)
        if alt != "0,00":
            d["valor_servicos"] = alt

    # Valor contábil = serviços - descontos - deduções
    try:
        vs  = float(d["valor_servicos"].replace(".","").replace(",","."))
        vd  = float(d["valor_descontos"].replace(".","").replace(",","."))
        vdd = float(d["valor_deducao"].replace(".","").replace(",","."))
        d["valor_contabil"] = f"{(vs - vd - vdd):.2f}".replace(".", ",")
    except Exception:
        d["valor_contabil"] = d["valor_servicos"]

    # ---------- Defaults Domínio
    d["situacao"]   = DEFAULTS["situacao"]
    d["acumulador"] = DEFAULTS["acumulador"]
    d["cfps"]       = DEFAULTS["cfps"]

    # ---------- Itens (vazios para não importar)
    d["codigo_item"]    = ""
    d["quantidade"]     = ""
    d["valor_unitario"] = ""

    return d

# ----------------------- Registro no roteador -----------------------

def can_parse_generic(text: str) -> bool:
    return True

PARSER = {
    "name": "Genérico",
    "can_parse": can_parse_generic,
    "parse": parse_generic,
}
