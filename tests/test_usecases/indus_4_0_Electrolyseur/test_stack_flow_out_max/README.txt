Description : Testing the input flow of the Stack class with flow_out_max: 0.4. 
If the maximum outflow is a positive value and the total inflow of the stack is greater than the maximum outflow of the stack, 
then we take the maximum outflow as the total inflow.

Expected values:
- v_flow_out_max = 0.4
- B1_flow_Elec_demand_export = 0.4
- B1_flow_Elec_out = 0.4
- Electro_flow_demand_export1 = 0.4
- Electro_flow_out = 0.4
- Local_H2_content increases by 0.4 at each time step without exceeding the capacity.
