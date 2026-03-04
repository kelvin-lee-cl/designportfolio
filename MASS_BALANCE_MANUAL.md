# Mass Balance Tab - User Manual

## Overview

The **Mass Balance** tab is designed for activated sludge system design calculations in wastewater treatment plants (WWTP). Currently, it provides a foundation for inputting key design parameters and performing iterative calculations to solve for reactor volume and return activated sludge (RAS) ratio.

## Current Implementation

### What It Does Now

The current Mass Balance tab includes:

1. **Input Parameters** (Activated Sludge section):
   - **Q_avg** (m³/s): Average flow rate
   - **BOD_in** (mg/L): Influent Biochemical Oxygen Demand concentration
   - **Yield (Y)**: Biomass yield coefficient (range: 0.4-0.8, default: 0.67)

2. **Residuals Function**: A mathematical function that calculates residuals for iterative solving of:
   - **V**: Reactor volume (m³)
   - **RAS**: Return Activated Sludge ratio

3. **Default Parameters** (stored in session state):
   - MLSS: 3000 mg/L (Mixed Liquor Suspended Solids)
   - kd: 0.06 day⁻¹ (endogenous decay coefficient)
   - SRT: 10 days (Solids Retention Time)

### How to Use the Current Implementation

#### Step 1: Input Design Parameters

1. Navigate to the **Mass Balance** tab
2. In the "Activated Sludge" section, you'll see two columns:
   - **Left column**: 
     - Enter your average flow rate (Q_avg) in m³/s
     - Enter influent BOD concentration (BOD_in) in mg/L
   - **Right column**:
     - Adjust the Yield coefficient (Y) using the slider/input (typically 0.4-0.8)

#### Step 2: Understanding the Residuals Function

The `residuals([V, RAS])` function calculates two equations:

1. **Equation 1**: `μ × SRT - 1 = 0`
   - Where μ (specific growth rate) = `Y × (BOD/1e6 × Q) / (V × MLSS/1e6) - kd`
   - This ensures the system operates at the desired SRT

2. **Equation 2**: `RAS - 0.5 = 0`
   - This sets the RAS ratio to 0.5 (50% return)

#### Step 3: Current Test Output

Currently, the tab displays a test calculation:
```python
residuals([1000, 0.5])
```
This shows the residual values for V=1000 m³ and RAS=0.5. When both residuals are close to zero, you've found the solution.

## Understanding the Gap

### What You Expected

You mentioned expecting to:
- Input different chains of systems
- Input mass balance for each system
- Perform iterative calculations across multiple systems

### Current Limitations

The current implementation:
- ✅ Handles basic activated sludge parameters
- ✅ Provides a residuals function for iterative solving
- ❌ Does NOT support multiple system chains
- ❌ Does NOT have a visual interface for iterative solving
- ❌ Does NOT show mass balance flows between systems
- ❌ Does NOT allow input of multiple treatment units

## How to Use It Effectively (Current State)

### For Basic Calculations

1. **Enter your design parameters**:
   - Flow rate (Q_avg)
   - Influent BOD (BOD_in)
   - Yield coefficient (Y)

2. **The values are stored** in `st.session_state.mb_inputs` and can be used in calculations

3. **Use the residuals function** with a solver (like `scipy.optimize.fsolve`) to find optimal V and RAS values

### Example Workflow

```python
# In your calculations, you can use:
from scipy.optimize import fsolve

# Get inputs from session state
mb_inputs = st.session_state.mb_inputs

# Solve for V and RAS
solution = fsolve(residuals, [1000, 0.5])
V_optimal, RAS_optimal = solution
```

## Recommended Enhancements

To match your expectations, consider adding:

1. **Multi-System Chain Interface**:
   - Visual flow diagram showing treatment units
   - Input forms for each unit (primary clarifier, aeration tank, secondary clarifier, etc.)
   - Mass balance calculations between units

2. **Iterative Solver Integration**:
   - Add `scipy.optimize.fsolve` or similar solver
   - Display solved values (V, RAS) automatically
   - Show convergence status

3. **Mass Balance Display**:
   - Show mass flows (BOD, TSS) through each system
   - Display removal efficiencies
   - Create mass balance tables

4. **Multiple Scenarios**:
   - Save different design scenarios
   - Compare results side-by-side
   - Export calculations

## Technical Details

### Residuals Function Breakdown

```python
def residuals(vars):
    V, RAS = vars  # Variables to solve for
    
    # Get parameters from inputs/defaults
    Y = mb_inputs.get('Y', defaults['Y'])
    BOD = mb_inputs.get('BOD_in', defaults['BOD_in'])
    Q = mb_inputs.get('Q_avg', defaults['Q_avg'])
    MLSS = defaults['MLSS']
    kd = defaults['kd']
    SRT = defaults['SRT']
    
    # Calculate specific growth rate
    mu = Y * (BOD / 1e6 * Q) / (V * MLSS / 1e6) - kd
    
    # Return residuals (should be zero at solution)
    return np.array([
        mu * SRT - 1,  # SRT constraint
        RAS - 0.5      # RAS ratio constraint
    ])
```

### Parameter Units

- **Q_avg**: m³/s (flow rate)
- **BOD_in**: mg/L (concentration)
- **MLSS**: mg/L (concentration)
- **Y**: dimensionless (yield coefficient)
- **kd**: day⁻¹ (decay rate)
- **SRT**: days (solids retention time)
- **V**: m³ (volume)
- **RAS**: dimensionless ratio (0-1)

## Next Steps

1. **For immediate use**: Input your parameters and use the residuals function with a solver
2. **For enhancement**: Consider implementing the multi-system chain interface
3. **For calculations**: Integrate `scipy.optimize` to automatically solve for V and RAS

## Questions or Issues?

If you need help implementing the multi-system chain functionality or iterative solver interface, please let me know!
