'''
record tobii eyetracker data into a folder os.environ['DATA_PATH']+'tobii_op'
it assumes you calibrated the ET already

Esc:     exit full screen
F1:      return to full screen
Alt+F4 : quit

to record to csv  : python stimdisplay/stimdispy/tobii.py
to record to image: python stimdisplay/stimdispy/tobii.py image

'''
import tobii_research
import time
import os
import sys
import pygame
import pandas    as     pd
import numpy     as     np
from   threading import Event
from   datetime  import datetime

TIME_LIMIT = 5 * 60  # in seconds, was originally 60*60

columns = ['time_ms', 'x', 'y', 'left_x', 'left_y', 'right_x', 'right_y', 'left_pupil', 'right_pupil']
def record(Continue = [True], timelimit=TIME_LIMIT, columns=columns):
    '''
    record eyetracking to a csv
    :param
        Continue: list of booleans
          Continue[0] continues the recording (can be manipulated outside the function)
        timelimit: int or None if no timelimit
        time limit in seconds
    :return:
    a csv with columns: time, left_x, left_y, right_x, right_y
    '''
    columns = ','.join([columns[0]] + columns[3:])
    def gaze2csv_callback(gaze_data):
        # Print gaze points of left and right eye
        t           = time.time()
        gaze_left   = gaze_data['left_gaze_point_on_display_area']
        gaze_right  = gaze_data['right_gaze_point_on_display_area']
        pupil_left  = gaze_data['left_pupil_diameter']
        pupil_right = gaze_data['right_pupil_diameter']
        # print(pupil_left)
        # op = 'fgf'
        op          = f'{t},{gaze_left[0]},{gaze_left[1]},{gaze_right[0]},{gaze_right[1]},{pupil_left},{pupil_right}'
        # print(op)
        os.system(f'echo "{op}" >> {op_file}')
    destination = os.environ['DATA_PATH']+'tobii_op'
    if not os.path.exists(destination):
      os.mkdir(destination)
    # prev = glob('ET_*.csv')
    now     = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    op_file = destination+'/ET_'+now+'.csv'
    if os.path.isfile(op_file):
        raise Exception('file exists\n'+op_file)
    existing_eyetrackers = tobii_research.find_all_eyetrackers()
    # Choose the required eye tracker
    eyetracker           = existing_eyetrackers[0]
    # print('left_x,left_y,right_x,right_Y')
    print('recording tobii')
    os.system(f'echo "{columns}" > {op_file}')
    # Set the callback that will be used each time new data arrives
    eyetracker.subscribe_to(
        tobii_research.EYETRACKER_GAZE_DATA, gaze2csv_callback, as_dictionary=True)
    starttime = time.time()
    # Let the application print the data for a while
    while Continue[0]:
      time.sleep(.1)
      if timelimit is not None and (time.time() - starttime) > timelimit:
        Continue[0] = False
    # Remove the callback
    eyetracker.unsubscribe_from(tobii_research.EYETRACKER_GAZE_DATA, gaze2csv_callback)
    print(f'Eyetracker data saved to {op_file}')


def record_image(image_file=None, background=None, eye='left', timelim=TIME_LIMIT, echo=True, columns=columns):
    # TODO: input- echo. output - change name to creation time, exit on Esc, crop image
    '''
    embed eyetrack data in the image watched.
    :param
        Continue: list of booleans
          Continue[0] continues the recording (can be manipulated outside the function)
          Continue[1] determines whether to take timelimit into account (can be manipulated outside the function)
        image_file: None | str
        eye: str
          'left', 'right' or 'both'
    :return:
        saves the image with ET marks near the watched image.
    '''
    #  First treat str arguments coming from sys.argv
    if type(echo) == str:
        echo = eval(echo)
    if type(timelim) == str:
        timelim = eval(timelim)
    existing_eyetrackers = tobii_research.find_all_eyetrackers()
    if len(existing_eyetrackers):
        eyetracker = existing_eyetrackers[0]
    else:
        raise Exception('Connect eyetracker')
    pygame.init()
    info = pygame.display.Info()
    SIZE = WIDTH, HEIGHT = info.current_w, info.current_h
    if background is None:
        composit = np.zeros((WIDTH, HEIGHT, 3), 'uint8')
        # background = pygame.surfarray.array3d(composit)
        backgroundimg = pygame.surfarray.make_surface(composit)
    else:
        if background == 'mosaic':
            background = '/home/innereye/Data/muRata/ETmaterials/assembly_line_mosaic.png'
        backgroundimg = pygame.image.load(background)
        composit = pygame.surfarray.array3d(backgroundimg)

    def end_recording():
        eyetracker.unsubscribe_from(
            tobii_research.EYETRACKER_GAZE_DATA, gaze2image_callback)
        # print('after')
        now = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        destination_path = destination[:-1] if destination[-1] == "/" else destination
        op_file = f'{destination_path}/{image_file.replace(".png", "")}_ET_{now}.png'
        # plt.imsave(op_file, composit)
        comp_surf = pygame.surfarray.make_surface(
            composit[start_row:end_row, start_col:end_col, :])
        print(destination_path)
        print(image_file)
        pygame.image.save(comp_surf, op_file)
        df = pd.DataFrame(xy, columns=columns)
        df.to_csv(op_file.replace(".png", ".csv"), index=None)
        print(f'Image saved to {op_file}')
        print(df)
        if not e.is_set():
            e.set()
        # pygame.quit()
        # sys.exit()

    def gaze2image_callback(gaze_data):
        time1 = time.time()
        if eye == 'both':
            gaze_one_eye = [np.nanmean([gaze_data[ 'left_gaze_point_on_display_area'][0],
                                        gaze_data['right_gaze_point_on_display_area'][0]]),
                            np.nanmean([gaze_data[ 'left_gaze_point_on_display_area'][1],
                                        gaze_data['right_gaze_point_on_display_area'][1]])]
        else:
            gaze_one_eye = gaze_data[eye+'_gaze_point_on_display_area']

        # print(gaze_one_eye)
        # gaze_right_eye = gaze_data['right_gaze_point_on_display_area']
        gazeW = int(
            gaze_one_eye[0] * WIDTH) if ~np.isnan(gaze_one_eye[0]) else np.nan
        gazeH = int(
            gaze_one_eye[1] * HEIGHT) if ~np.isnan(gaze_one_eye[1]) else np.nan
        if not any(np.isnan([gazeW, gazeH])):
            # Tried/true method
            composit[gazeW-2:gazeW+1, gazeH-2:gazeH+1, 0] = 255
            composit[gazeW-2:gazeW+1, gazeH-2:gazeH+1, 1:] = 0
            surf = pygame.surfarray.make_surface(composit)
            DISPLAYSURF.blit(surf, (0, 0))
            if echo:
                pygame.display.update()
        if 'time0' in locals():
            xy.append([int((time.time() - time0)*1000), gazeW, gazeH,
                       gaze_data['left_gaze_point_on_display_area' ][0],
                       gaze_data['left_gaze_point_on_display_area' ][1],
                       gaze_data['right_gaze_point_on_display_area'][0],
                       gaze_data['right_gaze_point_on_display_area'][1],
                       gaze_data['left_pupil_diameter' ],
                       gaze_data['right_pupil_diameter']])
        if any([event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN
                for event in pygame.event.get()]):
            # pygame.display.update()
            e.set()

    input_rect = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 - 100, 250, 50)
    small = (555, 474)  # to exit full screen with Esc
    # img           = pygame.transform.scale(img, SIZE)
    DISPLAYSURF = pygame.display.set_mode(
        SIZE, pygame.FULLSCREEN)  # pygame.RESIZABLE
    DISPLAYSURF.blit(backgroundimg, (0, 0))
    color_active = pygame.Color('lightskyblue3')
    color_passive = pygame.Color('chartreuse4')
    base_font = pygame.font.Font(None, 32)
    instruction = 'Press ENTER to continue'
    active = False
    if active:
        color = color_active
    else:
        color = color_passive
    pygame.draw.rect(DISPLAYSURF, color, input_rect)
    text_surface = base_font.render(instruction, True, (255, 255, 255))
    DISPLAYSURF.blit(text_surface, (input_rect.x + 5, input_rect.y + 5))
    input_rect.w = max(100, text_surface.get_width() + 10)
    pygame.display.update()
    reading = True
    while reading:
        for event in pygame.event.get():
            # if user types QUIT then the screen will close
            if event.type == pygame.QUIT:  # Alt+F4
                pygame.quit()
                print('quit')
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if input_rect.collidepoint(event.pos):
                    active = True
                else:
                    active = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    DISPLAYSURF = pygame.display.set_mode(small, 0, 32)
                    DISPLAYSURF.blit(backgroundimg, (0, 0))
                elif event.key == pygame.K_F1:  # F1
                    DISPLAYSURF = pygame.display.set_mode(
                        SIZE, pygame.FULLSCREEN)
                    DISPLAYSURF.blit(backgroundimg, (0, 0))
                    # print(event.type)
                elif event.key == pygame.K_RETURN:
                    reading = False

    if image_file is None or image_file == '':
        destination = '/home/innereye/Documents/ET_output/'
        image_file = 'bag.png'  # "example_lemon.jpg"
        image_files = [image_file]
    elif os.path.isdir(image_file):  # If folder, take all images in folder
        image_files = [fn for fn in os.listdir(image_file)
                       if not '_ET' in fn               # Ignore output files
                       and not fn == background      # Ignore background image file
                       and fn.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'))
                                                        # Only add image files
                       ]
        destination = image_file + '/'
    elif type(image_file) is str:  # If single image
        if not os.path.isfile(image_file):
            raise Exception('cannot find ' + image_file)
        destination, image_file = os.path.split(image_file)
        image_files = [image_file]
    if destination == '':
        destination = os.getcwd()+'/'
    if not os.path.isdir(destination):
        raise Exception('cannot find ' + destination)

    # Loop over all images
    for image_file in image_files:
        xy = []
        foreground = pygame.image.load(destination+'/'+image_file)
        foreground = pygame.surfarray.array3d(foreground)
        small_height, small_width, _ = foreground.shape
        # small_width, small_height = foreground.get_size()
        large_height, large_width, _ = composit.shape
        # Calculate the indices for the middle region in the large image
        start_row = (large_height - small_height) // 2
        end_row = start_row + small_height
        start_col = (large_width - small_width) // 2
        end_col = start_col + small_width
        composit = pygame.surfarray.array3d(backgroundimg)

        # Replace the middle region of the large image with the values from the small image
        composit[start_row:end_row, start_col:end_col, :] = foreground
        comp_surf = pygame.surfarray.make_surface(composit)
        DISPLAYSURF.blit(comp_surf, (0, 0))
        if 'time0' in locals():
            del time0
        eyetracker.subscribe_to(
            tobii_research.EYETRACKER_GAZE_DATA, gaze2image_callback, as_dictionary=True)
        print('Recording tobii')
        time.sleep(.3)
        pygame.display.update()
        time0 = time.time()
        # time.sleep(timelim)
        e = Event()
        e.wait(timelim)
        # pygame.display.update()
        end_recording()
    pygame.quit()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'image':
            kargs = {}
            for arg in sys.argv[2:]:
                print(arg)
                var, val = arg.split('=')
                kargs[var] = val
            record_image(**kargs)
        else:
            record()
    else:
        message = \
            '''
        InnerEye tobii recorder
        the first argument is image or csv, it determines if main calls record_image or record
        for image, you can have the following optional arguments:
            image_file=image.png
            background=background.png   this should be 1920x1080
            eye=left
        examples:
        python tobii.py csv
        python tobii.py image
        python tobii.py image background=mosaic.png
        python stimdisplay/stimdispy/tobii.py image image_file=heatmap.png
        '''
        print(message)
    # Search for all the existing eye trackers
