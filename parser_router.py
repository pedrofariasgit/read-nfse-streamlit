# parser_router.py
from typing import Callable, Tuple

# importe os parsers registrados
# cada módulo expõe um dicionário PARSER = {"name": str, "can_parse": fn, "parse": fn}
from parser_cwb import PARSER as PARSER_CWB
from parser_sp import PARSER as PARSER_SP
from parser_generic import PARSER as PARSER_GENERIC

# Ordem importa: tente específicos primeiro; genérico por último
_PARSERS = [PARSER_CWB, PARSER_SP, PARSER_GENERIC]


def select_parser(text: str) -> Tuple[str, Callable[[str], dict]]:
    """
    Seleciona automaticamente o parser mais adequado para o conteúdo do PDF.

    Retorna:
        (nome_do_parser, func_parse)

    Estratégia:
      1) Itera sobre _PARSERS e usa o primeiro cujo `can_parse(text)` for True.
      2) Se nenhum reconhecer, cai no PARSER_GENERIC (fallback).
    """
    for p in _PARSERS:
        try:
            if p.get("can_parse") and p["can_parse"](text):
                return p.get("name", "desconhecido"), p["parse"]
        except Exception:
            # se um parser der erro no can_parse, ignora e tenta o próximo
            continue

    # Fallback universal
    return PARSER_GENERIC.get("name", "Genérico (fallback)"), PARSER_GENERIC["parse"]
