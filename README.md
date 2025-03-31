# This is LibreFlow

LibreFlow is a simple (meaning thrown together quickly) tool to analyse the exported CSV data from the FreeStyle Libre CGM

It is designed to:

* Find all fields with a Note, which it assumes are meals (TODO: we could limit it to "meal" data points only, but that wasn't my use case)
* Fine the closest Glucose reading to the note
* Analyse the peak Glucose reading within a 2 hour window following the meal
* Analyse the Postprandial Glucose reading at the 2 hour mark following the meal
* Highlight any high readings for Peak and Post prandial with a *** marker
* Summarise the mealtime and overnight (00:00 - 06:00) Glucose readings
* Export data to a CSV for further analysis

## Example Output

```text
--------------------------------------------------
Time: 2025-03-30 18:00
Note: Dinner - Takeout
Initial Glucose: 5.8 mmol/L (105 mg/dL)
Peak (2h): 6.3 mmol/L (114 mg/dL)
Postprandial (2h): 6.3 mmol/L (114 mg/dL)
Delta: +0.5 mmol/L (+9 mg/dL)
--------------------------------------------------

SUMMARY STATISTICS
==================================================
Average Fasting Glucose: 5.8 mmol/L (105 mg/dL)
Average Overnight Glucose: 5.3 mmol/L (96 mg/dL)
Average Peak Glucose: 6.3 mmol/L (114 mg/dL)
Average Postprandial Glucose: 6.3 mmol/L (114 mg/dL)
==================================================
```
