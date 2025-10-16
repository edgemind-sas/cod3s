Description : 
Consumer class Test
The consumer sends a request for its nominal flow. 
It does not consume more than its demand.
We produce less water than we consume. The tank is almost full at initialization. 

Expected value:
-The export demand of consumer is the minimum between the nominal flow demand and the maximum input flow.
-The capacity stay to 0 or positiv content ( history : bug with negative value for content of CapacityMulti)

