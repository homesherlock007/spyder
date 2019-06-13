# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""Working Directory Plugin"""

# pylint: disable=C0103
# pylint: disable=R0903
# pylint: disable=R0911
# pylint: disable=R0201

# Standard library imports
import os
import os.path as osp
from pathlib import Path
# Third party imports
from qtpy import QtWidgets, QtGui, QtCore
from qtpy.QtCore import Qt
from qtpy.compat import getexistingdirectory
from qtpy.QtCore import QSize, Signal, Slot
from qtpy.QtWidgets import QToolBar

# Local imports
from spyder.config.base import _, get_conf_path, get_home_dir
from spyder.api.plugins import SpyderPluginWidget
from spyder.py3compat import to_text_string
from spyder.utils.misc import getcwd_or_home
from spyder.utils import encoding
from spyder.utils import icon_manager as ima
from spyder.utils.qthelpers import create_action
from spyder.widgets.comboboxes import PathComboBox
from spyder.plugins.workingdirectory.confpage import WorkingDirectoryConfigPage

TRANSP_ICON_SIZE = 40, 40 

class WorkingDirectory(SpyderPluginWidget):
    """Working directory changer plugin."""

    CONF_SECTION = 'workingdir'
    CONFIGWIDGET_CLASS = WorkingDirectoryConfigPage
    LOG_PATH = get_conf_path(CONF_SECTION)

    set_previous_enabled = Signal(bool)
    set_next_enabled = Signal(bool)
    redirect_stdio = Signal(bool)
    set_explorer_cwd = Signal(str)
    refresh_findinfiles = Signal()
    set_current_console_wd = Signal(str)
    
    def __init__(self, parent, workdir=None, **kwds):
        SpyderPluginWidget.__init__(self, parent)
        self.hide()

        self.toolbar = QToolBar(self)

        # Initialize plugin
        self.initialize_plugin()
        self.options_button.hide()
        
        self.toolbar.setWindowTitle(self.get_plugin_title())
        # Used to save Window state
        self.toolbar.setObjectName(self.get_plugin_title())

        # Previous dir action
        self.history = []
        self.histindex = None
        self.previous_action = create_action(self, "previous", None,
                                     ima.icon('previous'), _('Back'),
                                     triggered=self.previous_directory)
        self.toolbar.addAction(self.previous_action)

        # Next dir action
        self.next_action = create_action(self, "next", None,
                                     ima.icon('next'), _('Next'),
                                     triggered=self.next_directory)
        self.toolbar.addAction(self.next_action)

        # Enable/disable previous/next actions
        self.set_previous_enabled.connect(self.previous_action.setEnabled)
        self.set_next_enabled.connect(self.next_action.setEnabled)
        
        # Path combo box
        adjust = self.get_option('working_dir_adjusttocontents')
        self.pathedit = PathComboBox(self, adjust_to_contents=adjust)
        self.pathedit.setToolTip(_("This is the working directory for newly\n"
                               "opened consoles (Python/IPython consoles and\n"
                               "terminals), for the file explorer, for the\n"
                               "find in files plugin and for new files\n"
                               "created in the editor"))
        self.pathedit.open_dir.connect(self.chdir)
        self.pathedit.activated[str].connect(self.chdir)
        self.pathedit.setMaxCount(self.get_option('working_dir_history'))
        wdhistory = self.load_wdhistory(workdir)
        if workdir is None:
            if self.get_option('console/use_project_or_home_directory'):
                workdir = get_home_dir()
            else:
                workdir = self.get_option('console/fixed_directory', default='')
                if not osp.isdir(workdir):
                    workdir = get_home_dir()
        self.chdir(workdir)
        self.pathedit.addItems(wdhistory)
        self.pathedit.selected_text = self.pathedit.currentText()
        self.refresh_plugin()
        self.toolbar.addWidget(self.pathedit)
        
        # Browse action
        browse_action = create_action(self, "browse", None,
                                      ima.icon('DirOpenIcon'),
                                      _('Browse a working directory'),
                                      triggered=self.select_directory)
        self.toolbar.addAction(browse_action)

        # Parent dir action
        parent_action = create_action(self, "parent", None,
                                      ima.icon('up'),
                                      _('Change to parent directory'),
                                      triggered=self.parent_directory)
        self.toolbar.addAction(parent_action)
                
    #------ SpyderPluginWidget API ---------------------------------------------    
    def get_plugin_title(self):
        """Return widget title"""
        return _('Current working directory')
    
    def get_plugin_icon(self):
        """Return widget icon"""
        return ima.icon('DirOpenIcon')
        
    def get_plugin_actions(self):
        """Setup actions"""
        return [None, None]
    
    def register_plugin(self):
        """Register plugin in Spyder's main window"""
        self.redirect_stdio.connect(self.main.redirect_internalshell_stdio)
        self.main.console.shell.refresh.connect(self.refresh_plugin)
        iconsize = 24 
        self.toolbar.setIconSize(QSize(iconsize, iconsize))
        self.main.addToolBar(self.toolbar)
        
    def refresh_plugin(self):
        """Refresh widget"""
        curdir = getcwd_or_home()
        self.pathedit.add_text(curdir)
        self.save_wdhistory()
        self.set_previous_enabled.emit(
                             self.histindex is not None and self.histindex > 0)
        self.set_next_enabled.emit(self.histindex is not None and \
                                   self.histindex < len(self.history)-1)

    def apply_plugin_settings(self, options):
        """Apply configuration file's plugin settings"""
        pass
        
    def closing_plugin(self, cancelable=False):
        """Perform actions before parent main window is closed"""
        return True
        
    #------ Public API ---------------------------------------------------------
    def load_wdhistory(self, workdir=None):
        """Load history from a text file in user home directory"""
        if osp.isfile(self.LOG_PATH):
            wdhistory, _ = encoding.readlines(self.LOG_PATH)
            wdhistory = [name for name in wdhistory if os.path.isdir(name)]
        else:
            if workdir is None:
                workdir = get_home_dir()
            wdhistory = [ workdir ]
        return wdhistory

    def save_wdhistory(self):
        """Save history to a text file in user home directory"""
        text = [ to_text_string( self.pathedit.itemText(index) ) \
                 for index in range(self.pathedit.count()) ]
        try:
            encoding.writelines(text, self.LOG_PATH)
        except EnvironmentError:
            pass
    
    @Slot()
    def select_directory(self):
        """Select directory"""
        self.redirect_stdio.emit(False)
        directory = getexistingdirectory(self.main, _("Select directory"),
                                         getcwd_or_home())
        if directory:
            self.chdir(directory)
        self.redirect_stdio.emit(True)
    
    @Slot()
    def previous_directory(self):
        """Back to previous directory"""
        self.histindex -= 1
        self.chdir(directory='', browsing_history=True)
    
    @Slot()
    def next_directory(self):
        """Return to next directory"""
        self.histindex += 1
        self.chdir(directory='', browsing_history=True)
    
    @Slot()
    def parent_directory(self):
        """Change working directory to parent directory"""
        self.chdir(os.path.join(getcwd_or_home(), os.path.pardir))

    @Slot(str)
    @Slot(str, bool)
    @Slot(str, bool, bool)
    @Slot(str, bool, bool, bool)
    def chdir(self, directory, browsing_history=False,
              refresh_explorer=True, refresh_console=True):
        """Set directory as working directory"""
        if directory:
            directory = osp.abspath(to_text_string(directory))

        # Working directory history management
        if browsing_history:
            directory = self.history[self.histindex]
        elif directory in self.history:
            self.histindex = self.history.index(directory)
        else:
            if self.histindex is None:
                self.history = []
            else:
                self.history = self.history[:self.histindex+1]
            self.history.append(directory)
            self.histindex = len(self.history)-1
        
        # Changing working directory
        try:
            os.chdir(directory)
            if refresh_explorer:
                self.set_explorer_cwd.emit(directory)
            if refresh_console:
                self.set_current_console_wd.emit(directory)
            self.refresh_findinfiles.emit()
        except OSError:
            self.history.pop(self.histindex)
        self.refresh_plugin()

class BreadcrumbsAddressBar(QtWidgets.QFrame):
    """Windows Explorer-like address bar"""
    listdir_error = QtCore.Signal(Path)  # failed to list a directory
    path_error = QtCore.Signal(Path)  # entered path does not exist
    path_selected = QtCore.Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)

        self.file_ico_prov = QtWidgets.QFileIconProvider()
        self.fs_model = FilenameModel('dirs', icon_provider=self.get_icon)

        pal = self.palette()
        pal.setColor(QtGui.QPalette.Background,
                     pal.color(QtGui.QPalette.Base))
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        self.setFrameShape(self.StyledPanel)
        self.layout().setContentsMargins(4, 0, 0, 0)
        self.layout().setSpacing(0)

        # Edit presented path textually
        self.line_address = QtWidgets.QLineEdit(self)
        self.line_address.setFrame(False)
        self.line_address.hide()
        self.line_address.keyPressEvent_super = self.line_address.keyPressEvent
        self.line_address.keyPressEvent = self.line_address_keyPressEvent
        self.line_address.focusOutEvent = self.line_address_focusOutEvent
        self.line_address.contextMenuEvent_super = self.line_address.contextMenuEvent
        self.line_address.contextMenuEvent = self.line_address_contextMenuEvent
        layout.addWidget(self.line_address)
        # Add QCompleter to address line
        completer = self.init_completer(self.line_address, self.fs_model)
        completer.activated.connect(self.set_path)

        # Container for `btn_crumbs_hidden`, `crumbs_panel`, `switch_space`
        self.crumbs_container = QtWidgets.QWidget(self)
        crumbs_cont_layout = QtWidgets.QHBoxLayout(self.crumbs_container)
        crumbs_cont_layout.setContentsMargins(0, 0, 0, 0)
        crumbs_cont_layout.setSpacing(0)
        layout.addWidget(self.crumbs_container)

        # Hidden breadcrumbs menu button
        self.btn_crumbs_hidden = QtWidgets.QToolButton(self)
        self.btn_crumbs_hidden.setAutoRaise(True)
        self.btn_crumbs_hidden.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.btn_crumbs_hidden.setArrowType(Qt.LeftArrow)
        self.btn_crumbs_hidden.setStyleSheet("QToolButton::menu-indicator {"
                                             "image: none;}")
        self.btn_crumbs_hidden.setMinimumSize(self.btn_crumbs_hidden.minimumSizeHint())
        self.btn_crumbs_hidden.hide()
        crumbs_cont_layout.addWidget(self.btn_crumbs_hidden)
        menu = QtWidgets.QMenu(self.btn_crumbs_hidden)  # FIXME:
        menu.aboutToShow.connect(self._hidden_crumbs_menu_show)
        self.btn_crumbs_hidden.setMenu(menu)

        # Container for breadcrumbs
        self.crumbs_panel = QtWidgets.QWidget(self)
        crumbs_layout = LeftHBoxLayout(self.crumbs_panel)
        crumbs_layout.widget_state_changed.connect(self.crumb_hide_show)
        crumbs_layout.setContentsMargins(0, 0, 0, 0)
        crumbs_layout.setSpacing(0)
        crumbs_cont_layout.addWidget(self.crumbs_panel)

        # Clicking on empty space to the right puts the bar into edit mode
        self.switch_space = QtWidgets.QWidget(self)
        # s_policy = self.switch_space.sizePolicy()
        # s_policy.setHorizontalStretch(1)
        # self.switch_space.setSizePolicy(s_policy)
        self.switch_space.mouseReleaseEvent = self.switch_space_mouse_up
        # crumbs_cont_layout.addWidget(self.switch_space)
        crumbs_layout.set_space_widget(self.switch_space)

        self.btn_browse = QtWidgets.QToolButton(self)
        self.btn_browse.setAutoRaise(True)
        self.btn_browse.setText("...")
        self.btn_browse.setToolTip("Browse for folder")
        self.btn_browse.clicked.connect(self._browse_for_folder)
        layout.addWidget(self.btn_browse)

        self.setMaximumHeight(self.line_address.height())  # FIXME:

        self.ignore_resize = False
        self.path_ = None
        self.set_path(Path())

    @staticmethod
    def init_completer(edit_widget, model):
        "Init QCompleter to work with filesystem"
        completer = QtWidgets.QCompleter(edit_widget)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setModel(model)
        # Optimize performance https://stackoverflow.com/a/33454284/1119602
        popup = completer.popup()
        popup.setUniformItemSizes(True)
        popup.setLayoutMode(QtWidgets.QListView.Batched)
        edit_widget.setCompleter(completer)
        edit_widget.textEdited.connect(model.setPathPrefix)
        return completer

    def get_icon(self, path: (str, Path)):
        "Path -> QIcon"
        fileinfo = QtCore.QFileInfo(str(path))
        dat = self.file_ico_prov.icon(fileinfo)
        if fileinfo.isHidden():
            pmap = QtGui.QPixmap(*TRANSP_ICON_SIZE)
            pmap.fill(Qt.transparent)
            painter = QtGui.QPainter(pmap)
            painter.setOpacity(0.5)
            dat.paint(painter, 0, 0, *TRANSP_ICON_SIZE)
            painter.end()
            dat = QtGui.QIcon(pmap)
        return dat

    def line_address_contextMenuEvent(self, event):
        self.line_address_context_menu_flag = True
        self.line_address.contextMenuEvent_super(event)

    def line_address_focusOutEvent(self, event):
        if getattr(self, 'line_address_context_menu_flag', False):
            self.line_address_context_menu_flag = False
            return  # do not cancel edit on context menu
        self._cancel_edit()

    def _hidden_crumbs_menu_show(self):
        "SLOT: fill menu with hidden breadcrumbs list"
        menu = self.sender()
        menu.clear()
        # hid_count = self.crumbs_panel.layout().count_hidden()
        for i in reversed(list(self.crumbs_panel.layout().widgets('hidden'))):
            action = menu.addAction(self.get_icon(i.path), i.text())
            action.path = i.path
            action.triggered.connect(self.set_path)

    def _browse_for_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose folder", str(self.path()))
        if path:
            self.set_path(path)

    def line_address_keyPressEvent(self, event):
        "Actions to take after a key press in text address field"
        if event.key() == Qt.Key_Escape:
            self._cancel_edit()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.set_path(self.line_address.text())
            self._show_address_field(False)
        # elif event.text() == os.path.sep:  # FIXME: separator cannot be pasted
        #     print('fill completer data here')
        #     paths = [str(i) for i in
        #              Path(self.line_address.text()).iterdir() if i.is_dir()]
        #     self.completer.model().setStringList(paths)
        else:
            self.line_address.keyPressEvent_super(event)

    def _clear_crumbs(self):
        layout = self.crumbs_panel.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _insert_crumb(self, path):
        btn = QtWidgets.QToolButton(self.crumbs_panel)
        btn.setAutoRaise(True)
        btn.setPopupMode(btn.MenuButtonPopup)
        # FIXME: C:\ has no name. Use rstrip on Windows only?
        crumb_text = path.name or str(path).upper().rstrip(os.path.sep)
        btn.setText(crumb_text)
        btn.path = path
        btn.clicked.connect(self.crumb_clicked)
        menu = MenuListView(btn)
        menu.aboutToShow.connect(self.crumb_menu_show)
        menu.setModel(self.fs_model)
        menu.clicked.connect(self.crumb_menuitem_clicked)
        menu.activated.connect(self.crumb_menuitem_clicked)
        btn.setMenu(menu)
        self.crumbs_panel.layout().insertWidget(0, btn)
        btn.setMinimumSize(btn.minimumSizeHint())  # fixed size breadcrumbs
        sp = btn.sizePolicy()
        sp.setVerticalPolicy(sp.Minimum)
        btn.setSizePolicy(sp)
        # print(self._check_space_width(btn.minimumWidth()))
        # print(btn.size(), btn.sizeHint(), btn.minimumSizeHint())

    def crumb_menuitem_clicked(self, index):
        "SLOT: breadcrumb menu item was clicked"
        self.set_path(index.data(Qt.EditRole))

    def crumb_clicked(self):
        "SLOT: breadcrumb was clicked"
        self.set_path(self.sender().path)

    def crumb_menu_show(self):
        "SLOT: fill subdirectory list on menu open"
        menu = self.sender()
        self.fs_model.setPathPrefix(str(menu.parent().path) + os.path.sep)

    def set_path(self, path=None):
        """
        Set path displayed in this BreadcrumbsAddressBar
        Returns `False` if path does not exist or permission error.
        Can be used as a SLOT: `sender().path` is used if `path` is `None`)
        """
        path, emit_err = Path(path or self.sender().path), None
        try:  # C: -> C:\, folder\..\folder -> folder
            path = path.resolve()
        except PermissionError:
            emit_err = self.listdir_error
        if not path.exists():
            emit_err = self.path_error
        self._cancel_edit()  # exit edit mode
        if emit_err:  # permission error or path does not exist
            emit_err.emit(path)
            return False
        self._clear_crumbs()
        self.path_ = path
        self.line_address.setText(str(path))
        self._insert_crumb(path)
        while path.parent != path:
            path = path.parent
            self._insert_crumb(path)
        self.path_selected.emit(path)
        return True

    def _cancel_edit(self):
        "Set edit line text back to current path and switch to view mode"
        self.line_address.setText(str(self.path()))  # revert path
        self._show_address_field(False)  # switch back to breadcrumbs view

    def path(self):
        "Get path displayed in this BreadcrumbsAddressBar"
        return self.path_

    def switch_space_mouse_up(self, event):
        "EVENT: switch_space mouse clicked"
        if event.button() != Qt.LeftButton:  # left click only
            return
        self._show_address_field(True)

    def _show_address_field(self, b_show):
        "Show text address field"
        if b_show:
            self.crumbs_container.hide()
            self.line_address.show()
            self.line_address.setFocus()
            self.line_address.selectAll()
        else:
            self.line_address.hide()
            self.crumbs_container.show()

    def crumb_hide_show(self, widget, state:bool):
        "SLOT: a breadcrumb is hidden/removed or shown"
        layout = self.crumbs_panel.layout()
        if layout.count_hidden() > 0:
            self.btn_crumbs_hidden.show()
        else:
            self.btn_crumbs_hidden.hide()

    def minimumSizeHint(self):
        # print(self.layout().minimumSize().width())
        return QtCore.QSize(150, self.line_address.height())

    #--------------------------------------------------------#
    # def register_plugin(self):
    #     """Register plugin in Spyder's main window"""
    #     self.redirect_stdio.connect(self.main.redirect_internalshell_stdio)
    #     self.main.console.shell.refresh.connect(self.refresh_plugin)
    #     iconsize = 24 
    #     self.toolbar.setIconSize(QSize(iconsize, iconsize))
    #     self.main.addToolBar(self.toolbar)

class FilenameModel(QtCore.QStringListModel):
    """
    Model used by QCompleter for file name completions.
    Constructor options:
    `filter_` (None, 'dirs') - include all entries or folders only
    `fs_engine` ('qt', 'pathlib') - enumerate files using `QDir` or `pathlib`
    `icon_provider` (func, 'internal', None) - a function which gets path
                                               and returns QIcon
    """
    def __init__(self, filter_=None, fs_engine='qt', icon_provider='internal'):
        super().__init__()
        self.current_path = None
        self.fs_engine = fs_engine
        self.filter = filter_
        if icon_provider == 'internal':
            self.icons = QtWidgets.QFileIconProvider()
            self.icon_provider = self.get_icon
        else:
            self.icon_provider = icon_provider

    def data(self, index, role):
        "Get names/icons of files"
        default = super().data(index, role)
        if role == Qt.DecorationRole and self.icon_provider:
            # self.setData(index, dat, role)
            return self.icon_provider(super().data(index, Qt.DisplayRole))
        if role == Qt.DisplayRole:
            return Path(default).name
        return default

    def get_icon(self, path):
        "Internal icon provider"
        return self.icons.icon(QtCore.QFileInfo(path))

    def get_file_list(self, path):
        "List entries in `path` directory"
        lst = None
        if self.fs_engine == 'pathlib':
            lst = self.sort_paths([i for i in path.iterdir()
                                   if self.filter != 'dirs' or i.is_dir()])
        elif self.fs_engine == 'qt':
            qdir = QtCore.QDir(str(path))
            qdir.setFilter(qdir.NoDotAndDotDot | qdir.Hidden |
                (qdir.Dirs if self.filter == 'dirs' else qdir.AllEntries))
            names = qdir.entryList(sort=QtCore.QDir.DirsFirst |
                                   QtCore.QDir.LocaleAware)
            lst = [str(path / i) for i in names]
        return lst

    @staticmethod
    def sort_paths(paths):
        "Windows-Explorer-like filename sorting (for 'pathlib' engine)"
        dirs, files = [], []
        for i in paths:
            if i.is_dir():
                dirs.append(str(i))
            else:
                files.append(str(i))
        return sorted(dirs, key=str.lower) + sorted(files, key=str.lower)

    def setPathPrefix(self, prefix):
        path = Path(prefix)
        if not prefix.endswith(os.path.sep):
            path = path.parent
        if path == self.current_path:
            return  # already listed
        if not path.exists():
            return  # wrong path
        self.setStringList(self.get_file_list(path))
        self.current_path = path


class MenuListView(QtWidgets.QMenu):
    """
    QMenu with QListView.
    Supports `activated`, `clicked`, `setModel`.
    """
    max_visible_items = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self.listview = lv = QtWidgets.QListView()
        lv.setFrameShape(lv.NoFrame)
        lv.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pal = lv.palette()
        pal.setColor(pal.Base, self.palette().color(pal.Window))
        lv.setPalette(pal)

        act_wgt = QtWidgets.QWidgetAction(self)
        act_wgt.setDefaultWidget(lv)
        self.addAction(act_wgt)

        self.activated = lv.activated
        self.clicked = lv.clicked
        self.setModel = lv.setModel

        lv.sizeHint = self.size_hint
        lv.minimumSizeHint = self.size_hint
        lv.mousePressEvent = lambda event: None  # skip
        lv.mouseMoveEvent = self.mouse_move_event
        lv.setMouseTracking(True)  # receive mouse move events
        lv.leaveEvent = self.mouse_leave_event
        lv.mouseReleaseEvent = self.mouse_release_event
        lv.keyPressEvent = self.key_press_event
        lv.setFocusPolicy(Qt.NoFocus)  # no focus rect
        lv.setFocus()

        self.last_index = QtCore.QModelIndex()  # selected index

    def key_press_event(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self.last_index.isValid():
                self.activated.emit(self.last_index)
            self.close()
        elif key == Qt.Key_Escape:
            self.close()
        elif key in (Qt.Key_Down, Qt.Key_Up):
            model = self.listview.model()
            row_from, row_to = 0, model.rowCount()-1
            if key == Qt.Key_Down:
                row_from, row_to = row_to, row_from
            if not self.last_index or self.last_index.row() == row_from:
                index = model.index(row_to, 0)
            else:
                shift = 1 if key == Qt.Key_Down else -1
                index = model.index(self.last_index.row()+shift, 0)
            self.listview.setCurrentIndex(index)
            self.last_index = index

    def mouse_move_event(self, event):
        self.listview.clearSelection()
        self.last_index = self.listview.indexAt(event.pos())

    def mouse_leave_event(self, event):
        self.listview.clearSelection()
        self.last_index = QtCore.QModelIndex()

    def mouse_release_event(self, event):
        "When item is clicked w/ left mouse button close menu, emit `clicked`"
        if event.button() == Qt.LeftButton:
            if self.last_index.isValid():
                self.clicked.emit(self.last_index)
            self.close()

    def size_hint(self):
        lv = self.listview
        width = lv.sizeHintForColumn(0)
        width += lv.verticalScrollBar().sizeHint().width()
        if isinstance(self.parent(), QtWidgets.QToolButton):
            width = max(width, self.parent().width())
        visible_rows = min(self.max_visible_items, lv.model().rowCount())
        return QtCore.QSize(width, visible_rows * lv.sizeHintForRow(0))

class LeftHBoxLayout(QtWidgets.QHBoxLayout):
    '''
    Left aligned horizontal layout.
    Hides items similar to Windows Explorer address bar.
    '''
    # Signal is emitted when an item is hidden/shown or removed with `takeAt`
    widget_state_changed = QtCore.Signal(object, bool)

    def __init__(self, parent=None, minimal_space=0.1):
        super().__init__(parent)
        self.first_visible = 0
        self.set_space_widget()
        self.set_minimal_space(minimal_space)

    def set_space_widget(self, widget=None, stretch=1):
        """
        Set widget to be used to fill empty space to the right
        If `widget`=None the stretch item is used (by default)
        """
        super().takeAt(self.count())
        if widget:
            super().addWidget(widget, stretch)
        else:
            self.addStretch(stretch)

    def space_widget(self):
        "Widget used to fill free space"
        return self[self.count()]

    def setGeometry(self, rc:QtCore.QRect):
        "`rc` - layout's rectangle w/o margins"
        super().setGeometry(rc)  # perform the layout
        min_sp = self.minimal_space()
        if min_sp < 1:  # percent
            min_sp *= rc.width()
        free_space = self[self.count()].geometry().width() - min_sp
        if free_space < 0 and self.count_visible() > 1:  # hide more items
            widget = self[self.first_visible].widget()
            widget.hide()
            self.first_visible += 1
            self.widget_state_changed.emit(widget, False)
        elif free_space > 0 and self.count_hidden():  # show more items
            widget = self[self.first_visible-1].widget()
            w_width = widget.width() + self.spacing()
            if w_width <= free_space:  # enough space to show next item
                # setGeometry is called after show
                QtCore.QTimer.singleShot(0, widget.show)
                self.first_visible -= 1
                self.widget_state_changed.emit(widget, True)

    def count_visible(self):
        "Count of visible widgets"
        return self.count(visible=True)

    def count_hidden(self):
        "Count of hidden widgets"
        return self.count(visible=False)

    def minimumSize(self):
        margins = self.contentsMargins()
        return QtCore.QSize(margins.left() + margins.right(),
                            margins.top() + 24 + margins.bottom())

    def addWidget(self, widget, stretch=0, alignment=None):
        "Append widget to layout, make its width fixed"
        # widget.setMinimumSize(widget.minimumSizeHint())  # FIXME:
        super().insertWidget(self.count(), widget, stretch,
                             alignment or Qt.Alignment(0))

    def count(self, visible=None):
        "Count of items in layout: `visible`=True|False(hidden)|None(all)"
        cnt = super().count() - 1  # w/o last stretchable item
        if visible is None:  # all items
            return cnt
        if visible:  # visible items
            return cnt - self.first_visible
        return self.first_visible  # hidden items

    def widgets(self, state='all'):
        "Iterate over child widgets"
        for i in range(self.first_visible if state=='visible' else 0,
                       self.first_visible if state=='hidden' else self.count()
                       ):
            yield self[i].widget()

    def set_minimal_space(self, value):
        """
        Set minimal size of space area to the right:
        [0.0, 1.0) - % of the full width
        [1, ...) - size in pixels
        """
        self._minimal_space = value
        self.invalidate()

    def minimal_space(self):
        "See `set_minimal_space`"
        return self._minimal_space

    def __getitem__(self, index):
        "`itemAt` slices wrapper"
        if index < 0:
            index = self.count() + index
        return self.itemAt(index)

    def takeAt(self, index):
        "Return an item at the specified `index` and remove it from layout"
        if index < self.first_visible:
            self.first_visible -= 1
        item = super().takeAt(index)
        self.widget_state_changed.emit(item.widget(), False)
        return item

