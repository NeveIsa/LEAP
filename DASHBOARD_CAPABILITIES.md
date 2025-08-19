# Interactive Logs Dashboard - Complete Capabilities Guide

## 🎯 Overview

The Interactive Logs Dashboard is a powerful tool for teachers to visualize and analyze student RPC (Remote Procedure Call) progress in real-time. It provides an IDE-like environment where teachers can write custom JavaScript functions to transform and analyze student data.

## 📊 Core Features

### 1. Real-Time Data Visualization
- **Live RPC Call Tracking**: Monitors student function calls in real-time
- **Iteration-Based Plotting**: X-axis shows iteration numbers (1, 2, 3...) representing sequential RPC calls
- **Multi-Student Comparison**: Visualize multiple students simultaneously with different colored lines
- **Interactive Charts**: Built with uPlot for smooth, responsive visualizations

### 2. Advanced Filtering
- **Student Filtering**: Select specific students or view all students
- **Experiment Filtering**: Filter by experiment name to focus on specific assignments
- **Dynamic Updates**: Filters update the visualization immediately

### 3. Professional IDE Environment
- **Monaco Editor Integration**: VSCode-like syntax highlighting and autocomplete
- **JavaScript Support**: Full JavaScript language support with error detection
- **Dark Theme**: Professional dark theme matching the dashboard design
- **Real-Time Editing**: Live code editing with syntax validation

### 4. Custom Transformation Functions
- **Function Parameters**: 
  - `x`: Array of iteration numbers (1, 2, 3, ...)
  - `y`: Array of function results from RPC calls
- **Return Value**: Array of transformed values (same length as input)
- **Safe Execution**: Functions run in controlled environment

### 5. Results Analysis
- **Statistical Metrics**: 
  - Total data points
  - Average value
  - Maximum value
  - Minimum value
  - Standard deviation
- **Visual Feedback**: Success/error messages for transformations
- **Real-Time Updates**: Metrics update immediately after transformation

## 🔧 JavaScript Transformation Functions

### 1. Convergence Analysis Functions

#### Basic Convergence Rate
```javascript
function transform(x, y) {
  const result = [];
  for (let i = 0; i < y.length; i++) {
    if (i === 0) {
      result.push(0); // First iteration has no previous value
    } else {
      const diff = Math.abs(y[i] - y[i-1]);
      result.push(diff);
    }
  }
  return result;
}
```
**Use Case**: Shows how much the student's result changes between iterations
**Y-Axis Label**: "Convergence Rate"

#### Relative Convergence Rate
```javascript
function transform(x, y) {
  const result = [];
  for (let i = 0; i < y.length; i++) {
    if (i === 0) {
      result.push(0);
    } else {
      const relativeDiff = Math.abs((y[i] - y[i-1]) / y[i-1]) * 100;
      result.push(relativeDiff);
    }
  }
  return result;
}
```
**Use Case**: Shows percentage change between iterations
**Y-Axis Label**: "Relative Change (%)"

### 2. Optimization Tracking Functions

#### Distance from Target
```javascript
function transform(x, y) {
  const target = 0; // Set your target value
  return y.map(val => Math.abs(val - target));
}
```
**Use Case**: Shows how far each result is from the optimal solution
**Y-Axis Label**: "Distance from Target"

#### Distance from Global Minimum
```javascript
function transform(x, y) {
  const globalMin = Math.min(...y);
  return y.map(val => Math.abs(val - globalMin));
}
```
**Use Case**: Shows how far each result is from the best achieved value
**Y-Axis Label**: "Distance from Best"

#### Improvement Rate
```javascript
function transform(x, y) {
  const result = [];
  for (let i = 0; i < y.length; i++) {
    if (i === 0) {
      result.push(0);
    } else {
      const improvement = y[i] - y[i-1];
      result.push(improvement);
    }
  }
  return result;
}
```
**Use Case**: Shows whether the student is improving or getting worse
**Y-Axis Label**: "Improvement Rate"

### 3. Smoothing and Averaging Functions

#### Moving Average
```javascript
function transform(x, y) {
  const windowSize = 3;
  const result = [];
  for (let i = 0; i < y.length; i++) {
    if (i < windowSize - 1) {
      result.push(NaN);
    } else {
      const sum = y.slice(i - windowSize + 1, i + 1).reduce((a, b) => a + b, 0);
      result.push(sum / windowSize);
    }
  }
  return result;
}
```
**Use Case**: Smooths out noise in the data to show trends
**Y-Axis Label**: "Moving Average (3-point)"

#### Exponential Moving Average
```javascript
function transform(x, y) {
  const alpha = 0.3; // Smoothing factor (0-1)
  const result = [];
  for (let i = 0; i < y.length; i++) {
    if (i === 0) {
      result.push(y[0]);
    } else {
      const ema = alpha * y[i] + (1 - alpha) * result[i-1];
      result.push(ema);
    }
  }
  return result;
}
```
**Use Case**: Provides smoother trend analysis with more weight on recent values
**Y-Axis Label**: "Exponential Moving Average"

### 4. Performance Analysis Functions

#### Cumulative Performance
```javascript
function transform(x, y) {
  const result = [];
  let cumulative = 0;
  for (let i = 0; i < y.length; i++) {
    cumulative += y[i];
    result.push(cumulative);
  }
  return result;
}
```
**Use Case**: Shows total accumulated performance over time
**Y-Axis Label**: "Cumulative Performance"

#### Performance Ratio
```javascript
function transform(x, y) {
  const bestPossible = Math.min(...y); // Assuming lower is better
  return y.map(val => val / bestPossible);
}
```
**Use Case**: Shows how close each result is to the best possible outcome
**Y-Axis Label**: "Performance Ratio"

#### Efficiency Score
```javascript
function transform(x, y) {
  const result = [];
  for (let i = 0; i < y.length; i++) {
    // Efficiency = improvement per iteration
    if (i === 0) {
      result.push(0);
    } else {
      const efficiency = (y[i-1] - y[i]) / i; // Improvement per iteration
      result.push(efficiency);
    }
  }
  return result;
}
```
**Use Case**: Measures how efficiently the student is improving
**Y-Axis Label**: "Efficiency Score"

### 5. Statistical Analysis Functions

#### Z-Score Normalization
```javascript
function transform(x, y) {
  const mean = y.reduce((a, b) => a + b, 0) / y.length;
  const variance = y.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / y.length;
  const stdDev = Math.sqrt(variance);
  
  return y.map(val => (val - mean) / stdDev);
}
```
**Use Case**: Normalizes data to show how many standard deviations each value is from the mean
**Y-Axis Label**: "Z-Score"

#### Percentile Rank
```javascript
function transform(x, y) {
  return y.map(val => {
    const rank = y.filter(v => v <= val).length;
    return (rank / y.length) * 100;
  });
}
```
**Use Case**: Shows the percentile rank of each result
**Y-Axis Label**: "Percentile Rank (%)"

### 6. Learning Pattern Analysis

#### Learning Curve Slope
```javascript
function transform(x, y) {
  const result = [];
  for (let i = 0; i < y.length; i++) {
    if (i < 2) {
      result.push(NaN);
    } else {
      // Calculate slope over last 3 points
      const slope = (y[i] - y[i-2]) / 2;
      result.push(slope);
    }
  }
  return result;
}
```
**Use Case**: Shows the rate of learning/improvement over time
**Y-Axis Label**: "Learning Curve Slope"

#### Consistency Score
```javascript
function transform(x, y) {
  const result = [];
  for (let i = 0; i < y.length; i++) {
    if (i < 2) {
      result.push(NaN);
    } else {
      // Measure consistency by variance of last 3 values
      const recent = y.slice(i-2, i+1);
      const mean = recent.reduce((a, b) => a + b, 0) / 3;
      const variance = recent.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / 3;
      result.push(1 / (1 + variance)); // Higher score = more consistent
    }
  }
  return result;
}
```
**Use Case**: Measures how consistent the student's performance is
**Y-Axis Label**: "Consistency Score"

### 7. Advanced Analysis Functions

#### Momentum Indicator
```javascript
function transform(x, y) {
  const result = [];
  for (let i = 0; i < y.length; i++) {
    if (i < 3) {
      result.push(0);
    } else {
      // Momentum = acceleration of improvement
      const currentChange = y[i] - y[i-1];
      const previousChange = y[i-1] - y[i-2];
      const momentum = currentChange - previousChange;
      result.push(momentum);
    }
  }
  return result;
}
```
**Use Case**: Shows whether the student is accelerating or decelerating their improvement
**Y-Axis Label**: "Momentum"

#### Plateau Detection
```javascript
function transform(x, y) {
  const threshold = 0.01; // Minimum change to consider progress
  const result = [];
  for (let i = 0; i < y.length; i++) {
    if (i === 0) {
      result.push(0);
    } else {
      const change = Math.abs(y[i] - y[i-1]);
      result.push(change < threshold ? 1 : 0); // 1 = plateau, 0 = progress
    }
  }
  return result;
}
```
**Use Case**: Identifies when students reach plateaus in their learning
**Y-Axis Label**: "Plateau Indicator"

## 🎓 Educational Use Cases

### 1. Optimization Teaching
- **Gradient Descent Visualization**: Show convergence patterns
- **Algorithm Comparison**: Compare different optimization approaches
- **Parameter Tuning**: Visualize the impact of different parameters

### 2. Student Assessment
- **Progress Tracking**: Monitor individual student improvement
- **Class Performance**: Compare multiple students on the same problem
- **Learning Patterns**: Identify different learning styles and approaches

### 3. Problem Design
- **Difficulty Assessment**: Evaluate problem difficulty based on convergence rates
- **Iteration Optimization**: Determine optimal number of iterations for problems
- **Feedback Timing**: Identify when students need intervention

### 4. Research Applications
- **Learning Analytics**: Analyze learning patterns across different problems
- **Algorithm Performance**: Compare different algorithms' convergence rates
- **Educational Research**: Study the effectiveness of different teaching methods

## 🚀 Getting Started

1. **Access the Dashboard**: Navigate to `/ui/viz/lineplot.html`
2. **Select Data**: Choose student(s) and experiment to analyze
3. **Write Function**: Use the IDE to write your transformation function
4. **Apply Transformation**: Click "Transform & Plot" to see results
5. **Analyze Results**: Review the metrics and visualization
6. **Iterate**: Modify your function and reapply as needed

## 💡 Tips for Teachers

- **Start Simple**: Begin with basic convergence rate functions
- **Compare Students**: Use multiple student selection to compare approaches
- **Experiment**: Try different transformation functions to gain insights
- **Save Functions**: Keep useful functions for future analysis
- **Real-Time Monitoring**: Use the dashboard during live coding sessions

## 🔧 Technical Details

- **Backend**: FastAPI with DuckDB storage
- **Frontend**: Vanilla JavaScript with uPlot charts
- **Editor**: Monaco Editor (same as VSCode)
- **Data Format**: JSON with timestamp, student_id, experiment_name, func_name, args_json, result_json
- **Real-time Updates**: Automatic refresh of data and visualizations

This dashboard provides a comprehensive toolkit for analyzing student learning patterns and optimization progress in real-time!
