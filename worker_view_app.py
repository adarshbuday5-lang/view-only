import streamlit as st
import pandas as pd
from pathlib import Path

DATA_FILE = "rake_data.csv"

st.set_page_config(
    page_title="Rake Schedule View",
    page_icon="🚆",
    layout="wide"
)

st.title("🚆 Rake Unloading Schedule")
st.caption("View-only schedule for workers")

if not Path(DATA_FILE).exists():
    st.warning("No schedule data available.")

else:
    df = pd.read_csv(DATA_FILE)

    # --------------------------------
    # CREATE MISSING COLUMNS IF NEEDED
    # --------------------------------

    required_columns = [
        "Manual Sequence",
        "Scheduled Start",
        "Scheduled End",
        "Scheduled Tippler",
        "Scheduler Remarks"
    ]

    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    # --------------------------------
    # FILTER PENDING RAKES
    # --------------------------------

    if "Status" in df.columns:
        df = df[df["Status"] != "Completed"].copy()

    if df.empty:
        st.success("All rakes are completed.")

    else:

        df["Manual Sequence"] = pd.to_numeric(
            df["Manual Sequence"],
            errors="coerce"
        )

        df = df.sort_values(
            by=["Manual Sequence"],
            na_position="last"
        )

        st.subheader("Pending Rake Schedule")

        display_columns = [
            "Manual Sequence",
            "Rake ID",
            "Rake Type",
            "Arrival Time",
            "Scheduled Start",
            "Scheduled End",
            "Scheduled Tippler",
            "Priority",
            "Status",
            "Scheduler Remarks"
        ]

        available_columns = [
            col for col in display_columns
            if col in df.columns
        ]

        st.dataframe(
            df[available_columns],
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------
        # NEXT RAKE SECTION
        # ----------------------------

        if len(df) > 0:
            next_rake = df.iloc[0]

            st.markdown("---")
            st.subheader("Next Rake to Handle")

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Rake ID",
                str(next_rake.get("Rake ID", "N/A"))
            )

            col2.metric(
                "Tippler",
                str(next_rake.get("Scheduled Tippler", "N/A"))
            )

            col3.metric(
                "Status",
                str(next_rake.get("Status", "N/A"))
            )