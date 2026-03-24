# config/tickers.py
# Single source of truth for all market ticker symbols and keyword→ticker mappings.
# Edit this file to add/remove instruments or keyword triggers — no logic files need changing.

# ---------------------------------------------------------------------------
# EQUITY INDICES
# ---------------------------------------------------------------------------
EQUITY_TICKERS = {
    "SP500":  "^GSPC",    # S&P 500 (Americas)
    "NASDAQ": "^IXIC",    # NASDAQ Composite (Americas/Tech)
    "DJI":    "^DJI",     # Dow Jones Industrial Average (Americas)
    "XLE":    "XLE",      # Energy Select Sector SPDR ETF (energy sector proxy)
    "FTSE":   "^FTSE",    # FTSE 100 (Europe)
    "DAX":    "^GDAXI",   # DAX (Europe)
    "NIKKEI": "^N225",    # Nikkei 225 (APAC/Japan)
    "HSI":    "^HSI",     # Hang Seng (APAC/China)
    "ASX":    "^AXJO",    # ASX 200 (APAC/Australia)
    "SENSEX": "^BSESN",   # BSE Sensex (S Asia/India)
}

# ---------------------------------------------------------------------------
# COMMODITIES
# ---------------------------------------------------------------------------
COMMODITY_TICKERS = {
    "BRENT":  "BZ=F",     # Brent Crude Oil (Middle East linkage)
    "WTI":    "CL=F",     # WTI Crude Oil (Americas linkage)
    "GOLD":   "GC=F",     # Gold (Africa/global safe haven)
    "SILVER": "SI=F",     # Silver
    "WHEAT":  "ZW=F",     # Wheat futures (Europe/Ukraine linkage)
    "COPPER": "HG=F",     # Copper (APAC/China linkage)
    "NATGAS": "NG=F",     # Natural Gas (Europe linkage)
    "COTTON": "CT=F",     # Cotton (S Asia linkage)
    "COCOA":  "CC=F",     # Cocoa (Africa/West Africa linkage)
    "PALMOIL":"FCPO=F",   # Palm Oil futures (SE Asia linkage)
}

# ---------------------------------------------------------------------------
# FOREX PAIRS  (all quoted as X per 1 USD unless noted)
# ---------------------------------------------------------------------------
FOREX_TICKERS = {
    "EURUSD": "EURUSD=X",   # Euro (Europe)
    "USDJPY": "USDJPY=X",   # Japanese Yen (APAC)
    "GBPUSD": "GBPUSD=X",   # British Pound (Europe)
    "USDINR": "USDINR=X",   # Indian Rupee (S Asia)
    "USDPKR": "USDPKR=X",   # Pakistani Rupee (S Asia)
    "USDSAR": "USDSAR=X",   # Saudi Riyal (Middle East)
    "USDSGD": "USDSGD=X",   # Singapore Dollar (SE Asia)
    "AUDUSD": "AUDUSD=X",   # Australian Dollar (APAC)
    "USDZAR": "USDZAR=X",   # South African Rand (Africa)
    "USDBRL": "USDBRL=X",   # Brazilian Real (Americas)
    "USDCNY": "USDCNY=X",   # Chinese Yuan (APAC)
}

# ---------------------------------------------------------------------------
# FLAT LISTS — used by market_fetcher.py to pull all tickers in one pass
# ---------------------------------------------------------------------------
ALL_TICKERS = {
    **EQUITY_TICKERS,
    **COMMODITY_TICKERS,
    **FOREX_TICKERS,
}

# Reverse map: yfinance symbol → human-readable label
# e.g. "BZ=F" → "BRENT"
SYMBOL_TO_LABEL = {v: k for k, v in ALL_TICKERS.items()}

# ---------------------------------------------------------------------------
# KEYWORD → TICKER MAPPING
# Used by correlation_engine.py to tag articles on ingest.
# Keys are lowercase. Values are lists of internal labels (keys in ALL_TICKERS).
# ---------------------------------------------------------------------------
KEYWORD_TICKER_MAP = {

    # --- Middle East / Oil ---
    "iran":         ["BRENT", "WTI", "USDSAR", "XLE"],
    "iraq":         ["BRENT", "WTI", "XLE"],
    "saudi":        ["BRENT", "WTI", "USDSAR", "XLE"],
    "opec":         ["BRENT", "WTI", "XLE"],
    "strait of hormuz": ["BRENT", "WTI", "XLE"],
    "houthi":       ["BRENT", "WTI", "XLE"],
    "israel":       ["BRENT", "GOLD"],
    "gaza":         ["BRENT", "GOLD"],
    "lebanon":      ["BRENT"],
    "yemen":        ["BRENT", "WTI"],
    "gulf":         ["BRENT", "WTI", "USDSAR"],

    # --- Europe / Energy / Ukraine ---
    "ukraine":      ["WHEAT", "NATGAS", "EURUSD"],
    "russia":       ["BRENT", "NATGAS", "WHEAT", "GOLD"],
    "nato":         ["EURUSD", "GOLD"],
    "germany":      ["DAX", "EURUSD", "NATGAS"],
    "eurozone":     ["EURUSD", "DAX", "FTSE"],
    "ecb":          ["EURUSD", "DAX"],
    "sanctions":    ["BRENT", "GOLD", "EURUSD"],
    "pipeline":     ["NATGAS", "BRENT"],
    "nordstream":   ["NATGAS"],

    # --- US / Global Macro ---
    "fed":          ["SP500", "NASDAQ", "DJI", "EURUSD", "GOLD"],
    "federal reserve": ["SP500", "NASDAQ", "DJI", "EURUSD", "GOLD"],
    "interest rate": ["SP500", "NASDAQ", "DJI", "EURUSD", "GOLD", "USDJPY"],
    "inflation":    ["GOLD", "SP500", "NASDAQ", "EURUSD"],
    "recession":    ["GOLD", "SP500", "NASDAQ", "DJI"],
    "tariff":       ["SP500", "NASDAQ", "DJI", "EURUSD", "USDCNY"],
    "trade war":    ["SP500", "NASDAQ", "USDCNY", "COPPER"],
    "us dollar":    ["EURUSD", "USDJPY", "GOLD"],
    "treasury":     ["SP500", "DJI", "GOLD"],
    "pipeline":     ["NATGAS", "BRENT", "XLE"],
    "energy":       ["BRENT", "WTI", "XLE", "NATGAS"],

    # --- APAC / China ---
    "china":        ["COPPER", "USDCNY", "HSI", "AUDUSD"],
    "taiwan":       ["COPPER", "HSI", "USDCNY"],
    "south china sea": ["COPPER", "HSI", "USDSGD"],
    "north korea":  ["GOLD", "USDJPY", "NIKKEI"],
    "japan":        ["NIKKEI", "USDJPY"],
    "australia":    ["AUDUSD", "COPPER", "ASX"],
    "rare earth":   ["COPPER", "HSI"],
    "semiconductor": ["NIKKEI", "HSI", "SP500"],
    "chip":         ["NIKKEI", "HSI", "SP500"],

    # --- SE Asia ---
    "strait of malacca": ["BRENT", "USDSGD", "PALMOIL"],
    "singapore":    ["USDSGD"],
    "indonesia":    ["PALMOIL", "USDSGD"],
    "malaysia":     ["PALMOIL", "USDSGD"],
    "philippines":  ["USDSGD"],
    "myanmar":      ["USDSGD"],

    # --- S Asia ---
    "india":        ["SENSEX", "USDINR", "COTTON"],
    "pakistan":     ["USDPKR", "COTTON"],
    "bangladesh":   ["COTTON"],
    "kashmir":      ["USDINR", "USDPKR", "GOLD"],

    # --- Africa ---
    "south africa": ["GOLD", "USDZAR"],
    "sahel":        ["GOLD", "COCOA"],
    "nigeria":      ["BRENT", "USDZAR"],
    "ghana":        ["GOLD", "COCOA"],
    "congo":        ["GOLD", "COPPER"],
    "sudan":        ["GOLD"],
    "ethiopia":     ["USDZAR"],

    # --- Americas ---
    "brazil":       ["USDBRL", "SP500"],
    "venezuela":    ["BRENT", "WTI"],
    "colombia":     ["BRENT"],
    "mexico":       ["SP500"],
    "latin america": ["USDBRL", "SP500"],
}

