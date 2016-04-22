#!/usr/bin/env python
#
# LSST Data Management System
# Copyright 2016 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <https://www.lsstcorp.org/LegalNotices/>.
#
from __future__ import print_function

import os
import shutil
import tempfile
import unittest
import warnings

import lsst.afw.image as afwImage
import lsst.pex.exceptions as pexExcept
from lsst.pipe.tasks.processCcd import ProcessCcdTask
from lsst.utils import getPackageDir
import lsst.utils.tests as utilsTests

OutputName = None  # Specify a name (as a string) to save the output repository

class ProcessCcdTestCase(utilsTests.TestCase):
    """Tests to run processCcd or tests with processed data"""
    def setUp(self):
        try:
            self.datadir = getPackageDir("testdata_decam")
        except pexExcept.NotFoundError:
            message = "testdata_decam not setup. Skipping."
            warnings.warn(message)
            raise unittest.SkipTest(message)

        self.outPath = tempfile.mkdtemp() if OutputName is None else OutputName
        self.dataId = {'visit': 229388, 'ccdnum': 1}
        configPath = os.path.join(getPackageDir("obs_decam"), "config")
        argsList = [os.path.join(self.datadir, "rawData"), "--output", self.outPath, "--id"]
        argsList += ["%s=%s" % (key, val) for key, val in self.dataId.iteritems()]
        argsList += ["--config", "calibrate.doPhotoCal=False", "calibrate.doAstrometry=False",
                     # Temporary until DM-4232 is fixed.
                     "isr.assembleCcd.setGain=False",
                     # This test uses CP-MasterCal calibration products
                     "-C", "%s/processCcdCpIsr.py" % configPath]
        fullResult = ProcessCcdTask.parseAndRun(args=argsList, doReturnResults=True)
        self.butler = fullResult.parsedCmd.butler
        self.config = fullResult.parsedCmd.config

    def tearDown(self):
        del self.butler
        if OutputName is None:
            shutil.rmtree(self.outPath)
        else:
            print("testProcessCcd.py's output data saved to %r" % (OutputName,))

    def testProcessRaw(self):
        """Sanity check of running processCcd with raw data"""
        exp = self.butler.get("calexp", self.dataId, immediate=True)
        self.assertIsInstance(exp, afwImage.ExposureF)
        self.assertEqual(exp.getWidth(), 2048)
        self.assertEqual(exp.getHeight(), 4096)

    def testCcdKey(self):
        """Test to retrieve calexp using ccd as the ccd key"""
        exp = self.butler.get("calexp", visit=229388, ccd=1, immediate=True)
        self.assertIsInstance(exp, afwImage.ExposureF)

    def testWcsPostIsr(self):
        """Test the wcs of postISRCCD products

        The postISRCCD wcs should be the same as the raw wcs with the
        adjustment of overscan/prescan trimming. Test DM-4859.
        """
        if not self.config.isr.doWrite or not self.config.isr.assembleCcd.doTrim:
            return
        expRaw = self.butler.get("raw", self.dataId, immediate=True)
        expPost = self.butler.get("postISRCCD", self.dataId, immediate=True)
        self.assertIsInstance(expPost, afwImage.ExposureF)
        wcsRaw = expRaw.getWcs()
        wcsPost = expPost.getWcs()
        # Shift WCS for trimming the prescan and overscan region
        # ccdnum 1 is S29, with overscan in the bottom
        wcsRaw.shiftReferencePixel(-56, -50)
        self.assertWcsNearlyEqualOverBBox(wcsRaw, wcsPost, expPost.getBBox())


#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite():
    """Returns a suite containing all the test cases in this module."""

    utilsTests.init()

    suites = []
    suites += unittest.makeSuite(ProcessCcdTestCase)
    suites += unittest.makeSuite(utilsTests.MemoryTestCase)
    return unittest.TestSuite(suites)

def run(shouldExit=False):
    """Run the tests"""
    utilsTests.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
