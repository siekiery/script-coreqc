# CoreQC
### Developer: Jakub Pitera  

Performs automated QC of Recall CSV logs while also performing necessary postprocessing steps.

### List of QC actions:
1.	Check if metadata (first 7 columns) mnemonics and units are matching the template.
2.	Check metadata values (lab name, test type, sample type, test date).
3.	Check if mnemonics are unique
4.	Check if mnemonics are valid (for specific test type)
5.	Check if units are correct for specific mnemonic
6.	Check if data values are in expected range for that unit
7.	Check depth column for duplicates

### List of postprocessing actions:
1.	Cleans mnemonic and unit rows. Replaces to uppercase.
2.	Increment duplicates in Depth column by 0.00001. Causes all values in the column to be unique.
3.	Splits CSV logs that contain more than 10 data columns to subfiles containing 8 data columns each.

A mandatory supplement to the script, QC_Settings.xlsx (not available on GitHub) file is controlling the QC setup. It lists all the correct values for each QC action. Users can edit and improve QC_Settings.xlsx according to current demands.
