Description :
Testing the sensor class on the v_content data. 
The pump brings water to the tank. The tank fills over time. 
Checking that the sensor correctly records the amount of water in the tank. 
Adding a failure and checking that after repair, 
the sensor does not remain stuck on the last recorded value (historical bug).

Expected values:
After repair, the sensor retrieves the value of the amount of water in the tank at the same time.

