
Description : 
Consumer class Test
The consumer sends a request for its nominal flow. 
It does not consume more than its demand.

Expected value:
- v_consumer_flow_out is the minimum between the nominal flow demand of consumer, flow_in_max of consumer and flow_ou_max of capacity.
- The perf is equal to 0.25 (flow nominal of consumer = 8, flow_out_max of capacity = 10, flow_in_max of consumer = 2)
- the flow_demand_export of consumer is equal 2
