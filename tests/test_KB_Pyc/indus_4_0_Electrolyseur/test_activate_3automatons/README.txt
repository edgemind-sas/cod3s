Description : 
Testing the Stack, CapacityMulti, Sensor and Automaton classes, 
We have three automatons that must interact with the same time. 
The starting conditions for the automatons would be: to activate/desactivate automaton number 3, automaton number 2 must be active/desactivate. 
To activate/desactivate automaton number 2, automaton number 1 must be active/desactivate. 
To activate the first automaton, the sensor on the tank contents must be above 11.
To desactivate the first automaton, the sensor on the tank contents must be below 6.

Expected values :
- signal_out of the 3 automatons is equal to - 1 when Local_H2_content < 6 
- signal_out of the 3 automatons is equal to + 1 when Local_H2_content > 11
