Description : 
Testing the battery, stack, and capacitymulti classes, no failure
The battery has an export request from the electrolyzer, 
and we observe the battery slowly discharging. 
When it is empty, its output flow stops.
The electrolyzer then stops, and we observe the O2 flow stopping.
The quantity in the room increases until the electrolyzer stops.
Expected values:
- decrease of B1_content
- increase of Local_content_total
- Electrolyseur_flow_O2_out goes 1 to 0 when battery is empty
- B1_flow_out goes to 0 when battery is empty
