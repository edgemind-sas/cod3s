Description : 
Test of the DistribNode class ( update_flow method) , 
case where a single continuous electrical source is distributed 
to two batteries thanks to a distribution node. 
Test case with : iflow < demand1 + demand2 and p_percent_value1 = 0%, and p_percent_value2 = 0 % in model,
in this case, we have:
                    percent_value1 = demand1 / (demand1 + demand2) 
                    percent_value2 = demand2 / (demand1 + demand2) 

Expected values : 
demand of fist battery = 5, demand of second battery = 4, then
percent_value1 = 5.0 / (5.0 + 4.0) = 0.555
percent_value2 = 4.0 / (5.0 + 4.0) = 0.444

- Node_flow_out1 = 5 for all time
- Node_flow_out2 = 4 for all time
- Node_percent_value1 = 0 for all time
- Node_percent_value2 = 0 for all time
- Node_flow_demand_export = 9 for all time
