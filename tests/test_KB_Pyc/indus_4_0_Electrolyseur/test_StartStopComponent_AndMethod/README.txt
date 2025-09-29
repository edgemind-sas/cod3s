
Description : Testing the Battery, StartStopComponent (stop_required method) and Automaton classes, 
System with a battery, three controllers, and one consumer. 
The controllers activate or deactivate depending on the battery content threshold given by a sensor. 
Controllers 1 and 2 are still activated, but controller 3 is deactivated. 
The stop_required method of Battery class returns True, ready_to_release changes from True to False.

Expected values :
- the battery's ready_to_release value is False at all times
- the battery's flow_Elec_out value is 0 at all times
