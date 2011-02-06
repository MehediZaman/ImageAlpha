#
#  IAImage.py
#  ImageAlpha
#
#  Created by porneL on 30.listopada.08.
#  Copyright (c) 2008 Lyncroft. All rights reserved.
#
from objc import *
from Foundation import *
from AppKit import *

class IAImage(NSObject):
    _image = None
    _imageData = None

    path = None
    _sourceFileSize = None

    versions = None

    numberOfColors = 256;
    transparencyDepth = 8;
    transparencyAdjust = 0;

    quantizationMethod = 1; # 1 = pngnq; 2 = pngquant nofs
    dithering = NO

    callbackWhenImageChanges = None

    def init(self):
        self = super(IAImage, self).init()
        self.versions = {};
        return self

    def setCallbackWhenImageChanges_(self, documentToCallback):
        self.callbackWhenImageChanges = documentToCallback;
        self.update()

    def setImage_(self,image):
        self._image = image

    def image(self):
        return self._image

    def imageData(self):
        return self._imageData;

    def sourceFileSize(self):
		return self._sourceFileSize;

    def setPath_(self,path):
		self.path = path
		(attrs,error) = NSFileManager.defaultManager().attributesOfItemAtPath_error_(self.path,None);
		self._sourceFileSize = attrs.objectForKey_(NSFileSize) if attrs is not None and error is None else None;


    def setDithering_(self,val):
        self.dithering = int(val) > 0
        self.update()

    def setNumberOfColors_(self,num):
        self.numberOfColors = num
        self.update();

    def setQuantizationMethod_(self,num):
        self.quantizationMethod = num
        self.update()

    def isBusy(self):
        if self.path is None: return False
        id = self.currentVersionId()
        if id not in self.versions: return False # not sure about this
        return not self.versions[id].isDone;

    def update(self):
        if self.path:
            id = self.currentVersionId()

            if self.numberOfColors > 256:
                self._imageData = NSData.dataWithContentsOfFile_(self.path);
                self.setImage_(NSImage.alloc().initByReferencingFile_(self.path));

                if self.callbackWhenImageChanges is not None: self.callbackWhenImageChanges.imageChanged();

            elif id not in self.versions:
                self.versions[id] = IAImageVersion.alloc().init()
                self.versions[id].generateFromPath_method_dither_colors_callback_(self.path, self.quantizationMethod, self.dithering, self.numberOfColors, self)

                if self.callbackWhenImageChanges is not None: self.callbackWhenImageChanges.updateProgressbar();

            elif self.versions[id].isDone:
                self._imageData = self.versions[id].imageData
                self.setImage_(NSImage.alloc().initWithData_(self._imageData))

                if self.callbackWhenImageChanges is not None: self.callbackWhenImageChanges.imageChanged();

    def currentVersionId(self):
        return "c%d:t%d:m%d:d%d" % (self.numberOfColors, self.transparencyDepth, self.quantizationMethod, self.dithering);

    def destroy(self):
        self.callbackWhenImageChanges = None
        for id in self.versions:
            self.versions[id].destroy()
        self.versions = {}


class IAImageVersion(NSObject):
    imageData = None
    isDone = False

    task = None
    outputPipe = None
    callbackWhenFinished = None

    def generateFromPath_method_dither_colors_callback_(self,path,method,dither,colors,callbackWhenFinished):

        self.isDone = False
        self.callbackWhenFinished = callbackWhenFinished

        if method == 1:
            self.task = self.launchTask_withArguments_stdin_library_(NSBundle.mainBundle().pathForResource_ofType_("pngnq", ""), ["-Q","f" if dither else "n","-n","%d" % colors], path, True);
        else:
            self.task = self.launchTask_withArguments_stdin_library_(NSBundle.mainBundle().pathForResource_ofType_("pngquant", ""),["-fs" if dither else "-nofs","%d" % colors],path,False);


    def launchTask_withArguments_stdin_library_(self,launchPath,args,path,useLib):
        task = NSTask.alloc().init()

        task.setLaunchPath_(launchPath)
        task.setCurrentDirectoryPath_(NSBundle.mainBundle().resourcePath())
        task.setArguments_(args);

        if useLib:
            environment = NSProcessInfo.processInfo().environment();

            libpath = NSBundle.mainBundle().pathForResource_ofType_("liblibpng","dylib");
            if libpath:
                libpath = libpath.stringByDeletingLastPathComponent();
                environment.setObject_forKey_(libpath, "DYLD_FALLBACK_LIBRARY_PATH");
                task.setEnvironment_(environment);

        # pngout works best via standard input/output
        file = NSFileHandle.fileHandleForReadingAtPath_(path);
        task.setStandardInput_(file);

        # get output via pipe
        # use pipe's file handle to construct NSData object asynchronously
        outputPipe = NSPipe.pipe();
        task.setStandardOutput_(outputPipe);

        # pipe *must* be read, otheriwse task will block waiting for I/O
        handle = outputPipe.fileHandleForReading();
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(self, self.onHandleReadToEndOfFile_, NSFileHandleReadToEndOfFileCompletionNotification, handle);
        handle.readToEndOfFileInBackgroundAndNotify()

        task.launch();
        return task;

    def onHandleReadToEndOfFile_(self,notification):
        self.isDone = True

        data = notification.userInfo().objectForKey_(NSFileHandleNotificationDataItem);
        if data is not None:
            if self.callbackWhenFinished is not None:
                self.imageData = data
                self.callbackWhenFinished.update()

    # FIXME: use dealloc and super()?
    def destroy(self):
        NSNotificationCenter.defaultCenter().removeObserver_(self);
        self.callbackWhenFinished = None
        if self.task:
            self.task.terminate();
            self.task = None
        if self.outputPipe:
            self.outputPipe.fileHandleForReading().closeFile()
            self.outputPipe = None


