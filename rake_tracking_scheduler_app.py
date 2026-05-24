import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path

# -----------------------------------
# CONFIGURATION
# -----------------------------------

DATA_FILE = "rake_data.csv"
TARGET_CYCLE_HOURS = 7

st.set_page_config(
    page_title="Rake Tracking System",
    page_icon="🚆",
    layout="wide"
)

# -----------------------------------
# LOAD DATA
# -----------------------------------

def load_data():
    if Path(DATA_FILE).exists():
        df = pd.read_csv(DATA_FILE)

        date_columns = [
            "Arrival Time",
            "Placement Time",
            "Unloading Start",
            "Unloading End"
        ]

        for col in date_columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

        return df

    else:
        return pd.DataFrame(columns=[
            "Rake ID",
            "Coal Type",
            "Rake Type",
            "Source",
            "Arrival Time",
            "Placement Time",
            "Unloading Start",
            "Unloading End",
            "Tippler",
            "Priority",
            "Status",
            "Delay Reason",
            "Remarks"
        ])

df = load_data()

# -----------------------------------
# CALCULATIONS
# -----------------------------------

def calculate_cycle_hours(row):
    if pd.notna(row["Arrival Time"]) and pd.notna(row["Unloading End"]):
        return round(
            (row["Unloading End"] - row["Arrival Time"]).total_seconds() / 3600,
            2
        )
    return None

df["Cycle Hours"] = df.apply(calculate_cycle_hours, axis=1)

def get_delay_status(hours):
    if pd.isna(hours):
        return "In Progress"
    elif hours <= TARGET_CYCLE_HOURS:
        return "On Time"
    else:
        return "Delayed"

df["Delay Status"] = df["Cycle Hours"].apply(get_delay_status)

# -----------------------------------
# SIDEBAR
# -----------------------------------

st.sidebar.title("🚆 Rake Tracking")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Scheduler", "Raw Data"]
)

# -----------------------------------
# DASHBOARD
# -----------------------------------

if page == "Dashboard":

    st.title("Coal Handling Plant Rake Tracking Dashboard")

    total_rakes = len(df)
    delayed = len(df[df["Delay Status"] == "Delayed"])
    completed = len(df[df["Status"] == "Completed"])
    in_progress = total_rakes - completed

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Rakes", total_rakes)
    col2.metric("Completed", completed)
    col3.metric("In Progress", in_progress)
    col4.metric("Delayed", delayed)

    st.markdown("---")

    st.subheader("Live Rake Status")

    st.dataframe(
        df[[
            "Rake ID",
            "Rake Type",
            "Arrival Time",
            "Tippler",
            "Priority",
            "Status",
            "Cycle Hours",
            "Delay Status",
            "Delay Reason"
        ]],
        use_container_width=True
    )

    st.markdown("---")

    st.subheader("Delay Reason Analysis")

    delay_summary = (
        df["Delay Reason"]
        .fillna("Not Available")
        .value_counts()
    )

    st.bar_chart(delay_summary)

# -----------------------------------
# SCHEDULER
# -----------------------------------

elif page == "Scheduler":

    st.title("Rake Scheduler")

    pending_df = df[df["Status"] != "Completed"].copy()

    priority_map = {
        "High": 1,
        "Medium": 2,
        "Low": 3
    }

    pending_df["Priority Rank"] = pending_df["Priority"].map(priority_map)

    pending_df = pending_df.sort_values(
        by=["Priority Rank", "Arrival Time"]
    )

    pending_df["Suggested Sequence"] = range(
        1,
        len(pending_df) + 1
    )

    st.subheader("Recommended Unloading Sequence")

    st.dataframe(
        pending_df[[
            "Suggested Sequence",
            "Rake ID",
            "Rake Type",
            "Arrival Time",
            "Priority",
            "Tippler",
            "Status"
        ]],
        use_container_width=True
    )

    st.markdown("---")

    st.info(
        "Current scheduling logic uses priority and arrival time. "
        "Later you can add AI scheduling, tippler utilization, "
        "real-time CHP data, and predictive delay alerts."
    )

# -----------------------------------
# RAW DATA
# -----------------------------------

elif page == "Raw Data":

    st.title("Raw Rake Data")

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="rake_data_export.csv",
        mime="text/csv"
    )