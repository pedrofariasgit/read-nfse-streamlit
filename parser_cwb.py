import re
from dateutil import parser as dtp
from settings import DEFAULTS, FALLBACK_CLIENTE


def _first_line(s: str) -> str:
    s = (s or "").strip()
    return s.splitlines()[0].strip() if s else ""

def _m(rx, text, flags=re.I):
    m = re.search(rx, text, flags)
    return (m.group(1) or "").strip() if m else ""

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

def parse_cwb(text: str) -> dict:
    d = {}

    # ---------- DOCUMENTO (topo)
    d["numero_documento"] = _m(r"Nota\s*N[ºo]\s*([0-9]+)", text)
    d["serie"]            = _m(r"S[ée]rie\s*([A-Za-z0-9\-]+)", text)
    d["data"]             = _date_any(_m(r"emitido\s+em\s+([0-9]{2}/[0-9]{2}/[0-9]{4})", text))

    # ---------- ISOLAR BLOCO DO PRESTADOR
    # 1) Tenta pegar o trecho entre "PRESTADOR ..." e o próximo bloco ("TOMADOR", "DISCRIMINAÇÃO", etc.)
    m_prest = re.search(
        r"PRESTADOR(?:\s+DE\s+SERVI[ÇC]OS)?(.*?)(?:TOMADOR|DISCRIMINA[ÇC][AÃ]O|SERVI[ÇC]OS\s+PRESTADOS|VALOR\s+DOS\s+SERVI[ÇC]OS)",
        text, re.I | re.S
    )
    if m_prest:
        prest_bloco = m_prest.group(1)
    else:
        prest_bloco = ""

    # 2) Se não achou bloco formal, tenta fallback: "Recebi(emos) do Prestador: NOME ... CNPJ: 00.000.000/0000-00"
    if not prest_bloco:
        # Cria um bloco sintético só com os dados que conseguimos nessa linha
        nome_prest = _m(r"Recebi\(emos\)\s+do\s+Prestador\s*:\s*([^C\n\r]+)", text)  # antes de "CNPJ:"
        cnpj_prest = _m(r"Recebi\(emos\)\s+do\s+Prestador.*?CNPJ\s*:\s*([\d\.\-\/]{14,18})", text)
        prest_bloco = f"Razão Social: {nome_prest or ''}\nCNPJ: {cnpj_prest or ''}\n"

    # ---------- PRESTADOR: CNPJ / Razão Social / Endereço / Município / UF
    cnpj_prest  = _m(r"\bCNPJ\s*:\s*([\d\.\-\/]{14,18})", prest_bloco) \
              or _m(r"Recebi\(emos\)\s+do\s+Prestador.*?CNPJ\s*:\s*([\d\.\-\/]{14,18})", text)
    # Razão social: tenta no bloco; se vazio, pega da linha "Recebi(emos) do Prestador: ..."
    razao_prest = _first_line(_m(r"Raz[aã]o\s*Social\s*:\s*(.+)", prest_bloco)) \
              or _first_line(_m(r"Nome\s*:\s*(.+)", prest_bloco)) \
              or _first_line(_m(r"Recebi\(emos\)\s+do\s+Prestador\s*:\s*([^C\n\r]+)", text))


    end_prest   = _first_line(_m(r"Endere[cç]o\s*:\s*(.+)", prest_bloco))
    mun_line    = _m(r"Munic[ií]pio\s*:\s*(.+)", prest_bloco)
    mun_prest   = (mun_line.split("UF:")[0].strip() if mun_line else "")
    uf_prest    = _m(r"\bUF\s*:\s*([A-Z]{2})\b", prest_bloco)
    
    # Preenche os campos "CLIENTE" do layout com os dados do PRESTADOR
    d["cnpj_cpf"]     = cnpj_prest or FALLBACK_CLIENTE.get("cnpj_cpf","")
    d["razao_social"] = razao_prest or FALLBACK_CLIENTE.get("razao_social","")
    d["endereco"]     = end_prest or FALLBACK_CLIENTE.get("endereco","")
    d["municipio"]    = mun_prest or FALLBACK_CLIENTE.get("municipio","")
    d["uf"]           = uf_prest or FALLBACK_CLIENTE.get("uf","")


    # ---------- VALORES
    # ---------- VALORES (mapeando pares de linhas fixos por regex)
    lines = text.splitlines()

    # zera defaults
    d["valor_deducao"] = d["valor_descontos"] = d["base_calculo"] = "0,00"
    d["valor_iss_normal"] = d["valor_iss_retido"] = "0,00"
    d["valor_cofins"] = d["valor_pis"] = d["valor_csll"] = d["valor_irrf"] = d["valor_inss"] = "0,00"
    d["valor_servicos"] = d["aliquota_iss"] = "0,00"

    # 1) Bloco: "DEDUÇÕES DESCONTOS B. CÁLCULO ISS ISS RETIDO COFINS" -> linha seguinte tem:
    #    R$ <deducao>   R$ <desconto>   R$ <base>   R$ <iss>(<aliquota %>)   <SIM/NÃO>   R$ <cofins>
    for i, ln in enumerate(lines):
        if re.search(r"DEDU[CÇ][ÕO]ES\s+DESCONTOS\s+B\.\s*C[ÁA]LCULO\s+ISS\s+ISS\s+RETIDO\s+COFINS", ln, re.I):
            if i+1 < len(lines):
                val_line = lines[i+1]
                m = re.search(
                    r"R\$\s*([\d\.\,]+)\s+"      # 1 deduções
                    r"R\$\s*([\d\.\,]+)\s+"      # 2 descontos
                    r"R\$\s*([\d\.\,]+)\s+"      # 3 base cálculo
                    r"R\$\s*([\d\.\,]+)\s*\(\s*([\d\.\,]+)\s*%\s*\)\s+"  # 4 ISS valor, 5 alíquota
                    r"([A-ZÇÃÕ]+)\s+"            # 6 RETIDO (SIM/NÃO)
                    r"R\$\s*([\d\.\,]+)",        # 7 COFINS
                    val_line, re.I
                )
                if m:
                    ded, desc, base, iss_val, iss_pct, iss_ret, cofins = m.groups()
                    d["valor_deducao"]   = _money(ded)
                    d["valor_descontos"] = _money(desc)
                    d["base_calculo"]    = _money(base)
                    d["aliquota_iss"]    = _money(iss_pct)
                    # ISS normal x retido
                    if iss_ret.strip().upper().startswith("N"):   # NÃO
                        d["valor_iss_normal"] = _money(iss_val)
                        d["valor_iss_retido"] = "0,00"
                    else:  # SIM
                        d["valor_iss_normal"] = "0,00"
                        d["valor_iss_retido"] = _money(iss_val)
                    d["valor_cofins"]    = _money(cofins)
            break

    # 2) Bloco: "PIS CSLL IR INSS VALOR DOS SERVIÇOS" -> linha seguinte tem:
    #    R$ <pis>  R$ <csll>  R$ <ir>  R$ <inss>  R$ <valor_servicos>
    for i, ln in enumerate(lines):
        if re.search(r"\bPIS\s+CSLL\s+IR\s+INSS\s+VALOR\s+DOS\s+SERVI[ÇC]OS\b", ln, re.I):
            if i+1 < len(lines):
                val_line = lines[i+1]
                m = re.search(
                    r"R\$\s*([\d\.\,]+)\s+"   # 1 PIS
                    r"R\$\s*([\d\.\,]+)\s+"   # 2 CSLL
                    r"R\$\s*([\d\.\,]+)\s+"   # 3 IR
                    r"R\$\s*([\d\.\,]+)\s+"   # 4 INSS
                    r"R\$\s*([\d\.\,]+)",     # 5 VALOR DOS SERVIÇOS
                    val_line, re.I
                )
                if m:
                    pis, csll, ir, inss, vserv = m.groups()
                    d["valor_pis"]      = _money(pis)
                    d["valor_csll"]     = _money(csll)
                    d["valor_irrf"]     = _money(ir)
                    d["valor_inss"]     = _money(inss)
                    d["valor_servicos"] = _money(vserv)
            break


    # Valor contábil = serviços - descontos - dedução
    try:
        vs  = float(d["valor_servicos"].replace(".","").replace(",","."))
        vd  = float(d["valor_descontos"].replace(".","").replace(",","."))
        vdd = float(d["valor_deducao"].replace(".","").replace(",","."))
        d["valor_contabil"] = f"{(vs - vd - vdd):.2f}".replace(".", ",")
    except:
        d["valor_contabil"] = d["valor_servicos"]

    # ---------- Defaults Domínio
    d["situacao"]   = DEFAULTS["situacao"]
    d["acumulador"] = DEFAULTS["acumulador"]
    d["cfps"]       = DEFAULTS["cfps"]

    # ---------- Itens vazios
    d["codigo_item"]    = ""
    d["quantidade"]     = ""
    d["valor_unitario"] = ""

    return d

# --- AUTO-DETECÇÃO DE CIDADE (para o roteador) ---------------------
import re

def can_parse_cwb(text: str) -> bool:
    t = text.upper()
    # sinais bem característicos da NFS-e de Curitiba
    return (
        "PREFEITURA DE CURITIBA" in t
        or re.search(r"\bCURITIBA\s*\(PR\)", t)
        or "NFS-E - NOTA FISCAL DE SERVIÇOS ELETRÔNICA" in t and "CURITIBA" in t
    )

PARSER = {
    "name": "Curitiba (CWB)",
    "can_parse": can_parse_cwb,
    "parse": parse_cwb,
}