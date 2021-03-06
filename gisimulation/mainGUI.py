"""
GUI module for gi-simulation.

Usage
#####

python mainGUI.py [Option...]::
    -d, --debug     show debug logs

@author: buechner_m  <maria.buechner@gmail.com>
"""
import numpy as np
import sys
import re
from functools import partial
import os.path
import scipy.io
import logging
# Set kivy logger console output format
formatter = logging.Formatter('%(asctime)s - %(name)s -    %(levelname)s - '
                              '%(message)s')
console = logging.StreamHandler()
console.setFormatter(formatter)
sys._kivy_logging_handler = console
import kivy
kivy.require('1.10.0')  # Checks kivy version
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.logger import Logger
from kivy.app import App
from kivy.clock import Clock
from kivy.garden.filebrowser import FileBrowser
from kivy.core.window import Window
from kivy.factory import Factory as F  # Widgets etc. (UIX)
import kivy.graphics as G

# Logging
# Set logger before importing simulation modules (to set format for all)
# Use Kivy logger to handle logging.Logger
logging.Logger.manager.root = Logger  # Makes Kivy Logger root for all
                                      # following loggers
logger = logging.getLogger(__name__)

# All imports using logging
import matplotlib
matplotlib.use('module://kivy.garden.matplotlib.backend_kivy')
import matplotlib.pyplot as plt
# gisimulation imports
import main
import simulation.parser_def as parser_def
import simulation.utilities as utilities
import simulation.check_input as check_input
import simulation.geometry as geometry


# Set App Window configuration
Window.maximize() # NOTE: On desktop platforms only

# %% Constants

ERROR_MESSAGE_SIZE = (600, 450)  # absolute
FILE_BROWSER_SIZE = (0.9, 0.9)  # relative
LINE_HEIGHT = 35
TAB_HEIGHT = 1200

# %% Custom Widgets


# #############################################################################
# Menu bar ####################################################################
class CustomSpinnerButton(F.Button):
    """
    Custom button for CustomSpinner, defined in .kv.
    """
    pass


class CustomSpinner(F.Spinner):
    """
    Custom Spinner, uses CustomSpinnerButton.
    """
    option_cls = F.ObjectProperty(CustomSpinnerButton)


# #############################################################################
# FileBrowser #################################################################
# Does not work with globally modified Label, use custom label for everything
# else
class NonFileBrowserLabel(F.Label):
    """
    Custom Label to avoid conflict with FileBrowser and allow global changes,
    defined in .kv.
    """
    pass


# #############################################################################
# Inputs ######################################################################
class FloatInput(F.TextInput):
    """
    TextInput which only allows positive floats.

    Note
    ####

    Adapted from 'https://kivy.org/docs/api-kivy.uix.textinput.html'
    (22.10.2017)

    """

    # Set input pattern
    pattern = re.compile('[^0-9]')  # Allowed input numbers

    def insert_text(self, substring, from_undo=False):
        """
        Overwrites the insert_text function to only accept numbers 0...9
        and '.', and 1 line.
        """
        pattern = self.pattern
        if '.' in self.text:
            s = re.sub(pattern, '', substring)
        else:
            s = '.'.join([re.sub(pattern, '', s) for s in substring.split('.',
                          1)])
        return super(FloatInput, self).insert_text(s, from_undo=from_undo)


class IntInput(F.TextInput):
    """
    TextInput which only allows positive integers.
    """

    pattern = re.compile('[^0-9]')  # Allowed input numbers

    def insert_text(self, substring, from_undo=False):
        """
        Overwrites the insert_text function to only accept numbers 0...9.
        """
        pattern = self.pattern
        s = re.sub(pattern, '', substring)
        return super(IntInput, self).insert_text(s, from_undo=from_undo)


class Distances(F.GridLayout):
    def __init__(self, **kwargs):
        """
        Init for free and parallel beam, minimum required is Source to Detector
        distance.
        """
        super(Distances, self).__init__(**kwargs)
        self.cols = 1
        self.update(['Source', 'Detector'], False)
        self.distance_fixed = False

    def update(self, component_list, dual_phase, beam_geometry='parallel',
               gi_geometry='free'):
        """
        Update the distance widgets according to the component list or any
        special geometry/beam geometry.

        Parameters
        ==========

        component_list [list]
        beam_geometry [str]
        gi_geometry [str]
        dual_phase [boolean]

        Notes
        =====

        required:               not disabled and check for it
        optional:               not disabled, no problem if not set
        display:                disabled

        'free':                 have to set all distances manually, based
                                on component list

        'parallel'&'conv':      required:   none
                                display:    G1-G2

        'cone'& not 'free' or 'sym':    required:   S/G0_G1 OR S/G0_G2
                                        optional:   G2_Dectector
                                                    if G0, than S_G0
                                        display:    G1-G2

        'cone'& 'conv' and 'dual_phase':    required:   S/G0_G1 OR S/G0_G2
                                            optional:   G2_Dectector
                                                        if G0, than S_G0
                                            display:    G1-G2

        'cone'& 'sym':  required:   none
                        optional:   G2_Dectector
                                    if G0, than S_G0
                        display:    G1-G2
                                    S/G0 to G1

        """
        # Remove sample from list (if necessary)
        if 'Sample' in component_list:
            component_list.remove('Sample')
        # Set relevant components
        if beam_geometry == 'parallel' and gi_geometry != 'free':
            component_list = ['G1', 'G2']
        # Remove all old widgets
        self.clear_widgets()
        # Add new ones for all comonents
        height = (len(component_list)-1) * LINE_HEIGHT  # Height of self
        for index, component in enumerate(component_list[:-1]):
            logger.debug("component: {}".format(component))
            distance_container = F.BoxLayout()

            distance_text = ("Distance from {0} to {1} [mm]"
                             .format(component, component_list[index+1]))
            distance_label = NonFileBrowserLabel(text=distance_text)

            distance_value = FloatInput(size_hint_x=0.2)
            distance_id = "distance_{0}_{1}".format(component.lower(),
                                                    component_list[index+1]
                                                    .lower())
            distance_value.id = distance_id

            # Just to show results
            if beam_geometry == 'parallel' and gi_geometry != 'free':
                distance_value.disabled = True
            elif beam_geometry == 'cone' and gi_geometry != 'free':
                if distance_id == 'distance_g1_g2':
                    if not dual_phase:
                        distance_value.disabled = True
                if gi_geometry == 'sym':
                    if distance_id == 'distance_source_g1' or \
                            distance_id == 'distance_g0_g1':
                        distance_value.disabled = True

            distance_container.add_widget(distance_label)
            distance_container.add_widget(distance_value)
            self.add_widget(distance_container)
            logger.debug("Added label '{0}' with input ID '{1}'"
                         .format(distance_text, distance_id))

            # Add option to set S/G0 to G2 distance
            if (distance_id == 'distance_source_g1' or
                    distance_id == 'distance_g0_g1') and \
                    (gi_geometry == 'conv' or gi_geometry == 'inv'):
                # Add extra line for total length option
                height = (len(component_list)) * LINE_HEIGHT

                if distance_id == 'distance_source_g1':
                    extra_distance_text = "Distance from Source to G2 [mm]"
                    extra_distance_id = "distance_source_g2"
                else:
                    extra_distance_text = "Distance from G0 to G2 [mm]"
                    extra_distance_id = "distance_g0_g2"
                # Add extra distance
                extra_distance_container = F.BoxLayout()

                extra_distance_label = \
                    NonFileBrowserLabel(text=extra_distance_text)

                extra_distance_value = FloatInput(size_hint_x=0.2)
                extra_distance_value.id = extra_distance_id
                # Connect to only set one (if other is not empty, disabled)
                distance_value.bind(text=partial(self.on_text,
                                                 extra_distance_value))
                extra_distance_value.bind(text=partial(self.on_text,
                                                       distance_value))

                # Add wisgets
                extra_distance_container.add_widget(extra_distance_label)
                extra_distance_container.add_widget(extra_distance_value)
                self.add_widget(extra_distance_container)
                logger.debug("Added label '{0}' with input ID '{1}'"
                             .format(extra_distance_text, extra_distance_id))

        # Fill with new widgets
        self.size_hint_y = None
        self.height = height

    def on_text(self, linked_instance, instance, value):
        """
        if one of them has text, disable input
        if both have text (load file or results), enable both for input
            -> from disabled to enabled
        if both have text and one is changed, set other to "" (and disable)
            -> if both are already enabled
        """
        if value != '':
            if not self.distance_fixed:
                linked_instance.disabled = True
                linked_instance.text = ''
            if linked_instance.text != '':
                # Both not empty after results etc.
                if self.distance_fixed:
                    linked_instance.disabled = False
                    instance.disabled = False
                    self.distance_fixed = False
            else:
                # Disable other if text is entered here
                linked_instance.disabled = True
                self.distance_fixed = True
        else:
            linked_instance.disabled = False


# #############################################################################
# Error and warning popups ####################################################
class ErrorDisplay():
    """
    Popup window in case an exception is caught. Displays type of error and
    error message.

    Parameters
    ==========

    error_title [str]:      type of error
    error_message [str]:    error message

    """
    def __init__(self, error_title, error_message):
        """
        Init _OKPopupWindow and open popup.
        """
        error_popup = _OKPopupWindow(error_title, error_message)
        error_popup.popup.open()


class WarningDisplay():
    """
    Popup window in case an exception is caught and user can choose to
    continue. Displays type of warning and warning message.

    Parameters
    ==========

    warning_title [str]:        type of warning
    warning_message [str]:      warning message

    overwrite [func]:           function to execute if 'continue'
    overwrite_finish [func]:    after overwrite, finish up
    cancel_finish [func]:       after cancel, finish up

    """
    def __init__(self, warning_title, warning_message,
                 overwrite, overwrite_finish,
                 cancel_finish):
        """
        Init _ContinueCancelPopupWindow and open popup.
        """
        self.warning_popup = _ContinueCancelPopupWindow(warning_title,
                                                        warning_message,
                                                        overwrite,
                                                        overwrite_finish,
                                                        cancel_finish)
        self.warning_popup.popup.open()


class LabelHelp(NonFileBrowserLabel):
    """
    Label, but upon touch down a help message appears.

    Parameters
    ==========

    help_message [StringProperty]

    """
    help_message = F.StringProperty()

    def on_touch_down(self, touch):
        """
        On touch down a popup window is created, with its title indicating
        the variable to which the help is referring and its help message.

        """
        # If mouse clicked on
        if self.collide_point(touch.x, touch.y):
            window_title = 'Help: {}'.format(self.text)
            help_popup = _OKPopupWindow(window_title, self.help_message)
            help_popup.popup.open()
        # To manage input chain corectly
        return super(LabelHelp, self).on_touch_down(touch)


class ScrollableLabel(F.ScrollView):
    """
    Label is scrolable in y direction. See .kv file for more information.
    """
    text = F.StringProperty('')


# #############################################################################
# Geometry display ############################################################
class GeometrySketch(F.Widget):
    """
    """
    def __init__(self, **kwargs):
        """
        Add dark grey rectangle to geometry_group.
        """
        super(GeometrySketch, self).__init__(**kwargs)
        self.geometry_group = G.InstructionGroup()

        self.reset()

    def reset(self):
        self.geometry_group.clear()
        self.rectangle = G.Rectangle()
        self.geometry_group.add(G.Color(0, 0, 0, 0.75))
        self.geometry_group.add(self.rectangle)


class GeometryGrid(F.GridLayout):
    """
    GridLayout, which has one child, which canvas contains the
    geometry_group of GeometrySketch.
    """
    def __init__(self, **kwargs):
        """
        Init Geometry Grid with one child, that has a dark grey background.

        Child: GeometrySketch()

        """
        super(GeometryGrid, self).__init__(**kwargs)
        self.add_widget(GeometrySketch())
        self.sketch = self.children[0]
        # Link canvas to geometry_group
        self.canvas.add(self.sketch.geometry_group)

        # Update to parents size and position
        kivy.clock.Clock.schedule_once(self.set_attributes)

    def set_attributes(self, dt):
        """
        Set size and position after app has started.
        """
        self.sketch.rectangle.size = self.size
        #  1165=1200-line_height with tab height = 1200
        self.sketch.rectangle.pos = (0.0, 1165.0-self.height)

    def update_geometry(self, geometry_results):
        """
        Update Geometry Sketch according to geometry results.

        Parameters
        ==========

        geometry_results [dict]

        Notes
        =====

        Source: if cone beam
            Position: in y center and starting at 1/20 of width.
            Size: (10, 20)

        Detector:
            Position: in y center and ending at 1/20 of width.

        Beam:
            From source center to detector edges. Either triangel or rectangle.

        """
        # reset previous
        self.sketch.reset()
        # Update to parents size and position
        kivy.clock.Clock.schedule_once(self.set_attributes)

        # (0,0) coordinates of sketch
        frame_x0 = self.sketch.pos[0]
        frame_y0 = self.sketch.pos[1]
        # Width and height of sketch (absolut, not from origin)
        frame_width = self.sketch.width
        frame_height = self.sketch.height
        frame_y_center = frame_y0 + frame_height/2.0
        # Frame absolute offsets
        x0_offset = frame_width/20.0

        # Add Source if cone beam
        width = 10.0
        height = 20.0
        pos_x = frame_x0 + x0_offset - width/2.0
        pos_y = frame_y_center - height/2.0
        self.source = G.Ellipse(pos=(pos_x, pos_y), size=(width, height))
        if geometry_results['beam_geometry'] == 'cone':
            self.sketch.geometry_group.add(G.Color(1, 1, 0, 0.5))
            self.sketch.geometry_group.add(self.source)

        # Add Detector
        detector_width = 20.0
        detector_height = frame_height*0.8  # is max height of sketch
        detector_pos_x = frame_x0 + frame_width - x0_offset - \
            detector_width/2.0
        detector_pos_y = frame_y_center - detector_height/2.0

        if not geometry_results['curved_detector']:
            # straight
            self.detector = G.Rectangle(pos=(detector_pos_x, detector_pos_y),
                                        size=(detector_width, detector_height))
        else:
            # Curved detector
            line_width = detector_width / 2.0
            # from Source to Detector
            radius = detector_pos_x - self.source.pos[0]
            # Circle center at source center
            pos_x = self.source.pos[0] + self.source.size[0]/2.0
            pos_y = self.source.pos[1] + self.source.size[1]/2.0
            half_angle = np.rad2deg(np.arctan(0.5 * detector_height / radius))

            self.detector = G.Line(circle=(pos_x, pos_y,
                                           radius,
                                           90.0 - half_angle,
                                           90.0 + half_angle),
                                   width=line_width)

        self.sketch.geometry_group.add(G.Color(0.75, 0.75, 0.75, 1))
        self.sketch.geometry_group.add(self.detector)

        # Add beam
        width = frame_width - frame_width/10.0 - 10.0
        height = detector_height
        if geometry_results['beam_geometry'] == 'parallel':
            pos_x = self.source.pos[0] + self.source.size[0]/2.0
            pos_y = detector_pos_y
            self.beam = G.Rectangle(pos=(pos_x, pos_y), size=(width, height))
        else:
            x1 = self.source.pos[0] + self.source.size[0]/2.0
            y1 = self.source.pos[1] + self.source.size[1]/2.0
            x2 = x1 + width
            y2 = detector_pos_y + height
            x3 = x1 + width
            y3 = detector_pos_y
            self.beam = G.Triangle(points=[x1, y1, x2, y2, x3, y3])

        self.sketch.geometry_group.add(G.Color(1, 1, 0, 0.1))
        self.sketch.geometry_group.add(self.beam)

        # Scaling factors
        # Max width is distance source detector [mm] (inner edges)
        setup_width = detector_pos_x - detector_width/2.0 - \
            (self.source.pos[0] + self.source.size[0]/2.0)  # [points]
        setup_height = detector_height  # [points]
        width_scaling = setup_width / \
            geometry_results['distance_source_detector']  # [points]
        x0_offset = x0_offset + self.source.size[0]/2.0  # [points]
        # Angle for scaling height (only cone beam) (complete angle)
        fan_angle = 2.0 * np.arctan(setup_height / 2.0 / setup_width)

        # Add Gratings
        gratings = [grating for grating in
                    geometry_results['component_list']
                    if "G" in grating]
        for grating in gratings:

            width = 2.0  # [points]

            radius = geometry_results['radius_'+grating.lower()]
            if radius:
                # Bent
                radius = radius * width_scaling  # [points]

                pos_x = self.source.pos[0] + self.source.size[0]/2.0 - \
                    width/2.0
                pos_y = self.source.pos[1] + self.source.size[1]/2.0
                # add distance from source-radius to source pos x
                distance_from_source = \
                    geometry_results['distance_source_' +
                                     grating.lower()] * \
                    width_scaling  # [points]
                pos_x = pos_x + (distance_from_source - radius)
                half_angle = np.rad2deg(fan_angle)/2.0
                # Scale with ratio of radius to distance from source (approx.)
                half_angle = half_angle * (distance_from_source / radius)
                if half_angle > 90.0:
                    warning_message = ("Radius of {0} too small to display."
                                       .format(grating))
                    logger.warning(warning_message)
                    half_angle = 90.0

                # circle=(center_x, center_y, radius, angle_start, angle_end)
                self.grating = G.Line(circle=(pos_x, pos_y,
                                              radius,
                                              90.0 - half_angle,
                                              90.0 + half_angle),
                                      width=width)
            else:
                # Straight
                width = width * 2.0

                pos_x = geometry_results['distance_source_' + grating.lower()]
                pos_x = pos_x * width_scaling  # [points]
                pos_x = pos_x - width/2.0 + x0_offset
                height = (pos_x + width/2.0) * np.tan(fan_angle)  # [points]
                pos_y = frame_y_center - height/2.0
                self.grating = G.Rectangle(pos=(pos_x, pos_y),
                                           size=(width, height))

            self.sketch.geometry_group.add(G.Color(1, 0, 0, 0.75))
            self.sketch.geometry_group.add(self.grating)

        # Seperate between bent and straight gratings
        # Bent: Ellipse (or circle) with radius as size and
        # angle_start/angle_end

        # Add sample
        if 'Sample' in geometry_results['component_list']:
            if geometry_results['sample_shape'] == 'circular':
                width = geometry_results['sample_diameter']
                width = width * width_scaling  # [points]
                pos_x = geometry_results['distance_source_sample']
                pos_x = pos_x * width_scaling  # [points]
                pos_x = pos_x - width/2.0 + x0_offset
                pos_y = frame_y_center - width/2.0
                self.sample = G.Ellipse(pos=(pos_x, pos_y),
                                        size=(width, width))
                self.sketch.geometry_group.add(G.Color(0, 0, 1, 0.5))
                self.sketch.geometry_group.add(self.sample)

# %% Utilities


# #############################################################################
# Popups # ####################################################################
class _OKPopupWindow():
    """
    A popup window containing a label and a button.

    The button closes the window.

    Parameters
    ==========

    title [str]:    title of popup window
    message [str]:  message displayed

    """
    def __init__(self, title, message):
        """
        Init function, creates layout and adds functunality.

        """
        # Custom Window with close button
        popup_content = F.BoxLayout(orientation='vertical',
                                    spacing=10)

        message_label = F.ScrollableLabel(text=message)
        popup_content.add_widget(message_label)
        close_popup_button = F.Button(text='OK')

        popup_content.add_widget(close_popup_button)

        self.popup = F.Popup(title=title,
                             title_size=20,
                             auto_dismiss=False,
                             content=popup_content,
                             size_hint=(None, None),
                             size=ERROR_MESSAGE_SIZE)
        close_popup_button.bind(on_press=self.popup.dismiss)


class _ContinueCancelPopupWindow():
    """
    A popup window containing a label and 2 buttons (cancel and continue).


    Parameters
    ==========

    title [str]:    title of popup window
    message [str]:  message displayed

    Notes
    =====

    _continue stores the choice, True if continue, False if cancel.

    """
    def __init__(self, title, message,
                 overwrite, overwrite_finish,
                 cancel_finish):
        """
        Init function, creates layout and adds functunality.
        """
        # Init continuation state
        self._continue = False
        self.overwrite = overwrite
        self.overwrite_finish = overwrite_finish
        self.cancel_finish = cancel_finish
        # Custom Window with continue and cancel button
        popup_content = F.BoxLayout(orientation='vertical',
                                    spacing=10)

        message_label = F.ScrollableLabel(text=message)
        popup_content.add_widget(message_label)

        button_layout = F.BoxLayout(spacing=10)
        cancel_popup_button = F.Button(text='Cancel')
        continue_popup_button = F.Button(text='Continue')

        button_layout.add_widget(continue_popup_button)
        button_layout.add_widget(cancel_popup_button)

        popup_content.add_widget(button_layout)

        self.popup = F.Popup(title=title,
                             title_size=20,
                             auto_dismiss=False,
                             content=popup_content,
                             size_hint=(None, None),
                             size=ERROR_MESSAGE_SIZE)

        # Close help window when button 'OK' is pressed
        continue_popup_button.bind(on_press=partial(self.close, True))
        cancel_popup_button.bind(on_press=partial(self.close, False))

        self.popup.bind(on_dismiss=self.finish)  # Wait for dismiss

    def close(self, *args):
        """
        Executed on press of any button, stores continuation indicator.

        Parameters
        ==========

        continue_ [boolean]:    Continue (True) with action or cancel (False)
                                action

        """
        self._continue = args[0]
        self.popup.dismiss()

    def finish(self, *args):
        """
        Finishing function bound to popup's dismiss. If 'continue' was pressed,
        execute 'overwrite()' and the 'overwrite_finish()', else the
        'cancel_finish'.
        """
        if self._continue:
            logger.info("Overwriting file!")
            self.overwrite()
            logger.info('... done.')
            self.overwrite_finish()
        else:
            logger.info("... canceled.")
            self.cancel_finish()


# #############################################################################
# Input and results management ################################################

# Input
def _load_input_file(input_file_path, input_parameters):
    """
    Load string parameter keys and string values from input file.

    Parameters
    ==========

    input_file_path [str]:      file path to input file, including name.
    input_parameters [dict]:    in case multiple input files are loaded, pass
                                previous input_parameters

    Returns
    =======

    input_parameters [dict]:    input_parameters['var_key'] = var_value

    Notes
    =====

    var_value is string, var_key is string

    Flags (--) are set without value if true, else not set

    """
    # Read lines from file
    with open(input_file_path) as f:
        input_lines = f.readlines()
    input_lines = [line.strip() for line in input_lines]  # Strip spaces and \n

    # Find all keys
    key_indices = [i for i, str_ in enumerate(input_lines) if '-' in str_]
    # go from key-entry+1 to next-key-entry-1 to get all values in between keys
    key_indices.append(len(input_lines))  # Add last entry
    for number_key_index, key_index in enumerate(key_indices[:-1]):
        key = input_lines[key_index]
        logger.debug('Reading {0} ...'.format(key))
        if '--' in key:
            value = 'True'
        else:
            value = input_lines[key_index+1:key_indices[number_key_index+1]]
        input_parameters[key] = value
        logger.debug('Storing {0}.'.format(value))
    return input_parameters


# Results
def _load_results_dir(results_dir_path):
    """
    Load results dict from folder.

    Parameters
    ==========

    results_dir_path [str]:     folder path to store /mat files in

    Returns
    =======

    results [dict]

    Notes
    =====

    results_dir_path:  path/folder_name

    Structure results:
        results['input'] = dict of input parameters
        results['geometry'] = dict of geometry parameters
        results[...] = dict of ...

    Save as: at path/
        - folder name
            - input dict as foldername_input.text (via save_input)
            - geometry.mat: all keys/values from dict (here: geometry)
            - ... .mat:

    """
    results = dict()
    logger.info("Reading results folder at {0}...".format(results_dir_path))
    for file_ in os.listdir(results_dir_path):
        logger.debug("Reading file '{0}' in {1}".format(file_,
                                                        results_dir_path))
        file_path = os.path.join(results_dir_path, file_)
        logger.info(file_path)
        if '_input.txt' in file_:
            logger.info("Loading input...")
            results['input'] = _load_input_file(file_path, dict())
            logger.info("... done.")
        elif '.mat' in file_:
            matfile_name = str(file_.split('.')[0])
            logger.info("Loading {0} into results['{1}']..."
                        .format(file_, matfile_name))
            raw_mat = scipy.io.loadmat(file_path, squeeze_me=True,
                                       chars_as_strings=True)

            # Remove __header__ and __globals__
            del raw_mat['__header__']
            del raw_mat['__version__']
            del raw_mat['__globals__']
            # [] to None to read from .mat
            # [] are read as np.array([], dtype=float64)
            empty_arrays = [key for key, value in raw_mat.iteritems()
                            if (type(value).__module__ == 'numpy' and
                                value.size == 0)]
            results[matfile_name] = {key: value
                                     if key not in empty_arrays else None
                                     for key, value
                                     in raw_mat.iteritems()}
            # Convert strings from unicode to string
            results[matfile_name] = {key: value
                                     if not isinstance(value, unicode)
                                     else str(value) for key, value
                                     in results[matfile_name].iteritems()}
            # Change 'True'/'False' to True/False
            true_booleans = [key for key, value
                             in results[matfile_name].iteritems()
                             if (type(value) is str and value == 'True')]
            false_booleans = [key for key, var
                              in results[matfile_name].iteritems()
                              if (type(value) is str and value is 'False')]
            results[matfile_name] = {key: value
                                     if key not in true_booleans else True
                                     for key, value
                                     in results[matfile_name].iteritems()}
            results[matfile_name] = {key: value
                                     if key not in false_booleans else False
                                     for key, value
                                     in results[matfile_name].iteritems()}
            # Read list of strings correctly
            # (original as numpy str (<U8) array)
            component_list = results[matfile_name]['component_list']
            component_list = component_list.astype('str').tolist()
            component_list = [component.strip(' ')
                              for component in component_list]
            results[matfile_name]['component_list'] = component_list

            logger.info("... done.")
        else:
            logger.warning("Wrong file or file extention in '{0}', skipping..."
                           .format(file_))
    logger.info("... done.")
    return results


# #############################################################################
# Collect widgets #############################################################
def _collect_widgets(parameters, ids):
    """
    Converts self.ids from widget to dict, thus setting parameters based in
    widget values.

    Parameters
    ==========

    parameters [dict]:      parameters[var_name] = value
    ids [dict]:             ids[var_name] = var_value

    Notes
    =====

    If input is empty, stores None. Input parameters will be overwritten.

    """
    logger.debug("Collecting all widgets...")

    # Handle distances (not accesible directly via ids)
    #   ids.distances contains one boxlayout per distance,
    #   which then contains one label and one FloatInput
    for distance in ids.distances.children:
        for widget in distance.children:
            if 'FloatInput' in str(widget):
                if not widget.text:
                    parameters[widget.id] = None
                else:
                    parameters[widget.id] = float(widget.text)

    for var_name, value in ids.iteritems():
        if 'CheckBox' in str(value):
            continue
        elif 'TabbedPanel' in str(value):
            continue
        elif 'Layout' in str(value):
            continue
        elif 'Distances' in str(value):
            continue
        elif 'GeometryGrid' in str(value):
            continue
        elif 'CustomSpinner' in str(value):
            continue
        elif not value.text:
            parameters[var_name] = None
        elif 'FloatInput' in str(value):
            parameters[var_name] = float(value.text)
        elif 'IntInput' in str(value):
            parameters[var_name] = int(value.text)
        elif 'TextInput' in str(value):
            parameters[var_name] = value.text
        elif 'Spinner' in str(value):
            parameters[var_name] = value.text
#        logger.debug("var_name is: {0}".format(var_name))
#        logger.debug("value.text is: {0}".format(value.text))

    # Handle fixed grating
    if parameters['fixed_grating'] == 'Choose fixed grating...':
        parameters['fixed_grating'] = None
    else:
        # Make lower case
        parameters['fixed_grating'] = parameters['fixed_grating'].lower()

    # Reset grating type if not selected
    for grating in ['g0', 'g1', 'g2']:
        if not ids[grating+'_set'].active:
            parameters['type_'+grating] = None

    # Handle boolean
    if ids.dual_phase.active:
        parameters['dual_phase'] = True
    else:
        parameters['dual_phase'] = False
    if ids.photo_only.active:
        parameters['photo_only'] = True
    else:
        parameters['photo_only'] = False
    if ids.curved_detector.active:
        parameters['curved_detector'] = True
    else:
        parameters['curved_detector'] = False
    # Grating shape
    for grating in ['g0', 'g1', 'g2']:
        if ids[grating+'_bent'].active:
            parameters[grating+'_bent'] = True
        else:
            parameters[grating+'_bent'] = False
        if ids[grating+'_matching'].active:
            parameters[grating+'_matching'] = True
        else:
            parameters[grating+'_matching'] = False

    # Handel double numeric inputs
    # Spectrum range
    if parameters['spectrum_range_min'] is None or \
            parameters['spectrum_range_max'] is None:
        parameters['spectrum_range'] = None
    else:
        parameters['spectrum_range'] = \
            np.array([parameters['spectrum_range_min'],
                     parameters['spectrum_range_max']],
                     dtype=float)
    del parameters['spectrum_range_min']
    del parameters['spectrum_range_max']
    # FOV
    if parameters['field_of_view_x'] is None or \
            parameters['field_of_view_y'] is None:
        parameters['field_of_view'] = None
    else:
        parameters['field_of_view'] = np.array([parameters['field_of_view_x'],
                                               parameters['field_of_view_y']],
                                               dtype=int)
    del parameters['field_of_view_x']
    del parameters['field_of_view_y']

    logger.debug("... done.")


def _collect_input(parameters, ids, parser_info):
    """
    Collects input after updating parameters.

    Parameters
    ==========

    parameters [dict]:      parameters[var_name] = value
    ids [dict]:             ids[var_name] = var_value
    parser_info [dict]:     parser_info[var_name] = [var_key, var_help]

    Returns
    =======

    input_parameters [dict]:    input_parameters[var_key] = var_value

    """
    # Update parameters
    _collect_widgets(parameters, ids)

    input_parameters = main.collect_input(parameters, parser_info)

    return input_parameters


# #############################################################################
# Handle exceptions # #########################################################
class _IgnoreExceptions(ExceptionHandler):
    """
    Kivy Exception Handler to either display the exception or exit the
    program.

    """
    def handle_exception(self, inst):
        """
        Exception Handler disabeling the automatic exiting after any exception
        occured.
        Now: pass. Python needs to handlen all exceptions now.
        """
        return ExceptionManager.PASS

# If kivy is NOT set to debug, disable kivy error handling, so that the errors
# pop up
if Logger.level > 10:
    ExceptionManager.add_handler(_IgnoreExceptions())

# %% Main GUI


class giGUI(F.BoxLayout):
    """
    Main Widget, BoxLayout

    Notes
    =====

    File loading and saving based on
    "https://kivy.org/docs/api-kivy.uix.filechooser.html" (23.10.2017)

    Kivy properties necessary if check if changed or access at .kv is
    necessary.

    """
    # "Global kivy" variables (if kivy ..Property() sharable in .kv)
    # params[var_name] = value
    parameters = F.DictProperty()

    spectrum_file_path = F.StringProperty()
    spectrum_file_loaded = F.BooleanProperty(defaultvalue=False)
    load_input_file_paths = F.ListProperty()
    save_input_file_path = F.StringProperty()
    load_results_dir_path = F.StringProperty()
    save_results_dir_path = F.StringProperty()

    previous_results = F.DictProperty()

    setup_components = F.ListProperty()
    sample_added = False
    available_gratings = F.ListProperty()

    def __init__(self, **kwargs):
        super(giGUI, self).__init__(**kwargs)
        self.parser_info = \
            parser_def.get_arguments_info(parser_def.input_parser())
        self.parser_link = dict()
        for var_name, value in self.parser_info.iteritems():
            self.parser_link[value[0]] = var_name

        # Update parameters
        _collect_widgets(self.parameters, self.ids)
        self.parameters['spectrum_file'] = None
        self.parameters['fixed_distance'] = None
        self._set_widgets(self.parameters, from_file=False)

        # Init result dictionaries
        self.results = main.reset_results()

        # Components trackers (needed for immediate update in GUI, since
        # parameters...components... is set later)
        self.setup_components = ['Source', 'Detector']

        # Available fixed gratings
        self.ids.g0_set.disabled = True
        if self.ids.beam_geometry.text == 'parallel':
            self.available_gratings = ['G1', 'G2']
        else:
            self.available_gratings = ['G0', 'G1', 'G2']

        # Sample
        self.update_sample_distance_label()
        self.parameters['sample_position'] = None

    # #########################################################################
    # General simulation functions ############################################

    def check_all_input(self):
        """
        Check general input, by
            1) load values from all widgets,
            2) Check manually the required parameters from parser
            3) Check values with check_input.geometry_input(...)
            4) Reset widget values to include newly calculated parameters

        Notes
        =====

        Needs to return if successful or not, to avoid scheduling conflicts
        with followup function (which need results)

        """
        success = True
        try:
            # Update parameters
            _collect_widgets(self.parameters, self.ids)

            # Check values
            logger.info("Checking input parameters...")

            if self.parameters['spectrum_file']:
                # Check spectrum file (done in parser, but extra here)
                # Normally for OS
                self.parameters['spectrum_file'] = \
                    os.path.normpath(self.parameters['spectrum_file'])
                # if main path missing, add, then check
                logger.info(os.path.isabs(self.parameters['spectrum_file']))
                if not os.path.isabs(self.parameters['spectrum_file']):
                    script_path = os.path.dirname(os.path.abspath(__file__))
                    self.parameters['spectrum_file'] = \
                        os.path.join(script_path,
                                     self.parameters['spectrum_file'])
                logger.debug("Full path to spectrum is: {0}"
                             .format(self.parameters['spectrum_file']))
                # Check if file exists
                if not os.path.exists(self.parameters['spectrum_file']):
                    error_message = ("Spectrum file ({0}) does not exist."
                                     .format(self.parameters['spectrum_file']))
                    logger.error(error_message)
                    raise check_input.InputError(error_message)

            # Are required (in parser) defined?
            if not self.parameters['pixel_size']:
                error_message = "Input arguments missing: 'pixel_size' " \
                                "('-pxs')."
                logger.error(error_message)
                raise check_input.InputError(error_message)
            if self.parameters['field_of_view'] is None:
                error_message = "Input argument missing: 'field_of_view' " \
                                "('-fov')."
                logger.error(error_message)
                raise check_input.InputError(error_message)
            if not self.parameters['design_energy']:
                error_message = "Input argument missing: 'design_energy' " \
                                "('-e')."
                logger.error(error_message)
                raise check_input.InputError(error_message)

            # Gratings types defined if selected?
            for grating in ['g0', 'g1', 'g2']:
                if self.ids[grating+'_set'].active and \
                        not self.parameters['type_'+grating]:
                    error_message = ("Type of {0} not defined."
                                     .format(grating.upper()))
                    logger.error(error_message)
                    raise check_input.InputError(error_message)

            # Check rest
            check_input.all_input(self.parameters, self.parser_info)
            logger.info("... done.")

            # Update widget content
            self._set_widgets(self.parameters, from_file=False)

        except check_input.InputError as e:
            success = False
            ErrorDisplay('Input Error', str(e))
        finally:
            return success

    def check_geometry_input(self, *args):
        """
        Check general input, by
            1) load values from all widgets,
            2) Check manually the required parameters from parser
            3) Check values with check_input.geometry_input(...)
            4) Reset widget values to include newly calculated parameters

        Notes
        =====

        Needs to return if successful or not, to avoid scheduling conflicts
        with followup function (which need results)

        """
        success = True
        try:
            # Update parameters
            _collect_widgets(self.parameters, self.ids)

            # Check values
            logger.info("Checking geometry input parameters...")

            # Are required (in parser) defined?
            if not self.parameters['design_energy']:
                error_message = "Input argument missing: 'design_energy' " \
                                "('-e')."
                logger.error(error_message)
                raise check_input.InputError(error_message)
            # Gratings types defined if selected?
            for grating in ['g0', 'g1', 'g2']:
                if self.ids[grating+'_set'].active and \
                        not self.parameters['type_'+grating]:
                    error_message = ("Type of {0} not defined."
                                     .format(grating.upper()))
                    logger.error(error_message)
                    raise check_input.InputError(error_message)

            # Check rest
            check_input.geometry_input(self.parameters, self.parser_info)

            # Update widget content
            self._set_widgets(self.parameters, from_file=False)

            logger.info("... done.")

        except check_input.InputError as e:
            success = False
            ErrorDisplay('Input Error', str(e))
        finally:
            return success

    def calculate_geometry(self, switch_tab=False):
        """
        Calculate the GI geometry based on the set input parameters.

        Parameters
        ==========

        switch_tab [bool]:      Default is False, do not switch to geometry
                                results tab

        """
        if self.check_geometry_input():
            current_input = _collect_input(self.parameters, self.ids,
                                           self.parser_info)

            if (self.results['geometry'] and  # geometry must always be calc'ed
                    main.compare_dictionaries(current_input,
                                              self.results['input'])):
                logger.info("Storing current results in previous_results...")
                self.previous_results = self.results.copy()
                logger.info("... done.")

            # Reset results
            self.results = main.reset_results()

            # Store input
            self.results['input'] = current_input
            # Calc geometry
            try:
                logger.info("Calculationg geometry...")
                gi_geometry = geometry.Geometry(self.parameters)
                self.results['geometry'] = gi_geometry.results
                self.parameters = gi_geometry.update_parameters()
                logger.info("... done.")
            except geometry.GeometryError as e:
                ErrorDisplay('Geometry Error', str(e))

            # Update geom results
            self._set_widgets(self.parameters, from_file=False)
            self.show_geometry(self.results)
            # Switch tabs
            if switch_tab:
                self.ids.result_tabs.switch_to(self.ids.geometry_results)

    def calculate_analytical(self, switch_tab=False):
        """
        ...

        Parameters
        ==========

        switch_tab [bool]:      Default is False, do not switch to analytical
                                results tab

        """
        # Update geometry (also stores previous and resets self.results)
        self.calculate_geometry()

        # Calc analytical

        if switch_tab:
            self.ids.result_tabs.switch_to(self.ids.analytical_results)

    def run_simulation(self):
        """
        ...
        """
        self.ids.result_tabs.switch_to(self.ids.simulation_results)

    def show_results(self, results):
        """
        Display all results by calling the corresponding functions.

        Parameters
        ==========

        results [dict]:         can be self.results or self.previous_results

        """
        if 'geometry' in results:
            self.show_geometry(results)
#        elif 'analytical' in results:
#            self.show_analytical(results)

    def show_geometry(self, results):
        """
        Display the GI geometry results. Updates sketch and updates
        distances and gratings result info.

        Parameters
        ==========

        results [dict]:         can be self.results or self.previous_results

        """
        geometry_results = results['geometry'].copy()
        component_list = geometry_results['component_list']

        # Update sketch
        self.ids.geometry_sketch.update_geometry(geometry_results)

        # Clear geometry result tables
        self.ids.grating_results.clear_widgets()
        self.ids.distances_results.clear_widgets()

        # Show gratings results
        gratings = [gratings for gratings
                    in component_list if 'G' in gratings]
        for grating in gratings:
            boxlayout = F.BoxLayout()

            boxlayout.add_widget(F.NonFileBrowserLabel(text=grating))

            pitch = geometry_results['pitch_'+grating.lower()]
            pitch = str(round(pitch, 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=pitch))

            duty_cycle = geometry_results['duty_cycle_'+grating.lower()]
            duty_cycle = str(round(duty_cycle, 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=duty_cycle))

            radius = geometry_results['radius_'+grating.lower()]
            if radius is None:
                radius = '-'
            else:
                radius = str(round(radius, 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=radius))

            self.ids.grating_results.add_widget(boxlayout)

        # Fringe pitch on detector if dual phase
        if geometry_results['dual_phase']:
            boxlayout = F.BoxLayout()

            boxlayout.add_widget(F.NonFileBrowserLabel(text='Detector fringe'))

            pitch = str(round(geometry_results['pitch_fringe'], 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=pitch))

            duty_cycle = str(round(geometry_results['duty_cycle_fringe'], 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=duty_cycle))

            radius = geometry_results['radius_detector']
            if radius is None:
                radius = '-'
            else:
                radius = str(round(radius, 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=radius))

            self.ids.grating_results.add_widget(boxlayout)

        # Update height of 'grating_results'
        self.ids.grating_results.height = \
            self.calc_boxlayout_height(LINE_HEIGHT,
                                       self.ids.grating_results)

        # Show distances
        if geometry_results['gi_geometry'] != 'free':
            # Show d, l, s first
            if 'G0' in component_list:
                start_from = 'G0'
            else:
                start_from = 'Source'
            # l
            boxlayout = F.BoxLayout()
            boxlayout.add_widget(F.NonFileBrowserLabel(text=(start_from +
                                                             ' to G1')))
            distance = geometry_results.pop('distance_'+start_from.lower() +
                                            '_g1')
            distance = str(round(distance, 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=distance))
            self.ids.distances_results.add_widget(boxlayout)

            # d
            boxlayout = F.BoxLayout()
            boxlayout.add_widget(F.NonFileBrowserLabel(text='G1 to G2'))
            distance = geometry_results.pop('distance_g1_g2')
            distance = str(round(distance, 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=distance))
            self.ids.distances_results.add_widget(boxlayout)

            # s
            boxlayout = F.BoxLayout()
            boxlayout.add_widget(F.NonFileBrowserLabel(text=(start_from +
                                                             ' to G2')))
            distance = geometry_results.pop('distance_'+start_from.lower() +
                                            '_g2')
            distance = str(round(distance, 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=distance))
            self.ids.distances_results.add_widget(boxlayout)

        # Add total system length and if necessary source to sample
        boxlayout = F.BoxLayout()
        boxlayout.add_widget(F.NonFileBrowserLabel(text='Source to detector'))
        distance = geometry_results.pop('distance_source_detector')
        distance = str(round(distance, 3))
        boxlayout.add_widget(F.NonFileBrowserLabel(text=distance))
        self.ids.distances_results.add_widget(boxlayout)

        if 'Sample' in component_list:
            boxlayout = F.BoxLayout()
            boxlayout.add_widget(F.NonFileBrowserLabel(text='Source to sample'))
            distance = geometry_results.pop('distance_source_sample')
            distance = str(round(distance, 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=distance))
            self.ids.distances_results.add_widget(boxlayout)

        # Add remaining intergrating distances
        seperator = 85*'-'  # seperator line for tabel

        distance_keys = [key for key in geometry_results.keys()
                         if 'distance_g' in key]
        if distance_keys:
            boxlayout = F.BoxLayout()
            boxlayout.add_widget(F.NonFileBrowserLabel(text=seperator))
            self.ids.distances_results.add_widget(boxlayout)
            for distance_key in distance_keys:
                label_text = (distance_key.split('_')[1].upper()+' to ' +
                              distance_key.split('_')[2])
                boxlayout = F.BoxLayout()
                boxlayout.add_widget(F.NonFileBrowserLabel(text=label_text))
                distance = geometry_results.pop(distance_key)
                distance = str(round(distance, 3))
                boxlayout.add_widget(F.NonFileBrowserLabel(text=distance))
                self.ids.distances_results.add_widget(boxlayout)

        # Add remaining source to distances
        distance_keys = [key for key in geometry_results.keys()
                         if 'distance_source' in key]
        if distance_keys:
            boxlayout = F.BoxLayout()
            boxlayout.add_widget(F.NonFileBrowserLabel(text=seperator))
            self.ids.distances_results.add_widget(boxlayout)
            for distance_key in distance_keys:
                label_text = ('Source to ' +
                              distance_key.split('_')[2].upper())
                boxlayout = F.BoxLayout()
                boxlayout.add_widget(F.NonFileBrowserLabel(text=label_text))
                distance = geometry_results.pop(distance_key)
                distance = str(round(distance, 3))
                boxlayout.add_widget(F.NonFileBrowserLabel(text=distance))
                self.ids.distances_results.add_widget(boxlayout)

        # Add remaining sample relative to distance
        if 'Sample' in component_list:
            # Find reference component
            sample_index = component_list.index('Sample')
            if 'a' in results['geometry']['sample_position']:
                reference = component_list[sample_index-1]
            else:
                reference = component_list[sample_index+1]

            boxlayout = F.BoxLayout()
            boxlayout.add_widget(F.NonFileBrowserLabel(text=seperator))
            self.ids.distances_results.add_widget(boxlayout)
            boxlayout = F.BoxLayout()
            boxlayout.add_widget(F.NonFileBrowserLabel(text=(reference +
                                                             ' to sample')))
            distance = results['geometry']['sample_distance']
            distance = str(round(distance, 3))
            boxlayout.add_widget(F.NonFileBrowserLabel(text=distance))
            self.ids.distances_results.add_widget(boxlayout)

        # Update height of 'grating_results'
        self.ids.distances_results.height = \
            self.calc_boxlayout_height(LINE_HEIGHT,
                                       self.ids.distances_results)

    # #########################################################################
    # Manage global variables and widget behavior #############################

    # File I/O ################################################################

    # Spectrum
    def on_spectrum_file_path(self, instance, value):
        """
        When spectrum_file_path changes, set parameters and update load status.
        """
        if value:
            self.spectrum_file_loaded = True
            self.parameters['spectrum_file'] = self.spectrum_file_path
            # Reset load_input_file_paths to allow loading of same file
        else:
            self.spectrum_file_loaded = False
            self.parameters['spectrum_file'] = None

    # Input
    def on_load_input_file_paths(self, instance, value):
        """
        When load_input_file_paths changes, laod keys and values from all files
        in selection list.
        Update widget content accordingly.

        Notes
        =====

        input_parameters [dict]:    input_parameters[var_key] = str(value)

        """
        if value:
            # Store (all) previous results, if previous geometry results and
            # even if input is the same
            if self.results['geometry']:
                logger.info("Storing current results in previous_results...")
                self.previous_results = self.results.copy()
                logger.info("... done.")
            # Reset current results
            self.results = main.reset_results()

            # Clear all
            self.reset_widgets()
            _collect_widgets(self.parameters, self.ids)  # Resets parameters

            # Do for all files in load_input_file_paths and merge results.
            # Later files overwrite first files.
            input_parameters = dict()
            for input_file in value:
                input_file = os.path.normpath(input_file)
                logger.info("Loading input from file at: {0}"
                            .format(input_file))
                input_parameters = _load_input_file(input_file,
                                                    input_parameters)
            # Set widget content
            try:
                self._set_widgets(input_parameters, from_file=True)
                self._set_widgets(input_parameters, from_file=True)
            except check_input.InputError as e:
                ErrorDisplay('Input Error', str(e))
            finally:
                # Reset load_input_file_paths to allow loading of same file
                self.load_input_file_paths = ''

    def on_save_input_file_path(self, instance, value):
        """
        When save_input_file_path changes, try to save parameters var_name and
        value pairs that are listed in parser to file.

        Notes
        =====

        self.parameters [dict]:     widget_parameters[var_name] = value

        If file exists:             Popup to ask to 'continue' or 'cancel',
                                    give following functions to popup:
                                    save_input:             overwrite
                                    self.overwrite_save:    overwrite_finish
                                    self.cancel_save:       cancel_finish

        Reset save_input_file_path to '' to allow next save at same file.

        """
        if self.save_input_file_path != '':  # e.g. after reset.
            input_parameters = _collect_input(self.parameters, self.ids,
                                              self.parser_info)
            logger.info("Saving input to file...")
            if os.path.isfile(value):
                # File exists
                logger.warning("File '{0}' already exists!".format(value))
                WarningDisplay("File already exists!",
                               "Do you want to overwrite it?",
                               partial(main.save_input,
                                       value,
                                       input_parameters,
                                       True),
                               self.overwrite_input_save,
                               self.cancel_input_save)
            else:
                # File new
                main.save_input(value, input_parameters, True)
                logger.info('... done.')
                self.dismiss_popup()
                self.save_input_file_path = ''

    def overwrite_input_save(self):
        """
        Finish action if input is overwritten.

        Notes
        =====

        Reset save_input_file_path to '' to allow next save at same file.

        """
        self.dismiss_popup()
        self.save_input_file_path = ''

    def cancel_input_save(self):
        """
        Finish action if input saving is canceled (do not overwrite).

        Notes
        =====

        Reset save_input_file_path to '' to allow next save at same file.

        parser_link [dict]:        parser_link[var_key] = var_name

        """
        self.save_input_file_path = ''

    # Results
    def on_load_results_dir_path(self, instance, value):
        """
        When load_results_dir_path changes, laod keys and values from input
        file and all .mat files in selection list.
        Update widget content accordingly.

        Notes
        =====

        If nothing is selected, value is no '', but '.'

        Formats:

            stores booleans ('True'/'False') as True/False
            stores emptry numpy array [] as None

        """
        if value not in ['', '.']:
            # Store (all) previous results, if previous geometry results and
            # even if input is the same
            if self.results['geometry']:
                logger.info("Storing current results in previous_results...")
                self.previous_results = self.results.copy()
                logger.info("... done.")

            # Clear all
            self.reset_widgets()
            _collect_widgets(self.parameters, self.ids)  # Resets parameters

            logger.info("Loading results file...")
            self.results = _load_results_dir(value)

            # Set widgets
            for dict_name, sub_dict in self.results.iteritems():
                if dict_name == 'input':
                    try:
                        self._set_widgets(sub_dict, from_file=True)
                        self._set_widgets(sub_dict, from_file=True)
                    except check_input.InputError as e:
                        ErrorDisplay('Input Error', str(e))
                else:
                    # .mat
                    self._set_widgets(sub_dict, from_file=False)
            # Update parameters
            _collect_widgets(self.parameters, self.ids)

            # Show loaded results
            self.show_results(self.results)

            # Reset load_results_dir_path to allow loading of same file
            self.load_results_dir_path = ''
            logger.info('... done.')
        else:
            # Reset load_results_dir_path to allow loading of same file
            self.load_results_dir_path = ''


    def on_save_results_dir_path(self, instance, value):
        """
        When save_results_dir_path changes, ... .

        Notes
        =====

        If file exists:             Popup to ask to 'continue' or 'cancel',
                                    give following functions to popup:
                                    _save_results_dir:
                                        overwrite
                                    self.overwrite_results_save:
                                        overwrite_finish
                                    self.cancel_results_save:
                                        cancel_finish

        Reset save_results_dir_path to '' to allow next save at same file.

        """
        if self.save_results_dir_path != '':  # e.g. after reset.
            logger.info("Saving results to folder...")
            if os.path.isdir(value):
                # File exists
                logger.warning("Folder '{0}' already exists!".format(value))
                WarningDisplay("File already exists!",
                               "Do you want to overwrite it?",
                               partial(main.save_results,
                                       value,
                                       self.results,
                                       True),
                               self.overwrite_results_save,
                               self.cancel_results_save)
            else:
                # File new
                main.save_results(value, self.results, True)
                logger.info('... done.')
                self.dismiss_popup()
                self.save_results_dir_path = ''

    def overwrite_results_save(self):
        """
        Finish action if file is overwritten.

        Notes
        =====

        Reset sav_results_dir_path to '' to allow next save at same file.

        """
        self.dismiss_popup()
        self.save_results_dir_path = ''

    def cancel_results_save(self):
        """
        Finish action if results saving is canceled (do not overwrite).

        Notes
        =====

        Reset save_results_dir_path to '' to allow next save at same file.

        """
        self.save_results_dir_path = ''

    def on_show_previous_results_active(self):
        """
        Shows previous results if true, else current results.

        Notes
        =====

        If previous results are shown and no current results exists
        (minimum geometry), the current input is stored in
        self.results['input'] to be able to reset.

        self.parameters are left as is, only input and results change.

        """
        if self.ids.show_previous_results.active:
            logger.info("Showing previous results...")
            results = self.previous_results.copy()
            # If no current results, store current input in results to be able
            # to reset
            if not self.results['geometry']:  # Geometry is always calculated
                self.results['input'] = _collect_input(self.parameters,
                                                       self.ids,
                                                       self.parser_info)
        else:
            logger.info("Showing current results...")
            results = self.results.copy()

        # Set widgets from results
        self.reset_widgets(show_previous=True)
        # Set input
        try:
            self._set_widgets(results['input'], from_file=True)
            self._set_widgets(results['input'], from_file=True)
        except check_input.InputError as e:
            ErrorDisplay('Input Error', str(e))
        # Set .mat results
        for dict_name, sub_dict in results.iteritems():
            if dict_name != 'input':
                self._set_widgets(sub_dict, from_file=False)

        # Show loaded results
        self.show_results(results)

        logger.info("... done.")

    # General
    def dismiss_popup(self):
        """
        Dismisses current self._popup.
        """
        self._popup.dismiss()

    def _fbrowser_canceled(self, instance):
        """
        Closes current FileBrowser.
        """
        logger.debug('FileBrowser canceled, closing itself.')
        self.dismiss_popup()

    # Spectrum
    def show_spectrum_load(self):
        """
        Open popup with FileBrowser to load spectrum_file_path.

        Notes
        =====

        Default path:               ./data/spectra/
        Available file extentions:  ['*.csv','*.txt']

        """
        # Define browser
        spectra_path = os.path.join(os.path.dirname(os.path.
                                                    realpath(__file__)),
                                    'data', 'spectra')
        browser = FileBrowser(select_string='Select',
                              path=spectra_path,  # Folder to open at start
                              filters=['*.csv', '*.txt'])
        browser.bind(on_success=self._spectra_fbrowser_success,
                     on_canceled=self._fbrowser_canceled)

        # Add to popup
        self._popup = F.Popup(title="Load spectrum", content=browser,
                              size_hint=FILE_BROWSER_SIZE)
        self._popup.open()

    def _spectra_fbrowser_success(self, instance):
        """
        On spectrum file path selection, store and close FileBrowser.
        """
        self.spectrum_file_path = instance.selection[0]
        logger.debug("Spectrum filepath is: {}"
                     .format(self.spectrum_file_path))
        self.dismiss_popup()

    # Input file

    # Loading
    def show_input_load(self):
        """
        Open popup with file browser to select input file location.

        Notes
        =====

        Default path:               ./data/inputs/
        Available file extentions:  [*.txt']

        """
        # Define browser
        input_path = os.path.join(os.path.dirname(os.path.
                                                  realpath(__file__)),
                                  'data', 'inputs')
        browser = FileBrowser(select_string='Select',
                              multiselect=True,
                              path=input_path,  # Folder to open at start
                              filters=['*.txt'])
        browser.bind(on_success=self._input_load_fbrowser_success,
                     on_canceled=self._fbrowser_canceled)

        # Add to popup
        self._popup = F.Popup(title="Load input file", content=browser,
                              size_hint=FILE_BROWSER_SIZE)
        self._popup.open()

    def _input_load_fbrowser_success(self, instance):
        """
        On input file path selection, store and close FileBrowser.
        """
        self.load_input_file_paths = instance.selection
        logger.debug("{0} input files loaded."
                     .format(len(self.load_input_file_paths)))
        self.dismiss_popup()

    # Saving
    def show_input_save(self):
        """
        Open popup with file browser to select save input file path.

        Notes
        =====

        Default path:               ./data/inputs/
        Available file extentions:  [*.txt']

        """
        # Define browser
        input_path = os.path.join(os.path.dirname(os.path.
                                                  realpath(__file__)),
                                  'data', 'inputs')
        browser = FileBrowser(select_string='Save',
                              path=input_path,  # Folder to open at start
                              filters=['*.txt'])
        browser.bind(on_success=self._input_save_fbrowser_success,
                     on_canceled=self._fbrowser_canceled)

        # Add to popup
        self._popup = F.Popup(title="Save input file", content=browser,
                              size_hint=FILE_BROWSER_SIZE)
        self._popup.open()

    def _input_save_fbrowser_success(self, instance):
        """
        On input file path selection, store and close FileBrowser.
        """
        filename = instance.filename
        # Check extension
        if filename.split('.')[-1] == instance.filters[0].split('.')[-1]:
            # Correct extention
            file_path = os.path.join(instance.path, filename)
        elif filename.split('.')[-1] == '':
            # Just '.' set
            file_path = os.path.join(instance.path, filename+'txt')
        elif filename.split('.')[-1] == filename:
            # Not extention set
            file_path = os.path.join(instance.path, filename+'.txt')
        else:
            # Wrong file extention
            error_message = ("Input file must be of type '{0}'"
                             .format(instance.filters[0]))
            logger.error(error_message)
            ErrorDisplay('Saving input file: Wrong file extention.',
                         error_message)
            return
        logger.debug("Save input to file: {0}"
                     .format(file_path))
        self.save_input_file_path = os.path.normpath(file_path)

    # Results

    # Loading
    def show_results_load(self):
        """
        Open popup with file browser to select results folder.

        Notes
        =====

        Default path:               ./data/results/
        Available file extentions:  [self._list_directories]
                                    only show directories

        Accept only one file!

        """
        # Define browser
        results_path = os.path.join(os.path.dirname(os.path.
                                                    realpath(__file__)),
                                    'data', 'results')
        browser = FileBrowser(select_string='Select',
                              dirselect=True,
                              path=results_path,  # Folder to open at start
                              filters=[self._list_directories])
        browser.bind(on_success=self._results_load_fbrowser_success,
                     on_canceled=self._fbrowser_canceled)

        # Add to popup
        self._popup = F.Popup(title="Load results folder", content=browser,
                              size_hint=FILE_BROWSER_SIZE)
        self._popup.open()

    def _results_load_fbrowser_success(self, instance):
        """
        On results file path selection, store and close FileBrowser.
        """
        foldername = os.path.normpath(instance.filename)
        self.load_results_dir_path = foldername
#        self.load_results_dir_path = instance.selection
        self.dismiss_popup()

    # Saving
    def show_results_save(self):
        """
        Open popup with file browser to select save results folder path.

        Notes
        =====

        Default path:               ./data/results/
        Available file extentions:  [self._list_directories]
                                    only show directories

        """
        # Define browser
        results_path = os.path.join(os.path.dirname(os.path.
                                                    realpath(__file__)),
                                    'data', 'results')
        browser = FileBrowser(select_string='Save',
                              dirselect=True,
                              path=results_path,  # Folder to open at start
                              filters=[self._list_directories])
        browser.bind(on_success=self._results_save_fbrowser_success,
                     on_canceled=self._fbrowser_canceled)

        # Add to popup
        self._popup = F.Popup(title="Save results folder", content=browser,
                              size_hint=FILE_BROWSER_SIZE)
        self._popup.open()

    def _results_save_fbrowser_success(self, instance):
        """
        On results folder path selection, store and close FileBrowser.
        """
        foldername = instance.filename
        folder_path = os.path.join(instance.path, foldername)
        self.save_results_dir_path = os.path.normpath(folder_path)

    def _list_directories(self, directory, filename):
        return os.path.isdir(os.path.join(directory, filename))

    # Menu spinners ###########################################################

    def on_load_spinner(self, spinner):
        """
        On load_spinner change, keep text the same and call respective
        functions to execute.
        """
        selected = spinner.text
        spinner.text = 'Load...'
        if selected == 'Input file...':
            self.show_input_load()
        elif selected == 'Results...':
            self.show_results_load()

    def on_save_spinner(self, spinner):
        """
        On save_spinner change, keep text the same and call respective
        functions to execute.
        """
        selected = spinner.text
        spinner.text = 'Save...'
        if selected == 'Input file...':
            self.show_input_save()
        elif selected == 'Results...':
            self.show_results_save()

    def on_help_spinner(self, spinner):
        """
        On help_spinner change, keep text the same and show popup with
        corresponding help message.
        """
        selected = spinner.text
        spinner.text = 'Help...'
        if selected != 'Help...':
            if selected == 'Spectrum file':
                help_message = ("File format:\n"
                                "energy,photons\n"
                                "e1,p1\n"
                                "e2,p2\n"
                                ".,.\n"
                                ".,.\n"
                                ".,.\n\n"
                                "Photons are in [1/pixel/sec].")
            if selected == 'Input file':
                help_message = ("File type: .txt\n"
                                "Can use multiple files, in case of double "
                                "entries, the last file overwrites the "
                                "previous one(s).\n"
                                "File layout:        Example:\n"
                                "ArgName1                -sr\n"
                                "ArgValue1               100\n"
                                "ArgName2                -p0\n"
                                "ArgValue2               2.4\n"
                                "ArgName3                -fov\n"
                                "ArgValue3.1             200\n"
                                "ArgValue3.2             400\n"
                                "    .                    .\n"
                                "    .                    .\n"
                                "    .                    .")
            help_popup = _OKPopupWindow("Help: {0}".format(selected),
                                        help_message)
            help_popup.popup.open()

    # Conditional input rules #################################################

    # GI

    def on_dual_phase_checkbox_active(self):
        """
        Adjust paramters to dual phase option if active.
        """
        if self.ids.dual_phase.disabled:
            self.ids.dual_phase.active = False
        if self.ids.dual_phase.active:
            # Only G1 as fixed grating
            self.ids.fixed_grating.values = ['G1']
            self.ids.fixed_grating.text = 'G1'
            # Disable G0
            self.ids.g0_set.active = False
            self.ids.g0_set.disabled = True
            if self.ids.gi_geometry.text != 'free':
                if self.ids.type_g2.text == 'abs':
                    self.ids.type_g2.text = 'phase'
                self.ids.type_g2.values = ['mix', 'phase']
        else:
            if self.ids.beam_geometry.text == 'Cone':
                self.ids.fixed_grating.values = ['G0', 'G1', 'G2']
            self.ids.g0_set.disabled = False
            if self.ids.gi_geometry.text != 'free':
                if self.ids.type_g2.text == 'phase':
                    self.ids.type_g2.text = 'abs'
                self.ids.type_g2.values = ['mix', 'abs']
        # Update distances options
        self.ids.distances.update(self.setup_components,
                                  self.ids.dual_phase.active,
                                  self.ids.beam_geometry.text,
                                  self.ids.gi_geometry.text)

    def on_gi_geometry(self):
        """
        Set sample position options and activate required gratings.
        """
        if self.ids.gi_geometry.text not in self.ids.gi_geometry.values:
            self.ids.gi_geometry.text = 'free'
        # =====================================================================
        #   Dirty fix for issue #12
        self.ids.fixed_grating.text = 'G0'
        self.ids.fixed_grating.text = 'Choose fixed grating...'
        # ====================================================================
        # Remove sample if it was set before (to start fresh)
        if 'Sample' in self.setup_components:
                self.ids.add_sample.active = False
        else:
            logger.debug("Current setup consists of: {0}"
                         .format(self.setup_components))

        # Required gratings
        if self.ids.gi_geometry.text != 'free':
            # G1 and G2 required
            self.ids.g1_set.active = True
            self.ids.g2_set.active = True
            # Sample relative to G1
            self.ids.sample_relative_to.text = 'G1'
            self.ids.sample_relative_to.values = ['G1']
            # Grating types
            if self.ids.type_g0.text == 'phase':
                self.ids.type_g0.text = ''
            self.ids.type_g0.values = ['mix', 'abs']
            if self.ids.type_g1.text == 'abs':
                self.ids.type_g1.text = ''
            self.ids.type_g1.values = ['mix', 'phase']
            if self.ids.dual_phase.active:
                if self.ids.type_g2.text == 'abs':
                    self.ids.type_g2.text = ''
                self.ids.type_g2.values = ['mix', 'phase']
            else:
                if self.ids.type_g2.text == 'phase':
                    self.ids.type_g2.text = ''
                self.ids.type_g2.values = ['mix', 'abs']
            # Reset grating thickness values to '' if not abs grating
            if self.ids.type_g0.text != 'abs':
                self.ids.thickness_g0.text = ''
            if self.ids.type_g1.text != 'abs':
                self.ids.thickness_g1.text = ''
            if self.ids.type_g2.text != 'abs':
                self.ids.thickness_g2.text = ''
        else:
            # Reset to 'free' (same as start)
            self.ids.sample_relative_position.text = 'after'
            self.ids.sample_relative_position.values = ['after']
            self.ids.sample_relative_to.text = 'Source'
            self.ids.sample_relative_to.values = self.setup_components
            # Grating types
            self.ids.type_g0.text = ''
            self.ids.type_g0.values = ['mix', 'phase', 'abs']
            self.ids.type_g1.text = ''
            self.ids.type_g1.values = ['mix', 'phase', 'abs']
            self.ids.type_g2.text = ''
            self.ids.type_g2.values = ['mix', 'phase', 'abs']

        # GI cases
        if self.ids.gi_geometry.text == 'conv':
            self.ids.sample_relative_position.text = 'before'
            self.ids.sample_relative_position.values = ['before']
            if self.ids.beam_geometry.text == 'parallel':
                self.ids.sample_relative_position.values = ['after', 'before']
        elif self.ids.gi_geometry.text == 'inv':
            self.ids.sample_relative_position.text = 'after'
            self.ids.sample_relative_position.values = ['after']
        elif self.ids.gi_geometry.text == 'sym':
            # Symmetrical case
            self.ids.sample_relative_position.text = 'after'
            self.ids.sample_relative_position.values = ['after', 'before']

        # Update distances options
        self.ids.distances.update(self.setup_components,
                                  self.ids.dual_phase.active,
                                  self.ids.beam_geometry.text,
                                  self.ids.gi_geometry.text)

        # Always keeping previous distance results prevents distances to be
        # reset, so that when switch to free the previous distances remain
        # Keep calculated distances from previous results
        if self.results['geometry']:
            # Geometry results have been calculated
            distances = self.results['geometry']
            for distance_layout in self.ids.distances.children:
                for widget in distance_layout.children:
                    if 'FloatInput' in str(widget) and widget.id in distances:
                        # If distance from results can be set now
                        widget.text = str(distances[widget.id])
                        # Move cursor to front of text input
                        widget.do_cursor_movement('cursor_home')

        # Reset fixed grating input
        self.ids.fixed_grating.text = 'Choose fixed grating...'

        # Update dual_phase options
        self.on_dual_phase_checkbox_active()

    def on_beam_geometry(self):
        """
        Set availabel gratings, update geometry options and deactivate
        required gratings.
        """
        if self.ids.beam_geometry.text not in self.ids.beam_geometry.values:
            self.ids.beam_geometry.text = 'parallel'
        # Remove sample if it was set
        if 'Sample' in self.setup_components:
                self.ids.add_sample.active = False
        else:
            logger.debug("Current setup consists of: {0}"
                         .format(self.setup_components))
        # Reset fixed grating input
        self.ids.fixed_grating.text = 'Choose fixed grating...'

        if self.ids.beam_geometry.text == 'parallel':
            # Change GI geometry text
            if self.ids.gi_geometry.text == 'sym' or \
              self.ids.gi_geometry.text == 'inv':
                # Mode changes, reset GI geometry
                self.ids.gi_geometry.text = 'free'
            # Set available and deactive gratings
            self.ids.g0_set.active = False
            self.ids.g0_set.disabled = True
            self.available_gratings = ['G1', 'G2']
            # Update distances options
            self.ids.distances.update(self.setup_components,
                                      self.ids.dual_phase.active,
                                      self.ids.beam_geometry.text,
                                      self.ids.gi_geometry.text)
        else:
            # Update geometry conditions for cone beam
            self.on_gi_geometry()  # Includes update distances
            self.ids.g0_set.disabled = False
        # Update dual_phase options
        self.on_dual_phase_checkbox_active()

    def on_setup_components(self, instance, value):
        """
        On change in component list, update sample_relative_to spinner text.
        """
        if not self.sample_added:
            self.ids.sample_relative_to.text = self.setup_components[0]

    # Gratings

    def on_grating_thickness(self, grating):
        """
        Check that only thickness or phase shift is set.

        Parameters
        ==========

        grating [str]

        """
        # If both phase shift and thickness are set (after calc or load from
        # file), enable both to reset
        if self.ids['phase_shift_'+grating].text != '' and \
                self.ids['thickness_'+grating].text != '':
            self.ids['phase_shift_'+grating].disabled = False
            self.ids['thickness_'+grating].disabled = False

    def on_phase_shift_spinner(self, grating):
        """
        Set phase shift value according to selected option (pi, pi/2).

        Parameters
        ==========

        grating [str]

        """
        grating = grating.lower()
        if self.ids['phase_shift_'+grating+'_options'].text == 'pi':
            self.ids['phase_shift_'+grating].text = str(np.pi)
        elif self.ids['phase_shift_'+grating+'_options'].text == 'pi/2':
            self.ids['phase_shift_'+grating].text = str(np.pi/2)
        # Move cursor to front of number
        self.ids['phase_shift_'+grating].do_cursor_movement('cursor_home')

        # If both phase shift and thickness are set (after calc or load from
        # file), enable both to reset
        if self.ids['phase_shift_'+grating].text != '' and \
                self.ids['thickness_'+grating].text != '':
            self.ids['phase_shift_'+grating].disabled = False
            self.ids['thickness_'+grating].disabled = False

    def on_phase_shift(self, grating):
        """
        Set selected option (pi, pi/2) according to phase shift value .

        Parameters
        ==========

        grating [str]

        """
        grating = grating.lower()
        if self.ids['phase_shift_'+grating].text == str(np.pi):
            self.ids['phase_shift_'+grating+'_options'].text = 'pi'
        elif self.ids['phase_shift_'+grating].text == str(np.pi/2):
            self.ids['phase_shift_'+grating+'_options'].text = 'pi/2'
        else:
            self.ids['phase_shift_'+grating+'_options'].text = ''

    def on_grating_checkbox_active(self, state, grating):
        """
        Add/remove activate/deactivaded grating to/from component list and
        update distances.

        Parameters
        ==========

        state [boolean]
        grating [str]

        """
        if state:
            self.setup_components.append(grating)
            self.setup_components.sort()
            # After sort, switch Source and Detector
            self.setup_components[0], self.setup_components[-1] = \
                self.setup_components[-1], self.setup_components[0]
            if grating == 'G0':
                self.available_gratings = ['G0', 'G1', 'G2']
            # Update grating shape options
            grating_bent = self.ids[grating.lower()+'_bent'].active
            self.on_grating_shape_active(grating_bent, grating)
        else:
            # Reset type
            self.ids['type_'+grating.lower()].text = ''
            self.setup_components.remove(grating)
            # Also uncheck sample_added
            self.ids.add_sample.active = False
            self.ids.sample_relative_to.text = self.setup_components[0]
            if grating == 'G0':
                self.available_gratings = ['G1', 'G2']

        logger.debug("Current setup consists of: {0}"
                     .format(self.setup_components))
        # Update sample_relative_to and sample_relative_position
        self.on_gi_geometry()
        self.on_beam_geometry()  # Includes update distances

    def on_grating_shape_active(self, state, grating):
        """
        If grating is set to not bent, reset matching and radius to
        False/empty.
        """
        grating = grating.lower()
        if state:
            self.ids[grating+'_matching'].disabled = False
            self.ids['radius_'+grating].disabled = False
        else:
            self.ids[grating+'_matching'].disabled = True
            self.ids[grating+'_matching'].active = False
            self.ids['radius_'+grating].disabled = True
            self.ids['radius_'+grating].text = ""

    def on_radius_matching_active(self, state, grating):
        """
        """
        grating = grating.lower()
        if state:
            # matching radius
            self.ids['radius_'+grating].disabled = True
            self.ids['radius_'+grating].text = ""
        else:
            self.ids['radius_'+grating].disabled = False

    def on_grating_type(self, grating):
        """
        Manage phase/thickness input options based on set grating type and
        selected geometries.

        Parameters
        ==========

        grating [str]

        """
        grating = grating.lower()
        # If wrong type loaded, leave empty
        if self.ids['type_'+grating].text not in \
                self.ids['type_'+grating].values:
            warning_message = ("Chosen grating type is not a valid option. "
                               "Options are {0}."
                               .format(self.ids['type_'+grating].values))
            logger.warning(warning_message)
            self.ids['type_'+grating].text = ''

        # Abs grating: reset phase input
        if self.ids['type_'+grating].text == 'abs':
            self.ids['phase_shift_'+grating].text = ''
            self.ids['phase_shift_'+grating+'_options'].text = ''

        # If type is set, activate grating
        if self.ids['type_'+grating].text != '':
            self.ids[grating+'_set'].active = True

    # Sample

    def on_sample_relative_to(self):
        """
        Update sample_relative_position values and text accoring to selected
        sample_relative_to, update sample in components.
        """
        self.update_sample_distance_label()
        if self.ids.sample_relative_to.text == 'Source':
            self.ids.sample_relative_position.values = ['after']
            self.ids.sample_relative_position.text = 'after'
        elif self.ids.sample_relative_to.text == 'Detector':
            self.ids.sample_relative_position.values = ['before']
            self.ids.sample_relative_position.text = 'before'
        elif self.ids.gi_geometry.text == 'free':
            self.ids.sample_relative_position.values = ['after', 'before']
        # If sample is selected, Update component list and distances
        if self.sample_added:
            self.on_sample_checkbox_active(False)
            self.on_sample_checkbox_active(True)

    def on_sample_relative_position(self):
        """
        Update sample_relative_position values and text accoring to selected
        sample_relative_position, update sample in components.
        """
        self.update_sample_distance_label()
        # If sample is selected, Update component list and distances
        if self.sample_added:
            self.on_sample_checkbox_active(False)
            self.on_sample_checkbox_active(True)

    def on_sample_checkbox_active(self, state):
        """
        Add/Remove sample to/from component list and update distances.

        Parameters
        ==========

        state [boolean]

        """
        if state:
            # Add sample at right position
            self.sample_added = True
            reference_index = \
                self.setup_components.index(self.ids.sample_relative_to.text)
            if self.ids.sample_relative_position.text == 'after':
                self.setup_components.insert(reference_index+1, 'Sample')
            else:
                self.setup_components.insert(reference_index, 'Sample')
            # Set sample_position in parameters (after G1: ag1, before
            # Detector: bd)
            if self.ids.sample_relative_to.text in ['Source', 'Detector']:
                # Only first letter of component
                self.parameters['sample_position'] = \
                    self.ids.sample_relative_position.text[0] + \
                    self.ids.sample_relative_to.text[0].lower()
            else:
                # All component name
                self.parameters['sample_position'] = \
                    self.ids.sample_relative_position.text[0] + \
                    self.ids.sample_relative_to.text.lower()
        else:
            # Remove sample, in case that geometry is changing
            self.setup_components.remove('Sample')
            self.sample_added = False
            self.parameters['sample_position'] = None

        logger.debug("Current setup consists of: {0}"
                     .format(self.setup_components))

    def update_sample_distance_label(self):
        """
        Updates label of relative sample position according to sample position.
        """
        if self.ids.sample_relative_position.text == 'after':
            label = ("Distance from {0} to Sample [mm]"
                     .format(self.ids.sample_relative_to.text))
        else:
            label = ("Distance from Sample to {0} [mm]"
                     .format(self.ids.sample_relative_to.text))
        self.ids.sample_distance_label.text = label

    # Material

    def on_look_up_table(self):
        """
        Set photo_only to false it Xh0 and make input uppercase and default if
        necessary.
        """
        if self.ids.look_up_table.text != 'NIST':
            self.ids.photo_only.active = False
        if self.ids.look_up_table.text.upper() not in \
                self.ids.look_up_table.values:
            warning_message = ("Chosen material LUT not a valid option, "
                               "setting to default ({0}). Options are {1}."
                               .format('NIST',
                                       self.ids.look_up_table.values))
            logger.warning(warning_message)
            self.ids.look_up_table.text = 'NIST'
        else:
            self.ids.look_up_table.text = self.ids.look_up_table.text.upper()

    # Set widgete values

    def _set_widgets(self, parameters, from_file):
        """
        Update widget content (text) to values stored in parameters.

        Parameters
        ==========

        parameters [dict]
        from_file [bool]

        Notes
        =====

        Make all strings lower case, except for materials, to remain compatible
        with parser. If not from file, only necessary for material LUT
        (look_up_table).

        if from file:

            input_parameters [dict]:    input_parameters[var_key] = value

        if from app (not from file):

            input_parameters [dict]:    parameters[var_name] = value

        self.parameters [dict]:         widget_parameters[var_name] = value
        self.parser_link [dict]:        parser_link[var_key] = var_name
        self.parser_info [dict]:        parser_info[var_name] = [var_key,
                                                                 var_help]
        """
        # distances ('distance_...)' need to be handled extra, since they are
        # not stored in ids!
        distances = dict()
        try:
            if from_file:
                logger.info("Setting widget values from file...")

                sample_position = None  # See below

                for var_key, value_str in parameters.iteritems():
                    logger.debug("var_key is {0}".format(var_key))
                    logger.debug("value_str is {0}".format(value_str))
                    if var_key not in self.parser_link:
                        # Input key not implemented in parser
                        logger.warning("Key '{0}' read from input file, but "
                                       "not defined in parser. Skipping..."
                                       .format(var_key))
                        continue
                    var_name = self.parser_link[var_key]
                    logger.debug("var_name is {0}".format(var_name))
                    # Skip all distances, except sample_distance
                    if 'distance_' in var_name:
                        logger.debug("Storing away {0} = {1} to set later."
                                     .format(var_name, value_str[0]))
                        distances[var_name] = value_str[0]
                        continue
                    if var_name not in self.parameters:
                        # Input key not implemented in GUI
                        logger.warning("Key '{0}' with name '{1}' read from "
                                       "input file, but not defined in App. "
                                       "Skipping..."
                                       .format(var_key, var_name))
                        continue

                    # Set input values to ids.texts
                    # Make input strings lower caps
                    if 'material' not in var_name and \
                            var_name != 'spectrum_file':
                        value_str = [value_cap.lower() for value_cap in
                                     value_str]
                    if 'phase_shift_' in var_name:
                        if value_str[0] == 'pi':
                            value_str[0] = str(np.pi)
                        elif value_str[0] == 'pi/2':
                            value_str[0] = str(np.pi / 2)
#                        # Move cursor to front of number
#                        self.ids[var_name].do_cursor_movement('cursor_home')
                    if var_name == 'spectrum_range':
                        self.ids['spectrum_range_min'].text = value_str[0]
                        self.ids['spectrum_range_max'].text = value_str[1]
                        logger.debug("Setting text of widget '{0}' to: [{1}, "
                                     "{2}]."
                                     .format(var_name, value_str[0],
                                             value_str[1]))
                        # Also set spectrum_range_set to true
                        self.ids['spectrum_range_set'].active = True
                        logger.debug("Setting text of widget '{0}' to: {1}."
                                     .format('spectrum_range_set', True))
                    elif var_name == 'field_of_view':
                        # Check if it is integer
                        if '.' in value_str[0] or '.' in value_str[1]:
                            value_str = np.array(value_str)
                            value_str = np.round(value_str.astype(float))
                            value_str = value_str.astype(int)
                            value_str = value_str.astype('|S4')
                            warning_message = ("FOV must be integer, not "
                                               "float. Rounding to next "
                                               "integers: [{0}, {1}]"
                                               .format(value_str[0],
                                                       value_str[1]))
                            logger.warning(warning_message)
                        logger.debug("Setting text of widget '{0}' to: [{1}, "
                                     "{2}]"
                                     .format(var_name, value_str[0],
                                             value_str[1]))
                        self.ids['field_of_view_x'].text = value_str[0]
                        self.ids['field_of_view_y'].text = value_str[1]
                    elif var_name == 'fixed_grating':
                        # Make upper case for GUI
                        logger.debug("Setting text of widget '{0}' to: {1}"
                                     .format(var_name, value_str[0].upper()))
                        self.ids[var_name].text = value_str[0].upper()
                    elif var_name == 'fixed_distance':
                        # Not a widget, but set in self.parameters
                        logger.debug("Setting self.parameter[{0}] to: {1}"
                                     .format(var_name, value_str[0]))
                        self.parameters[var_name] = value_str[0]
                    elif var_name == 'sample_position':
                        # Set later, since component list must be updated first
                        sample_position = value_str[0]
                    # Booleans
                    # From file: in file only of true
                    elif any(phrase in var_name for phrase
                             in ['_bent', '_matching', 'photo_only',
                                 'dual_phase', 'curved_detector']):
                        logger.debug("Setting widget '{0}' to: {1}"
                                     .format(var_name, True))
                        self.ids[var_name].active = True
                    elif var_name == 'spectrum_file':
                        logger.debug("Setting self.spectrum_file_path to: {0}"
                                     .format(value_str[0]))
                        self.spectrum_file_path = value_str[0]
                    else:
                        logger.debug("Setting text of widget '{0}' to: {1}"
                                     .format(var_name, value_str[0]))
                        self.ids[var_name].text = value_str[0]

                # Set sample info
                if sample_position is not None:
                    # if a in var set sample_relative_position to after
                    logger.debug("Sample position is set to {0}"
                                 .format(sample_position))
                    if 'a' in sample_position:
                        self.ids.sample_relative_position.text = 'after'
                    else:
                        self.ids.sample_relative_position.text = 'before'
                    logger.debug("Set 'sample_relative_position' to {0}"
                                 .format(self.ids.sample_relative_position.text))
                    # filter letters and set sample_relative_to accordingly
                    if 's' in sample_position:
                        reference_component = 'Source'
                    elif 'd' in sample_position:
                        reference_component = 'Detector'
                    else:
                        # g0, g1 or g2
                        reference_component = sample_position[1:].upper()
                    logger.debug("Setting 'sample_relative_to' to {0}"
                                 .format(reference_component))
                    self.ids.sample_relative_to.text = reference_component
                    # make samples as added
                    self.ids.add_sample.active = True
            else:
                logger.info("Setting widget values from parameters...")
                for var_name, value in parameters.iteritems():
                    # Skip all distances and do later (except sample_distance)
                    if var_name in ['sample_position', 'fixed_distance']:
                        # No widget
                        continue
                    if value is None:
                        # Set empty string to overwrite falsy set values
                        # booleans will always be not none
                        value = ''
                    if 'distance_' not in var_name:
                        if var_name == 'look_up_table':
                            value = str(value).lower()
                        logger.debug("var_name is: {0}".format(var_name))
                        logger.debug("value is: {0}".format(value))
                        if var_name not in self.parser_info:
                            # Input variable not implemented in parser
                            logger.warning("Parameter '{0}' read from app, "
                                           "but not defined in parser. "
                                           "Skipping...".format(var_name))
                            continue
                        var_key = self.parser_info[var_name][0]
                        logger.debug("var_key is: {0}".format(var_key))
                        # Set input values to ids.texts
                        if var_name == 'spectrum_range':
                            if value == '':
                                value = ['', '']
                                range_set = False
                            else:
                                range_set = True
                            logger.debug("Setting text of widget '{0}' to: "
                                         "[{1}, {2}]".format(var_name,
                                                             value[0],
                                                             value[1]))
                            self.ids['spectrum_range_min'].text = str(value[0])
                            self.ids['spectrum_range_max'].text = str(value[1])
                            # Also set spectrum_range_set
                            self.ids['spectrum_range_set'].active = range_set
                            logger.debug("Setting text of widget '{0}' to: "
                                         "{1}.".format('spectrum_range_set',
                                                       range_set))
                        elif var_name == 'field_of_view':
                            if value == '':
                                logger.debug("Setting text of widget '{0}' "
                                             "to: ['', '']"
                                             .format(var_name))
                                self.ids['field_of_view_x'].text = ''
                                self.ids['field_of_view_y'].text = ''
                            else:
                                logger.debug("Setting text of widget '{0}' "
                                             "to: [{1}, {2}]"
                                             .format(var_name, value[0],
                                                     value[1]))
                                self.ids['field_of_view_x'].text = \
                                    str(int(value[0]))
                                self.ids['field_of_view_y'].text = \
                                    str(int(value[1]))
                        elif var_name == 'fixed_grating':
                            # Make upper case for GUI
                            if not value:
                                value = 'Choose fixed grating...'
                                logger.debug("Setting text of widget '{0}' "
                                             "to: ''"
                                             .format(var_name))
                                self.ids[var_name].text = ''
                            else:
                                logger.debug("Setting text of widget '{0}' "
                                             "to: {1}"
                                             .format(var_name,
                                                     str(value).upper()))
                                self.ids[var_name].text = str(value).upper()
                        # Booleans
                        elif any(phrase in var_name for
                                 phrase in ['_bent', '_matching', 'photo_only',
                                            'dual_phase', 'add_sample',
                                            'curved_detector']):
                            logger.debug("Setting widget '{0}' to: {1}"
                                         .format(var_name, value))
                            self.ids[var_name].active = value
                        elif var_name == 'spectrum_file':
                            self.spectrum_file_path = value
                        else:
                            logger.debug("Setting text of widget '{0}' to: {1}"
                                         .format(var_name, value))
                            self.ids[var_name].text = str(value)
                    else:
                        logger.debug("Storing away {0} = {1} to set later."
                                     .format(var_name, value))
                        distances[var_name] = str(value)

            # Move cursor to front of text input
            for widget_id, widget in self.ids.iteritems():
                if 'Input' in str(widget):
                    widget.do_cursor_movement('cursor_home')

            # Setting distances (not accesible directly via ids)
            #   ids.distances contains one boxlayout per distance,
            #   which then contains one label and one FloatInput
            if distances:
                for distance_layout in self.ids.distances.children:
                    for widget in distance_layout.children:
                        if 'FloatInput' in str(widget):
                            if widget.id in distances:
                                logger.debug("Setting text of widget '{0}' "
                                             "to: {1}"
                                             .format(widget.id,
                                                     distances[widget.id]))
                                widget.text = distances[widget.id]
                                # Move cursor to front of text input
                                widget.do_cursor_movement('cursor_home')

            logger.info("...done.")
        except IndexError:
            error_message = ("Input argument '{0}' ({1}) is invalid. "
                             "Alternatively, check the file layout and "
                             "content.".format(var_name, var_key))
            logger.error(error_message)
            raise check_input.InputError(error_message)

    # Clear widgets
    def reset_input(self):
        """
        Reset all input widgets to 'empty'.

        Notes
        =====

        self.parameters [dict]:     parameters[var_name] = var_value
        self.parser_info [dict]:    parser_info[var_name] = [var_key, var_help]
        input_parameters [dict]:    input_parameters[var_key] = var_value
        self.ids [dict]:            self.ids[var_name] = var_value

        """
        # First switch back to curent results
        self.ids.show_previous_results.active = False

        input_parameters = _collect_input(self.parameters, self.ids,
                                          self.parser_info)

        logger.info("Resetting input widget values...")

        # Handle distances (not accesible directly via ids)
        #   ids.distances contains one boxlayout per distance,
        #   which then contains one label and one FloatInput
        for distance in self.ids.distances.children:
            for widget in distance.children:
                if 'FloatInput' in str(widget):
                    widget.text = ''

        variables = [(var_name, var_value) for var_name, var_value
                     in self.ids.iteritems()
                     if (var_name in self.parser_info and
                         self.parser_info[var_name][0] in input_parameters)]
        for var_name, value in variables:
            if var_name not in self.parser_info:
                continue
            elif self.parser_info[var_name][0] not in input_parameters:
                continue
            if 'CheckBox' in str(value):
                value.active = False
            elif 'TabbedPanel' in str(value):
                continue
            elif 'Layout' in str(value):
                continue
            elif 'Distances' in str(value):
                continue
            elif 'GeometryGrid' in str(value):
                continue
            elif 'CustomSpinner' in str(value):
                continue
            elif not value.text:
                continue
            elif 'FloatInput' in str(value):
                value.text = ""
            elif 'IntInput' in str(value):
                value.text = ""
            elif 'TextInput' in str(value):
                value.text = ""
            elif 'Spinner' in str(value):
                if var_name == 'fixed_grating':
                    value.text = 'Choose fixed grating...'
                elif var_name == 'sample_shape':
                    value.text = ''

        # Remove spectrum
        self.ids.spectrum_file_name.text = ''
        # Reset defaults
        self.ids.spectrum_step.text = '1.0'
        self.ids.exposure_time.text = '1.0'

        # Handle special checkboxes
        self.ids.g0_set.active = False
        self.ids.add_sample.active = False
        self.ids.spectrum_range_set.active = False
        self.ids.spectrum_range_min.text = ''
        self.ids.spectrum_range_max.text = ''
        self.ids.field_of_view_x.text = ''
        self.ids.field_of_view_y.text = ''

        logger.info("... done.")

    def reset_distances(self):
        """
        Reset all distances to 'empty'.
        """
        # First switch back to curent results
        self.ids.show_previous_results.active = False

        logger.info("Resetting distances...")

        for distance in self.ids.distances.children:
            for widget in distance.children:
                if 'FloatInput' in str(widget):
                    widget.text = ''

        logger.info("... done.")

    def reset_widgets(self, show_previous=False):
        """
        Reset all widgets to 'empty'/False, except if show_previous is true.

        Parameters
        ==========

        show_pervious [bool]:   Default is false, reset all.
                                If true, do not reset show_previous_results
                                checkbox

        """
        logger.info("Resetting widget values...")

        # Handle distances (not accesible directly via ids)
        #   ids.distances contains one boxlayout per distance,
        #   which then contains one label and one FloatInput
        for distance in self.ids.distances.children:
            for widget in distance.children:
                if 'FloatInput' in str(widget):
                    widget.text = ''

        # Clear geometry result tables
        self.ids.grating_results.clear_widgets()
        self.ids.distances_results.clear_widgets()
        # Reset geometry results sketch
        self.ids.geometry_sketch.sketch.reset()

        for var_name, value in self.ids.iteritems():
            if 'CheckBox' in str(value):
                # Exclude show previous, since on_show_previous_results_active
                # is calling this function
                if not show_previous:
                    value.active = False
                elif var_name != 'show_previous_results':
                    value.active = False
            elif 'TabbedPanel' in str(value):
                continue
            elif 'Layout' in str(value):
                continue
            elif 'Distances' in str(value):
                continue
            elif 'GeometryGrid' in str(value):
                continue
            elif 'CustomSpinner' in str(value):
                continue
            elif not value.text:
                continue
            elif 'FloatInput' in str(value):
                value.text = ""
            elif 'IntInput' in str(value):
                value.text = ""
            elif 'TextInput' in str(value):
                value.text = ""
            elif 'Spinner' in str(value):
                if var_name == 'fixed_grating':
                    value.text = 'Choose fixed grating...'
                elif var_name == 'sample_shape':
                    value.text = ''

        # Remove spectrum
        self.ids.spectrum_file_name.text = ''
        # Reset defaults
        self.ids.spectrum_step.text = '1.0'
        self.ids.exposure_time.text = '1.0'

        logger.info("... done.")

    # Utility functions #######################################################

    def calc_boxlayout_height(self, childen_height, boxlayout):
        """
        Calculates the height of a boxlayout, in case it is only filled with
        childen of height = children_height.

        Parameters
        ==========

        childen_height [pxls]
        boxlayout [BoxLayout]

        Returns
        =======

        boxlayout_height [pxls]

        """
        boxlayout_height = ((childen_height + boxlayout.spacing +
                             boxlayout.padding[1] + boxlayout.padding[3]) *
                            len(boxlayout.children))
        return boxlayout_height


# %% Main App

class giGUIApp(App):
    def build(self):
        self.title = 'GI Simumlation'
        return giGUI()  # Main widget, root

# %% Main

if __name__ == '__main__':
    giGUIApp().run()
