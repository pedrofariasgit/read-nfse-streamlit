from settings import FILE_ENCODING, LINE_ENDING

def _fmt_money(v):
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

def _fmt_date(s):
    from datetime import datetime
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return s

def build_record(n: dict) -> str:
    campos = [
        n.get("cnpj_cpf",""),
        n.get("razao_social",""),
        n.get("uf",""),
        n.get("municipio",""),
        n.get("endereco",""),
        str(n.get("numero_documento","")).strip(),
        str(n.get("serie","")).strip(),
        _fmt_date(n.get("data")),
        str(n.get("situacao","0")).strip(),
        str(n.get("acumulador","")).strip(),
        str(n.get("cfps","")).strip(),
        _fmt_money(n.get("valor_servicos")),
        _fmt_money(n.get("valor_descontos")),
        _fmt_money(n.get("valor_deducao")),
        _fmt_money(n.get("valor_contabil")),
        _fmt_money(n.get("base_calculo")),
        _fmt_money(n.get("aliquota_iss")),
        _fmt_money(n.get("valor_iss_normal")),
        _fmt_money(n.get("valor_iss_retido")),
        _fmt_money(n.get("valor_irrf")),
        _fmt_money(n.get("valor_pis")),
        _fmt_money(n.get("valor_cofins")),
        _fmt_money(n.get("valor_csll")),
        _fmt_money(n.get("valor_crf")),
        _fmt_money(n.get("valor_inss")),
        n.get("codigo_item","") or "",
        (str(n.get("quantidade","")).replace(".", ",") if n.get("quantidade") not in (None,"") else ""),
        (str(n.get("valor_unitario","")).replace(".", ",") if n.get("valor_unitario") not in (None,"") else ""),
    ]
    campos += [""] * (28 - len(campos))
    return ";".join(campos) + LINE_ENDING

def write_txt(registros, path):
    with open(path, "w", encoding=FILE_ENCODING, newline="") as f:
        for r in registros:
            f.write(build_record(r))
