# parser_router.py
from typing import Callable, Tuple
import logging

# importe os parsers registrados (cada módulo expõe PARSER = {"name", "can_parse", "parse"})
from parser_nfse_padrao import PARSER as PARSER_NFSE
from parser_cwb import PARSER as PARSER_CWB
from parser_sp import PARSER as PARSER_SP
from parser_generic import PARSER as PARSER_GENERIC

logger = logging.getLogger(__name__)

# Ordem importa: específicos primeiro; genérico por último
_PARSERS = [
    PARSER_NFSE,
    PARSER_CWB,
    PARSER_SP,
    PARSER_GENERIC,  # sempre por último como fallback
]


def select_parser(text: str) -> Tuple[str, Callable[[str], dict]]:
    """
    Seleciona automaticamente o parser mais adequado para o conteúdo do PDF.

    Retorna:
        (nome_do_parser, func_parse)
    """
    for p in _PARSERS:
        try:
            can = p.get("can_parse")
            if callable(can) and can(text):
                return p.get("name", "desconhecido"), p["parse"]
        except Exception as e:
            # loga o erro (ajuda a diagnosticar parsers problemáticos)
            logger.exception("Erro ao testar can_parse para parser %s: %s", p.get("name"), e)
            continue

    # Fallback universal (garantido existir porque PARSER_GENERIC está na lista)
    return PARSER_GENERIC.get("name", "Genérico (fallback)"), PARSER_GENERIC["parse"]
