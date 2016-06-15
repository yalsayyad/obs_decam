#!/usr/bin/env python
from __future__ import print_function
#
# LSST Data Management System
# Copyright 2012, 2015 LSST Corporation.
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import os

import warnings
import unittest
import lsst.afw.image as afwImage
import lsst.utils.tests as utilsTests
from lsst.utils import getPackageDir

import lsst.pex.exceptions as pexExcept
import lsst.daf.persistence as dafPersist


class GetRawTestCase(unittest.TestCase):
    """Testing butler raw image retrieval"""

    def setUp(self):
        try:
            datadir = getPackageDir("testdata_decam")
        except pexExcept.NotFoundError:
            message = "testdata_decam not setup. Skipping."
            warnings.warn(message)
            raise unittest.SkipTest(message)

        self.repoPath = os.path.join(datadir, "rawData")
        self.butler = dafPersist.Butler(root=self.repoPath)
        self.size = (2160, 4146)
        self.dataId = {'visit': 229388, 'ccdnum': 1}
        self.filter = "z"
        self.exptime = 200.0

    def tearDown(self):
        del self.butler

    def testPackageName(self):
        name = dafPersist.Butler.getMapperClass(root=self.repoPath).packageName
        self.assertEqual(name, "obs_decam")

    def testRaw(self):
        """Test retrieval of raw image"""
        exp = self.butler.get("raw", self.dataId)

        print("dataId: %s" % self.dataId)
        print("width: %s" % exp.getWidth())
        print("height: %s" % exp.getHeight())
        print("detector id: %s" % exp.getDetector().getId())

        self.assertEqual(exp.getWidth(), self.size[0])
        self.assertEqual(exp.getHeight(), self.size[1])
        self.assertEqual(exp.getDetector().getId(), self.dataId["ccdnum"])
        self.assertEqual(exp.getFilter().getFilterProperty().getName(), self.filter)
        self.assertTrue(exp.hasWcs())

        # Metadata which should have been copied from zeroth extension.
        self.assertIn("MJD-OBS", exp.getMetadata().paramNames())
        self.assertEqual(exp.getCalib().getExptime(), self.exptime)

        # Example of metadata which should *not* have been copied from zeroth extension.
        self.assertNotIn("PROPOSER", exp.getMetadata().paramNames())

    def testRawMetadata(self):
        """Test retrieval of metadata"""
        md = self.butler.get("raw_md", self.dataId)
        print("EXPNUM(visit): %s" % md.get('EXPNUM'))
        print("ccdnum: %s" % md.get('CCDNUM'))
        self.assertEqual(md.get('EXPNUM'), self.dataId["visit"])
        self.assertEqual(md.get('CCDNUM'), self.dataId["ccdnum"])

    def testBias(self):
        """Test retrieval of bias image"""
        exp = self.butler.get("cpBias", self.dataId)
        print("dataId: %s" % self.dataId)
        print("detector id: %s" % exp.getDetector().getId())
        self.assertEqual(exp.getDetector().getId(), self.dataId["ccdnum"])
        self.assertTrue(exp.hasWcs())

    def testFlat(self):
        """Test retrieval of flat image"""
        exp = self.butler.get("cpFlat", self.dataId)
        print("dataId: %s" % self.dataId)
        print("detector id: %s" % exp.getDetector().getId())
        print("filter: %s" % self.filter)
        self.assertEqual(exp.getDetector().getId(), self.dataId["ccdnum"])
        self.assertEqual(exp.getFilter().getFilterProperty().getName(), self.filter)
        self.assertTrue(exp.hasWcs())

    def testFringe(self):
        """Test retrieval of fringe image"""
        exp = self.butler.get("fringe", self.dataId)
        print("dataId: %s" % self.dataId)
        print("detector id: %s" % exp.getDetector().getId())
        print("filter: %s" % self.filter)
        self.assertEqual(exp.getDetector().getId(), self.dataId["ccdnum"])
        self.assertEqual(exp.getFilter().getFilterProperty().getName(), self.filter)

    def testDefect(self):
        """Test retrieval of defect list"""
        defectList = self.butler.get("defects", self.dataId)
        self.assertEqual(len(defectList), 9)
        for d in defectList:
            self.assertIsInstance(d, afwImage.DefectBase)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def suite():
    """Returns a suite containing all the test cases in this module."""

    utilsTests.init()

    suites = []
    suites += unittest.makeSuite(GetRawTestCase)
    suites += unittest.makeSuite(utilsTests.MemoryTestCase)
    return unittest.TestSuite(suites)

def run(shouldExit = False):
    """Run the tests"""
    utilsTests.run(suite(), shouldExit)

if __name__ == "__main__":
    run(True)
