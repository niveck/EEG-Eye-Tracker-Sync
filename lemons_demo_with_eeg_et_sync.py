# ET is Eye Tracker
# "Trial Onset" means the start of the real data collection trial, right after the synchronization protocol

# The Synchronization Protocol:
# In this demo, the synchronization protocol is different, because of the short beginning phase of the EEG recording
# (3 seconds). Therefore, the full protocol is as follows:
# 1. Start recording the ET data (EEG trial should start within 25 seconds - can be changed in ET_BEGINNING_TIME).
#    It is important to leave both eyes uncovered when it starts, so the initial calibration would work.
# 2. Click "play" on the EEG trial, and cover the left eye for the 3 seconds countdown, until the trial onsets.
#    Best to du using an object that is similar to a paper, being held not with a small distance form the face,
#    so the eye can remain open until the trial starts.
# 3. When the trial onsets uncover the left eye.
# 4. When the trial ends, stop the ET recording by manually interrupting it.

import os
import numpy as np
from PIL import Image, ImageDraw
from datetime import datetime
from eeg_et_hr_synchronizer import handle_argv, find_data_paths, preprocess_eeg_data, preprocess_et_data, \
    save_synchronized_data, get_most_recent_file, EEG_SAMPLE_RATE, ET_SAMPLE_RATE

# Paths:
LEMONS_EEG_DATA_PARENT_DIR = "/home/innereye/innereye/Datasets/Lemons/EEG"
USED_LEMON_IMAGES_RECORDS_DIR = "/home/innereye/innereye/Datasets/Lemons/outputLists"
IMAGES_DIR = "/home/innereye/innereye/Datasets/Lemons/stim"

# Images dimensions (when using the 175% view on the RSVP app):
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
LEMON_LEFT_EDGE_ON_SCREEN = 523  # on X-axis
LEMON_RIGHT_EDGE_ON_SCREEN = 1397.8  # on X-axis
LEMON_WIDTH = LEMON_RIGHT_EDGE_ON_SCREEN - LEMON_LEFT_EDGE_ON_SCREEN
LEMON_TOP_EDGE_ON_SCREEN = 11  # on Y-axis
LEMON_BOTTOM_EDGE_ON_SCREEN = 810.8  # on Y-axis
LEMON_HEIGHT = LEMON_BOTTOM_EDGE_ON_SCREEN - LEMON_TOP_EDGE_ON_SCREEN

# Timings:
ET_BEGINNING_TIME = 25  # seconds (time for the demo beginning protocol, before starting RSVP task)
MIN_BEGINNING_PROTOCOL_WINK_TIME = 2  # seconds (in case first second was missed)
MIN_BEGINNING_PROTOCOL_WINK_SAMPLES = MIN_BEGINNING_PROTOCOL_WINK_TIME * EEG_SAMPLE_RATE  # samples

# Gaze marks:
GAZE_MARK_COLOR = (255, 0, 0)  # red in RGB
GAZE_MARK_RADIUS = 3  # pixels


def get_lemon_onset_timestamps(eeg_df):
    """
    :param eeg_df: EEG data frame
    :return: timestamps (indices in the data frame) for onsets of new lemons
    """
    return np.where(eeg_df.TRG.diff() == -1)[0]


def get_trial_images_paths():
    """
    :return: list of paths for the images that were used in the trial,
    ordered by their order in the trial
    """
    record_file = get_most_recent_file(USED_LEMON_IMAGES_RECORDS_DIR)
    with open(record_file, "r") as f:
        records = f.readlines()
    # record.split(" ") is: [<image file name>, <type of target>]
    return [os.path.join(IMAGES_DIR, record.split(" ")[0]) for record in records]


def get_gaze_center(sample):
    """
    :param sample: ET data frame sample
    :return: tuple with the coordinates of the center between the 2 eyes' gaze
    """
    return ((sample["left_x"] + sample["right_x"]) / 2 * SCREEN_WIDTH,
            (sample["left_y"] + sample["right_y"]) / 2 * SCREEN_HEIGHT)


def is_located_inside_image(gaze_center):
    """
    :param gaze_center: tuple with the coordinates of the center between the 2 eyes' gaze
    :return: whether this point is in the target image boundaries
    """
    return (LEMON_LEFT_EDGE_ON_SCREEN < gaze_center[0] < LEMON_RIGHT_EDGE_ON_SCREEN and
            LEMON_TOP_EDGE_ON_SCREEN < gaze_center[1] < LEMON_BOTTOM_EDGE_ON_SCREEN)


def adjust_screen_coordinates_to_image(gaze_center, image):
    """
    :param gaze_center: tuple with the coordinates of the center between the 2 eyes' gaze
    (in relation to the total screen)
    :param image: the target image object
    :return: an adjustment of the coordinates to only the target image
    """
    image_width, image_height = image.size
    return (int((gaze_center[0] - LEMON_LEFT_EDGE_ON_SCREEN) / LEMON_WIDTH * image_width),
            int((gaze_center[1] - LEMON_TOP_EDGE_ON_SCREEN) / LEMON_HEIGHT * image_height))


def add_gaze_mark_to_image(draw, x_coordinate, y_coordinate):
    """
    Adds a red circle mark in the requested coordinates to the target image
    :param draw: the drawing object of the image
    :param x_coordinate: of the center of the dot
    :param y_coordinate: of the center of the dot
    """
    draw.ellipse((x_coordinate - GAZE_MARK_RADIUS, y_coordinate - GAZE_MARK_RADIUS,
                  x_coordinate + GAZE_MARK_RADIUS, y_coordinate + GAZE_MARK_RADIUS),
                 fill=GAZE_MARK_COLOR)
    # can also be done with one pixel using the image object:
    # image.putpixel((x_coordinate, y_coordinate), GAZE_MARK_COLOR)


def save_et_locations_over_images(sync_df, output_dir):
    """
    Saves the ET coordinates over the images used for the RSVP trial
    :param sync_df: synchronized data frame for both ET and EEG data
    :param output_dir: the output directory
    """
    sync_df["diff"] = sync_df.TRG.diff()
    image_index = 0
    currently_processing_image = True  # synchronized data starts at a real event (lemon is shown)
    all_image_paths = get_trial_images_paths()
    image, draw = create_new_image_objects(all_image_paths[0])
    for index, row in sync_df.iterrows():
        if row["diff"] == 1:  # lemon finished
            image.save(os.path.join(output_dir, f"{image_index}_" + os.path.basename(all_image_paths[image_index])))
            currently_processing_image = False
        elif row["diff"] == -1:  # a new lemon starts
            image_index += 1
            image, draw = create_new_image_objects(all_image_paths[image_index])
            currently_processing_image = True
        else:  # == 0, or nan for the first sample
            if (not currently_processing_image or
                    index % int(EEG_SAMPLE_RATE / ET_SAMPLE_RATE) != 0):  # ET data is resampled
                continue
            gaze_center = get_gaze_center(row)
            if not is_located_inside_image(gaze_center):
                continue
            x_coordinate, y_coordinate = adjust_screen_coordinates_to_image(gaze_center, image)
            add_gaze_mark_to_image(draw, x_coordinate, y_coordinate)
            # image.show()  # can be uncommented-out for debugging
    print("All gazes were successfully visually recorded on images!")


def create_new_image_objects(image_path):
    """
    :param image_path: path to a new target image
    :return: the image object after being resized to screen dimension
    and its respective draw image that allows adding dots to it
    """
    image = Image.open(image_path)
    image.resize((int(LEMON_RIGHT_EDGE_ON_SCREEN - LEMON_LEFT_EDGE_ON_SCREEN),
                  int(LEMON_BOTTOM_EDGE_ON_SCREEN - LEMON_TOP_EDGE_ON_SCREEN)))
    draw = ImageDraw.Draw(image)
    return image, draw


def left_eye_winks(sample):
    """
    :param sample: a row from the ET data frame
    :return: whether the left eye was closed and the right one was open during that sample
    """
    return (np.isnan(sample["left_x"]) and np.isnan(sample["left_y"]) and
            not np.isnan(sample["right_x"]) and not np.isnan(sample["right_y"]))


def get_et_trial_onset_timestamp_by_wink(et_df):
    """
    :param et_df: ET data frame
    :return: end timestamp (index) for the winking phase before real trial onsets
    """
    data = et_df[:ET_BEGINNING_TIME * EEG_SAMPLE_RATE]
    wink_timestamps = []
    current_index = 0
    currently_winking = False
    new_start = None
    while current_index < len(data):
        if left_eye_winks(data.loc[current_index]):
            if not currently_winking:
                new_start = current_index
                currently_winking = True
        else:  # eyes are open
            if currently_winking:
                wink_timestamps.append((new_start, current_index))
                currently_winking = False
        current_index += 1
    if not wink_timestamps:
        return ET_BEGINNING_TIME * EEG_SAMPLE_RATE
    # index [0] will be the longest wink, and its index [1] will be the end timestamp
    return sorted(wink_timestamps, key=lambda pair: pair[1] - pair[0], reverse=True)[0][1]


def main():
    """
    Main function of the demo that synchronizes the EEG and ET data of an RSVP trial
    """
    recording_identifier = handle_argv(usage_message="")
    eeg_data_path, et_data_path, _ = find_data_paths(recording_identifier,
                                                     eeg_data_parent_dir=LEMONS_EEG_DATA_PARENT_DIR)
    eeg_df = preprocess_eeg_data(eeg_data_path)
    et_df = preprocess_et_data(et_data_path)
    lemon_onset_timestamps = get_lemon_onset_timestamps(eeg_df)
    eeg_trial_onset_timestamp = lemon_onset_timestamps[0] if len(lemon_onset_timestamps) > 0 else 0
    et_trial_onset_timestamp = get_et_trial_onset_timestamp_by_wink(et_df)
    sync_df, output_dir = save_synchronized_data(eeg_df, et_df, eeg_trial_onset_timestamp, et_trial_onset_timestamp)
    save_et_locations_over_images(sync_df, output_dir)


if __name__ == '__main__':
    main()
