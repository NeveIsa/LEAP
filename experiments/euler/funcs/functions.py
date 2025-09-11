# Euler's Method Functions for Educational Use
# These functions help students learn Euler's method by implementing it themselves

import math
from typing import List, Tuple, Callable

def euler_step(f: Callable[[float, float], float], 
               t: float, 
               y: float, 
               h: float) -> Tuple[float, float]:
    """
    Perform one step of Euler's method.
    
    This is the core formula: y_{n+1} = y_n + h * f(t_n, y_n)
    
    Args:
        f: The derivative function f(t, y) = dy/dt
        t: Current time
        y: Current value
        h: Step size
    
    Returns:
        Tuple of (next_time, next_value)
    """
    next_y = y + h * f(t, y)
    next_t = t + h
    return (next_t, next_y)

def euler_method(f: Callable[[float, float], float], 
                y0: float, 
                t0: float, 
                h: float, 
                n_steps: int) -> List[Tuple[float, float]]:
    """
    Solve an ODE using Euler's method.
    
    This function shows the complete algorithm, but students should try to implement
    their own version using euler_step().
    
    Args:
        f: The derivative function f(t, y) = dy/dt
        y0: Initial value y(t0)
        t0: Initial time
        h: Step size
        n_steps: Number of steps to take
    
    Returns:
        List of (t, y) pairs representing the solution
    """
    result = [(t0, y0)]
    t, y = t0, y0
    
    for _ in range(n_steps):
        t, y = euler_step(f, t, y, h)
        result.append((t, y))
    
    return result

def exponential_growth(t: float, y: float) -> float:
    """Exponential growth: dy/dt = y"""
    return y

def exponential_decay(t: float, y: float) -> float:
    """Exponential decay: dy/dt = -y"""
    return -y

def logistic_growth(t: float, y: float, r: float = 1.0, K: float = 10.0) -> float:
    """Logistic growth: dy/dt = r*y*(1 - y/K)"""
    return r * y * (1 - y / K)

def harmonic_oscillator(t: float, y: float, omega: float = 1.0) -> float:
    """Simple harmonic oscillator: dy/dt = -omega^2 * y"""
    return -omega**2 * y

def population_with_predation(t: float, y: float, r: float = 0.5, a: float = 0.1) -> float:
    """Population with predation: dy/dt = r*y - a*y^2"""
    return r * y - a * y**2

def solve_exponential_growth(y0: float = 1.0, 
                           t0: float = 0.0, 
                           h: float = 0.1, 
                           n_steps: int = 10) -> List[Tuple[float, float]]:
    """
    Solve dy/dt = y using Euler's method.
    
    Args:
        y0: Initial value (default: 1.0)
        t0: Initial time (default: 0.0)
        h: Step size (default: 0.1)
        n_steps: Number of steps (default: 10)
    
    Returns:
        List of (t, y) pairs
    """
    return euler_method(exponential_growth, y0, t0, h, n_steps)

def solve_exponential_decay(y0: float = 1.0, 
                           t0: float = 0.0, 
                           h: float = 0.1, 
                           n_steps: int = 10) -> List[Tuple[float, float]]:
    """
    Solve dy/dt = -y using Euler's method.
    
    Args:
        y0: Initial value (default: 1.0)
        t0: Initial time (default: 0.0)
        h: Step size (default: 0.1)
        n_steps: Number of steps (default: 10)
    
    Returns:
        List of (t, y) pairs
    """
    return euler_method(exponential_decay, y0, t0, h, n_steps)

def solve_logistic_growth(y0: float = 1.0, 
                         t0: float = 0.0, 
                         h: float = 0.1, 
                         n_steps: int = 50,
                         r: float = 1.0, 
                         K: float = 10.0) -> List[Tuple[float, float]]:
    """
    Solve logistic growth dy/dt = r*y*(1 - y/K) using Euler's method.
    
    Args:
        y0: Initial value (default: 1.0)
        t0: Initial time (default: 0.0)
        h: Step size (default: 0.1)
        n_steps: Number of steps (default: 50)
        r: Growth rate (default: 1.0)
        K: Carrying capacity (default: 10.0)
    
    Returns:
        List of (t, y) pairs
    """
    def f(t, y):
        return logistic_growth(t, y, r, K)
    return euler_method(f, y0, t0, h, n_steps)

def solve_harmonic_oscillator(y0: float = 1.0, 
                            t0: float = 0.0, 
                            h: float = 0.1, 
                            n_steps: int = 50,
                            omega: float = 1.0) -> List[Tuple[float, float]]:
    """
    Solve harmonic oscillator dy/dt = -omega^2 * y using Euler's method.
    
    Args:
        y0: Initial value (default: 1.0)
        t0: Initial time (default: 0.0)
        h: Step size (default: 0.1)
        n_steps: Number of steps (default: 50)
        omega: Angular frequency (default: 1.0)
    
    Returns:
        List of (t, y) pairs
    """
    def f(t, y):
        return harmonic_oscillator(t, y, omega)
    return euler_method(f, y0, t0, h, n_steps)

def solve_population_predation(y0: float = 5.0, 
                              t0: float = 0.0, 
                              h: float = 0.1, 
                              n_steps: int = 50,
                              r: float = 0.5, 
                              a: float = 0.1) -> List[Tuple[float, float]]:
    """
    Solve population with predation dy/dt = r*y - a*y^2 using Euler's method.
    
    Args:
        y0: Initial value (default: 5.0)
        t0: Initial time (default: 0.0)
        h: Step size (default: 0.1)
        n_steps: Number of steps (default: 50)
        r: Growth rate (default: 0.5)
        a: Predation coefficient (default: 0.1)
    
    Returns:
        List of (t, y) pairs
    """
    def f(t, y):
        return population_with_predation(t, y, r, a)
    return euler_method(f, y0, t0, h, n_steps)

def compare_step_sizes(f: Callable[[float, float], float],
                      y0: float,
                      t0: float,
                      t_end: float,
                      step_sizes: List[float]) -> dict:
    """
    Compare Euler's method with different step sizes.
    
    Args:
        f: The derivative function f(t, y) = dy/dt
        y0: Initial value
        t0: Initial time
        t_end: Final time
        step_sizes: List of step sizes to compare
    
    Returns:
        Dictionary with step sizes as keys and solution lists as values
    """
    results = {}
    for h in step_sizes:
        n_steps = int((t_end - t0) / h)
        solution = euler_method(f, y0, t0, h, n_steps)
        results[h] = solution
    return results

def calculate_error(true_solution: Callable[[float], float],
                   euler_solution: List[Tuple[float, float]]) -> List[float]:
    """
    Calculate the error between true solution and Euler's method.
    
    Args:
        true_solution: Function that gives the true solution y(t)
        euler_solution: List of (t, y) pairs from Euler's method
    
    Returns:
        List of absolute errors at each time point
    """
    errors = []
    for t, y_euler in euler_solution:
        y_true = true_solution(t)
        error = abs(y_true - y_euler)
        errors.append(error)
    return errors

def exponential_true_solution(t: float, y0: float = 1.0) -> float:
    """True solution for dy/dt = y: y(t) = y0 * e^t"""
    return y0 * math.exp(t)

def exponential_decay_true_solution(t: float, y0: float = 1.0) -> float:
    """True solution for dy/dt = -y: y(t) = y0 * e^(-t)"""
    return y0 * math.exp(-t)

def student_euler_solution(solution_data):
    """
    Validate a student's Euler method implementation.
    
    Args:
        solution_data: Dictionary containing:
            - 'derivative_function': The derivative function name
            - 'y0': Initial value
            - 't0': Initial time  
            - 'h': Step size
            - 'n_steps': Number of steps
            - 'student_solution': List of (t, y) pairs from student's implementation
    
    Returns:
        Dictionary with validation results and feedback
    """
    try:
        # Extract parameters
        derivative_name = solution_data.get('derivative_function', 'exponential_growth')
        y0 = solution_data.get('y0', 1.0)
        t0 = solution_data.get('t0', 0.0)
        h = solution_data.get('h', 0.1)
        n_steps = solution_data.get('n_steps', 10)
        student_solution = solution_data.get('student_solution', [])
        
        # Get the derivative function
        derivative_functions = {
            'exponential_growth': exponential_growth,
            'exponential_decay': exponential_decay,
            'logistic_growth': lambda t, y: logistic_growth(t, y, solution_data.get('r', 1.0), solution_data.get('K', 10.0)),
            'harmonic_oscillator': lambda t, y: harmonic_oscillator(t, y, solution_data.get('omega', 1.0)),
            'population_predation': lambda t, y: population_with_predation(t, y, solution_data.get('r', 0.5), solution_data.get('a', 0.1))
        }
        
        f = derivative_functions.get(derivative_name, exponential_growth)
        
        # Compute correct solution
        correct_solution = euler_method(f, y0, t0, h, n_steps)
        
        # Validate student solution
        if len(student_solution) != len(correct_solution):
            return {
                'valid': False,
                'error': f'Expected {len(correct_solution)} points, got {len(student_solution)}',
                'correct_solution': correct_solution,
                'student_solution': student_solution
            }
        
        # Check each point
        errors = []
        for i, ((t_student, y_student), (t_correct, y_correct)) in enumerate(zip(student_solution, correct_solution)):
            t_error = abs(t_student - t_correct)
            y_error = abs(y_student - y_correct)
            errors.append((t_error, y_error))
            
            if t_error > 1e-10:
                return {
                    'valid': False,
                    'error': f'Time error at step {i}: expected {t_correct}, got {t_student}',
                    'correct_solution': correct_solution,
                    'student_solution': student_solution
                }
        
        # Check if solution is close enough
        max_y_error = max(y_error for _, y_error in errors)
        tolerance = 1e-6
        
        if max_y_error > tolerance:
            return {
                'valid': False,
                'error': f'Solution accuracy too low. Max error: {max_y_error:.2e}, tolerance: {tolerance:.2e}',
                'correct_solution': correct_solution,
                'student_solution': student_solution,
                'max_error': max_y_error
            }
        
        return {
            'valid': True,
            'message': f'Excellent! Your implementation is correct. Max error: {max_y_error:.2e}',
            'correct_solution': correct_solution,
            'student_solution': student_solution,
            'max_error': max_y_error
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': f'Validation error: {str(e)}',
            'correct_solution': [],
            'student_solution': solution_data.get('student_solution', [])
        }


def check_euler_formula(t: float, y: float, h: float, f_value: float, next_y: float) -> dict:
    """
    Check if a student's Euler formula implementation is correct.
    
    Args:
        t: Current time
        y: Current value
        h: Step size
        f_value: Value of f(t, y)
        next_y: Student's calculated next y value
    
    Returns:
        Dictionary with feedback
    """
    correct_next_y = y + h * f_value
    
    if abs(next_y - correct_next_y) < 1e-10:
        return {
            'correct': True,
            'message': 'Perfect! Your Euler formula is correct.',
            'correct_value': correct_next_y,
            'student_value': next_y
        }
    else:
        return {
            'correct': False,
            'message': f'Not quite right. Expected: {correct_next_y}, Got: {next_y}',
            'correct_value': correct_next_y,
            'student_value': next_y,
            'error': abs(next_y - correct_next_y)
        }

def echo(value):
    """Return the input value unchanged. Useful for logging arbitrary payloads via /call."""
    return value
