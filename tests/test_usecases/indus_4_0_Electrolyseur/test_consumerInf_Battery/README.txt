Description: 
Test with an electric source and pump to fill a battery.
A automaton with a threshold between 0 and 20. The electricity consumer demands as much electricity as the electricity source.
A sensor is connected to the battery's contents. The battery must not contain more than its capacity.
When the automaton is deactivated, the consumer receives anything, and the battery then fills up. 
Automaton failures:
v_inactive_forced = true between t = 1 and t = 7
v_active_forced = true after time 8

Expected values:
- B1_Elec_content and B1_content_total are equal and increase up to 5 but do not exceed 5 (capacity = 5)
- B1_Elec_ratio is 1 all the time except at t = 0
- B1_flow_available_out = False when the PLC is forced to v_inactive_forced = True (between times 1 and 7), B1_flow_available_out = True the rest of the time
- B1_flow_elec_out = False when the PLC is forced to v_inactive_forced = True (between times 1 and 7), B1_flow_elec_out = True the rest of the time

