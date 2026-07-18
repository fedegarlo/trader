"""Metadatos de tickers para la web: nombre legible y dominio para el logo.

La página del ranking es estática y autocontenida, pero el detalle de un
ticker enseña el logo de la empresa y enlaces a noticias. Los logos se piden
en tiempo de vista al servicio gratuito de Clearbit por **dominio**
(``https://logo.clearbit.com/<dominio>``); por eso aquí solo mapeamos
``ticker -> {nombre, dominio}``. Si un ticker no está en el mapa, la web usa un
monograma de color como respaldo (nunca falla) y las noticias se buscan por el
propio símbolo. Ampliar la lista es solo añadir una fila.

Nada de esto expone operaciones ni importes: el símbolo del ticker ya es
público (aparece en el reparto de la cartera), y el nombre/dominio/logo son
datos públicos de la empresa.
"""

from __future__ import annotations

# ticker -> (nombre a mostrar, dominio para el logo de Clearbit)
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


def ticker_meta(ticker: str) -> dict:
    """Nombre y dominio (para el logo) de un ticker.

    Si no está en el mapa devuelve el propio símbolo como nombre y ``domain``
    vacío: la web usará entonces un monograma de color en vez del logo.
    """
    name, domain = _META.get(ticker.upper(), (ticker, ""))
    return {"name": name, "domain": domain}
