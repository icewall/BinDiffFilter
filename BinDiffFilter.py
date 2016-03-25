from PySide import QtGui, QtCore
import idc  
import pickle

class AbstractFilter(object):
    class_counter = 0
    def __init__(self,name = ""):
        print "AbstractFilter __init__ : {0}".format(AbstractFilter.class_counter)
        self.__name = name
        if self.__name == "":
            self.__name = str(AbstractFilter.class_counter)
        AbstractFilter.class_counter += 1
        pass
    
    def filter(self,row):
        raise NotImplementedError()

    def getName(self):
        return self.__name

"""
    Sample filter
"""
class MatchedFunctions(AbstractFilter):

    def filter(self,row):
        print "filter test"


class CustomSortFilterProxyModel(QtGui.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super(CustomSortFilterProxyModel, self).__init__(parent)
        self.__lambdasToPickle = {}
        self.__filterFunctions = {} 
        self.__hiddenFunctions = set()
        self.__filtersCounter = 0
        self.__colorRow = {} # list of {"color" : Qt.magenta,"func": set()}
        self.__colorRow["intSafeFunctions"] = {
                                               "color"     : QtCore.Qt.magenta,
                                               "indexes" : set()
                                               }
        
        self.__buildinFilters = {
                                 "hideFunction": self.__filterHideFunction ,
                                 "matched"     : self.__filterHideMatchedFunctions
                                }

    def addFilterFunction(self, func, name = ""):
        """
             ex:
            model.addFilterFunction(
                lambda row: int(row["primary instructions"] > 3),
                "more_than_3"
                )
        """
        if name == "":
            name = str(self.__filtersCounter)
        #detect whether it's lambda function cos we need to handle it in different way
        #lambda functions should be passed as strings cos in that way they can be pickled
        if isinstance(func,str):
            self.__lambdasToPickle[name] = func
            func = eval(func)
                     
        self.__filterFunctions[name] = func
        self.invalidateFilter()
        self.__filtersCounter += 1
 
    def removeFilterFunction(self, name):
        """
        name : hashable object        
        Removes the filter function associated with name,
        if it exists.
        """
        if name in self.__filterFunctions.keys():
            del self.__filterFunctions[name]
            if name in self.__lambdasToPickle.keys():
                del self.__lambdasToPickle[name]
            self.invalidateFilter()
            

    def __filterExists(self,name):
        return name in self.__filterFunctions.keys()
 
    def filterAcceptsRow(self, row_num, parent): 
        try:                               
            functions = self.__filterFunctions.values()
            if functions == []:
                return True

            model = self.sourceModel()
            row = self.__getRow(model,row_num)
            #simple lambda filters
            flags = [func(row) for func in functions]
            return not False in flags

        except Exception as e:
            print e.message
            return True
   
    def data(self,index,role = QtCore.Qt.DisplayRole):
        try:
            if role == QtCore.Qt.BackgroundColorRole and index.isValid():
                for item in self.__colorRow.values():
                    if index.row() in item["indexes"]:
                        #return item["color"]
                        return QtGui.QBrush(QtCore.Qt.yellow)
        except:
            pass

        return super(QtGui.QSortFilterProxyModel,self).data(index,role)

    """
        Built-in filters
    """
    def __filterHideFunction(self,row):
        try:
            ea_primary = row["EA primary"]
        except:
            return True
        return ea_primary not in self.__hiddenFunctions
    
    def __filterHideMatchedFunctions(self,row):
        try:
            return float(row["similarity"]) < 1.0
        except:
            return True
        
    """
        Public methods
    """
    def hideFunction(self,ea_primary,refresh = True):
        if not self.__filterExists("hideFunction"):
            self.addFilterFunction(self.__filterHideFunction,"hideFunction")
        self.__hiddenFunctions.add(ea_primary)
        if refresh:
            self.invalidateFilter()
    
    def showFunction(self,ea_primary):
        if ea_primary in self.__hiddenFunctions:
            self.__hiddenFunctions.remove(ea_primary)
            self.invalidateFilter()
        else:
            "Function : {0} is not hidden".format(ea_primary)

    def hideMatchedFunctions(self):
        self.addFilterFunction(self.__filterHideMatchedFunctions,"matched")
    
    def showMatchedFunctions(self):
        self.removeFilterFunction("matched")    

    """
        Helpers
    """
    def __getColumnIdByName(self,name):
        model = self.sourceModel()
        for i in range(0,model.columnCount()):
            if model.headerData(i,QtCore.Qt.Horizontal) == name:
                return i
        return -1            

    def __getRow(self,model,index):
        row = {}
        for colIndex in range(0,model.columnCount()):
            #need column name + data
            name = model.headerData(colIndex,QtCore.Qt.Horizontal)
            data = model.data( model.index(index,colIndex) )
            row[name] = data
        return row               

    """
        Getters & Setters [necessary during pickling]
    """
    def getFilterFunctions(self):
        return self.__filterFunctions

    def setFilterFunctions(self,ff):
        self.__filterFunctions = ff
    
    def getHiddenFunctions(self):
        return self.__hiddenFunctions                 

    def setHiddenFunctions(self,hf):
        self.__hiddenFunctions = hf

    def addInfSafeRowIndex(self,index):
        self.__colorRow["intSafeFunctions"]["indexes"].add(index)
    
    def getLambdaFilters(self):
        return self.__lambdasToPickle

    def getColoredRows(self):
        return self.__colorRow

class CBinDiffFilter(object):
    def __init__(self):
        self.__columns = {}
        self.__hiddenColumns = set()
        self.__uselessStandardColumns = [
                                        "confidence",
                                        "change",
                                        "comments ported",
                                        "algorithm",
                                        "matched basicblocks",
                                        "basicblocks primary",
                                        "basicblocks secondary",
                                        "matched edges",
                                        "edges primary",
                                        "edges secondary"
                                        ]        
    
    def findBinDiffWindow(self):
        try:
            #collect necessary info
            self.window = self.findWindow("Matched Functions")
            self.table = self.findTableView()
            self.orig_model = self.table.model()

            #setup our new proxy model
            self.proxy_model = CustomSortFilterProxyModel()
            self.proxy_model.setSourceModel(self.orig_model)            
            self.proxy_model.setDynamicSortFilter(True)

            #inject our new proxy model into the tableview
            self.table.setModel(self.proxy_model)
            
            self.__initColumnNamesWithId()
            return True
        
        except Exception as e:
            print e.message
            return False


    def findWindow(self, windowName):
        """
        Locate the IDA window we are looking for
        """
        ins = QtCore.QCoreApplication.instance()
        widgets = ins.allWidgets()
        for x in widgets:
            if x.objectName() == windowName:
                return x
        raise Exception('Could not locate window, make sure that it is open.')

    def findTableView(self):
        """
        Locate the TableView inside the window
        """
        for x in self.window.children()[-1].children(): #last QWidget seems to hold all the children
            if type(x) == QtGui.QTableView:
                return x
        raise Exception('Could not locate QTableView of the window.')

    def findWindowLayout(self):
        """
        Locate the the QVBoxLayout of the window
        """
        for x in self.window.children(): #should always be [1] but we will search for it anyways
            if type(x) == QtGui.QVBoxLayout:
                return x
        raise Exception('Could not locate QVBoxLayout of the window.')
    
    def menuHandler(self,pos):
        menu = QtGui.QMenu()
        messageAction = menu.addAction("About")
        print repr(pos)
        action = menu.exec_(self.table.mapToGlobal(pos))
        print "after menu.exec"
        print repr(action)
        print repr(messageAction)
        if action == messageAction:
            print "Message action clicked"

    def saveFilters(self,filePath):
        """
        TODO: maybe refactor this code to do it more general and automatic ????
        """
        #hiddenFunctions
        filterFunctions = self.proxy_model.getFilterFunctions()
        hiddenFunctionsStatus = filterFunctions.has_key("hiddenFunctions")
        hiddenFunctions = self.proxy_model.getHiddenFunctions()
        #lambdas
        lambdaFilters = self.proxy_model.getLambdaFilters()

        filterObjects = {}               
        if hiddenFunctionsStatus:
            filterObjects["hiddenFunctions"] = {}
            filterObjects["hiddenFunctions"]["functions"] = hiddenFunctions            
        
        if len(lambdaFilters):
            filterObjects["lambdaFilters"] = {}
            filterObjects["lambdaFilters"] = lambdaFilters
        
        if filterFunctions.has_key("matched"):
            filterObjects["matched"] = {} #just to have that info 
        
        filterObjects["coloredRows"] = self.proxy_model.getColoredRows()

        pickle.dump(filtersObjects,open(filePath,'wb'))
    
    def loadFilters(self,filePath):
        filtersObjects = pickle.load(open(filePath,'rb'))
        self.proxy_model.setFilterFunctions(filtersObjects[0])
        self.proxy_model.setHiddenFunctions(filtersObjects[1])
        self.proxy_model.invalidateFilter()
    
    def hideSomeStandardColumns(self):
        for column in self.__uselessStandardColumns:
            self.table.hideColumn( self.__columns[column] )
                                
    def showSomeStandardColumns(self):
        for column in self.__uselessStandardColumns:
            self.table.showColumn( self.__columns[column] )
    
    def hideColumn(self,name):
        self.table.hideColumn( self.__columns[name] )

    def showColumn(self,name):
        self.table.showColumn( self.__columns[name] )

    def addIntSafeFunction(self,ea):
        index = self.__getIndexFromValue(ea,"EA primary")
        self.proxy_model.addInfSafeRowIndex(index)
                
    """
        Helpers
    """
    def __initColumnNamesWithId(self):
        for colIndex in range(0,self.orig_model.columnCount()):
            name = self.orig_model.headerData(colIndex,QtCore.Qt.Horizontal)
            self.__columns[name] = colIndex
    
    def __getIndexFromValue(self,value,columnName):
        colIndex = self.__columns[columnName]
        for rowIndex in range(0,self.proxy_model.rowCount()):
            index = self.proxy_model.index(rowIndex,colIndex)
            if self.proxy_model.data( index ) == value:
                return rowIndex

#BinDiffFilter = CBinDiffFilter()
print "[+]BinDiffFilter plugin loaded"