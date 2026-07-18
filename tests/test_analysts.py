from trader.analysts import parse_summary


def _payload(fin=None, trend=None):
    result = {}
    if fin is not None:
        result["financialData"] = fin
    if trend is not None:
        result["recommendationTrend"] = {"trend": trend}
    return {"quoteSummary": {"result": [result]}}


def test_parse_full_summary_raw_numbers():
    payload = _payload(
        fin={
            "recommendationMean": 1.9,
            "numberOfAnalystOpinions": 40,
            "targetMeanPrice": 240.0,
            "targetHighPrice": 300.0,
            "targetLowPrice": 180.0,
            "currentPrice": 200.0,
        },
        trend=[{"period": "0m", "strongBuy": 12, "buy": 20, "hold": 6,
                "sell": 1, "strongSell": 1}],
    )
    a = parse_summary(payload)
    assert a["label"] == "Comprar" and a["tone"] == "pos"
    assert a["mean"] == 1.9 and a["count"] == 40
    assert a["target"] == 240.0 and a["upside"] == 20.0  # 240/200-1
    assert a["dist"] == {"strongBuy": 12, "buy": 20, "hold": 6, "sell": 1, "strongSell": 1}


def test_parse_accepts_yahoo_raw_wrapper():
    # Con formatted=true Yahoo envuelve los números en {"raw":..,"fmt":..}.
    payload = _payload(fin={
        "recommendationMean": {"raw": 3.2, "fmt": "3.2"},
        "numberOfAnalystOpinions": {"raw": 10, "fmt": "10"},
    })
    a = parse_summary(payload)
    assert a["mean"] == 3.2 and a["count"] == 10
    assert a["label"] == "Mantener" and a["tone"] == "neutral"


def test_parse_label_thresholds():
    assert parse_summary(_payload(fin={"recommendationMean": 1.2}))["label"] == "Compra fuerte"
    assert parse_summary(_payload(fin={"recommendationMean": 4.9}))["label"] == "Venta fuerte"
    assert parse_summary(_payload(fin={"recommendationMean": 4.0}))["tone"] == "neg"


def test_parse_returns_none_when_nothing_useful():
    assert parse_summary(_payload(fin={})) is None
    assert parse_summary({"quoteSummary": {"result": []}}) is None
    assert parse_summary({}) is None


def test_parse_ignores_empty_trend():
    a = parse_summary(_payload(
        fin={"recommendationMean": 2.0},
        trend=[{"strongBuy": 0, "buy": 0, "hold": 0, "sell": 0, "strongSell": 0}]))
    assert a["dist"] is None
