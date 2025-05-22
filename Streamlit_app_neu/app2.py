# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
import sqlite3
import streamlit as st

# ---------------------------------------------------------------------------
# Basis‑Konfiguration & Pfade
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "einkauf.db"
CSV_PATH = BASE_DIR / "alle_Haeuser_2022-2025_synthetic_70000_clean.csv"

st.set_page_config(
    page_title="RoMed Klinik Einkauf",
    page_icon=":shopping_trolley:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Kleines CSS-Tuning ---------------------------------------------------------
CUSTOM_CSS = """
<style>
    div[data-testid="stMetric"] > div:nth-child(2) {
        font-size: 2rem;
    }
    section[data-testid="stSidebar"] h1 {
        font-size: 1.6rem;
        padding-bottom: .2rem;
        border-bottom: 1px solid #eee;
        margin-bottom: .5rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Datenbank-Initialisierung
# ---------------------------------------------------------------------------
def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS einkaeufe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Material TEXT,
            Materialkurztext TEXT,
            Werk TEXT,
            Kostenstelle TEXT,
            Kostenstellenbez TEXT,
            Menge REAL,
            Einzelpreis REAL,
            Warengruppe TEXT,
            Jahr INTEGER,
            Monat INTEGER,
            Lieferant TEXT,
            Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    if pd.read_sql("SELECT COUNT(*) AS cnt FROM einkaeufe", conn).iloc[0, 0] == 0:
        try:
            df_csv = pd.read_csv(CSV_PATH)
            df_csv = df_csv.rename(columns={
                "Menge Ausw.-Zr": "Menge",
                "Wert Ausw.-Zr": "Wert",
                "Name Regellieferant": "Lieferant",
            })
            with st.spinner("Importiere Basisdaten …"):
                df_csv.to_sql("einkaeufe", conn, if_exists="append", index=False, method="multi")
        except FileNotFoundError:
            st.error(":x: CSV-Datei nicht gefunden. Bitte sicherstellen, dass sie im Projektverzeichnis liegt.")
        except Exception as e:
            st.error(f":x: Fehler beim CSV-Import: {e}")
    conn.close()

@st.cache_data(ttl=120)
def get_all_data() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql("SELECT * FROM einkaeufe", conn)

init_db()

# ---------------------------------------------------------------------------
# Sidebar – Navigation
# ---------------------------------------------------------------------------
st.sidebar.title(":pushpin: Navigation")
page = st.sidebar.radio(
    label="",
    options=(
        ":house: Start",
        ":bar_chart: Analyse",
        ":heavy_plus_sign: Einkauf erfassen",
        ":open_file_folder: Alle Einkäufe",
        ":wastebasket: Einkauf löschen",
    ),
    label_visibility="collapsed",
)

# ---------------------------------------------------------------------------
# Seite: Start
# ---------------------------------------------------------------------------
if page.startswith(":house:"):
    st.header(":shopping_trolley: RoMed Klinik Einkaufs-App")
    st.markdown("""
Willkommen! Mit dieser App kannst du:

- **Einkaufsdaten analysieren** :bar_chart:
- **neue Bestellungen erfassen** :heavy_plus_sign:
- **alle Transaktionen einsehen** :open_file_folder:
- **Einkäufe löschen** :wastebasket:

_Datenquelle:_ automatisch importierte CSV-Datei (2022–2025).
    """)

# ---------------------------------------------------------------------------
# Seite: Analyse
# ---------------------------------------------------------------------------
elif page.startswith(":bar_chart:"):
    st.header(":bar_chart: Analyse der Einkaufsdaten")
    df = get_all_data()

    with st.sidebar.expander(":mag_right: Filter", expanded=True):
        kostenstellen = st.multiselect("Kostenstellenbez.", sorted(df["Kostenstellenbez"].dropna().unique()))
        warengruppen = st.multiselect("Warengruppe", sorted(df["Warengruppe"].dropna().unique()))
        lieferanten = st.multiselect("Lieferant", sorted(df["Lieferant"].dropna().unique()))

    mask = pd.Series(True, index=df.index)
    if kostenstellen:
        mask &= df["Kostenstellenbez"].isin(kostenstellen)
    if warengruppen:
        mask &= df["Warengruppe"].isin(warengruppen)
    if lieferanten:
        mask &= df["Lieferant"].isin(lieferanten)

    df_filtered = df[mask]
    gesamt = (df_filtered["Einzelpreis"] * df_filtered["Menge"]).sum()
    artikelanzahl = df_filtered["Material"].nunique()
    avg_preis = gesamt / df_filtered["Menge"].sum() if df_filtered["Menge"].sum() > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Gesamtkosten", f"{gesamt:,.0f} €")
    col2.metric("Artikelanzahl", f"{artikelanzahl}")
    col3.metric("Ø Einzelpreis", f"{avg_preis:,.2f} €")

    with st.expander(":mag: Gefilterte Datensätze"):
        st.dataframe(df_filtered, use_container_width=True, height=400)

# ---------------------------------------------------------------------------
# Seite: Einkauf erfassen + CSV Upload + Beispiel-CSV
# ---------------------------------------------------------------------------
elif page.startswith(":heavy_plus_sign:"):
    st.header(":heavy_plus_sign: Neuen Einkauf erfassen")
    with st.form("einkauf_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            material = st.text_input("Materialnummer", placeholder="z. B. 12345678")
            materialkurz = st.text_input("Materialkurztext", placeholder="z. B. Tupfer steril")
            werk = st.text_input("Werk", placeholder="z. B. ROMS")
        with col2:
            kostenstelle = st.text_input("Kostenstelle", placeholder="z. B. 100010")
            kostenbez = st.text_input("Kostenstellenbez.", placeholder="z. B. Station 3A")
            warengruppe = st.text_input("Warengruppe", placeholder="z. B. Hygienebedarf")
        with col3:
            menge = st.number_input("Menge", min_value=0.0, step=1.0, value=1.0)
            einzelpreis = st.number_input("Einzelpreis (€)", min_value=0.0, step=0.01)
            lieferant = st.text_input("Lieferant", placeholder="z. B. Hartmann")
        datum = st.date_input("Buchungsmonat", value=datetime.today().replace(day=1))
        jahr, monat = datum.year, datum.month

        submitted = st.form_submit_button(":floppy_disk: Speichern")
        if submitted:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                """
                INSERT INTO einkaeufe (
                    Material, Materialkurztext, Werk,
                    Kostenstelle, Kostenstellenbez,
                    Menge, Einzelpreis, Warengruppe,
                    Jahr, Monat, Lieferant
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    material, materialkurz, werk,
                    kostenstelle, kostenbez,
                    menge, einzelpreis, warengruppe,
                    jahr, monat, lieferant
                ),
            )
            conn.commit()
            conn.close()
            st.success(":white_check_mark: Einkauf erfolgreich gespeichert.")

    # ---------------- CSV Upload mit Optionen ----------------
    st.markdown("---")
    st.subheader("Weitere Einkäufe per CSV-Datei hochladen")

    upload_mode = st.radio(
        "Was soll beim Hochladen passieren?",
        options=[
            "Nur hinzufügen (keine Prüfung)",
            "Nur neue Datensätze einfügen (Dubletten vermeiden)",
            "Vorhandene Datensätze aktualisieren (nach Schlüssel)"
        ]
    )

    uploaded_file = st.file_uploader("CSV-Datei auswählen", type=["csv"])
    if uploaded_file:
        try:
            df_upload = pd.read_csv(uploaded_file)
            df_upload = df_upload.rename(columns={
                "Menge Ausw.-Zr": "Menge",
                "Wert Ausw.-Zr": "Wert",
                "Name Regellieferant": "Lieferant",
            })
            required_cols = {"Material", "Materialkurztext", "Werk", "Kostenstelle", "Kostenstellenbez", "Menge", "Einzelpreis", "Warengruppe", "Jahr", "Monat", "Lieferant"}
            if not required_cols.issubset(df_upload.columns):
                st.error(f":x: CSV-Datei fehlt eine oder mehrere notwendige Spalten: {required_cols - set(df_upload.columns)}")
            else:
                with sqlite3.connect(DB_PATH) as conn:
                    if upload_mode == "Nur hinzufügen (keine Prüfung)":
                        df_upload.to_sql("einkaeufe", conn, if_exists="append", index=False, method="multi")
                        st.success(":white_check_mark: Daten erfolgreich hinzugefügt.")
                    else:
                        db_data = pd.read_sql("SELECT * FROM einkaeufe", conn)
                        key_cols = ["Material", "Kostenstelle", "Jahr", "Monat"]

                        df_upload["merge_key"] = df_upload[key_cols].astype(str).agg("_".join, axis=1)
                        db_data["merge_key"] = db_data[key_cols].astype(str).agg("_".join, axis=1)

                        if upload_mode == "Nur neue Datensätze einfügen (Dubletten vermeiden)":
                            df_filtered = df_upload[~df_upload["merge_key"].isin(db_data["merge_key"])]
                            df_filtered.drop(columns=["merge_key"], inplace=True)
                            df_filtered.to_sql("einkaeufe", conn, if_exists="append", index=False, method="multi")
                            st.success(f":white_check_mark: {len(df_filtered)} neue Datensätze eingefügt.")
                        elif upload_mode == "Vorhandene Datensätze aktualisieren (nach Schlüssel)":
                            updated = 0
                            for _, row in df_upload.iterrows():
                                key_values = tuple(row[k] for k in key_cols)
                                exists = conn.execute(
                                    f"SELECT COUNT(*) FROM einkaeufe WHERE Material=? AND Kostenstelle=? AND Jahr=? AND Monat=?", key_values
                                ).fetchone()[0]
                                if exists:
                                    conn.execute(
                                        """
                                        UPDATE einkaeufe SET
                                            Materialkurztext = ?, Werk = ?, Kostenstellenbez = ?,
                                            Menge = ?, Einzelpreis = ?, Warengruppe = ?, Lieferant = ?
                                        WHERE Material = ? AND Kostenstelle = ? AND Jahr = ? AND Monat = ?
                                        """,
                                        (
                                            row["Materialkurztext"], row["Werk"], row["Kostenstellenbez"],
                                            row["Menge"], row["Einzelpreis"], row["Warengruppe"], row["Lieferant"],
                                            *key_values
                                        )
                                    )
                                    updated += 1
                                else:
                                    row.drop(labels=["merge_key"], errors="ignore", inplace=True)
                                    row.to_frame().T.to_sql("einkaeufe", conn, if_exists="append", index=False)
                            conn.commit()
                            st.success(f":white_check_mark: {updated} Datensätze aktualisiert oder eingefügt.")
        except Exception as e:
            st.error(f":x: Fehler beim Verarbeiten der Datei: {e}")

    # Beispiel-CSV zum Download
    st.markdown("---")
    st.subheader("📄 Beispiel-CSV herunterladen")
    example_data = pd.DataFrame([{
        "Material": "12345678",
        "Materialkurztext": "Tupfer steril",
        "Werk": "ROMS",
        "Kostenstelle": "100010",
        "Kostenstellenbez": "Station 3A",
        "Menge": 10,
        "Einzelpreis": 2.50,
        "Warengruppe": "Hygienebedarf",
        "Jahr": 2025,
        "Monat": 5,
        "Lieferant": "Hartmann"
    }])
    st.download_button(
        label="📥 Beispiel-CSV herunterladen",
        data=example_data.to_csv(index=False).encode("utf-8"),
        file_name="beispiel_einkauf.csv",
        mime="text/csv"
    )

# ---------------------------------------------------------------------------
# Seite: Alle Einkäufe
# ---------------------------------------------------------------------------
elif page.startswith(":open_file_folder:"):
    st.header(":open_file_folder: Alle Einkäufe")
    df = get_all_data()
    st.dataframe(df, use_container_width=True, height=500)

# ---------------------------------------------------------------------------
# Seite: Einkauf löschen
# ---------------------------------------------------------------------------
elif page.startswith(":wastebasket:"):
    st.header(":wastebasket: Einkauf löschen")
    df = get_all_data().sort_values("Timestamp", ascending=False).reset_index(drop=True)

    st.info("Wähle eine ID, um den entsprechenden Einkauf zu löschen.")
    selected_id = st.selectbox("ID auswählen", df["id"])

    if selected_id:
        record = df[df["id"] == selected_id].iloc[0]
        st.write(f"**Material:** {record['Material']} – {record['Materialkurztext']}")
        st.write(f"**Kostenstelle:** {record['Kostenstellenbez']} • **Lieferant:** {record['Lieferant']}")
        st.write(f"**Einzelpreis:** {record['Einzelpreis']} € • **Menge:** {record['Menge']}")

        if st.button(":x: Einkauf wirklich löschen?"):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM einkaeufe WHERE id = ?", (int(selected_id),))
            conn.commit()
            conn.close()
            st.success(":white_check_mark: Einkauf gelöscht. Bitte Seite neu laden, um die Tabelle zu aktualisieren.")
