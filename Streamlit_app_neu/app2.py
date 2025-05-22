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
DB_PATH = BASE_DIR / "einkauf.db3"
# Ensure the CSV exists or handle its absence gracefully
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
    # Check if the table is empty before attempting import
    if pd.read_sql("SELECT COUNT(*) AS cnt FROM einkaeufe", conn).iloc[0, 0] == 0:
        if CSV_PATH.exists(): # Check if CSV file actually exists
            try:
                df_csv = pd.read_csv(CSV_PATH)
                df_csv = df_csv.rename(columns={
                    "Menge Ausw.-Zr": "Menge",
                    "Wert Ausw.-Zr": "Wert",
                    "Name Regellieferant": "Lieferant",
                    "Kostenstellenbez.": "Kostenstellenbez", # FIX: Added mapping for column with period from CSV
                })
                # Ensure all necessary columns exist after renaming
                required_cols = {"Material", "Materialkurztext", "Werk", "Kostenstelle", 
                                 "Kostenstellenbez", "Menge", "Einzelpreis", 
                                 "Warengruppe", "Jahr", "Monat", "Lieferant"}
                
                # Check for missing required columns after potential renames
                missing_cols = required_cols - set(df_csv.columns)
                if missing_cols:
                    st.error(f":x: Die Initial-CSV-Datei '{CSV_PATH.name}' fehlt eine oder mehrere notwendige Spalten für den Import: {', '.join(missing_cols)}. Bitte korrigieren Sie die CSV-Datei.")
                else:
                    with st.spinner(f"Importiere Basisdaten von {CSV_PATH.name} …"):
                        # FIX: Removed method="multi" to avoid "too many SQL variables" error
                        df_csv.to_sql("einkaeufe", conn, if_exists="append", index=False)
                    st.success(":white_check_mark: Basisdaten erfolgreich importiert.")
            except Exception as e:
                st.error(f":x: Fehler beim CSV-Import der Initialdatei: {e}")
        else:
            st.warning(f":exclamation: Initial-CSV-Datei '{CSV_PATH.name}' nicht gefunden. Die Datenbank wurde leer initialisiert.")
    conn.close()

@st.cache_data(ttl=120)
def get_all_data() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql("SELECT * FROM einkaeufe", conn)

# Initialize the database when the app starts
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

_Datenquelle:_ Die App versucht, eine `alle_Haeuser_2022-2025_synthetic_70000_clean.csv`-Datei im selben Verzeichnis beim ersten Start automatisch zu importieren.
    """)

# ---------------------------------------------------------------------------
# Seite: Analyse
# ---------------------------------------------------------------------------
elif page.startswith(":bar_chart:"):
    st.header(":bar_chart: Analyse der Einkaufsdaten")
    df = get_all_data()

    if df.empty:
        st.info("Keine Daten zum Analysieren vorhanden. Bitte erfassen Sie zuerst Einkäufe.")
    else:
        with st.sidebar.expander(":mag_right: Filter", expanded=True):
            # Use .dropna() to handle potential NaN values in selectbox options
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
        
        if df_filtered.empty:
            st.warning("Keine Daten gefunden, die den angewendeten Filtern entsprechen.")
        else:
            gesamt = (df_filtered["Einzelpreis"] * df_filtered["Menge"]).sum()
            artikelanzahl = df_filtered["Material"].nunique()
            # Calculate average price correctly even if Menge sum is zero
            avg_preis = gesamt / df_filtered["Menge"].sum() if df_filtered["Menge"].sum() > 0 else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Gesamtkosten", f"{gesamt:,.2f} €") # Added .2f for currency formatting
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
            # Basic validation for required fields
            if not all([material, materialkurz, werk, kostenstelle, kostenbez, warengruppe, lieferant]):
                st.warning("Bitte füllen Sie alle Textfelder aus.")
            elif menge <= 0 or einzelpreis <= 0:
                st.warning("Menge und Einzelpreis müssen größer als Null sein.")
            else:
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
                # Clear cache to ensure new data is reflected in "Alle Einkäufe" and "Analyse"
                st.cache_data.clear()

    # ---------------- CSV Upload mit Optionen ----------------
    st.markdown("---")
    st.subheader("Weitere Einkäufe per CSV-Datei hochladen")

    upload_mode = st.radio(
        "Was soll beim Hochladen passieren?",
        options=[
            "Nur hinzufügen (keine Prüfung)",
            "Nur neue Datensätze einfügen (Dubletten vermeiden)",
            "Vorhandene Datensätze aktualisieren (nach Schlüssel)"
        ],
        key="upload_mode_radio" # Added a key to avoid potential conflicts
    )

    uploaded_file = st.file_uploader("CSV-Datei auswählen", type=["csv"])
    if uploaded_file:
        try:
            df_upload = pd.read_csv(uploaded_file)
            df_upload = df_upload.rename(columns={
                "Menge Ausw.-Zr": "Menge",
                "Wert Ausw.-Zr": "Wert", # 'Wert' column isn't used in the DB, but renaming it is fine.
                "Name Regellieferant": "Lieferant",
                "Kostenstellenbez.": "Kostenstellenbez", # FIX: Added mapping for column with period from CSV
            })
            
            # Define required columns for CSV upload
            required_cols_upload = {"Material", "Materialkurztext", "Werk", "Kostenstelle", 
                                    "Kostenstellenbez", "Menge", "Einzelpreis", 
                                    "Warengruppe", "Jahr", "Monat", "Lieferant"}
            
            missing_cols_upload = required_cols_upload - set(df_upload.columns)
            if missing_cols_upload:
                st.error(f":x: Die hochgeladene CSV-Datei fehlt eine oder mehrere notwendige Spalten: {', '.join(missing_cols_upload)}")
            else:
                # Type conversion for consistency and robustness
                df_upload["Menge"] = pd.to_numeric(df_upload["Menge"], errors='coerce')
                df_upload["Einzelpreis"] = pd.to_numeric(df_upload["Einzelpreis"], errors='coerce')
                # FIX: Use nullable integer dtype for Jahr and Monat to handle potential NaNs
                df_upload["Jahr"] = pd.to_numeric(df_upload["Jahr"], errors='coerce').astype(pd.Int64Dtype()) 
                df_upload["Monat"] = pd.to_numeric(df_upload["Monat"], errors='coerce').astype(pd.Int64Dtype()) 

                # Drop rows where critical numeric conversions failed (e.g., NaN for Menge/Einzelpreis/Jahr/Monat)
                df_upload.dropna(subset=["Menge", "Einzelpreis", "Jahr", "Monat"], inplace=True)
                
                # FIX: If, after dropping, the DataFrame is empty, we should exit gracefully
                if df_upload.empty:
                    st.warning("Die hochgeladene CSV-Datei enthält nach der Bereinigung keine gültigen Datensätze zum Importieren.")
                    st.stop() # FIX: Changed from return to st.stop() for Streamlit script execution
                
                with sqlite3.connect(DB_PATH) as conn:
                    if upload_mode == "Nur hinzufügen (keine Prüfung)":
                        # FIX: Removed method="multi" for CSV upload too, for consistency and robustness
                        df_upload.to_sql("einkaeufe", conn, if_exists="append", index=False)
                        st.success(f":white_check_mark: {len(df_upload)} Datensätze erfolgreich hinzugefügt.")
                    else:
                        db_data = pd.read_sql("SELECT * FROM einkaeufe", conn)
                        key_cols = ["Material", "Kostenstelle", "Jahr", "Monat"]

                        # FIX: More robust merge_key creation using fillna('') and apply
                        # Convert to string and fill any potential NaNs with empty strings before joining
                        df_upload["merge_key"] = df_upload[key_cols].astype(str).fillna('').apply(lambda x: "_".join(x), axis=1)
                        db_data["merge_key"] = db_data[key_cols].astype(str).fillna('').apply(lambda x: "_".join(x), axis=1)

                        if upload_mode == "Nur neue Datensätze einfügen (Dubletten vermeiden)":
                            df_filtered = df_upload[~df_upload["merge_key"].isin(db_data["merge_key"])]
                            df_filtered = df_filtered.drop(columns=["merge_key"]) # Safer way than inplace
                            
                            if not df_filtered.empty:
                                df_filtered.to_sql("einkaeufe", conn, if_exists="append", index=False)
                                st.success(f":white_check_mark: {len(df_filtered)} neue Datensätze eingefügt.")
                            else:
                                st.info("Keine neuen Datensätze zum Einfügen gefunden (alle sind bereits vorhanden oder ungültig).")
                                
                        elif upload_mode == "Vorhandene Datensätze aktualisieren (nach Schlüssel)":
                            updated_count = 0
                            inserted_count = 0
                            
                            # Identify records that exist in both (for update)
                            df_to_update = df_upload[df_upload["merge_key"].isin(db_data["merge_key"])]
                            
                            # Identify records that are new (for insert)
                            df_to_insert = df_upload[~df_upload["merge_key"].isin(db_data["merge_key"])]
                            
                            # Process updates
                            for _, row in df_to_update.iterrows():
                                key_values = tuple(row[k] for k in key_cols)
                                # Update statement
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
                                        *key_values # Unpack key values for WHERE clause
                                    )
                                )
                                updated_count += 1
                                
                            # Process inserts for truly new records
                            if not df_to_insert.empty:
                                df_to_insert = df_to_insert.drop(columns=["merge_key"]) # Safer way than inplace
                                inserted_count = len(df_to_insert)
                                df_to_insert.to_sql("einkaeufe", conn, if_exists="append", index=False)
                                
                            conn.commit()
                            st.success(f":white_check_mark: {updated_count} Datensätze aktualisiert und {inserted_count} neue Datensätze eingefügt.")
                
                # Clear cache after successful upload to refresh displayed data
                st.cache_data.clear()

        except Exception as e:
            st.error(f":x: Fehler beim Verarbeiten der hochgeladenen Datei: {e}")
        finally:
            # Optionally clear the file uploader after processing. 
            # This generally requires Streamlit's session state, which is a bit more complex for a simple code update.
            # For direct code replacement, we'll keep it as is, but it's a UX improvement to consider.
            pass


    # Beispiel-CSV zum Download
    st.markdown("---")
    st.subheader("📄 Beispiel-CSV herunterladen")
    example_data = pd.DataFrame([{
        "Material": "12345678",
        "Materialkurztext": "Tupfer steril",
        "Werk": "ROMS",
        "Kostenstelle": "100010",
        "Kostenstellenbez.": "Station 3A", # IMPORTANT: Column name with period to match the provided CSV format
        "Menge Ausw.-Zr": 10, # Renamed to match the expected input CSV column
        "Wert Ausw.-Zr": 25.00, # Added for completeness of example input, though not stored in DB
        "Einzelpreis": 2.50,
        "Warengruppe": "Hygienebedarf",
        "Jahr": 2025,
        "Monat": 5,
        "Name Regellieferant": "Hartmann" # Renamed to match the expected input CSV column
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
    if df.empty:
        st.info("Keine Einkäufe vorhanden.")
    else:
        st.dataframe(df, use_container_width=True, height=500)

# ---------------------------------------------------------------------------
# Seite: Einkauf löschen
# ---------------------------------------------------------------------------
elif page.startswith(":wastebasket:"):
    st.header(":wastebasket: Einkauf löschen")
    df = get_all_data().sort_values("Timestamp", ascending=False).reset_index(drop=True)

    if df.empty:
        st.info("Keine Einkäufe zum Löschen vorhanden.")
    else:
        # Create a display string for better readability in selectbox
        df["display_string"] = df.apply(lambda row: f"ID: {row['id']} | Material: {row['Materialkurztext']} | KO: {row['Kostenstellenbez']} | Lieferant: {row['Lieferant']} ({row['Jahr']}/{row['Monat']})", axis=1)
        
        selected_display = st.selectbox(
            "Einkauf zum Löschen auswählen", 
            df["display_string"], 
            index=0 # Select the first item by default if available
        )

        if selected_display:
            # Extract the ID from the display string
            selected_id = int(selected_display.split(" |")[0].replace("ID: ", ""))
            
            record = df[df["id"] == selected_id].iloc[0]
            st.write(f"**Material:** {record['Material']} – {record['Materialkurztext']}")
            st.write(f"**Kostenstelle:** {record['Kostenstellenbez']} • **Lieferant:** {record['Lieferant']}")
            st.write(f"**Einzelpreis:** {record['Einzelpreis']:,.2f} € • **Menge:** {record['Menge']:,.0f}") # Formatted for clarity

            if st.button(":x: Einkauf wirklich löschen?", key="delete_button"): # Added key to avoid warning
                conn = sqlite3.connect(DB_PATH)
                conn.execute("DELETE FROM einkaeufe WHERE id = ?", (int(selected_id),))
                conn.commit()
                conn.close()
                st.success(":white_check_mark: Einkauf erfolgreich gelöscht.")
                
                # FIX: Invalidate cache and rerun the app to immediately reflect changes
                st.cache_data.clear() 
                st.rerun()
