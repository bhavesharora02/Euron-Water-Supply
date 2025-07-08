import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import sqlite3
import os
from src.database import log_intake, get_intake, get_daily_summary
from src.agent import WaterIntakeAgent

# Debug info
print("\n=== DEBUG INFO ===")
print("Current working directory:", os.getcwd())
print("Database exists:", os.path.exists("water_tracker.db"))
if os.path.exists("water_tracker.db"):
    print("Database size:", os.path.getsize("water_tracker.db"), "bytes")

# Page configuration
st.set_page_config(
    page_title="💧 Water Intake Tracker",
    page_icon="💧",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1.5rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize the agent
@st.cache_resource
def get_agent():
    try:
        return WaterIntakeAgent()
    except Exception as e:
        st.error(f"Failed to initialize the AI agent: {str(e)}")
        st.stop()

agent = get_agent()

def debug_database_state(user_id):
    """Debug function to print database state"""
    try:
        conn = sqlite3.connect("water_tracker.db")
        cursor = conn.cursor()
        
        # Print all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print("\n=== DATABASE TABLES ===")
        print(cursor.fetchall())
        
        # Print all records for the user
        cursor.execute("SELECT * FROM water_intake WHERE user_id = ?", (user_id,))
        records = cursor.fetchall()
        print("\n=== ALL RECORDS ===")
        for r in records:
            print(r)
        
        # Print today's records
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT * FROM water_intake 
            WHERE user_id = ? AND date = ?
        """, (user_id, today))
        print(f"\n=== TODAY'S RECORDS ({today}) ===")
        print(cursor.fetchall())
        
        conn.close()
    except Exception as e:
        print("Debug error:", e)

def get_todays_total(user_id):
    try:
        today_str = datetime.now().strftime('%Y-%m-%d')
        print(f"\n=== GETTING TODAY'S TOTAL ===")
        print("Today's date string:", today_str)
        
        history = get_intake(user_id)
        print("Raw history from get_intake:", history)
        
        if not history:
            print("No history found")
            return 0
            
        history_df = pd.DataFrame(history, columns=["id", "user_id", "intake_ml", "date", "timestamp"])
        print("History DataFrame:", history_df)
        
        # Convert date strings to datetime objects for comparison
        history_df['date'] = pd.to_datetime(history_df['date'])
        history_df['date_str'] = history_df['date'].dt.strftime('%Y-%m-%d')
        
        print("All dates in history:", history_df['date_str'].unique())
        
        today_total = history_df[history_df['date_str'] == today_str]['intake_ml'].sum()
        print("Today's total calculated:", today_total)
        
        return today_total
    except Exception as e:
        print(f"Error in get_todays_total: {e}")
        return 0

# Sidebar for user input
with st.sidebar:
    st.title("💧 Water Tracker")
    st.markdown("---")
    
    with st.form("intake_form"):
        user_id = st.text_input("User ID", "user123")
        intake_ml = st.number_input("Water Intake (ml)", min_value=0, step=50, value=500)
        submitted = st.form_submit_button("💧 Log Intake")
        
        if submitted:
            with st.spinner("Logging your intake..."):
                try:
                    print("\n=== ATTEMPTING TO LOG INTAKE ===")
                    debug_database_state(user_id)
                    
                    success = log_intake(user_id, intake_ml)
                    
                    print("\n=== AFTER LOGGING ===")
                    debug_database_state(user_id)
                    
                    if success:
                        st.success("✅ Intake logged successfully!")
                        
                        # Get AI feedback
                        with st.spinner("Getting AI feedback..."):
                            try:
                                today_total = get_todays_total(user_id)
                                feedback = agent.analyze_intake(today_total)
                                
                                with st.expander("💡 AI Hydration Feedback", expanded=True):
                                    st.write(f"Today's total intake: {today_total} ml")
                                    st.write(feedback)
                                    
                            except Exception as e:
                                st.error(f"Couldn't generate AI feedback: {str(e)}")
                                st.exception(e)
                        
                        st.balloons()
                    else:
                        st.error("❌ Failed to log water intake. Please try again.")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    st.exception(e)
    
    # Debug button
    if st.button("🛠️ Debug Database"):
        st.sidebar.write("### Database Debug Info")
        debug_database_state(user_id)
        st.sidebar.success("Debug info printed to console")

# Main content
st.title("💧 Hydration Dashboard")

# Get data
try:
    history = get_intake(user_id)
    
    if history:
        # Convert to DataFrame
        history_df = pd.DataFrame(history, columns=["id", "user_id", "intake_ml", "date", "timestamp"])
        history_df['date'] = pd.to_datetime(history_df['date'])
        history_df['time'] = pd.to_datetime(history_df['timestamp']).dt.strftime('%H:%M')
        
        # Today's stats
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_df = history_df[history_df['date'].dt.strftime('%Y-%m-%d') == today_str]
        today_total = today_df['intake_ml'].sum()
        daily_goal = 2000  # ml
        
        # Create columns for metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Today's Intake", f"{today_total} ml")
            
        with col2:
            remaining = max(0, daily_goal - today_total)
            st.metric("Remaining", f"{remaining} ml")
            
        with col3:
            progress = min(1.0, today_total / daily_goal)
            st.metric("Daily Goal", f"{int(progress * 100)}%")
            
        st.progress(progress)
        
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 Overview", "📅 History", "📈 Trends"])
        
        with tab1:
            # Last 7 days summary
            st.subheader("Weekly Summary")
            weekly_summary = get_daily_summary(user_id, days=7)
            weekly_df = pd.DataFrame(weekly_summary, columns=["date", "total_intake", "intake_count"])
            weekly_df['date'] = pd.to_datetime(weekly_df['date'])
            
            # Create bar chart
            fig = px.bar(
                weekly_df,
                x='date',
                y='total_intake',
                title='Daily Intake (Last 7 Days)',
                labels={'total_intake': 'Water Intake (ml)', 'date': 'Date'}
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Recent intakes
            st.subheader("Recent Intakes")
            st.dataframe(
                history_df[['time', 'intake_ml']].tail(5).rename(
                    columns={'time': 'Time', 'intake_ml': 'Amount (ml)'}
                ).set_index('Time'),
                use_container_width=True
            )
            
        with tab2:
            # Full history with filtering
            st.subheader("Intake History")
            st.write("Here's your complete water intake history:")
            
            # Date range filter
            col1, col2 = st.columns(2)
            with col1:
                date_range = st.date_input(
                    "Select Date Range",
                    value=(datetime.now().date() - timedelta(days=7), datetime.now().date()),
                    min_value=history_df['date'].min().date(),
                    max_value=datetime.now().date()
                )
            
            # Filter data
            filtered_df = history_df[
                (history_df['date'].dt.date >= date_range[0]) & 
                (history_df['date'].dt.date <= date_range[1])
            ]
            
            if not filtered_df.empty:
                # Display summary
                total_intake = filtered_df['intake_ml'].sum()
                avg_intake = filtered_df['intake_ml'].mean()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Intake", f"{total_intake} ml")
                with col2:
                    st.metric("Average per Entry", f"{avg_intake:.1f} ml")
                
                # Display the data table
                st.dataframe(
                    filtered_df[['date', 'time', 'intake_ml']].sort_values('date', ascending=False).rename(
                        columns={'date': 'Date', 'time': 'Time', 'intake_ml': 'Amount (ml)'}
                    ).set_index('Date'),
                    use_container_width=True
                )
            else:
                st.info("No entries found for the selected date range.")
            
        with tab3:
            # Trends and analysis
            st.subheader("Hydration Trends")
            
            # Weekly pattern
            weekly_pattern = history_df.copy()
            weekly_pattern['day_of_week'] = weekly_pattern['date'].dt.day_name()
            weekly_pattern = weekly_pattern.groupby('day_of_week')['intake_ml'].mean().reindex([
                'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
            ])
            
            fig = px.line(
                weekly_pattern,
                title='Average Intake by Day of Week',
                labels={'value': 'Average Intake (ml)', 'index': 'Day of Week'}
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Hourly pattern
            history_df['hour'] = pd.to_datetime(history_df['time']).dt.hour
            hourly_pattern = history_df.groupby('hour')['intake_ml'].mean()
            
            fig = px.bar(
                hourly_pattern,
                title='Average Intake by Hour of Day',
                labels={'value': 'Average Intake (ml)', 'index': 'Hour of Day'}
            )
            st.plotly_chart(fig, use_container_width=True)
            
    else:
        st.info("No intake history found. Log your first water intake using the sidebar!")
        
except Exception as e:
    st.error(f"An error occurred while loading data: {str(e)}")
    st.exception(e)

# Footer
st.markdown("---")
st.markdown("💧 Stay Hydrated! | Made with ❤️")