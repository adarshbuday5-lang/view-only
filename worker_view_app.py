import streamlit as st
import pandas as pd
import simpy
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# =========================================================
# PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="CHP Digital Twin Simulation",
    page_icon="🚂",
    layout="wide"
)

# =========================================================
# CUSTOM CSS
# =========================================================
st.markdown("""
<style>
    .main {
        background-color: #f7f9fc;
    }

    .big-title {
        font-size: 34px;
        font-weight: 800;
        color: #1f2937;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 17px;
        color: #4b5563;
        margin-bottom: 25px;
    }

    .section-box {
        background-color: white;
        padding: 22px;
        border-radius: 16px;
        box-shadow: 0px 4px 14px rgba(0,0,0,0.08);
        margin-bottom: 20px;
    }

    .info-box {
        background-color: #eef6ff;
        color: #1e3a8a;
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #2563eb;
        margin-bottom: 18px;
    }

    .success-box {
        background-color: #ecfdf5;
        color: #065f46;
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #10b981;
        font-weight: 600;
    }

    .danger-box {
        background-color: #fef2f2;
        color: #991b1b;
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #ef4444;
        font-weight: 600;
    }

    .warning-box {
        background-color: #fffbeb;
        color: #92400e;
        padding: 16px;
        border-radius: 12px;
        border-left: 6px solid #f59e0b;
        font-weight: 600;
    }

    .metric-card {
        background-color: white;
        padding: 18px;
        border-radius: 14px;
        box-shadow: 0px 3px 10px rgba(0,0,0,0.08);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="big-title">🚂 CHP Digital Twin Simulation for Rake Congestion</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Predictive decision-support system for rake scheduling, unloading delay, and congestion control.</div>',
    unsafe_allow_html=True
)

# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title("⚙️ Simulation Settings")

target_cycle_time = st.sidebar.number_input(
    "Target Cycle Time / UCL in Hours",
    min_value=1.0,
    max_value=48.0,
    value=7.0,
    step=0.5
)

simulation_hours = st.sidebar.number_input(
    "Simulation Horizon in Hours",
    min_value=4,
    max_value=72,
    value=24,
    step=1
)

tippler_capacity = st.sidebar.number_input(
    "Available Wagon Tipplers",
    min_value=1,
    max_value=3,
    value=1,
    step=1
)

sticky_coal_extra_delay = st.sidebar.number_input(
    "Extra Delay for Sticky Coal in Hours",
    min_value=0.0,
    max_value=10.0,
    value=2.0,
    step=0.5
)

chp_interruption_delay = st.sidebar.number_input(
    "Extra Delay for CHP Interruption in Hours",
    min_value=0.0,
    max_value=10.0,
    value=1.5,
    step=0.5
)

st.sidebar.markdown("---")
st.sidebar.info(
    "Arrival_Time should be entered as hours from current time. "
    "Example: 0 = now, 1 = after 1 hour, 2.5 = after 2.5 hours."
)

# =========================================================
# SAMPLE DATA
# =========================================================
def create_sample_data():
    data = pd.DataFrame({
        "Rake_ID": ["R1", "R2", "R3", "R4", "New_Rake"],
        "Arrival_Time": [0, 1, 2, 4, 5],
        "Unloading_Time": [5, 5, 6, 5, 5],
        "Sticky_Coal": ["No", "Yes", "No", "No", "Yes"],
        "CHP_Interruption": ["No", "No", "Yes", "No", "No"],
        "Siding": ["Siding 1", "Siding 2", "Siding 1", "Siding 2", "Siding 2"],
        "Rake_Type": ["BOXN", "BOXN", "BOXN", "BOBR", "BOXN"]
    })
    return data

# =========================================================
# FILE UPLOAD SECTION
# =========================================================
st.markdown('<div class="section-box">', unsafe_allow_html=True)

st.subheader("📂 Upload Rake Schedule Data")

st.markdown("""
<div class="info-box">
<b>Required columns:</b> Rake_ID, Arrival_Time, Unloading_Time<br>
<b>Optional columns:</b> Sticky_Coal, CHP_Interruption, Siding, Rake_Type<br><br>
Upload file as <b>CSV UTF-8</b> or <b>Excel (.xlsx)</b>.
</div>
""", unsafe_allow_html=True)

use_sample = st.checkbox("Use sample data instead of uploading file")

uploaded_file = st.file_uploader(
    "Upload CSV or Excel file",
    type=["csv", "xlsx"]
)

if use_sample:
    rake_data = create_sample_data()
elif uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            rake_data = pd.read_csv(uploaded_file)
        else:
            rake_data = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Error reading file: {e}")
        rake_data = None
else:
    rake_data = None

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# DATA VALIDATION
# =========================================================
def validate_data(df):
    required_columns = ["Rake_ID", "Arrival_Time", "Unloading_Time"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        return False, missing_columns

    return True, []

# =========================================================
# SIMULATION PROCESS
# =========================================================
def rake_process(
    env,
    rake_id,
    tippler,
    arrival_time,
    unloading_time,
    sticky_coal,
    chp_interruption,
    siding,
    rake_type,
    results,
    sticky_delay,
    chp_delay
):
    yield env.timeout(arrival_time)

    arrival = env.now

    adjusted_unloading_time = unloading_time

    if str(sticky_coal).strip().lower() == "yes":
        adjusted_unloading_time += sticky_delay

    if str(chp_interruption).strip().lower() == "yes":
        adjusted_unloading_time += chp_delay

    with tippler.request() as request:
        yield request

        start_unloading = env.now
        waiting_time = start_unloading - arrival

        yield env.timeout(adjusted_unloading_time)

        end_unloading = env.now
        cycle_time = end_unloading - arrival

        results.append({
            "Rake_ID": rake_id,
            "Rake_Type": rake_type,
            "Siding": siding,
            "Arrival_Time": round(arrival, 2),
            "Start_Unloading": round(start_unloading, 2),
            "End_Unloading": round(end_unloading, 2),
            "Base_Unloading_Time": round(unloading_time, 2),
            "Adjusted_Unloading_Time": round(adjusted_unloading_time, 2),
            "Waiting_Time": round(waiting_time, 2),
            "Cycle_Time": round(cycle_time, 2),
            "Sticky_Coal": sticky_coal,
            "CHP_Interruption": chp_interruption
        })

# =========================================================
# RUN SIMULATION FUNCTION
# =========================================================
def run_simulation(
    df,
    tippler_capacity,
    simulation_hours,
    sticky_delay,
    chp_delay
):
    env = simpy.Environment()
    tippler = simpy.Resource(env, capacity=tippler_capacity)

    results = []

    for _, row in df.iterrows():
        rake_id = row["Rake_ID"]
        arrival_time = float(row["Arrival_Time"])
        unloading_time = float(row["Unloading_Time"])

        sticky_coal = row["Sticky_Coal"] if "Sticky_Coal" in df.columns else "No"
        chp_interruption = row["CHP_Interruption"] if "CHP_Interruption" in df.columns else "No"
        siding = row["Siding"] if "Siding" in df.columns else "Not Assigned"
        rake_type = row["Rake_Type"] if "Rake_Type" in df.columns else "Not Given"

        env.process(
            rake_process(
                env,
                rake_id,
                tippler,
                arrival_time,
                unloading_time,
                sticky_coal,
                chp_interruption,
                siding,
                rake_type,
                results,
                sticky_delay,
                chp_delay
            )
        )

    env.run(until=simulation_hours)

    result_df = pd.DataFrame(results)

    return result_df

# =========================================================
# MAIN DASHBOARD
# =========================================================
if rake_data is not None:

    is_valid, missing = validate_data(rake_data)

    if not is_valid:
        st.error(f"Missing required columns: {missing}")

    else:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.subheader("📊 Input Rake Data")
        st.dataframe(rake_data, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        run_button = st.button("▶️ Run Digital Twin Simulation", use_container_width=True)

        if run_button:

            result = run_simulation(
                rake_data,
                tippler_capacity,
                simulation_hours,
                sticky_coal_extra_delay,
                chp_interruption_delay
            )

            if result.empty:
                st.warning("No rakes were processed within the selected simulation horizon.")
            else:
                result["Decision"] = result["Cycle_Time"].apply(
                    lambda x: "Allow Entry" if x <= target_cycle_time else "Delayed Arrival"
                )

                result["Delay_Status"] = result["Cycle_Time"].apply(
                    lambda x: "Within Target" if x <= target_cycle_time else "Above Target"
                )

                delayed_count = (result["Decision"] == "Delayed Arrival").sum()
                allowed_count = (result["Decision"] == "Allow Entry").sum()
                avg_cycle_time = result["Cycle_Time"].mean()
                avg_waiting_time = result["Waiting_Time"].mean()
                max_cycle_time = result["Cycle_Time"].max()

                # =========================================================
                # KPI CARDS
                # =========================================================
                st.markdown('<div class="section-box">', unsafe_allow_html=True)
                st.subheader("📌 Simulation KPI Summary")

                col1, col2, col3, col4, col5 = st.columns(5)

                col1.metric("Total Rakes Simulated", len(result))
                col2.metric("Allowed Rakes", allowed_count)
                col3.metric("Delayed Rakes", delayed_count)
                col4.metric("Avg Cycle Time", f"{avg_cycle_time:.2f} hrs")
                col5.metric("Avg Waiting Time", f"{avg_waiting_time:.2f} hrs")

                st.markdown('</div>', unsafe_allow_html=True)

                # =========================================================
                # FINAL DECISION FOR LAST RAKE
                # =========================================================
                st.markdown('<div class="section-box">', unsafe_allow_html=True)
                st.subheader("🚦 Decision Recommendation for Latest Rake")

                latest_rake = result.iloc[-1]

                if latest_rake["Decision"] == "Allow Entry":
                    st.markdown(f"""
                    <div class="success-box">
                    ✅ Recommendation: Allow Entry<br>
                    Rake {latest_rake["Rake_ID"]} is predicted to clear within the target cycle time of {target_cycle_time} hours.
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="danger-box">
                    ❌ Recommendation: Delayed Arrival Suggested<br>
                    Rake {latest_rake["Rake_ID"]} is predicted to exceed the target cycle time of {target_cycle_time} hours.
                    </div>
                    """, unsafe_allow_html=True)

                st.write("Latest rake details:")
                st.dataframe(pd.DataFrame([latest_rake]), use_container_width=True)

                st.markdown('</div>', unsafe_allow_html=True)

                # =========================================================
                # SIMULATION RESULT TABLE
                # =========================================================
                st.markdown('<div class="section-box">', unsafe_allow_html=True)
                st.subheader("🧾 Detailed Simulation Output")
                st.dataframe(result, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # =========================================================
                # CONTROL CHART
                # =========================================================
                st.markdown('<div class="section-box">', unsafe_allow_html=True)
                st.subheader("📈 Predicted Cycle Time Control Chart")

                fig_control = go.Figure()

                fig_control.add_trace(go.Scatter(
                    x=result["Rake_ID"],
                    y=result["Cycle_Time"],
                    mode="lines+markers",
                    name="Predicted Cycle Time"
                ))

                fig_control.add_trace(go.Scatter(
                    x=result["Rake_ID"],
                    y=[target_cycle_time] * len(result),
                    mode="lines",
                    name=f"Target / UCL = {target_cycle_time} hrs",
                    line=dict(dash="dash")
                ))

                fig_control.update_layout(
                    xaxis_title="Rake ID",
                    yaxis_title="Cycle Time in Hours",
                    height=450
                )

                st.plotly_chart(fig_control, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # =========================================================
                # GANTT CHART
                # =========================================================
                st.markdown('<div class="section-box">', unsafe_allow_html=True)
                st.subheader("🕒 Rake Unloading Timeline")

                gantt_data = result.copy()
                gantt_data["Start"] = gantt_data["Start_Unloading"]
                gantt_data["Finish"] = gantt_data["End_Unloading"]

                fig_gantt = px.timeline(
                    gantt_data,
                    x_start="Start",
                    x_end="Finish",
                    y="Rake_ID",
                    color="Decision",
                    hover_data=[
                        "Siding",
                        "Rake_Type",
                        "Waiting_Time",
                        "Cycle_Time",
                        "Sticky_Coal",
                        "CHP_Interruption"
                    ],
                    title="Predicted Unloading Timeline"
                )

                fig_gantt.update_yaxes(autorange="reversed")
                fig_gantt.update_layout(
                    xaxis_title="Simulation Hour",
                    yaxis_title="Rake ID",
                    height=450
                )

                st.plotly_chart(fig_gantt, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # =========================================================
                # WAITING TIME CHART
                # =========================================================
                st.markdown('<div class="section-box">', unsafe_allow_html=True)
                st.subheader("⏳ Predicted Waiting Time by Rake")

                fig_wait = px.bar(
                    result,
                    x="Rake_ID",
                    y="Waiting_Time",
                    color="Decision",
                    text="Waiting_Time",
                    title="Waiting Time Before Unloading"
                )

                fig_wait.update_layout(
                    xaxis_title="Rake ID",
                    yaxis_title="Waiting Time in Hours",
                    height=430
                )

                st.plotly_chart(fig_wait, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # =========================================================
                # DECISION PIE CHART
                # =========================================================
                st.markdown('<div class="section-box">', unsafe_allow_html=True)
                st.subheader("🚦 Allow vs Delayed Rake Summary")

                decision_count = result["Decision"].value_counts().reset_index()
                decision_count.columns = ["Decision", "Count"]

                fig_pie = px.pie(
                    decision_count,
                    names="Decision",
                    values="Count",
                    title="Simulation-Based Rake Entry Decision"
                )

                st.plotly_chart(fig_pie, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                # =========================================================
                # DOWNLOAD OUTPUT
                # =========================================================
                st.markdown('<div class="section-box">', unsafe_allow_html=True)
                st.subheader("⬇️ Download Simulation Output")

                csv = result.to_csv(index=False).encode("utf-8")

                st.download_button(
                    label="Download Result as CSV",
                    data=csv,
                    file_name="digital_twin_simulation_output.csv",
                    mime="text/csv",
                    use_container_width=True
                )

                st.markdown('</div>', unsafe_allow_html=True)

                # =========================================================
                # REPORT WRITE-UP
                # =========================================================
                st.markdown('<div class="section-box">', unsafe_allow_html=True)
                st.subheader("📝 SIP Report Explanation")

                st.markdown(f"""
                A simplified Digital Twin Simulation model was developed using Discrete Event Simulation logic.
                In this model, each rake is treated as a process entity and the wagon tippler is treated as a limited-capacity resource.
                The simulation considers rake arrival time, unloading duration, sticky coal delay, CHP interruption delay, and wagon tippler availability.

                The model predicts waiting time, unloading start time, unloading completion time, and total cycle time for each rake.
                Based on the target cycle time of **{target_cycle_time} hours**, the system gives a decision recommendation:
                **Allow Entry** or **Delayed Arrival**.

                This helps convert the rake tracking system from a historical monitoring dashboard into a predictive decision-support system.
                """)

                st.markdown('</div>', unsafe_allow_html=True)

else:
    st.markdown("""
    <div class="warning-box">
    Please upload a CSV/Excel file or select the sample data option to run the simulation.
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# INSTRUCTIONS SECTION
# =========================================================
with st.expander("📘 How to Prepare the Input File"):
    st.markdown("""
    Your file should contain at least these columns:

    | Column Name | Meaning | Example |
    |---|---|---|
    | Rake_ID | Unique rake name/code | R1 |
    | Arrival_Time | Arrival time in hours from current time | 0, 1, 2.5 |
    | Unloading_Time | Expected unloading time in hours | 5 |
    | Sticky_Coal | Whether sticky coal issue exists | Yes / No |
    | CHP_Interruption | Whether CHP interruption is expected | Yes / No |
    | Siding | Assigned siding | Siding 1 |
    | Rake_Type | Type of rake | BOXN / BOBR |

    Example CSV:

    ```csv
    Rake_ID,Arrival_Time,Unloading_Time,Sticky_Coal,CHP_Interruption,Siding,Rake_Type
    R1,0,5,No,No,Siding 1,BOXN
    R2,1,5,Yes,No,Siding 2,BOXN
    R3,2,6,No,Yes,Siding 1,BOXN
    R4,4,5,No,No,Siding 2,BOBR
    New_Rake,5,5,Yes,No,Siding 2,BOXN
    ```
    """)

with st.expander("📌 How This Helps in Your SIP"):
    st.markdown("""
    This app supports the **Improve Phase** and **Control Phase** of DMAIC.

    **Improve Phase:**
    - Predicts future congestion before rake entry.
    - Helps operators decide whether to allow or delay a rake.
    - Supports better rake scheduling.

    **Control Phase:**
    - Compares predicted cycle time with the target cycle time.
    - Gives visual control chart.
    - Tracks whether rakes are likely to exceed the 7-hour operational target.
    - Helps monitor process stability after improvement.
    """)

with st.expander("🔍 Meaning of Decision Logic"):
    st.markdown("""
    The decision is based on this logic:

    ```text
    If Predicted Cycle Time <= Target Cycle Time:
        Allow Entry
    Else:
        Delayed Arrival Suggested
    ```

    Example:

    ```text
    Target Cycle Time = 7 hours
    Predicted Cycle Time = 12 hours

    Decision = Delayed Arrival Suggested
    ```
    """)
