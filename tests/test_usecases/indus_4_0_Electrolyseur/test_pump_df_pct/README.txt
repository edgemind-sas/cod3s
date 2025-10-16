Description : 
Test of the Pump class with automaton
Added a failure on the pump's production flow percentage: 0.25%.

Expected values after failure:
- Production goes from FLOW_NOMINAL_PUMP to FLOW_NOMINAL_PUMP * 0.25.
- The v_prod_pct variable goes from 100% to 25%.

Expected values after repair:
- Production goes from FLOW_NOMINAL_PUMP * 0.25 to FLOW_NOMINAL_PUMP.
- The v_prod_pct variable goes from 25% to 100%.

