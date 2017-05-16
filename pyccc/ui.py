# Copyright 2016 Autodesk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import print_function, unicode_literals, absolute_import, division
from future import standard_library
standard_library.install_aliases()
from future.builtins import *

from . import status
import sys

from pyccc import status, utils

if utils.can_use_widgets():
    widgets_enabled = True
    from ipywidgets import Box, Tab
    import ipywidgets as ipy
    import traitlets

else:
    widgets_enabled = False
    ipy = traitlets = None
    Box = Tab = object


__all__ = 'JobStatusDisplay'.split()


class JobStatusDisplay(Box):
    """
    To be mixed into pyccc job objects
    """

    def __init__(self, job, **kwargs):
        """
        :param job:
        :type job: bioplatform.job.Job
        :param kwargs:
        :return:
        """
        kwargs.setdefault('orientation', 'vertical')
        super(JobStatusDisplay, self).__init__(**kwargs)
        self._job = job
        self.update()
        self.on_displayed(self.update)

    def update(self, *args):
        jobstat = self._job.status
        status_display = StatusView(self._job)
        if self._job.inputs:
            input_browser = FileBrowser(self._job.inputs, margin=5, font_size=9)
        else:
            input_browser = ipy.HTML('No input files')
        file_browser = ipy.Tab([input_browser])
        file_browser.set_title(0, 'Input files')
        file_browser.selected_index = -1

        if jobstat == status.FINISHED:
            output_files = self._job.get_output()
            if self._job.stdout:
                output_files['Standard output'] = self._job.stdout
            if self._job.stderr:
                output_files['Standard error'] = self._job.stderr
            output_browser = FileBrowser(output_files, margin=5, font_size=9)
            file_browser.children = [input_browser, output_browser]
            file_browser.set_title(1, 'Output files')
            self.children = [status_display, file_browser]

        else:
            update_button = ipy.Button(description='Update')
            update_button.on_click(self.update)
            self.children = [status_display, update_button, file_browser]


class FileBrowser(Tab):
    def __init__(self, file_dict, ignore_ext=None, **kwargs):
        if ignore_ext is None:
            ignore_ext = 'pyo pyc'.split()

        titles = []
        file_list = [ipy.Box()]
        ignores = set(ignore_ext)
        for filename, fileobj in file_dict.items():
            ext = filename.split('.')[-1]
            if ext in ignores:
                continue
            file_display = FileView(fileobj)
            file_list.append(file_display)
            titles.append(filename)
        super(FileBrowser, self).__init__(file_list, **kwargs)
        self.set_title(0, 'x')
        for ititle, title in enumerate(titles):
            self.set_title(ititle + 1, title)
        self.selected_index = -1


class FileView(Box):
    CHUNK = 10000
    TRUNCATE_MESSAGE = '... [click "See more" to continue]'
    TEXTAREA_KWARGS = dict(font_family='monospace',
                           width='75%',
                           disabled=True)

    def __init__(self, fileobj, **kwargs):
        super(FileView, self).__init__(**kwargs)
        self._string = None
        self._current_pos = 0
        self.load_more_button = None
        self.textarea = None
        self._fileobj = fileobj
        # For files that need to be fetched, make a download button
        if hasattr(fileobj, '_fetched') and not fileobj._fetched:
            self.download_button = ipy.Button(description='Download')
            self.children = [self.download_button]
            self.download_button.on_click(self.handle_download_click)
        # if it's file-like, get the _contents
        elif hasattr(fileobj, 'read'):
            try:
                self._string = fileobj.read()
            except UnicodeDecodeError:
                self._string = '[NOT SHOWN - UNABLE TO DECODE FILE]'
            self.render_string()
        # Just display a string
        else:
            self._string = fileobj
            self.render_string()

    def render_string(self):
        height = '%spx' % min(self._string.count('\n') * 16 + 36, 600)
        try:
            self.textarea = ipy.Textarea(self._string[:self.CHUNK],
                                         height=height,
                                         **self.TEXTAREA_KWARGS)
        except traitlets.TraitError:
            self.textarea = ipy.Textarea('[NOT SHOWN - UNABLE TO DECODE FILE]',
                                         height='300px',
                                         **self.TEXTAREA_KWARGS)
            return
        finally:
            self.children = [self.textarea]
            self._current_pos = self.CHUNK

        if len(self._string) > self.CHUNK:
            self.textarea.value += self.TRUNCATE_MESSAGE
            self.load_more_button = ipy.Button(description='See more')
            self.load_more_button.on_click(self.load_more)
            self.children = self.children + (self.load_more_button,)

    def load_more(self, *args, **kwargs):
        self._current_pos += self.CHUNK
        if self._current_pos >= len(self._string):
            self.textarea.value = self._string
            self.children = tuple(c for c in self.children if c is not self.load_more_button)
        else:
            self.textarea.value = self._string[:self._current_pos] + self.TRUNCATE_MESSAGE

    def handle_download_click(self, *args):
        """
        Callback for download button. Downloads the file and replaces the button
        with a view of the file.
        :param args:
        :return:
        """
        self.download_button.on_click(self.handle_download_click,remove=True)
        self.download_button.description = 'Downloading ...'
        self._string = self._fileobj.read()
        self.render_string()


class StatusView(Box):
    STATUS_STRING = ('<h5>Job: %s</h5>'
                     '<b>Provider:</b> %s<br>'
                     '<b>JobId:</b> %s<br>'
                     '<b>Image: </b>%s<br>'
                     '<b>Command: </b>%s<br>'
                     '<b>Status:</b> %s</font>')

    def __init__(self, job, **kwargs):
        kwargs.setdefault('orientation', 'vertical')

        super(StatusView,self).__init__(**kwargs)
        self._job = job
        stat = job.status
        text = ipy.HTML(self.STATUS_STRING%(job.name,
                                              str(job.engine),
                                              job.jobid,
                                              job.image,
                                              job.command,
                                            stat))
        if stat == status.QUEUED:
            bar_spec = dict(value=1, bar_style='danger')
        elif stat == status.RUNNING:
            bar_spec = dict(value=50, bar_style='info')
        elif stat == status.FINISHED:
            bar_spec = dict(value=100, bar_style='success')
        else:
            bar_spec = dict(value=100, bar_style='danger')
        bar = ipy.FloatProgress(**bar_spec)
        bar._css = [("div", "margin-top", "0px")]
        self.children = [text, bar]


