# ET is Eye Tracker
# HR is Heart Rate
# "Beginning" usually means the beginning protocol used for the synchronization, before actual trial
# "Trial Onset" means the start of the real data collection trial, right after the synchronization protocol

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime


# Usage:
HELP_FLAGS = ["?"] + [flag_prefix + flag for flag_prefix in ["", "-", "--"] for flag in ["h", "help", "u", "usage"]]
USAGE_MESSAGE = f"""Usage:
For using the most recent data files in the output directories: 
    python eeg_et_hr_synchronizer.py
For using specific data files that contain an identifier substring in their name:
    python eeg_et_hr_synchronizer.py <identifier>
For getting this help/usage message:
    python eeg_et_hr_synchronizer.py <any of the following help flags>
        {HELP_FLAGS}
"""

# Paths:
EEG_DATA_PARENT_DIR = "/home/innereye/Documents/EEG_output"
ET_DATA_PARENT_DIR = "/home/innereye/Documents/ET_output"
HR_DATA_PARENT_DIR = "/home/innereye/Documents/HR_output"
SYNCHRONIZED_OUTPUT_DIR = "/home/innereye/Documents/synchronized_data"

# Steady constants:
EEG_SAMPLE_RATE = 300  # Hz
ET_SAMPLE_RATE = 60  # Hz
EEG_ELECTRODES = ["F3", "F4", "C3", "C4", "Pz", "P3", "P4", "TRG"]
ET_COLUMN_FOR_SYNC = "left_x"

# Beginning protocol: start running Eye-Tracker, then start recording EEG; During the first 10 seconds of the trial,
# 3 distinct presses should be manually made onto the left frontal electrode (F3).
# When the subject feels the press, they should close their eyes until it is released.

# Adjustable constants (depend on the beginning protocol)
ARTIFACT_ELECTRODE = "F3"
ARTIFACT_EPOCH_LENGTH = 0.5  # seconds
EPOCH_JUMP = int(ARTIFACT_EPOCH_LENGTH * EEG_SAMPLE_RATE)
ARTIFACT_DIFFERENCE_THRESHOLD = 100
EEG_BEGINNING_TIME = 12  # seconds (time for the beginning protocol, before starting real trial)
ET_BEGINNING_TIME = 20  # seconds (time for the beginning protocol, before starting real trial)
SHORT_BLINK_SAMPLES_NUM = 10  # after over sampling the ET data, equivalent to / 5 == 2


def get_most_recent_file(dir, type=None, name_identifier=None):
    """
    :param dir: directory path
    :param type: specific file type to look for (or all if None)
    :param name_identifier: specific substring to look for in file's name (or all if None)
    :return: the most recently modified file in dir, with the specific type
    """
    if not os.path.isdir(dir):
        raise ValueError(f"The following is not a directory path: {dir}")
    files = []
    for file in os.listdir(dir):
        file_path = os.path.join(dir, file)
        if os.path.isfile(file_path):
            if (type and not file.endswith(type)) or (name_identifier and name_identifier not in file):
                continue
            files.append((file_path, os.path.getmtime(file_path)))
    if not files:
        wanted_type = type + " " if type else ""
        wanted_name = f"with {name_identifier} in their name" if name_identifier else ""
        raise ValueError(f"No {wanted_type}files {wanted_name}in {dir}")
    files.sort(key=lambda file: file[1], reverse=True)
    return files[0][0]


def find_data_paths(recording_identifier=None, eeg_data_parent_dir=EEG_DATA_PARENT_DIR,
                    et_data_parent_dir=ET_DATA_PARENT_DIR, hr_data_parent_dir=HR_DATA_PARENT_DIR):
    """
    Finds the EEG, ET, HR data paths (by this order) based on the recording_identifier.
    If recording_identifier not given, chooses the most recent files.
    """
    return tuple([get_most_recent_file(parent_dir, type="csv",
                                       name_identifier=recording_identifier)
                  for parent_dir in [eeg_data_parent_dir, et_data_parent_dir, hr_data_parent_dir]])


def preprocess_et_data(et_data_path):
    """
    Removes the original timestamp column and duplicates each row to fit the EEG sample rate
    """
    df = pd.read_csv(et_data_path).drop("time_ms", axis=1)
    rows = []
    for index, row in df.iterrows():
        rows.extend([row] * (EEG_SAMPLE_RATE // ET_SAMPLE_RATE))  # resample to suit EEG sample rate
    return pd.DataFrame(rows).reset_index(drop=True)


def preprocess_eeg_data(eeg_data_path):
    """
    Names the columns by the right electrodes names (including the trigger)
    """
    df = pd.read_csv(eeg_data_path)
    df.columns = EEG_ELECTRODES
    return df


def get_eeg_artifact_timestamps(eeg_df):
    """
    :param eeg_df: EEG data frame
    :return: list of (start, end) epoch timestamps which have an artifact,
    based on their max value's difference from the previous one
    """
    data = eeg_df[ARTIFACT_ELECTRODE]
    artifact_epochs = []
    prev_max = data[:EPOCH_JUMP].max()
    epoch_start = EPOCH_JUMP
    epoch_end = 2 * EPOCH_JUMP
    while epoch_end < len(data):
        cur_max = data[epoch_start:epoch_end].max()
        if cur_max - prev_max > ARTIFACT_DIFFERENCE_THRESHOLD:
            artifact_epochs.append((epoch_start, epoch_end))
        prev_max = cur_max
        epoch_start = epoch_end
        epoch_end = epoch_start + EPOCH_JUMP
    return artifact_epochs


def get_eeg_trial_onset_timestamp(eeg_artifact_timestamps):
    """
    :param eeg_artifact_timestamps: list of (start, end) epoch timestamps
    :return: end timestamp of the last artifact epoch that is part of a 3 artifact sequence
    """
    return get_trial_onset_timestamps(eeg_artifact_timestamps, EEG_BEGINNING_TIME)


def get_beginning_timestamps(timestamps, end_time_of_beginning):
    """
    :param timestamps: list of (start, end) epoch timestamps
    :param end_time_of_beginning: the required end timestamp (index) for the beginning protocol
    :return: only timestamps that are part of the beginning protocol (based on index)
    """
    return [(start, end) for start, end in timestamps
            if end <= end_time_of_beginning]


def get_closed_eyes_timestamps(et_df):
    """
    :param et_df: ET data frame
    :return: list of (start, end) timestamps for closed eyes periods
    """
    data = et_df[ET_COLUMN_FOR_SYNC]
    closed_eyes_timestamps = []
    current_index = 0
    # advance index until first eye tracking samples (beginning is usually NaN)
    while np.isnan(data[current_index]):
        current_index += 1
    eyes_were_open = True
    new_start = None
    while current_index < len(data):
        if np.isnan(data[current_index]):  # eyes are closed
            if eyes_were_open:
                new_start = current_index
                eyes_were_open = False
        else:  # eyes are open
            if not eyes_were_open:
                if current_index - new_start > SHORT_BLINK_SAMPLES_NUM:  # don't count short blinks
                    closed_eyes_timestamps.append((new_start, current_index))
                eyes_were_open = True
        current_index += 1
    return closed_eyes_timestamps


def get_et_trial_onset_timestamps(closed_eyes_timestamps):
    """
    :param closed_eyes_timestamps: list of (start, end) closed eye period timestamps
    :return: end timestamp of the last closed eye period that is part of a 3 periods sequence
    """
    return get_trial_onset_timestamps(closed_eyes_timestamps, ET_BEGINNING_TIME)


def get_trial_onset_timestamps(timestamps, end_time_of_beginning):
    """
    Generic function to use for all types of data
    :param timestamps: list of (start, end) epoch timestamps
    :param end_time_of_beginning: the required time (in seconds) of the beginning protocol
    :return: end timestamp of the last event that represents this type of data's trial onset
    """
    beginning_timestamps = get_beginning_timestamps(timestamps, EEG_SAMPLE_RATE * end_time_of_beginning)
    if not beginning_timestamps:
        return EEG_SAMPLE_RATE * end_time_of_beginning  # start right after the beginning protocol
    # starting with a naive solution - just get the end of the last event:
    return beginning_timestamps[-1][1]


def save_synchronized_data(eeg_df, et_df, eeg_trial_onset_timestamp, et_trial_onset_timestamp):
    """
    Saves the synchronized data of the real trial into both separate and combined CSV files.
    :param eeg_df: EEG data frame
    :param et_df: ET data frame
    :param eeg_trial_onset_timestamp: timestamp (index) of the EEG data for the onset of the real trial
    :param et_trial_onset_timestamp: timestamp (index) of the ET data for the onset of the real trial
    :return: the synchronized data frame and the output directory, in case their use is needed
    """
    trial_eeg = eeg_df[eeg_trial_onset_timestamp:]
    trial_et = et_df[et_trial_onset_timestamp:]
    all_trial_data_combined = pd.concat([trial_eeg.reset_index(drop=True), trial_et.reset_index(drop=True)], axis=1)

    output_dir = os.path.join(SYNCHRONIZED_OUTPUT_DIR, datetime.now().strftime("%d%m%Y_%H%M"))
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    trial_eeg.to_csv(os.path.join(output_dir, "trial_eeg.csv"))
    trial_et.to_csv(os.path.join(output_dir, "trial_et.csv"))
    all_trial_data_combined.to_csv(os.path.join(output_dir, "all_trial_data_combined.csv"))
    print("Synchronized data files were successfully saved in " + output_dir)
    return all_trial_data_combined, output_dir


def handle_argv(usage_message=USAGE_MESSAGE):
    """
    Handles the argument variables.
    If arguments supplied are not suitable for a run, exits the program.
    :param usage_message: a help message with explanation about usage of the code
    :return: the data recordings identifier to use for data extraction (or None)
    """
    if len(sys.argv) > 2:
        print("Wrong usage!")
        print(usage_message)
        sys.exit()
    elif len(sys.argv) == 2:
        if sys.argv[1] in HELP_FLAGS:
            print(usage_message)
            sys.exit()
        else:
            return sys.argv[1]  # recording_identifier
    else:
        return None


def main():
    """
    Main code to run when running the beginning protocol for the synchronization.
    """
    recording_identifier = handle_argv()
    eeg_data_path, et_data_path, hr_data_path = find_data_paths(recording_identifier)
    eeg_df = preprocess_eeg_data(eeg_data_path)
    et_df = preprocess_et_data(et_data_path)
    # hr_df = preprocess_hr_data(hr_data_path)
    eeg_artifact_timestamps = get_eeg_artifact_timestamps(eeg_df)
    eeg_trial_onset_timestamp = get_eeg_trial_onset_timestamp(eeg_artifact_timestamps)
    closed_eyes_timestamps = get_closed_eyes_timestamps(et_df)
    et_trial_onset_timestamp = get_et_trial_onset_timestamps(closed_eyes_timestamps)
    save_synchronized_data(eeg_df, et_df, eeg_trial_onset_timestamp, et_trial_onset_timestamp)


if __name__ == '__main__':
    main()
