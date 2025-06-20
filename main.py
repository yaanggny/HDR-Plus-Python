import numpy as np
import rawpy
import imageio
import os, sys, glob
import os.path as opath
import multiprocessing
import halide as hl
from datetime import datetime
import threading
from functools import partial
os.environ['KIVY_NO_CONSOLELOG'] = '1' # Comment this line when debugging UI
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.factory import Factory
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from utils import time_diff
from align import align_images
from merge import merge_images
from finish import finish_image

from PIL import Image
import tiffile


'''
Loads a raw image

image_path : str
    String representing the path to the image

Returns: numpy ndarray with 4 values for each pixel (RGGB)
'''
def load_image(image_path):
    with rawpy.imread(image_path) as raw:
        image = raw.raw_image_visible.copy()
        return image


'''
Decode a raw CFA pattern

pattern : list of lists of integers (numpy.ndarray)
    RawPy.raw_pattern: the smallest possible Bayer pattern of a raw image

Returns: Integer in range 1 - 4, where
    1 : RGGB
    2 : GRBG
    3 : BGGR
    4 : RGBG
'''
def decode_pattern(pattern):
    pattern_str = ""
    for row in pattern:
        for val in row:
            if val == 0:
                pattern_str += 'R'
            elif val == 1:
                pattern_str += 'G'
            elif val == 2:
                pattern_str += 'B'
            else:
                pattern_str += 'G'
    if pattern_str == 'RGGB':
        return 1
    elif pattern_str == 'GRBG':
        return 2
    elif pattern_str == 'BGGR':
        return 3
    else:
        return 4


'''
Loads a burst of images

burst_path : str
    String representing the path to the folder containing the burst images

Returns: Halide buffer of raw images, reference image, white balance values for RGGB, 
         black level, white level, CFA pattern, color correction matrix
'''
def load_images(burst_path):
    print(f'\n{"=" * 30}\nLoading images...\n{"=" * 30}')
    start = datetime.utcnow()
    images = []
    white_balance_r = 0
    white_balance_g0 = 0
    white_balance_g1 = 0
    white_balance_b = 0
    black_point = 0
    white_point = 0
    cfa_pattern = 0

    # Create list of paths to the images
    paths = []
    paths = glob.glob(opath.join(burst_path, '*.dng'))
    if len(paths) == 0:
        raise ValueError("Burst format [*.dng] not recognized.")
    paths.sort(key=lambda x: int(x.split('load_N')[-1].split('.')[0]))

    # Load raw images
    print('Loading raw images...')
    p = multiprocessing.Pool(min(multiprocessing.cpu_count() - 1, len(paths)))
    for image in p.imap(load_image, paths):
        images.append(hl.Buffer(image))

    assert len(images) >= 2, "Burst must consist of at least 2 images"

    # Get a reference image to compare results
    print('Getting reference image...')
    with rawpy.imread(paths[0]) as raw:
        white_balance = raw.camera_whitebalance
        print('white balance', white_balance)
        white_balance_r = white_balance[0] / white_balance[1]
        white_balance_g0 = 1
        white_balance_g1 = 1
        white_balance_b = white_balance[2] / white_balance[1]
        cfa_pattern = raw.raw_pattern
        cfa_pattern = decode_pattern(cfa_pattern)
        ccm = raw.color_matrix
        black_point = int(raw.black_level_per_channel[0])
        white_point = int(raw.white_level)

        ref_img = raw.postprocess(output_bps=16)

    print('Building image buffer...')
    result = hl.Buffer(hl.UInt(16), [images[0].width(), images[0].height(), len(images)])
    for index, image in enumerate(images):
        resultSlice = result.sliced(2, index)
        resultSlice.copy_from(image)

    print(f'Loading finished in {time_diff(start)} ms.\n')
    return result, ref_img, white_balance_r, white_balance_g0, white_balance_g1, white_balance_b, black_point, white_point, cfa_pattern, ccm


'''
Main method of the HDR+ pipeline: align, merge, finish

burst_path : str
    The path to the folder containing the burst images
compression : float
    Compression to be used in finish step
gain : float
    Gain to be used in finish step
contrast : float
    Contrast to be used in finish step
UI : Root(FloatLayout) class object
    Kivy object used to update UI elements

After execution finishes, UI.original and UI.image will be set to the reference frame of the input,
and the result of the burst processed by the HDR+ pipeline, respectively.

If an error is encountered, these values will instead remain unchanged, and an error will be passed to the UI.
'''
def HDR(burst_path, compression, gain, contrast, UI):
    try:
        start = datetime.utcnow()

        print(f'Compression: {compression}, gain: {gain}, contrast: {contrast}')

        # Load the images
        print('Loading images... from ', burst_path)
        images, ref_img, white_balance_r, white_balance_g0, white_balance_g1, white_balance_b, black_point, white_point, cfa_pattern, ccm = load_images(
            burst_path)
        Clock.schedule_once(partial(UI.update_progress, 20))

        # dimensions of image should be 3
        assert images.dimensions() == 3, f"Incorrect buffer dimensions, expected 3 but got {images.dimensions()}"
        assert images.dim(2).extent() >= 2, f"Must have at least one alternate image"
        # Save the reference image
        print('Saving reference image...')
        # imageio.imsave('Output/input.jpg', ref_img)
        tiffile.imwrite("Output/input.tiff", ref_img)

        # Align the images
        alignment = align_images(images)

        # Merge the images
        merged = merge_images(images, alignment)

        # Finish the image
        print(f'\n{"=" * 30}\nFinishing image...\n{"=" * 30}')
        start_finish = datetime.utcnow()
        finished = finish_image(merged, images.width(), images.height(), black_point, white_point, white_balance_r,
                                white_balance_g0, white_balance_g1, white_balance_b, compression, gain, contrast,
                                cfa_pattern, ccm)

        Clock.schedule_once(partial(UI.update_progress, 30))

        result = finished.realize([images.width(), images.height(), 3])

        Clock.schedule_once(partial(UI.update_progress, 90))

        print(f'Finishing finished in {time_diff(start_finish)} ms.\n')

        # If portrait orientation, rotate image 90 degrees clockwise
        print('ref_img.shape: ', ref_img.shape)
        np_array = np.array(result, copy=False)  # (3, H, W)
        print('np_array.shape(result): ', np_array.shape)
        np_array = np.transpose(np_array, (1, 2, 0))  # (H, W, 3)
        if ref_img.shape[0] > ref_img.shape[1]:
            print('Rotating image')
            np_array = np.rot90(np_array, -1)
        print('np_array.shape(final): ', np_array.shape)
        Image.fromarray(np_array).save('Output/output.jpg')

        Clock.schedule_once(partial(UI.update_progress, 100))

        print(f'Processed in: {time_diff(start)} ms')

        # return 'Output/input.jpg', 'Output/output.jpg'

        Clock.schedule_once(partial(UI.update_paths, 'Output/input.tiff', 'Output/output.jpg'))

        Clock.schedule_once(UI.dismiss_progress)

    except Exception as e:
        Clock.schedule_once(partial(UI.show_error, e))


class Imglayout(FloatLayout):
    def __init__(self, **args):
        super(Imglayout, self).__init__(**args)

        with self.canvas.before:
            Color(0, 0, 0, 0)
            self.rect = Rectangle(size=self.size, pos=self.pos)

        self.bind(size=self.updates, pos=self.updates)

    def updates(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos


class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)
    path = StringProperty('')

class Root(FloatLayout):
    loadfile = ObjectProperty(None)
    progress_bar = ObjectProperty()
    progress_popup = None

    # Empty gallery images
    original = 'Images/gallery.jpg'
    image = 'Images/gallery.jpg'

    # Path to the burst images
    path = ''

    cancelled = False

    compression = 3.8
    gain = 1.1
    contrast = 1.0

    def build():
        c = Imglayout()
        root.add_widget(c)

    def dismiss_popup(self):
        self._popup.dismiss()

    def dismiss_progress(self, *largs):
        self.progress_popup.dismiss()

    def update_progress(self, num, *largs):
        self.progress_bar.value = num

    def update_paths(self, input_path, output_path, *largs):
        self.original = input_path
        self.image = output_path

    def reload_images(self, instance):
        self.ids.image0.source = self.original
        self.ids.image0.reload()
        self.ids.image1.source = self.image
        self.ids.image1.reload()

    def next(self, dt):
        if self.progress_bar.value >= 100:
            return False
        self.progress_bar.value += 1

    def show_error(self, error, *largs):
        if self.progress_popup:
            self.dismiss_progress()
        txt = '\n'.join(str(error)[i:i + 80] for i in range(0, len(str(error)), 80))
        float_popup = FloatLayout(size_hint=(0.9, .04))
        float_popup.add_widget(Label(text=txt,
                                     size_hint=(0.7, 1),
                                     pos_hint={'x': 0.15, 'y': 12}))
        float_popup.add_widget(Button(text='Close',
                                      on_press=lambda *args: popup.dismiss(),
                                      size_hint=(0.2, 4),
                                      pos_hint={'x': 0.4, 'y': 1}))
        popup = Popup(title='Error',
                      content=float_popup,
                      size_hint=(0.9, 0.4))
        popup.open()

    # Function to call the HDR+ pipeline
    def process(self):
        try:
            if not self.path:
                raise ValueError('No burst selected.')
            # Get slider values for compression, gain, and contrast
            self.compression = self.ids.compression.value
            self.gain = self.ids.gain.value
            self.contrast = self.ids.contrast.value

            self.progress_bar = ProgressBar()
            self.progress_popup = Popup(title=f'Processing {self.path}',
                                        content=self.progress_bar,
                                        size_hint=(0.7, 0.2),
                                        auto_dismiss=False)
            self.progress_popup.bind(on_dismiss=self.reload_images)
            self.progress_bar.value = 1
            self.progress_popup.open()
            Clock.schedule_interval(self.next, 0.1)

            HDR_thread = threading.Thread(target=HDR,
                                          args=(self.path, self.compression, self.gain, self.contrast, self,))
            HDR_thread.start()

        except Exception as e:
            self.show_error(e)

    def show_load(self):
        content = LoadDialog(load=self.load, cancel=self.dismiss_popup)
        content.path = r'E:\Dev\dataset\hdrplus'
        self._popup = Popup(title="Select burst image", content=content,
                            size_hint=(0.9, 0.9))

        self._popup.open()

    def load(self, path, filename):
        # Set the path to the burst images
        self.path = path
        self.cancelled = False
        self.dismiss_popup()

    def cancel(self):
        self.cancelled = True
        self.dismiss_popup()


class HDR_Plus(App):
    pass


Factory.register('Root', cls=Root)
Factory.register('LoadDialog', cls=LoadDialog)

if __name__ == '__main__':
    HDR_Plus().run()
