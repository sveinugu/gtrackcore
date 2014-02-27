#!/usr/bin/env python

import os
import unittest

from subprocess import call

from gtrackcore.util.CommonFunctions import createOrigPath, get_dir_path, createPath

class TestWithGeSourceData(unittest.TestCase):
    def _removeDir(self, procDir, trackName):
        #print procDir, trackName
        self.assertTrue(procDir.endswith(os.sep + trackName[-1]))
        if os.path.exists(procDir):
            call('rm -R ' + procDir, shell=True)
            
    def _removeAllTrackData(self, trackName, removeOrigData=True):
        self._removeDir(get_dir_path(self.GENOME, trackName, allow_overlaps=False), trackName)
        self._removeDir(get_dir_path(self.GENOME, trackName, allow_overlaps=True), trackName)
        if removeOrigData:
            self._removeDir(createOrigPath(self.GENOME, trackName), trackName)
        
    def _commonSetup(self):
        from gtrackcore.test.input.core.TestGenomeElementSource import TestGenomeElementSource
        testGESource = TestGenomeElementSource()
        testGESource.setUp()
        origDir = createOrigPath(self.GENOME, self.TRACK_NAME_PREFIX)
        self._removeDir(origDir, self.TRACK_NAME_PREFIX)
        return testGESource
    
    def _writeTestFile(self, case):
        fn = createOrigPath(self.GENOME, self.TRACK_NAME_PREFIX + case.trackName, 'testfile' + case.suffix)
        createPath(fn)
        testfile = open(fn, 'w')
        testfile.write('\n'.join(case.headerLines + case.lines))
        testfile.close()
        return fn
