"""Metadatos de tickers para la web: nombre legible y dominio para el logo.

La página del ranking es estática y autocontenida, pero el detalle de un
ticker enseña el logo de la empresa y enlaces a noticias. Los logos se piden
en tiempo de vista al servicio de logo.dev por **ticker**
(``https://img.logo.dev/ticker/<TICKER>``), con respaldo a un monograma de
color si la imagen falla (nunca se rompe). Aquí mapeamos
``ticker -> {nombre, dominio}``: el **nombre** se muestra en el detalle y el
**dominio** se conserva como metadato de la empresa. Si un ticker no está en el
mapa, se muestra el propio símbolo como nombre (el logo se sigue intentando por
ticker) y las noticias se buscan por el símbolo. Ampliar la lista es solo
añadir una fila.

Nada de esto expone operaciones ni importes: el símbolo del ticker ya es
público (aparece en el reparto de la cartera), y el nombre/dominio/logo son
datos públicos de la empresa.
"""

from __future__ import annotations

# ticker -> (nombre a mostrar, dominio para el logo de logo.dev)
_META: dict[str, tuple[str, str]] = {
    # presentes en el repo / la liga
    "AAPL": ("Apple", "apple.com"),
    "MSFT": ("Microsoft", "microsoft.com"),
    "NVDA": ("NVIDIA", "nvidia.com"),
    "META": ("Meta Platforms", "meta.com"),
    "PLTR": ("Palantir", "palantir.com"),
    "SMCI": ("Super Micro Computer", "supermicro.com"),
    "TSM": ("Taiwan Semiconductor", "tsmc.com"),
    "MU": ("Micron Technology", "micron.com"),
    "WDC": ("Western Digital", "westerndigital.com"),
    # populares (por si entran en cartera más adelante)
    "GOOGL": ("Alphabet", "abc.xyz"),
    "GOOG": ("Alphabet", "abc.xyz"),
    "AMZN": ("Amazon", "amazon.com"),
    "TSLA": ("Tesla", "tesla.com"),
    "AMD": ("AMD", "amd.com"),
    "NFLX": ("Netflix", "netflix.com"),
    "INTC": ("Intel", "intel.com"),
    "AVGO": ("Broadcom", "broadcom.com"),
    "QCOM": ("Qualcomm", "qualcomm.com"),
    "ADBE": ("Adobe", "adobe.com"),
    "CRM": ("Salesforce", "salesforce.com"),
    "ORCL": ("Oracle", "oracle.com"),
    "IBM": ("IBM", "ibm.com"),
    "UBER": ("Uber", "uber.com"),
    "COIN": ("Coinbase", "coinbase.com"),
    "PYPL": ("PayPal", "paypal.com"),
    "SHOP": ("Shopify", "shopify.com"),
    "DIS": ("Disney", "disney.com"),
    "BABA": ("Alibaba", "alibaba.com"),
    "V": ("Visa", "visa.com"),
    "MA": ("Mastercard", "mastercard.com"),
    "JPM": ("JPMorgan Chase", "jpmorganchase.com"),
    "KO": ("Coca-Cola", "coca-cola.com"),
    "PEP": ("PepsiCo", "pepsico.com"),
    "NKE": ("Nike", "nike.com"),
    "SBUX": ("Starbucks", "starbucks.com"),
    "BA": ("Boeing", "boeing.com"),
    "F": ("Ford", "ford.com"),
    "GM": ("General Motors", "gm.com"),
    "ASML": ("ASML", "asml.com"),
    "ARM": ("Arm Holdings", "arm.com"),
    "MRVL": ("Marvell Technology", "marvell.com"),
}


# Valores relacionados (mismo sector / competidores) para «Valores relacionados»
# del detalle del ticker. Son relaciones estables y de dominio público (no son
# métricas que se queden obsoletas); la web los muestra como chips que llevan al
# detalle del valor si está en la liga, o a su ficha de Yahoo si no.
_PEERS: dict[str, list[str]] = {
    "AAPL": ["MSFT", "GOOGL", "AMZN"],
    "MSFT": ["AAPL", "GOOGL", "ORCL"],
    "NVDA": ["AMD", "TSM", "AVGO"],
    "META": ["GOOGL", "AMZN", "NFLX"],
    "PLTR": ["SNOW", "CRM", "MSFT"],
    "SMCI": ["DELL", "HPE", "NVDA"],
    "TSM": ["NVDA", "ASML", "MU"],
    "MU": ["WDC", "TSM", "NVDA"],
    "WDC": ["MU", "STX", "TSM"],
    "GOOGL": ["MSFT", "META", "AMZN"],
    "GOOG": ["MSFT", "META", "AMZN"],
    "AMZN": ["MSFT", "GOOGL", "AAPL"],
    "TSLA": ["GM", "F", "NVDA"],
    "AMD": ["NVDA", "INTC", "TSM"],
    "NFLX": ["DIS", "META", "AMZN"],
    "INTC": ["AMD", "NVDA", "TSM"],
    "AVGO": ["QCOM", "NVDA", "AMD"],
    "QCOM": ["AVGO", "ARM", "MRVL"],
    "ORCL": ["MSFT", "CRM", "SAP"],
    "CRM": ["MSFT", "ORCL", "ADBE"],
    "ADBE": ["CRM", "MSFT", "ORCL"],
    "ASML": ["TSM", "AMAT", "LRCX"],
    "ARM": ["QCOM", "NVDA", "AVGO"],
    "MRVL": ["AVGO", "QCOM", "NVDA"],
}


def ticker_meta(ticker: str) -> dict:
    """Nombre, dominio (para el logo) y valores relacionados de un ticker.

    Si no está en el mapa devuelve el propio símbolo como nombre, ``domain``
    vacío (la web usará un monograma de color) y sin relacionados.
    """
    sym = ticker.upper()
    name, domain = _META.get(sym, (ticker, ""))
    return {"name": name, "domain": domain, "peers": _PEERS.get(sym, [])}
