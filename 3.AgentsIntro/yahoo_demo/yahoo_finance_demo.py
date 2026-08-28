# ============================================================================
# DRY RUN: every comment below shows the REAL value produced by
# get_stock_price("AAPL"), captured from an actual run.
# Prices are live market data, so the exact number will differ when you run it.
# ============================================================================

import yfinance as yf   # Yahoo Finance client. This is what actually hits the network.
import json             # NOTE: imported but never used in this file — safe to delete.
from pydantic import BaseModel, Field   # BaseModel = validated data class; Field = per-field rules/docs


# ---------------------------------------------------------------------------
# The SUCCESS shape. Pydantic guarantees these 3 fields exist and have the
# right types — if they don't, it raises instead of returning bad data.
# ---------------------------------------------------------------------------
class StockPriceResult(BaseModel):
    """Result of the get_stock_price tool"""
    # `...` (Ellipsis) as the first arg means REQUIRED — no default value.
    # `description` is not just a docstring: it lands in the JSON schema that
    # you hand to the LLM, so the model reads these sentences.
    ticker: str = Field(..., description="The ticker symbol of the stock")
    price: float = Field(..., description="The current price of the stock")
    currency: str = Field(..., description="The currency of the stock price")
    # AAPL -> StockPriceResult(ticker='AAPL', price=313.45001220703125, currency='USD')


# ---------------------------------------------------------------------------
# The FAILURE shape. Deliberately a different model, so the caller (or the LLM)
# can tell "here is a price" apart from "here is what went wrong".
# ---------------------------------------------------------------------------
class StockPriceError(BaseModel):
    """Error result of the get_stock_price tool"""
    error: str = Field(..., description="The error message")


def get_stock_price(ticker_symbol: str) -> str:
    """Fetch the current price of a stock given it's ticker symbol"""
    # Called as: get_stock_price("AAPL")
    #   ticker_symbol == 'AAPL'   <class 'str'>
    try:

        # .upper() normalises user input, so "aapl" / "Aapl" / "AAPL" all work.
        # Yahoo's API is case-sensitive and only accepts uppercase symbols.
        #   'aapl'.upper()  ->  'AAPL'
        # yf.Ticker() does NOT fetch anything yet — it just builds a lazy handle.
        stock = yf.Ticker(ticker_symbol.upper())
        #   stock  ->  yfinance.Ticker object <AAPL>
        #   type   ->  <class 'yfinance.ticker.Ticker'>

        # THIS line is where the network request actually happens.
        # .fast_info is a lightweight quote endpoint (much faster than .info).
        #   type(stock.fast_info) -> <class 'yfinance.scrapers.quote.FastInfo'>
        #   available keys        -> ['currency', 'dayHigh', 'dayLow', 'exchange',
        #                             'fiftyDayAverage', 'lastPrice', 'lastVolume',
        #                             'marketCap', 'open', 'previousClose', 'quoteType',
        #                             'regularMarketPreviousClose', 'shares', 'timezone',
        #                             'tenDayAverageVolume', 'threeMonthAverageVolume',
        #                             'twoHundredDayAverage', 'yearChange',
        #                             'yearHigh', 'yearLow']
        # Note the keys list says 'lastPrice' (camelCase) but "last_price" works too —
        # FastInfo normalises snake_case lookups to camelCase for you.
        price = stock.fast_info["last_price"]
        #   price  ->  313.45001220703125   <class 'float'>
        #   (raw float straight from the API — not rounded to 2 decimal places)

        # Second lookup — served from FastInfo's cache, so no extra network call.
        currency = stock.fast_info["currency"]
        #   currency  ->  'USD'   <class 'str'>

        # Build + VALIDATE in one step. If price came back as None or a string,
        # pydantic raises ValidationError here and the except block catches it.
        result = StockPriceResult(
            ticker=ticker_symbol.upper(),   # 'AAPL'
            price=price,                    # 313.45001220703125
            currency=currency               # 'USD'
        )
        #   result  ->  StockPriceResult(ticker='AAPL', price=313.45001220703125, currency='USD')
        #   this is a Python OBJECT — you can do result.price, result.ticker, etc.

        # Serialise the object to a JSON *string*.
        # A string is required because this is destined for an LLM tool result,
        # and the {"role": "tool", "content": ...} field must be text.
        return result.model_dump_json()
        #   returns  ->  '{"ticker":"AAPL","price":313.45001220703125,"currency":"USD"}'
        #   type     ->  <class 'str'>   (NOT a dict — note the outer quotes)

    except Exception as e:
        # Catches network failures, bad tickers, and pydantic validation errors.
        # Real behaviour with a bad symbol, e.g. get_stock_price("NOTAREALTICKER"):
        #   yfinance first prints its own noise to stderr:
        #     HTTP Error 404: {"quoteSummary":{"result":null,"error":{...
        #     $NOTAREALTICKER: No data found, symbol may be delisted
        #   then the raised exception is:
        #     type(e) -> KeyError
        #     str(e)  -> "'currentTradingPeriod'"
        print(f"Error fetching stock price for {ticker_symbol}: {e}")
        #   prints  ->  Error fetching stock price for NOTAREALTICKER: 'currentTradingPeriod'

        error = StockPriceError(error=str(e))
        #   error  ->  StockPriceError(error="'currentTradingPeriod'")

        # Returns a JSON string too, so the caller always gets the same TYPE back
        # (str) whether it succeeded or failed. Only the shape of the JSON differs.
        return error.model_dump_json()
        #   returns  ->  '{"error":"\'currentTradingPeriod\'"}'


# Only runs when you execute this file directly (`uv run yahoo_finance_demo.py`),
# not when another module imports get_stock_price from it.
if __name__ == "__main__":
    print(get_stock_price("AAPL"))
    # FINAL TERMINAL OUTPUT:
    #   {"ticker":"AAPL","price":313.45001220703125,"currency":"USD"}
