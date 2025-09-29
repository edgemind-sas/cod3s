Description : 
Testing Battery and StartStopComponent classes with a method "mean" initialized to "stop,"
if the automaton is at stop, it no longer sends out any flow; it does not let anything out, 
so the content increases if there is something coming in. 
We ensure this with an consumer that always wants to consume a nominal flow equal to 1.

Expected values:
- flow_Elec_out = 0 for all times
- B1_ready_to_release = 0 for all times
- Elec_content fills up with all the flow that comes in (no outflow) until its maximum capacity of 9
- B1_content_total fills up with all the flow that comes in (no outflow) until its maximum capacity of 9
