"""
filebrowser --- Dock with file system tree
==========================================
"""
import sys
import fnmatch
import re
import os
import os.path

from PyQt4.QtCore import QDir, QRect, QEvent, QModelIndex, QObject, Qt
from PyQt4.QtGui import QAction, QDialogButtonBox, QFileDialog, QFrame, QFileSystemModel, \
                        QIcon, QItemSelectionModel, QKeySequence, QComboBox, QMenu, \
                        QPainter, \
                        QShortcut, QSortFilterProxyModel, QToolButton, QTreeView, QVBoxLayout, QWidget

from PyQt4.fresh import pDockWidget
from PyQt4.fresh import pStringListEditor

from mks.core.core import core

class Plugin(QObject):
    """File system tree.
    
    Allows to open files quickly
    """
    def __init__(self):
        """Create and install the plugin
        """
        QObject.__init__(self)
        # create dock
        self.dock = DockFileBrowser(core.mainWindow())
        self.dock.hide()
        # add dock to dock toolbar entry
        core.mainWindow().dockToolBar( Qt.LeftToolBarArea ).addDockWidget(self.dock)
    
    def __del__(self):
        """Uninstall the plugin
        """
        self.dock.deleteLater()

    def moduleConfiguratorClass(self):
        """ ::class:`mks.core.uisettings.ModuleConfigurator` used to configure plugin with UISettings dialogue
        """
        return None  # No any settings

    def settingsWidget(self):
        """Get settings widget of the plugin
        """
        return FileBrowserSettings( self )

class FileBrowserSettings(QWidget):
    """Plugin settings widget
    """
    def __init__(self, plugin): 
        QWidget.__init__(self, plugin)
        self.plugin = plugin
        
        # list editor
        self.editor = pStringListEditor( self, self.tr( "Except Suffixes" ) )
        self.editor.setValues( core.config()["FileBrowser"]["NegativeFilter"] )
        
        # apply button
        dbbApply = QDialogButtonBox( self )
        dbbApply.addButton( QDialogButtonBox.Apply )
        
        # global layout
        vbox = QVBoxLayout( self )
        vbox.addWidget( self.editor )
        vbox.addWidget( dbbApply )
        
        # connections
        dbbApply.button( QDialogButtonBox.Apply ).clicked.connect(self.applySettings)

    def applySettings(self):
        """Handler of clicking Apply button. Applying settings
        """
        pyStrList = map(str, self.editor.values())
        """FIXME
        core.config()["FileBrowser"]["NegativeFilter"] = pyStrList
        """
        self.plugin.dock.setFilters(pyStrList)

class FileBrowserFilteredModel(QSortFilterProxyModel):
    """Model filters out files using negative filter.
    i.e. does not show .o .pyc and other temporary files
    """
    def __init__(self, parent):
        QSortFilterProxyModel.__init__(self, parent)
    
    def setFilters(self, filters):
        """Set list of negative filters. (Wildards of files, which are not visible)
        """
        regExPatterns = map(fnmatch.translate, filters)
        compositeRegExpPattern = '(' + ')|('.join(regExPatterns) + ')'
        self.filterRegExp = re.compile(compositeRegExpPattern)
        
        self.invalidateFilter()

    def columnCount(self, parent = QModelIndex()):
        """Column count for the model
        """
        return 1
    
    def hasChildren(self, parent = QModelIndex()):
        """Check if node has children. QAbstractItemModel standard method
        """
        return self.sourceModel().hasChildren( self.mapToSource( parent ) )
        
    def filterAcceptsRow(self, source_row, source_parent):
        """ Main method. Check if file matches filter
        """
        if  source_parent == QModelIndex():
            return True
        return not self.filterRegExp.match(source_parent.child( source_row, 0 ).data().toString() )

class DockFileBrowser(pDockWidget):
    """UI interface of FileBrowser plugin. 
        
    Dock with file system tree, Box, navigation in a file system
    tree, for moving root of tree to currently selected dirrectory and
    up (relatively for current dirrectory)
    """
    
    def __init__(self, parent):
        pDockWidget.__init__(self, parent)
        self.setObjectName("FileBrowserDock")
        self.setWindowTitle(self.tr( "File Browser" ))
        self.setWindowIcon(QIcon(':/mksicons/open.png'))
        # restrict areas
        self.setAllowedAreas( Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea )
        
        """ FIXME
        # create menu action for the dock
        pActionsManager.setDefaultShortcut( self.dock.toggleViewAction(), QKeySequence( "F7" ) )
        """
        self.showAction().setShortcut("F7")
        core.actionModel().addAction("mDocks/aFileBrowser", self.showAction())
        
        self.visibilityChanged.connect(self._onVisibilityChanged)
    
    def __term__(self, parent):
        core.actionModel().removeAction("mDocks/aFileBrowser")
    
    def _onVisibilityChanged(self, visible):
        """Postnoted widget initialization.
        Create element, when widget appears first timer
        """
        if visible:
            self._initialize()
            self.visibilityChanged.disconnect(self._onVisibilityChanged)
    
    def _initialize(self):
        """Delayed initialization of the widget for quicker start of application
        """
        def createAction(text, icon, slot, index):
            """Create action object and add it to title bar
            """
            actionObject = QAction(self.tr(text), self)
            actionObject.setIcon(QIcon(":/mksicons/%s.png" % icon))
            actionObject.setToolTip( actionObject.text() )
            actionObject.triggered.connect(slot)
            self.titleBar().addAction(actionObject, index )

        createAction("Add selected folder to bookmarks",      "add",       self.aAdd_triggered,       0)
        createAction("Remove selected folder from bookmarks", "remove",    self.aRemove_triggered,    1)
        
        # bookmarks menu
        self._bookmarksMenu = QMenu( self )
        aBookmarks = QAction( self.tr( "Bookmarks..." ), self )
        aBookmarks.setIcon( QIcon(":/mksicons/bookmark.png" ) )
        aBookmarks.setToolTip( aBookmarks.text() )
        toolButton = self.titleBar().addAction( aBookmarks, 2 )
        toolButton.setPopupMode( QToolButton.InstantPopup )
        aBookmarks.setMenu( self._bookmarksMenu )
        
        # add separator
        self.titleBar().addSeparator( 3 )

        # central widget
        wdg = QWidget( self )
        self.setWidget( wdg )
        
        # vertical layout
        vertLayout = QVBoxLayout( wdg )
        vertLayout.setMargin( 5 )
        vertLayout.setSpacing( 3 )
        
        # lineedit
        self._comboBox = QComboBox()
        self._comboBox.setAttribute( Qt.WA_MacShowFocusRect, False )
        self._comboBox.setAttribute( Qt.WA_MacSmallSize )
        self._comboBox.setEditable(True)
        self._comboBox.lineEdit().setReadOnly( True )
        vertLayout.addWidget( self._comboBox )
        
        # hline
        hline = QFrame( self )
        hline.setFrameStyle( QFrame.HLine | QFrame.Sunken )
        vertLayout.addWidget( hline )
        
        # dir model
        self._dirsModel = QFileSystemModel( self )
        self._dirsModel.setNameFilterDisables( False )
        self._dirsModel.setFilter( QDir.AllDirs | QDir.AllEntries | QDir.CaseSensitive | QDir.NoDotAndDotDot )
        # self._dirsModel.directoryLoaded.connect(self._setFocusToTree)  TODO don't have this signal in my Qt version
        
        # create proxy model
        self._filteredModel = FileBrowserFilteredModel( self )
        self._filteredModel.setSourceModel( self._dirsModel )
        self.setFilters(core.config()["FileBrowser"]["NegativeFilter"])
        
        # files view
        self._tree = QTreeView()
        self._tree.setAttribute( Qt.WA_MacShowFocusRect, False )
        self._tree.setAttribute( Qt.WA_MacSmallSize )
        self._tree.setContextMenuPolicy( Qt.ActionsContextMenu )
        self._tree.setHeaderHidden( True )
        self._tree.setUniformRowHeights( True )
        vertLayout.addWidget( self._tree )
        
        # assign model to views
        self._tree.setModel( self._filteredModel)

        # cd up action
        self._tbCdUp = QToolButton( self._comboBox.lineEdit() )
        self._tbCdUp.setIcon( QIcon( ":/mksicons/go-up.png" ) )
        self._tbCdUp.setCursor( Qt.ArrowCursor )
        self._tbCdUp.installEventFilter( self )
        
        if not sys.platform.startswith('win'):
            self._dirsModel.setRootPath( "/" )
        else:
            self._dirsModel.setRootPath('')
        
        # redirirect focus proxy
        self.setFocusProxy( self._tree )
        
        # shortcut accessible only when self._tree has focus
        aUpShortcut = QShortcut( QKeySequence( "BackSpace" ), self._tree )
        aUpShortcut.setContext( Qt.WidgetShortcut )
        
        # connections
        aUpShortcut.activated.connect(self._onTbCdUpClicked)
        self._bookmarksMenu.triggered.connect(self.bookmark_triggered)
        self._tree.activated.connect(self.tv_activated)
        self._tbCdUp.clicked.connect(self._onTbCdUpClicked)
        
        self.setCurrentPath( core.config()["FileBrowser"]["Path"] )
        self.setCurrentFilePath( core.config()["FileBrowser"]["FilePath"] )
        self._bookmarks = core.config()["FileBrowser"]["Bookmarks"]
        self.updateBookMarksMenu()
        
    
    def eventFilter(self, object_, event ):
        """ Event filter for mode switch tool button
        Draws icons in the search and path lineEdits
        """
        if  event.type() == QEvent.Paint:
            toolButton = object_
            lineEdit = self._comboBox.lineEdit()
            height = lineEdit.height()
            lineEdit.setContentsMargins( height, 0, 0, 0 )
            
            availableRect = QRect( 0, 0, height, height )
            toolButton.setGeometry( availableRect )
            
            painter = QPainter ( toolButton )
            toolButton.icon().paint( painter, availableRect )
            
            return True

        return pDockWidget.eventFilter( self, object_, event )
        
    def _filteredModelIndexToPath(self, index):
        """Map index to file path
        """
        srcIndex = self._filteredModel.mapToSource( index )
        return unicode(self._dirsModel.filePath( srcIndex ))
    
    def _onTbCdUpClicked(self):
        """Handler of click on Up button.
        """
        current = self._tree.currentIndex()
        if not current.isValid():
            current = self._tree.rootIndex().child(0, 0)
            self._tree.setCurrentIndex(current)
        
        # move tree root up, if necessary
        if current.parent() == self._tree.rootIndex() or \
           current == self._tree.rootIndex():  # need to move root up
            if self._tree.rootIndex().parent().isValid():  # not reached root of the FS tree
                self.setCurrentPath( self._filteredModelIndexToPath(self._tree.rootIndex().parent()))
        
        parentOfCurrent = self._tree.currentIndex().parent()
        if parentOfCurrent != self._tree.rootIndex():  # if not reached top
            self._tree.setCurrentIndex(parentOfCurrent)  # move selection up
    
    def aAdd_triggered(self):
        """Add bookmark action triggered
        """
        path = self.currentPath()
        if not os.path.isdir(path):
            path = os.path.dirname(path)
        
        if  path and not path in self._bookmarks:
            self._bookmarks.append(path)
            self.updateBookMarksMenu()

    def aRemove_triggered(self):
        """Remove bookmark triggered
        """
        path = self.currentPath()
        if not os.path.isdir(path):
            path = os.path.dirname(path)
        
        if  path in self._bookmarks:
            self._bookmarks.remove( path )
            self.updateBookMarksMenu()

    def bookmark_triggered(self, action ):
        """Bookmark triggered, go to marked folder
        """
        self.setCurrentPath( action.data().toString() )

    def tv_activated(self, idx ):
        """File or dirrectory doubleClicked
        """
        index = self._filteredModel.mapToSource( idx )
        
        if  self._dirsModel.isDir( index ) :
            self.setCurrentPath( unicode(self._dirsModel.filePath( index )) )
        else:
            core.workspace().openFile( unicode(self._dirsModel.filePath( index )))

    def currentPath(self):
        """Get current path (root of the tree)
        """
        index = self._tree.rootIndex()
        index = self._filteredModel.mapToSource( index )
        return unicode(self._dirsModel.filePath( index ))

    def _setFocusToTree(self, attempts = 5):
        """Moves focus and selection to the first item, if nothing focused
        If attempts > 0 and model not yet loaded data, function will call semself 
        automatically later after 10ms for do next attempt to set focus to the first child
        """
        rootIndex = self._tree.rootIndex()
        
        selected =  self._tree.selectionModel().selectedIndexes()
        for index in selected:
            if index.parent() == rootIndex:   # Already having selected item
                return
        
        firstChild = self._filteredModel.index(0, 0, rootIndex)
        if firstChild.isValid():  # There may be no rows, if directory is empty, or not loaded yet
            self._tree.selectionModel().select(firstChild, QItemSelectionModel.SelectCurrent)

    def setCurrentPath(self, path):
        """Set current path (root of the tree)
        """
        # get index
        index = self._dirsModel.index(path)
        
        # set current path
        self._filteredModel.invalidate()
        self._tree.setRootIndex( self._filteredModel.mapFromSource( index ) )
        
        self._setFocusToTree(15)
        
        # set lineedit path
        text = unicode(self._dirsModel.filePath( index ))
        self._comboBox.lineEdit().setText(text)
        self._comboBox.setToolTip( text )

    def currentFilePath(self):
        """Get current file path (selected item)
        """
        index = self._tree.selectionModel().selectedIndexes().value( 0 )
        index = self._filteredModel.mapToSource( index )
        return unicode(self._dirsModel.filePath( index ))

    def setCurrentFilePath(self, filePath):
        """Set current file path (selected item)
        """
        # get index
        index = self._dirsModel.index(filePath)
        index = self._filteredModel.mapFromSource( index )
        self._tree.setCurrentIndex( index )

    def setFilters(self, filters ):
        """Set filter wildcards for filter out unneeded files
        """
        self._filteredModel.setFilters( filters )

    def updateBookMarksMenu(self):
        """Create new Bookmarks menu
        """
        self._bookmarksMenu.clear()
        
        for path in self._bookmarks:
            action = self._bookmarksMenu.addAction(path)
            action.setToolTip( path )
            action.setStatusTip( path )
            action.setData( path )
