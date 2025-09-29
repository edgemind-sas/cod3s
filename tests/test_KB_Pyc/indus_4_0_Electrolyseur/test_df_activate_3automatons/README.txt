Description : 
Testing the Stack, CapacityMulti, Sensor and Automaton classes, 
We have three automatons that must interact with the same time. 
The starting conditions for the automatons would be: to activate/desactivate automaton number 3, automaton number 2 must be active/desactivate. 
To activate/desactivate automaton number 2, automaton number 1 must be active/desactivate. 
To activate the first automaton, the sensor on the tank contents must be above 11.
To desactivate the first automaton, the sensor on the tank contents must be below 6.
A time-dependent failure on automaton n°2 is added to the variable v_inactive_forced.

Expected values :
- signal_out of the 3 automatons is equal to - 1 when Local_H2_content < 6 
- signal_out of the 3 automatons is equal to + 1 when Local_H2_content > 11
- At time=3, v_inactive_forced = True for sensors n°2 and n°3 (failure_param = 3, repair_param = 1): 
AP_Local_1_signal_out = 0 , AP_Local_3_signal_out = -1, AP_Local_2_signal_out = -1, 
v_inactive_forced = 1 of automaton n°2 

