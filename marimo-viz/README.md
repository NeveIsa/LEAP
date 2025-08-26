# Marimo Log Visualization

This directory contains marimo notebooks for visualizing logs from the TeachingOptimization system.

## Files

- `test.py` - Original test notebook (basic scatter plot)
- `log_viz.py` - Enhanced log visualization notebook with comprehensive analytics

## Features

The `log_viz.py` notebook provides:

1. **Log Fetching**: Connects to the server API to fetch logs
2. **Data Transformation**: Converts logs into pandas DataFrames for analysis
3. **Statistics**: Shows basic statistics about log data
4. **Visualizations**: Creates multiple charts including:
   - Success vs Failure pie chart
   - Function usage bar chart
   - Execution timeline
   - Student activity chart
5. **Interactive Exploration**: Provides tools for data exploration

## Usage

1. Start the server: `python server/rpc_server.py`
2. Navigate to the dashboard: `http://localhost:9000`
3. Click on "Marimo Log Visualization"
4. Select a notebook and click "Load Notebook"

## Configuration

The notebook is configured to connect to `http://localhost:9000` by default. You can modify the `config` cell in the notebook to change:

- API base URL
- Default student ID
- Default experiment name

## Dependencies

Make sure you have the following packages installed:
- marimo
- pandas
- matplotlib
- seaborn
- requests

## Future Enhancements

- Real-time log streaming
- Interactive filters
- Performance metrics
- Error analysis tools
- Export capabilities
- Custom visualization templates
