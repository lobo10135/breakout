import io
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# Streamlit Layout konfigurieren
st.set_page_config(
    page_title="Globaler Markt-Scanner",
    layout="wide",
)

st.title("📈📉 Globaler Markt-Scanner")
st.markdown(
    "Dieses Tool scannt Aktienindizes sowie Makro-Märkte auf Basis historischer Wochenkerzen "
    "mit individuellen Schwellenwerten pro Anlageklasse."
)
st.markdown(
    "**Feste Schwellenwerte:** Aktien > 7 %, Rohstoffe > 6 %, Währungen > 2 %, "
    "Kryptowährungen > 8 %, Bonds > 7 %"
)

# Feste Schwellenwerte (ohne manuelle Regler)
THRESH_STOCKS = 7.0
THRESH_COMM = 6.0
THRESH_CURR = 2.0
THRESH_CRYPTO = 8.0
THRESH_BONDS = 7.0


@st.cache_data(ttl=86400)
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        df = pd.read_html(io.StringIO(response.text))[0]
        return df["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception:
        return []


@st.cache_data(ttl=86400)
def get_german_tickers():
    dax_40 = [
        "ADS.DE", "AIR.DE", "ALV.DE", "BAS.DE", "BAYN.DE", "BEI.DE", "BMW.DE", 
        "BNR.DE", "CBK.DE", "CON.DE", "DT.DE", "DB1.DE", "DBK.DE", "DHL.DE", 
        "DTE.DE", "EOAN.DE", "FRE.DE", "HNR1.DE", "HEI.DE", "HEN3.DE", "IFX.DE", 
        "MBG.DE", "MRK.DE", "MTX.DE", "MUV2.DE", "P911.DE", "PAH3.DE", "RWE.DE", 
        "SAP.DE", "SRT3.DE", "SIE.DE", "SHL.DE", "VOW3.DE", "VNA.DE", "ZAL.DE",
        "ENR.DE", "QIA.DE", "SY1.DE", "BEZ.DE", "DBAN.DE"
    ]
    mdax_50 = [
        "AIXA.DE", "AT1.DE", "NDA.DE", "BC8.DE", "BFSA.DE", "GBF.DE", "AFX.DE", 
        "EVD.DE", "DHER.DE", "ECV.DE", "EVK.DE", "EVT.DE", "FRA.DE", "FNTN.DE", 
        "FPE3.DE", "G1A.DE", "GXI.DE", "HLE.DE", "HFG.DE", "HAG.DE", "HOT.DE", 
        "BOSS.DE", "JEN.DE", "JUN3.DE", "SDF.DE", "KGX.DE", "KBX.DE", "KRN.DE", 
        "LXS.DE", "LEG.DE", "NEM.DE", "NDX1.DE", "PUM.DE", "RAA.DE", "RDC.DE", 
        "RRTL.DE", "G24.DE", "WAF.DE", "STM.DE", "SAX.DE", "TEG.DE", "TLX.DE", 
        "TMV.DE", "TKA.DE", "8TRA.DE", "TUI1.DE", "UTDI.DE", "WCH.DE", "RHM.DE", "S92.DE"
    ]
    return list(set(dax_40 + mdax_50))


@st.cache_data(ttl=86400)
def get_dow_jones_tickers():
    url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        df_list = pd.read_html(io.StringIO(response.text))
        for df in df_list:
            for col in df.columns:
                if "Symbol" in str(col) or "Ticker" in str(col):
                    return df[col].str.replace(".", "-", regex=False).tolist()
    except Exception:
        pass
    return ["AAPL", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", 
            "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", 
            "MMM", "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WMT"]


def get_macro_dictionaries():
    commodities = {
        "GC=F": "Gold", "SI=F": "Silver", "CL=F": "Crude Oil", "BZ=F": "Brent Crude",
        "NG=F": "Natural Gas", "HG=F": "Copper", "ZC=F": "Corn", "ZW=F": "Wheat",
    }
    currencies = {
        "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY",
        "AUDUSD=X": "AUD/USD", "USDCAD=X": "USD/CAD", "USDCHF=X": "USD/CHF",
    }
    cryptos = {
        "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana",
        "XRP-USD": "XRP", "ADA-USD": "Cardano",
    }
    bonds = {
        "^TNX": "US 10y Treasury Yield", "^TYX": "US 30y Treasury Yield",
        "^FVX": "US 5y Treasury Yield", "^IRX": "US 13w Treasury Bill",
        "ZB=F": "US Treasury Bond Futures", "ZN=F": "10-Year U.S. Treasury Note Futures",
    }
    return commodities, currencies, cryptos, bonds


def scan_tickers(tickers, limit, custom_names=None):
    """Lädt Ticker herunter und filtert nach festem Schwellenwert."""
    if not tickers:
        return pd.DataFrame(), pd.DataFrame()

    data = yf.download(
        tickers, period="2mo", interval="1wk", group_by="ticker", threads=True, progress=False
    )

    crashes = []
    spikes = []
    is_multi = len(tickers) > 1

    for ticker in tickers:
        try:
            if is_multi:
                if ticker not in data.columns.levels[0]:
                    continue
                df_ticker = data[ticker].dropna(subset=["Close"])
            else:
                df_ticker = data.dropna(subset=["Close"])

            if len(df_ticker) >= 2:
                prev_close = df_ticker["Close"].iloc[-2]
                curr_close = df_ticker["Close"].iloc[-1]
                pct_change = ((curr_close - prev_close) / prev_close) * 100

                display_name = custom_names.get(ticker, ticker) if custom_names else ticker

                item = {
                    "Ticker / Name": display_name,
                    "Vorheriger Schluss": round(prev_close, 2),
                    "Aktueller Schluss": round(curr_close, 2),
                    "Wochenänderung (%)": round(pct_change, 2),
                }

                if pct_change <= -limit:
                    crashes.append(item)
                elif pct_change >= limit:
                    spikes.append(item)
        except Exception:
            continue

    return pd.DataFrame(crashes), pd.DataFrame(spikes)


# Hauptlogik
if st.button("🚀 Scan starten", type="primary"):
    progress_bar = st.progress(0, text="Initialisiere Scan...")
    
    # Schritt 1: Ticker-Listen sammeln
    progress_bar.progress(10, text="Sammle S&P 500, DAX, MDAX und Dow Ticker...")
    sp500 = get_sp500_tickers()
    german_stocks = get_german_tickers()
    dow = get_dow_jones_tickers()
    stock_tickers = list(set(sp500 + german_stocks + dow))
    
    comm_dict, curr_dict, crypto_dict, bond_dict = get_macro_dictionaries()

    # Schritt 2: Aktien scannen
    progress_bar.progress(25, text=f"Lade Kursdaten für {len(stock_tickers)} Aktien...")
    df_c_stocks, df_s_stocks = scan_tickers(stock_tickers, THRESH_STOCKS)

    # Schritt 3: Rohstoffe scannen
    progress_bar.progress(45, text="Lade Rohstoffmärkte...")
    df_c_comm, df_s_comm = scan_tickers(list(comm_dict.keys()), THRESH_COMM, comm_dict)

    # Schritt 4: Währungen scannen
    progress_bar.progress(60, text="Lade Währungsmärkte (Forex)...")
    df_c_curr, df_s_curr = scan_tickers(list(curr_dict.keys()), THRESH_CURR, curr_dict)

    # Schritt 5: Kryptowährungen scannen
    progress_bar.progress(75, text="Lade Kryptowährungen...")
    df_c_crypto, df_s_crypto = scan_tickers(list(crypto_dict.keys()), THRESH_CRYPTO, crypto_dict)

    # Schritt 6: Bonds scannen
    progress_bar.progress(90, text="Lade Anleihen und Zinsen (Bonds)...")
    df_c_bond, df_s_bond = scan_tickers(list(bond_dict.keys()), THRESH_BONDS, bond_dict)

    # Abschluss
    progress_bar.progress(100, text="Daten erfolgreich analysiert!")
    
    # Ergebnisse zusammenführen
    df_crashes = pd.concat([df_c_stocks, df_c_comm, df_c_curr, df_c_crypto, df_c_bond], ignore_index=True)
    df_spikes = pd.concat([df_s_stocks, df_s_comm, df_s_curr, df_s_crypto, df_s_bond], ignore_index=True)
    
    progress_bar.empty()

    st.markdown("---")
    st.subheader("📉 Starke Einbrüche")
    if not df_crashes.empty:
        st.success(f"{len(df_crashes)} Werte gefunden.")
        st.dataframe(
            df_crashes.style.format({"Wochenänderung (%)": "{:.2f}%"})
            .background_gradient(subset=["Wochenänderung (%)"], cmap="Reds_r"),
            use_container_width=True,
        )
    else:
        st.info("Keine Werte mit den definierten Einbrüchen gefunden.")

    st.markdown("---")
    st.subheader("📈 Starke Ausbrüche")
    if not df_spikes.empty:
        st.success(f"{len(df_spikes)} Werte gefunden.")
        st.dataframe(
            df_spikes.style.format({"Wochenänderung (%)": "{:.2f}%"})
            .background_gradient(subset=["Wochenänderung (%)"], cmap="Greens"),
            use_container_width=True,
        )
    else:
        st.info("Keine Werte mit den definierten Anstiegen gefunden.")
