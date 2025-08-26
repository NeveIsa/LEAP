import marimo

__generated_with = "0.14.16"
app = marimo.App(width="medium")


@app.cell
def _():
    import requests as req
    import seaborn as sns
    import matplotlib.pyplot as plt
    import pandas as pd
    from datetime import datetime
    import json
    
    return req, sns, plt, pd, datetime, json


@app.cell
def _():
    # Configuration cell - this will be used to set up the visualization
    # In a real implementation, these could be passed as parameters
    config = {
        "api_base": "http://localhost:9000",
        "default_student": "s001",
        "default_experiment": "eigen"
    }
    return config


@app.cell
def _(config):
    # Function to fetch logs from the API
    def fetch_logs(student_id=None, experiment_name=None, n=100):
        """Fetch logs from the server API"""
        params = {}
        if student_id:
            params['sid'] = student_id
        if experiment_name:
            params['exp'] = experiment_name
        params['n'] = n
        
        try:
            response = req.get(f"{config['api_base']}/logs", params=params)
            if response.status_code == 200:
                return response.json()["logs"]
            else:
                print(f"Error fetching logs: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error fetching logs: {e}")
            return []
    
    return fetch_logs


@app.cell
def _(fetch_logs, config):
    # Fetch logs using default configuration
    logs = fetch_logs(
        student_id=config["default_student"],
        experiment_name=config["default_experiment"]
    )
    
    if logs:
        print(f"Fetched {len(logs)} logs")
        # Show first log as example
        print("Sample log structure:")
        print(json.dumps(logs[0], indent=2))
    else:
        print("No logs found or error occurred")
    
    return logs


@app.cell
def _(logs):
    # Transform logs into a more usable format
    def transform_logs(logs):
        """Transform logs into a pandas DataFrame for easier analysis"""
        data = []
        for log in logs:
            try:
                # Parse the result_json if it exists
                result = None
                if log.get("result_json"):
                    result = json.loads(log["result_json"])
                
                data.append({
                    "timestamp": log.get("timestamp"),
                    "student_id": log.get("student_id"),
                    "experiment": log.get("experiment_name"),
                    "function": log.get("func_name"),
                    "args": log.get("args_json"),
                    "result": result,
                    "error": log.get("error"),
                    "success": log.get("error") is None
                })
            except Exception as e:
                print(f"Error processing log: {e}")
                continue
        
        return pd.DataFrame(data)
    
    df = transform_logs(logs)
    print(f"Transformed {len(df)} logs into DataFrame")
    return df


@app.cell
def _(df):
    # Display basic statistics
    if not df.empty:
        print("=== Log Statistics ===")
        print(f"Total logs: {len(df)}")
        print(f"Successful executions: {df['success'].sum()}")
        print(f"Failed executions: {len(df) - df['success'].sum()}")
        print(f"Unique students: {df['student_id'].nunique()}")
        print(f"Unique experiments: {df['experiment'].nunique()}")
        print(f"Unique functions: {df['function'].nunique()}")
        
        print("\n=== Function Usage ===")
        function_counts = df['function'].value_counts()
        print(function_counts)
    else:
        print("No data to display")
    
    return df


@app.cell
def _(df, plt, sns):
    # Create visualizations
    if df.empty:
        print("No data to visualize")
        return "No data to visualize"
    
    # Set up the plotting style
    plt.style.use('default')
    sns.set_palette("husl")
    
    # Create a figure with multiple subplots
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Log Analysis Dashboard', fontsize=16)
    
    # 1. Success vs Failure pie chart
    if len(df) > 0:
        success_counts = df['success'].value_counts()
        axes[0, 0].pie(success_counts.values, labels=['Failed' if not x else 'Success' for x in success_counts.index], 
                      autopct='%1.1f%%', startangle=90)
        axes[0, 0].set_title('Success vs Failure Rate')
    
    # 2. Function usage bar chart
    if df['function'].nunique() > 0:
        function_counts = df['function'].value_counts().head(10)
        axes[0, 1].bar(range(len(function_counts)), function_counts.values)
        axes[0, 1].set_xticks(range(len(function_counts)))
        axes[0, 1].set_xticklabels(function_counts.index, rotation=45, ha='right')
        axes[0, 1].set_title('Most Used Functions')
        axes[0, 1].set_ylabel('Count')
    
    # 3. Timeline of executions
    if 'timestamp' in df.columns and not df['timestamp'].isna().all():
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df_sorted = df.sort_values('timestamp')
        axes[1, 0].plot(df_sorted['timestamp'], range(len(df_sorted)), marker='o', markersize=2)
        axes[1, 0].set_title('Execution Timeline')
        axes[1, 0].set_xlabel('Time')
        axes[1, 0].set_ylabel('Log Index')
        axes[1, 0].tick_params(axis='x', rotation=45)
    
    # 4. Student activity
    if df['student_id'].nunique() > 0:
        student_counts = df['student_id'].value_counts().head(10)
        axes[1, 1].bar(range(len(student_counts)), student_counts.values)
        axes[1, 1].set_xticks(range(len(student_counts)))
        axes[1, 1].set_xticklabels(student_counts.index, rotation=45, ha='right')
        axes[1, 1].set_title('Student Activity')
        axes[1, 1].set_ylabel('Log Count')
    
    plt.tight_layout()
    plt.show()
    
    return "Visualizations created"


@app.cell
def _(df):
    # Interactive data exploration
    if df.empty:
        print("No data to explore")
        return "No data to explore"
    
    print("=== Interactive Data Exploration ===")
    print("Use the DataFrame 'df' to explore the data:")
    print(f"df.head() - Show first 5 rows")
    print(f"df.columns - Show all columns")
    print(f"df.describe() - Show statistical summary")
    
    # Show a sample of the data
    print("\n=== Sample Data ===")
    display_cols = ['timestamp', 'student_id', 'function', 'success']
    print(df[display_cols].head(10).to_string())
    
    return df


@app.cell
def _():
    # Future enhancements cell
    print("=== Future Enhancement Ideas ===")
    print("1. Real-time log streaming")
    print("2. Interactive filters for student/experiment selection")
    print("3. Performance metrics and trends")
    print("4. Error analysis and debugging tools")
    print("5. Export capabilities for reports")
    print("6. Custom visualization templates")
    
    return "Future enhancements listed"


if __name__ == "__main__":
    app.run()
