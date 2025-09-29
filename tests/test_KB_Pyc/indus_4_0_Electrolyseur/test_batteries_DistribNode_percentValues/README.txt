Description : 
Test of the DistribNode class, 
case where a single continuous electrical source is distributed 
to two batteries thanks to a distribution node. 
25% of the flow is distributed to battery 1 and 75% of the flow to battery 2. 

We observe the complete filling of battery 2 at time = 2.66
Expected values : 
- The export request then changes to False. 
- The output flow 2 of the distribution therefore changes to 0 
- The output flow of the distribution for battery 1 then increases up to the value of the nominal flow of battery 1.
- Battery 1 fills faster now that Battery 2 is full

We observe the complete filling of battery 2 (time = 2.6), then the complete filling of battery 1 (time = 4).
Expected values forme time > 4:
- The export request for battery 1 then changes to 0. 
- The output flow 1 of the distribution therefore changes to 0 
- The output flow of the source changes to 0
