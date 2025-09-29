
Description : 
Simple test on the Multi Capacity class with a single flow type: H2. 
The consumer consumes a sinusoidal source.

Expected values:
- Good values ​​at initialization
- When the capacity's total capacity is reached, no more exports are possible to the consumer.
- The tank send the out flux that the consumer consumes
- No output flows for the consumer.
- the variable v_perf of consumer isn't 100 % all time
