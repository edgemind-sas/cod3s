Description : 
Testing DCC (Common Cause Failure) with three sensors. Using failure mode :

failure_modes:
  - fm_name: "vc_capteur"
    targets: ["C_H2_Local_1", "C_H2_Local_2", "C_H2_Local_3"]
    failure_effects:
      v_measure_blocked: true
    occ_law: "delay"
    failure_param: [4, 5, 6]
    repair_param: [1, 1, 1]

Expected values :
- For the three sensors, v_measure_blocked = 0 at t = 0,1,2,3,4 ( no failing sensors, one failing sensor, or two failing sensors)
- For the three sensors, v_measure_blocked = 1 at t = 5,6,7 (all 3 sensors are failing)
- For the three sensors, v_measure_blocked = 0 at t = 8 (after repair)

