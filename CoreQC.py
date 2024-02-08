import os
import os.path as osp
import numpy as np
import pandas as pd
import re

LOG_NAME = r''
LOG_DIR = r''

class CoreQC:

    __VERSION__ = 1.0

    WELCOME = f"""
CoreQC
v{__VERSION__}

Quality Check of recall logs.

Developer: Jakub Pitera 
______________________________________________________________________


Single mode: Enter path of the .csv log into the prompt below. 

Bulk mode: Alternatively, enter the path of the directory. 
All logs found inside that directory tree (including the subfolders) will be checked.

CoreQC will proofread logs and notify about any errors or warnings.

Finally, decide if logs should be split into parts.
______________________________________________________________________
"""

    def __init__(self, ):

        print(CoreQC.WELCOME)

        while True:
            self.main()

    def main(self):
        """Main loop of the tool. Controls the flow. Prepare vars, ask users for input and calls methods."""

        # Prepare vars
        self.clear_logs()
        self.warnings = []
        self.errors = []

        # Ask user for filepath
        filepath = input("Enter path: ")
        assert osp.exists(filepath), "Invalid filepath."

        # Import settings
        self.load_settings()

        # Set QC mode- single or bulk
        if osp.isfile(filepath):
            self.mode = 'single'
            self.load_single(filepath)
        elif osp.isdir(filepath):
            self.mode = 'bulk'
            self.load_bulk(filepath)

        # Perform QC pipeline on each log
        for log in self.logs:
            print(f"\n# {osp.relpath(log, filepath)}")
            self.run_qc(log)

        # Split logs
        split = self.ask_split()
        if split:
            for log in self.logs:
                self.split_export(log)

        # Save output to .txt
        self.save_report()

        input("\nFinished.")

    def run_qc(self, log):
        """Controls flow of QC pipeline"""

        # Prepare variables
        self.clear_vars()

        # Load log from csv
        self.log_df = pd.read_csv(log, encoding_errors='ignore')

        # Run QC pipeline
        self.clean_log()
        self.qc_metadata()
        if not self.invalid_testtype:
            self.qc_data()
        self.qc_depth()

    def load_settings(self):
        """Sets settings, templates and valid mnemonics from QC_Settings.xlsx"""

        print("\nReading QC_Settings.xlsx")

        xl = pd.ExcelFile('QC_Settings.xlsx')
        general = xl.parse(sheet_name='GENERAL')
        template = xl.parse(sheet_name='TEMPLATE')
        mnemonics = {}
        for sheet in xl.sheet_names[2:]:
            df = xl.parse(sheet_name=sheet)
            df['MNEMONIC'] = df['MNEMONIC'].str.upper()
            df['UNIT'] = df['UNIT'].str.upper()
            if len(df['MNEMONIC'].unique()) != len(df['MNEMONIC']):
                self.raise_warning(sheet, 'mnemonic are not unique in QC_Settings.xlsx', type='', message='')
                df.drop_duplicates(subset='MNEMONIC', inplace=True)
            df.set_index('MNEMONIC', inplace=True)
            mnemonics[sheet] = df

        self.general = general
        self.template = template
        self.mnemonics = mnemonics

        self.metadata_cols = 7
        self.data_col_cap = 10
        self.data_cols_segment = 8

        self.log_indicator = '.CSV'

        del (xl)

    def load_single(self, filepath):
        """Loads single log if a filepath to single log has been provided"""

        assert filepath.upper().endswith(self.log_indicator), "Not a .csv"

        self.logs.add(filepath)

    def load_bulk(self, directory):
        """Loads all logs from the directory tree"""

        for (root, _, files) in os.walk(directory):
            for f in files:
                if f.upper().endswith(self.log_indicator):
                    self.logs.add(os.path.join(root, f))

        print(f"\nLoaded {len(self.logs)} logs.")

    def clear_logs(self):
        self.logs = set()

    def clear_vars(self):
        self.log_df = None
        self.lab_name = None
        self.test_type = None
        self.invalid_testtype = False
        self.sample_type = None
        self.test_date = None

    def clean_log(self):
        """Perform basic cleaning on the log"""
        df = self.log_df.copy()

        # Drop empty rows
        df.dropna(how='all', inplace=True)

        # Clean headers
        df.rename(columns=lambda x: str(x).strip().upper(), inplace=True)

        # Clean units row
        df.iloc[0] = df.iloc[0].str.strip('()[]').str.upper()

        self.log_df = df.copy()

    @staticmethod
    def ask_split():
        """Wraps user input regaridng the split"""
        split = ''
        while split not in ('y', 'n'):
            split = input("\nSplit logs? (y / n) ").lower()
        if split == 'y':
            split = True
        else:
            split = False
        return split

    def qc_metadata(self):
        """Perform QC on metadata"""

        df = self.log_df.iloc[:, :self.metadata_cols]
        template = self.template

        # Print test_type for reference
        print(f"CREP_TESTTYPE : {df.loc[1,'CREP_TESTTYPE']}")

        # Check metadata mnemonics and units
        for i in range(self.metadata_cols):
            df_col = df.columns[i]
            template_col = template.columns[i]
            df_unit = df.iloc[0, i]
            template_unit = template.iloc[0, i]
            if df_col != template_col:
                self.raise_error('', df_col, type='mnemonic')
            elif df_unit != template_unit:
                self.raise_error(df_col, df_unit, type='unit')

        lab_name = df.loc[1, 'CREP_LAB_NAME']
        test_type = df.loc[1, 'CREP_TESTTYPE']
        sample_type = df.loc[1, 'CREP_SAMPLETYPE']
        test_date = df.loc[1, 'CREP_TEST_DATE']

        # Check lab name
        if lab_name not in self.general['LAB_NAME'].values:
            self.raise_warning('CREP_LAB_NAME', lab_name)

        # Check test type
        if test_type not in self.general['TEST_TYPE'].values:
            self.invalid_testtype = True
            self.raise_error('CREP_TESTTYPE', test_type)

        # Check sample type
        if sample_type not in self.general['SAMPLE_TYPE'].values:
            self.raise_error('CREP_SAMPLE_TYPE', sample_type)

        # Check test date
        pattern = ("^\d{2}-(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)-\d{4}$")
        flag = re.match(pattern, test_date)
        if flag is None:
            self.raise_error('CREP_TEST_DATE', test_date)

        self.lab_name = lab_name
        self.test_type = test_type
        self.sample_type = sample_type
        self.test_date = test_date

    def qc_data(self):
        """Perform QC on data"""

        df = self.log_df.iloc[:, self.metadata_cols:]
        mnems = self.mnemonics[self.test_type]

        # Check if all mnemonics are unique
        if not len(df.columns.unique()) == len(df.columns):
            self.raise_error('', '', message='MNEMONICS ARE NOT UNIQUE!')
            return

        for col in df.columns:

            colx = re.sub("[0-9.]+", "XXXX", col)

            # Check menmonics
            if colx not in mnems.index:
                self.raise_error(col, '', type='mnemonic')
                continue

            # Store column units as variables
            df_unit = df.loc[0, col]
            mnems_unit = mnems.loc[colx, 'UNIT']

            # # If QC_Settings.xlsx has duplicated mnemonics
            # if isinstance(mnems_unit, pd.Series):
            #     mnems_unit = mnems_unit.iloc[0]
            #     print(mnems_unit)
            #     self.raise_warning(colx, '', message='mnemonic is duplicated in QC_Settings.xlsx')

            # Check units
            if df_unit != mnems_unit:
                self.raise_error(col, df_unit, type='unit')

            # Check values range
            try:
                df_min = float(df.loc[1:, col].min())
                df_max = float(df.loc[1:, col].max())
            except TypeError:
                continue
            except ValueError:
                continue

            if mnems.loc[colx, 'MIN'] is not np.nan \
                    and df_min < mnems.loc[colx, 'MIN']:
                self.raise_warning(col, df_min, type='min value', message='is not in expected range')

            if mnems.loc[colx, 'MAX'] is not np.nan \
                    and df_max > mnems.loc[colx, 'MAX']:
                self.raise_warning(col, df_max, type='max value', message='is not in expected range')

    def qc_depth(self):
        """Checks for duplicates in DEPTH and increments by 0.00001 if any"""

        df = self.log_df.copy()

        duplicated = df['DEPTH'].notna() & df['DEPTH'].duplicated()
        if duplicated.any():
            print(f"Incrementing {duplicated.sum()} duplicated DEPTHs")
        while duplicated.any():
            df['DEPTH'].loc[duplicated] = df['DEPTH'].loc[duplicated].astype(float) + 0.00001
            duplicated = df['DEPTH'].notna() & df['DEPTH'].duplicated()

        self.log_df = df.copy()

    def split_export(self, log):
        """Splits log into parts."""

        # Load log from csv
        self.log_df = pd.read_csv(log, encoding_errors='ignore')

        df = self.log_df

        # Save cleaned file before splitting
        df.to_csv(log, index=False)

        if df.shape[1] < self.metadata_cols + self.data_col_cap:
            return

        # Split to parts
        i = 1
        first_col = self.metadata_cols
        total_cols = df.shape[1]

        while first_col < total_cols:

            last_col = first_col + self.data_cols_segment
            savename = f'{log.upper().removesuffix(".CSV")}_{i}.csv'

            if last_col < total_cols:
                df.iloc[:, np.r_[:self.metadata_cols, first_col:last_col]].to_csv(savename, index=False)
            else:
                df.iloc[:, np.r_[:self.metadata_cols, first_col:total_cols]].to_csv(savename, index=False)

            first_col += self.data_cols_segment
            i += 1

    def save_report(self):
        pass

    def raise_warning(self, item, value, type='value', message='is not recognized', sep=' '):
        """Raises warning notification"""
        msg = f"WARNING:   {item}{sep}{value}{sep}{type}{sep}{message}."
        print(msg)
        self.warnings.append(msg)

    def raise_error(self, item, value, type='value', message='is invalid', sep=' '):
        """Raises error notification"""
        msg = f"ERROR:      {item}{sep}{value}{sep}{type}{sep}{message}!"
        print(msg)
        self.errors.append(msg)


if __name__ == "__main__":
    qc = CoreQC()
