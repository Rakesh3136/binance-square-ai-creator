from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("nic_prediction_engine", ROOT / "src/nic_prediction_engine.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def pair(symbol, base, *, status="TRADING", quote="USDT", spot=True):
    return {"symbol": symbol, "baseAsset": base, "quoteAsset": quote,
            "status": status, "isSpotTradingAllowed": spot}


def test_only_explicitly_active_spot_usdt_pairs_are_accepted():
    candidates = [("BTC", "LONG"), ("ETH", "SHORT")]
    info = {"symbols": [pair("BTCUSDT", "BTC"), pair("ETHUSDT", "ETH")]}
    accepted, audit = MODULE.validate_spot_candidates(candidates, info)
    assert accepted == candidates
    assert audit["status"] == "VERIFIED"
    assert audit["accepted"] == 2


def test_unknown_inactive_and_non_spot_pairs_are_rejected():
    candidates = [("MISSING", "LONG"), ("HALT", "LONG"), ("MARGIN", "SHORT")]
    info = {"symbols": [
        pair("HALTUSDT", "HALT", status="BREAK"),
        pair("MARGINUSDT", "MARGIN", spot=False),
    ]}
    accepted, audit = MODULE.validate_spot_candidates(candidates, info)
    assert accepted == []
    assert audit["rejected"] == 3
    assert audit["rejections"]["not_listed_as_usdt_pair"] == 1
    assert audit["rejections"]["pair_not_trading"] == 1
    assert audit["rejections"]["spot_trading_not_explicitly_allowed"] == 1


def test_non_usdt_and_base_asset_mismatch_are_rejected():
    candidates = [("BTC", "LONG"), ("ETH", "SHORT")]
    info = {"symbols": [
        pair("BTCBUSD", "BTC", quote="BUSD"),
        pair("ETHUSDT", "WRONG"),
    ]}
    accepted, audit = MODULE.validate_spot_candidates(candidates, info)
    assert accepted == []
    assert audit["rejected"] == 2


def test_common_leveraged_token_suffixes_are_excluded():
    candidates = [(x, "LONG") for x in ("BTCUP", "BTCDOWN", "ETHBULL", "ETHBEAR")]
    info = {"symbols": [pair(x + "USDT", x) for x, _ in candidates]}
    accepted, audit = MODULE.validate_spot_candidates(candidates, info)
    assert accepted == []
    assert audit["rejections"]["leveraged_token_excluded"] == 4


def test_duplicate_candidates_are_deduplicated_and_capped():
    candidates = [("BTC", "LONG"), ("BTC", "LONG"), ("ETH", "SHORT")]
    info = {"symbols": [pair("BTCUSDT", "BTC"), pair("ETHUSDT", "ETH")]}
    accepted, audit = MODULE.validate_spot_candidates(candidates, info)
    assert accepted == [("BTC", "LONG"), ("ETH", "SHORT")]
    assert audit["accepted"] == 2


def test_missing_or_malformed_exchange_metadata_fails_closed():
    for info in ({}, {"symbols": []}, {"symbols": "not-a-list"}):
        accepted, audit = MODULE.validate_spot_candidates([("BTC", "LONG")], info)
        assert accepted == []
        assert audit["status"] == "BLOCKED_EXCHANGE_UNIVERSE_UNVERIFIED"


def test_bad_side_and_invalid_symbol_are_rejected():
    accepted, audit = MODULE.validate_spot_candidates(
        [("BTC", "WAIT"), ("", "LONG")],
        {"symbols": [pair("BTCUSDT", "BTC")]},
    )
    assert accepted == []
    assert audit["rejections"]["invalid_candidate"] == 2


if __name__ == "__main__":
    test_only_explicitly_active_spot_usdt_pairs_are_accepted()
    test_unknown_inactive_and_non_spot_pairs_are_rejected()
    test_non_usdt_and_base_asset_mismatch_are_rejected()
    test_common_leveraged_token_suffixes_are_excluded()
    test_duplicate_candidates_are_deduplicated_and_capped()
    test_missing_or_malformed_exchange_metadata_fails_closed()
    test_bad_side_and_invalid_symbol_are_rejected()
    print("NIC verified Spot universe gate tests: PASS")
