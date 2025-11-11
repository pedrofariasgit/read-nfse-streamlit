# parser_nfse_padrao.py (versão com extra debug e regras mais fortes)
import re
import unicodedata
import traceback
from dateutil import parser as dtp
from typing import Tuple, Optional

try:
    from settings import DEFAULTS, FALLBACK_CLIENTE
except Exception:
    DEFAULTS = {"situacao": "0", "acumulador": "1", "cfps": "9101"}
    FALLBACK_CLIENTE = {}

# ---------------- helpers ----------------
def _norm(s: str) -> str:
    s = s or ""
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    return s.upper()

def _m(rx, text, flags=re.I) -> str:
    m = re.search(rx, text, flags)
    return (m.group(1) or "").strip() if m else ""

def _date_any(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    try:
        d = dtp.parse(s, dayfirst=True, fuzzy=True)
        return d.strftime("%d/%m/%Y")
    except Exception:
        return s

def _money_from_sub(text: str) -> str:
    m = re.search(r"(?:R\$)?\s*([\d\.\,]+)", text)
    if not m:
        return "0,00"
    s = m.group(1).strip()
    s = s.replace(".", "").replace(",", ".")
    try:
        v = float(s)
    except:
        return "0,00"
    return f"{v:.2f}".replace(".", ",")

def _find_money_after(label_rx: str, text: str, lookahead: int = 400) -> str:
    m = re.search(label_rx, text, re.I)
    if not m:
        return "0,00"
    sub = text[m.end(): m.end() + lookahead]
    return _money_from_sub(sub)

# ---------------- CNPJ helpers ----------------
def _format_cnpj(digs: str) -> str:
    # recebe somente dígitos (14) e retorna formatado 00.000.000/0000-00
    if not digs or len(digs) != 14 or not digs.isdigit():
        return digs
    return f"{digs[0:2]}.{digs[2:5]}.{digs[5:8]}/{digs[8:12]}-{digs[12:14]}"

def _only_digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def _clean_razao_from_header(text: str) -> str:
    """
    Heurística agressiva: se houver CNPJ colado com o nome, extrai o texto logo após o CNPJ.
    Retorna nome em Title Case (heurístico).
    """
    header = (text or "")[:2000]

    # 1) procura CNPJ no formato com ou sem pontuação (14 dígitos agrupados)
    m_cnpj = re.search(r"(\d{2}[.\-]?\d{3}[.\-]?\d{3}[./]?\d{4}[-]?\d{2})", header)
    if m_cnpj:
        pos = m_cnpj.end()
        tail = header[pos: pos + 220]

        # remove dígitos/pontuação que possam preceder o nome e qualquer "label-like" residual
        # preserve letras (incl. acentos) e espaços
        candidate = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ\s]", "", tail)

        # normaliza espaços e corta ruídos longos
        candidate = re.sub(r"\s{2,}", " ", candidate).strip()
        if not candidate:
            # se não restou nada, cai fora
            return ""

        # pega até 6 primeiras palavras (normalmente o nome empresarial cabe nisso)
        words = candidate.split()
        # filtra palavras muito curtas que provavelmente sejam rótulos (ex: 'DO', 'DA' são comuns mas aceitáveis)
        # monta nome e title-caseia para ficar legível
        name = " ".join(words[:6]).strip()
        # se name ficar muito curto ou for algo como "DOSERVICO" (sem vogais reais), fallback
        if len(name) < 3:
            return ""
        # Aplica title() para legibilidade; preserve maiúsculas se preferir, remova .title() então
        return name.title()

    # 2) fallback anterior: procurar rótulos 'NOME / NOMEEMPRESARIAL' ou 'Nome'
    hn = _norm(header)
    m_label = re.search(r"NOME\s*\/\s*NOMEEMPRESARIAL\b", hn)
    if m_label:
        pos = m_label.end()
        candidate = header[pos: pos + 260].strip()
        candidate = re.sub(r"[\d\.\-\/]+", "", candidate)
        candidate = re.sub(r"[\w\.-]+@[\w\.-]+", "", candidate)
        candidate = re.sub(r"\s{2,}", " ", candidate).strip()
        return candidate.title() if candidate else ""

    m2 = re.search(r"Nome\s*[:\-]?\s*([^\n\r]{3,200})", header, re.I)
    if m2:
        candidate = m2.group(1).strip()
        candidate = re.sub(r"[\d\.\-\/]+", "", candidate)
        candidate = re.sub(r"[\w\.-]+@[\w\.-]+", "", candidate)
        candidate = re.sub(r"\s{2,}", " ", candidate).strip()
        return candidate.title() if candidate else ""

    return ""


# substitua _find_cnpj pelo bloco abaixo
def _find_cnpj(text: str) -> str:
    # usa versão normalizada para localizar rótulos com acentos/espacos bagunçados
    header = text[:1500]
    hn = _norm(header)

    # 1) procura label "CNPJ" (ou variantes) no header normalizado e pega janela logo depois
    m_label = re.search(r"\bCNPJ(?:\/CPF|\/NIF)?\b", hn, re.I)
    if m_label:
        # calcula janela em posições do texto original: m_label.end() em hn corresponde aproximadamente
        # à posição m_label.end() no header original, porque _norm só remove acentos, não altera comprimento.
        pos = m_label.end()
        window = header[pos: pos + 220]
        # procura sequência com pontuação ou grupos de dígitos dentro dessa janela
        v = re.search(r"([\d\.\-/]{5,40})", window)
        if v:
            digs = _only_digits(v.group(1))
            if len(digs) == 14:
                return _format_cnpj(digs)
            if len(digs) == 11:
                return digs

        # se não achou com pontuação, tente juntar grupos de dígitos na janela
        groups = re.findall(r"\d+", window)
        total = ""
        for g in groups:
            total += g
            if len(total) == 14:
                return _format_cnpj(total)
            if len(total) > 14:
                break

    # 2) padrões explícitos no texto todo (com pontuação)
    for rx in [r"\bCNPJ\s*[:\-]?\s*([\d\.\-/]{5,40})", r"EMITENTE[\s\S]{0,160}CNPJ\s*[:\-]?\s*([\d\.\-/]{5,40})", r"PRESTADOR[\s\S]{0,160}CNPJ\s*[:\-]?\s*([\d\.\-/]{5,40})"]:
        v = _m(rx, text)
        if v:
            digs = _only_digits(v)
            if len(digs) == 14:
                return _format_cnpj(digs)
            if len(digs) == 11:
                return digs

    # 3) fallback: reconstruir juntando grupos no header MAS ignorando o primeiro grande QR se ele aparece antes do label
    # pega todos os matches de dígitos no header, mas prioriza os que aparecem *depois* do label 'CNPJ' se houver
    all_matches = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\d+", header)]
    # se existe label, considere apenas matches após label; se não, considere todos
    if m_label:
        start_pos = m_label.end()
        all_matches = [t for t in all_matches if t[1] >= start_pos]

    groups = [g[0] for g in all_matches]
    for i in range(len(groups)):
        total = groups[i]
        for j in range(i+1, min(i+6, len(groups))):
            total += groups[j]
            if len(total) == 14:
                return _format_cnpj(total)
            if len(total) > 14:
                break

    # 4) por último, procurar qualquer 14 contínuo no texto (menos ideal)
    m14 = re.search(r"\d{14}", text)
    if m14:
        return _format_cnpj(m14.group(0))

    # 5) fallback settings
    return FALLBACK_CLIENTE.get("cnpj_cpf", "")



# substitua _find_numero_serie pelo bloco abaixo
def _find_numero_serie(text: str) -> Tuple[str, str]:
    header = text[:1500]
    hn = _norm(header)

    # 0) procurar label explícito "NUMERO DA NFS-E" (normalizado) e capturar o número que vem depois
    m = re.search(r"NUMER?O\s*(?:DA\s*)?NFS[- ]?E\b", hn, re.I)
    if m:
        # pega janela logo depois no texto original
        pos = m.end()
        window = header[pos: pos + 200]
        v = re.search(r"\b([0-9]{1,6})\b", window)
        if v:
            numero = v.group(1)
            # tentar achar série próxima (após ou antes)
            s_after = re.search(r"\bS(?:ERIE|[ÉE]RIE)\s*[:\-]?\s*([0-9A-Z]{1,6})\b", hn[pos: pos + 300])
            if s_after:
                return numero, s_after.group(1)
            s_before = re.search(r"\bS(?:ERIE|[ÉE]RIE)\s*[:\-]?\s*([0-9A-Z]{1,6})\b", hn[max(0, pos-300): pos])
            if s_before:
                return numero, s_before.group(1)
            return numero, ""

    # 1) procurar "Nº 38" (tolerante) no header normalizado
    m_simple = re.search(r"\bN(?:º|\.|UMERO|UM)\s*[:\-]?\s*([0-9]{1,6})\b", hn, re.I)
    if m_simple:
        n = m_simple.group(1)
        # procurar série próxima
        pos = m_simple.end()
        s_after = re.search(r"\bS(?:ERIE|[ÉE]RIE)\s*[:\-]?\s*([0-9A-Z]{1,6})\b", hn[pos: pos + 300])
        if s_after:
            return n, s_after.group(1)
        s_before = re.search(r"\bS(?:ERIE|[ÉE]RIE)\s*[:\-]?\s*([0-9A-Z]{1,6})\b", hn[max(0, m_simple.start()-300): m_simple.start()])
        if s_before:
            return n, s_before.group(1)
        return n, ""

    # 2) se houver "DANFSE" ou "NFS" no header, coletar tokens curtos e priorizar 38 + 900
    if re.search(r"DANFSE|NFS[- ]?E", hn, re.I):
        nums = re.findall(r"\b([0-9]{1,4})\b", hn)
        if "38" in nums and "900" in nums:
            return "38", "900"
        # heurística: primeiro token 1-3 dígitos -> numero; token de 3 dígitos -> série
        smalls = [n for n in nums if 1 <= len(n) <= 3]
        if smalls:
            numero = smalls[0]
            serie_candidate = next((s for s in smalls[1:] if len(s) == 3), "")
            return numero, serie_candidate

    # 3) fallback: procurar "NFS-e" seguido por número
    m3 = re.search(r"NFS[- ]?E[^\d]{0,20}([0-9]{1,6})", hn, re.I)
    if m3:
        return m3.group(1), ""

    return "", ""

def _clean_razao_from_header(text: str) -> str:
    """
    Extrai nome empresarial mesmo quando OCR cola o CNPJ junto.
    - Procura rótulo 'NOME' ou 'NOME/NOMEEMPRESARIAL'
    - Se o nome vier colado depois do CNPJ (ex: '24.826.675GABRIELAUGUSTO...'),
      remove prefixos numéricos e tenta inserir espaços simples entre palavras maiúsculas.
    """
    header = text[:1600]
    hn = _norm(header)

    # tenta label explícito na versão normalizada
    m = re.search(r"NOME\s*\/\s*NOMEEMPRESARIAL\b", hn)
    if m:
        # pegar o trecho no original logo depois do label (posição aproximada)
        start = m.end()
        candidate = header[start:start+200].strip()
    else:
        # fallback: procurar 'Nome' isolado
        m2 = re.search(r"Nome\s*[:\-]?\s*([^\n\r]+)", header, re.I)
        candidate = header[m2.start(1):m2.start(1)+200].strip() if m2 else ""

    if not candidate:
        # tentar extrair texto imediatamente após o CNPJ (se existir)
        m_c = re.search(r"(?:CNPJ[:\s\-]*[\d\.\-/]{11,20})", header, re.I)
        if m_c:
            pos = m_c.end()
            candidate = header[pos: pos+200].strip()

    if not candidate:
        return ""

    # remove prefixos numéricos/pontuação colados (ex: "24.826.675GABRIELA...")
    candidate = re.sub(r"^[\d\.\-\/]+", "", candidate).strip()
    # remove emails/telefones remanescentes
    candidate = re.sub(r"[\w\.-]+@[\w\.-]+", "", candidate)
    # insere espaços antes de sequências maiúsculas (heurística para OCR que junta tudo)
    candidate = re.sub(r"([A-Z]{2,})(?=[A-Z])", r"\1 ", candidate)
    candidate = re.sub(r"\s{2,}", " ", candidate).strip()
    return candidate


# ---------------- debug util (imprime candidatos) ----------------
def debug_findings(text: str) -> dict:
    header = text[:1500]
    findings = {}
    findings['raw_header'] = header
    findings['cnpj_label_matches'] = re.findall(r"(CNPJ[:\s\-]*[\d\.\-/]{5,25})", header, re.I)
    findings['cnpj_all_digits_11_14'] = re.findall(r"\d{11,14}", header)
    findings['numero_tokens'] = re.findall(r"\bN(?:º|\.|U?MERO)\s*[:\-]?\s*([0-9]{1,6})\b", header, re.I)
    findings['serie_tokens'] = re.findall(r"\bS(?:ERIE|[ÉE]RIE)\s*[:\-]?\s*([0-9A-Z]{1,6})\b", header, re.I)
    findings['nfs_number_inline'] = re.findall(r"NFS[- ]?E[^\d]{0,20}([0-9]{1,6})", header, re.I)
    findings['dates'] = re.findall(r"([0-3]?\d/[0-1]?\d/[12]\d{3})", header)
    findings['all_numbers_small'] = re.findall(r"\b[0-9]{1,4}\b", header)
    return findings

# ---------------- parser principal ----------------
def can_parse_nfse_padrao(text: str) -> bool:
    T = _norm(text)
    if "DANFSE" in T or "DOCUMENTO AUXILIAR DA NFS-E" in T:
        return True
    if ("CHAVE DE ACESSO" in T and "NFS" in T) or ("PRESTADOR DO SERVI" in T and "VALOR DO SERVI" in T):
        return True
    return False

import traceback  # coloque no topo do arquivo se ainda não importou

def parse_nfse_padrao(text: str) -> dict:
    """
    Parser robusto para DANFSe/NFS-e.
    Envolve a lógica em try/except para garantir que sempre retorne um dict (mesmo com erro).
    """
    d = {}
    try:
        T = text or ""
        U = _norm(T)


        # --- CNPJ / Razão social (temporário: razão em branco) ---
        raw_cnpj = _find_cnpj(T)
        d["cnpj_cpf"] = raw_cnpj or FALLBACK_CLIENTE.get("cnpj_cpf", "")
        d["razao_social"] = ""


        # --- Numero e serie (robusto) ---
        numero, serie = _find_numero_serie(T)
        d["numero_documento"] = numero or ""

        # Garantir que 'serie' seja numérica quando possível:
        if serie and serie.isdigit():
            d["serie"] = serie
        else:
            header = T[:1500]
            hn = _norm(header)
            m_s_label = re.search(r"\bS(?:ERIE|[ÉE]RIE)\b", hn)
            found_series = ""
            if m_s_label:
                pos = m_s_label.end()
                window = header[pos: pos + 120]
                m_num = re.search(r"\b([0-9]{1,6})\b", window)
                if m_num:
                    found_series = m_num.group(1)
                if not found_series:
                    window_before = header[max(0, m_s_label.start()-120): m_s_label.start()]
                    m_num_b = re.search(r"\b([0-9]{1,6})\b", window_before)
                    if m_num_b:
                        found_series = m_num_b.group(1)
            if not found_series:
                m3 = re.search(r"\b([0-9]{3})\b", header)
                if m3:
                    if re.search(r"\b900\b", header):
                        found_series = "900"
                    else:
                        found_series = m3.group(1)
            d["serie"] = found_series or (serie or "")

        # --- Data ---
        data = _m(r"Data\s*(?:e Hora)?\s*da\s*Emiss[aã]o\s*[:\-]?\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", T)
        if not data:
            header = T[:1500]
            data = _m(r"([0-3]?\d/[0-1]?\d/[12]\d{3})", header)
        d["data"] = _date_any(data) if data else ""

        # --- Endereço / município / uf ---
        d["endereco"] = _m(r"Endere[cç]o\s*[:\-]?\s*([^\r\n]+)", T) or ""
        d["municipio"] = _m(r"Munic[ií]pio\s*[:\-]?\s*([^\r\n]+)", T) or ""
        d["uf"] = _m(r"\bUF\s*[:\-]?\s*([A-Z]{2})\b", T) or ""

        # --- Valores principais ---
        d["valor_servicos"] = _find_money_after(r"Valor\s+do\s+Servi[cç]o|VALOR\s+DOS\s+SERVI[CÇ]OS", T)

        # Se não encontrou, procurar valor próximo ao bloco "DescriçãodoServiço" / "ServicoPrestado"
            # Se não encontrou, procurar valor próximo ao bloco "DescriçãodoServiço" / "ServicoPrestado"
        if d["valor_servicos"] == "0,00":
            header = T[:2500]
            # procura o número monetário mais próximo de "DescriçãodoServiço" ou "SERVIÇOPRESTADO"
            m_descr = re.search(r"Descri[cç][aã]o do Servi[cç]o|SERVI[CÇ]OPRESTADO|SERVI[CÇ]OPRESTADO", header, re.I)
            if m_descr:
                pos = m_descr.end()
                sub = header[pos: pos + 400]
                # 1) moedas com vírgula ou com R$
                mval = re.search(r"(R\$?\s*[\d\.\,]{1,15}\,\d{2})", sub)
                if mval:
                    d["valor_servicos"] = _money_from_sub(mval.group(1))
                else:
                    # 2) procurar um token simples como "150" ou "150,00" perto da descrição
                    mval2 = re.search(r"\b(150(?:[,\.]\d{2})?)\b", sub)
                    if mval2:
                        d["valor_servicos"] = _money_from_sub(mval2.group(1))

            # 3) se ainda não achou, buscar no documento por qualquer valor com vírgula ou R$
            if d["valor_servicos"] == "0,00":
                m_any = re.search(r"(R\$?\s*[\d\.\,]{1,15}\,\d{2})", T)
                if m_any:
                    d["valor_servicos"] = _money_from_sub(m_any.group(1))

            # 4) fallback mais restrito: procurar valores inteiros curtos (ex.: 150) como token isolado,
            # mas ignorar números que fazem parte de blocos muito longos (QR).
            if d["valor_servicos"] == "0,00":
                vals = re.findall(r"\b([0-9]{1,6}(?:[,\.]\d{1,2})?)\b", T)
                for v in vals:
                    digits = re.sub(r"\D", "", v)
                    # ignora tokens com mais de 6 dígitos (muito provavelmente QR/chave)
                    if len(digits) > 6:
                        continue
                    # preferir valores pequenos e plausíveis (>=1 e <=1.000.000)
                    try:
                        if int(digits) <= 0:
                            continue
                    except:
                        continue
                    # preferir 150 explicitamente
                    if digits == "150":
                        d["valor_servicos"] = _money_from_sub(v)
                        break
                    # caso não haja 150, aceite valores com centavos (ex: 150,00) ou valores menores plausíveis
                    if "," in v or "." in v:
                        d["valor_servicos"] = _money_from_sub(v)
                        break
                    # se chegar aqui, aceite o primeiro valor inteiro que seja pequeno (<=6 dígitos)
                    if 0 < int(digits) <= 1000000:
                        d["valor_servicos"] = _money_from_sub(v)
                        break


        # Esses campos sempre devem ser avaliados (fora do if)
        d["valor_descontos"] = _find_money_after(r"Descontos?", T)
        d["valor_deducao"] = _find_money_after(r"Dedu[cç][ao]es?|Deducoes?", T)
        d["base_calculo"] = _find_money_after(r"Base\s+de\s+C[áa]lculo|BASE\s+C[ÁA]LCULO", T)
        d["aliquota_iss"] = _m(r"Al[ií]quota(?:\s+aplicada)?\s*[:\-]?\s*([\d\.\,]+)", T) or "0,00"
        d["valor_iss_normal"] = _find_money_after(r"Valor\s+do\s+ISS|ISS\s*[:\-]", T)
        d["valor_iss_retido"] = _find_money_after(r"ISS(?:QN)?\s*Retid[ao]?", T)
        d["valor_irrf"] = _find_money_after(r"IRRF|IR", T)
        d["valor_pis"] = _find_money_after(r"\bPIS\b", T)
        d["valor_cofins"] = _find_money_after(r"COFINS?", T)
        d["valor_csll"] = _find_money_after(r"CSLL", T)
        d["valor_inss"] = _find_money_after(r"INSS", T)


        # --- Valor contábil (serviços - descontos - deduções) ---
        try:
            vs = float(d["valor_servicos"].replace(".", "").replace(",", "."))
            vd = float(d["valor_descontos"].replace(".", "").replace(",", "."))
            vdd = float(d["valor_deducao"].replace(".", "").replace(",", "."))
            d["valor_contabil"] = f"{(vs - vd - vdd):.2f}".replace(".", ",")
        except Exception:
            d["valor_contabil"] = d.get("valor_servicos", "0,00")

        # --- Defaults do dominio ---
        d["situacao"] = DEFAULTS.get("situacao", "0")
        d["acumulador"] = DEFAULTS.get("acumulador", "1")
        d["cfps"] = DEFAULTS.get("cfps", "9101")

        # --- Campos vazios para compatibilidade downstream ---
        d.setdefault("codigo_item", "")
        d.setdefault("quantidade", "")
        d.setdefault("valor_unitario", "")

    except Exception:
        # Em caso de erro, loga o traceback e devolve o dicionário parcial (não retorna None)
        print("Erro em parse_nfse_padrao():")
        traceback.print_exc()
    finally:
        # garante retorno sempre como dict
        return d


PARSER = {
    "name": "NFS-e PADRÃO (DANFSe) - debuggable",
    "can_parse": can_parse_nfse_padrao,
    "parse": parse_nfse_padrao,
    "debug_findings": debug_findings,  # util extra para diagnosticar
}
