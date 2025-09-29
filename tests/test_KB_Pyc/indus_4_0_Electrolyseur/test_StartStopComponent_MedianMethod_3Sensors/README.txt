Description : 
Testing the StartStopComponent (compute_reference_mediane method), Sensor and Automaton classes, 
System with a battery with init_state = "stop" and method = "median", three controllers, three sensors and one consumer. 
Source 1 produces 20, source 2 produces 10, source 3 produces 1.
Each source has a connected sensor that monitors production.
Each sensor is connected to a controller with an activation threshold of > 5 and a deactivation threshold of < 5.
The battery therefore has 3 controllers, of which 1 returns -1 and the two other return +1.
The median [+1, +1, -1] = +1, which activates the battery.

Expected values :
- Autom_1_signal_out = +1
- Autom_2_signal_out = +1
- Autom_3_signal_out = -1
- the battery's ready_to_release value is True 
- the battery's flow_Elec_out value is 6
