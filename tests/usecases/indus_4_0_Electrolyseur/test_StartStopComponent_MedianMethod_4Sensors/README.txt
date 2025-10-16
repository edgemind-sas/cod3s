
Description : 
Testing the StartStopComponent (compute_reference_mediane method), Sensor and Automaton classes, 
System with a battery with init_state = "stop" ans method = "median", four controllers, four sensors and one consumer. 
Source 1 produces 1, source 2 produces 5, source 3 produces 10 and source 4 produces 20.
Each source has a connected sensor that monitors production.
Each sensor is connected to a controller with an activation threshold of > 5 and a deactivation threshold of < 5.
The battery therefore has 4 controllers, of which 1 returns 0, 1 returns -1, and the other two return 1.
The median [0, -1, 1, 1] = 0.5, which activates the battery.

Expected values :
- Autom_1_signal_out = - 1
- Autom_2_signal_out = 0
- Autom_3_signal_out = 1
- Autom_4_signal_out = 1
- the battery's ready_to_release value is True 
- the battery's flow_Elec_out value is 6
