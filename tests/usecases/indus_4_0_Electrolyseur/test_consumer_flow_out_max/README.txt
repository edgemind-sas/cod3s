
Description : 
Consumer class Test
The consumer sends a request for its nominal flow. 
It does not consume more than its demand.

Expected value:
- v_consumer_flow_out is the minimum between the nominal flow demand of consumer, flow_in_max of consumer and flow_ou_max of capacity.
- The perf is equal to 0.5 (flow nominal of consumer = 4, flow_out_max of capacity = 2, flow_in_max of consumer = 3)
- The flow_demand_export of consumer is 3
