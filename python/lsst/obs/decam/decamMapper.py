#
# LSST Data Management System
# Copyright 2012-2016 LSST Corporation.
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
import re
import numpy as np
from lsst.utils import getPackageDir
import lsst.afw.image as afwImage
import lsst.afw.image.utils as afwImageUtils
from lsst.daf.butlerUtils import CameraMapper, exposureFromImage
from lsst.daf.persistence import ButlerLocation
from lsst.ip.isr import isr
import lsst.pex.policy as pexPolicy

np.seterr(divide="ignore")

class DecamMapper(CameraMapper):
    packageName = 'obs_decam'

    detectorNames = {1:'S29', 2:'S30', 3:'S31', 4:'S25', 5:'S26', 6:'S27', 7:'S28', 8:'S20', 9:'S21',
                      10:'S22', 11:'S23', 12:'S24', 13:'S14', 14:'S15', 15:'S16', 16:'S17', 17:'S18',
                      18:'S19', 19:'S8', 20:'S9', 21:'S10', 22:'S11', 23:'S12', 24:'S13', 25:'S1', 26:'S2',
                      27:'S3', 28:'S4', 29:'S5', 30:'S6', 31:'S7', 32:'N1', 33:'N2', 34:'N3', 35:'N4',
                      36:'N5', 37:'N6', 38:'N7', 39:'N8', 40:'N9', 41:'N10', 42:'N11', 43:'N12', 44:'N13',
                      45:'N14', 46:'N15', 47:'N16', 48:'N17', 49:'N18', 50:'N19', 51:'N20', 52:'N21',
                      53:'N22', 54:'N23', 55:'N24', 56:'N25', 57:'N26', 58:'N27', 59:'N28', 60:'N29',
                      62:'N31'}


    def __init__(self, inputPolicy=None, **kwargs):
        policyFile = pexPolicy.DefaultPolicyFile(self.packageName, "DecamMapper.paf", "policy")
        policy = pexPolicy.Policy(policyFile)

        super(DecamMapper, self).__init__(policy, policyFile.getRepositoryPath(), **kwargs)

        afwImageUtils.defineFilter('u', lambdaEff=350, alias=['u DECam c0006 3500.0 1000.0'])
        afwImageUtils.defineFilter('g', lambdaEff=450, alias=['g DECam SDSS c0001 4720.0 1520.0'])
        afwImageUtils.defineFilter('r', lambdaEff=600, alias=['r DECam SDSS c0002 6415.0 1480.0'])
        afwImageUtils.defineFilter('i', lambdaEff=750, alias=['i DECam SDSS c0003 7835.0 1470.0'])
        afwImageUtils.defineFilter('z', lambdaEff=900, alias=['z DECam SDSS c0004 9260.0 1520.0'])
        afwImageUtils.defineFilter('y', lambdaEff=1000, alias=['Y DECam c0005 10095.0 1130.0'])

        # The data ID key ccdnum is not directly used in the current policy
        # template of the raw dataset, so is not in its keyDict automatically.
        # Add it so raw dataset know about the data ID key ccdnum.
        self.mappings["raw"].keyDict.update({'ccdnum': int})

        # The number of bits allocated for fields in object IDs
        # TODO: This needs to be updated; also see Trac #2797
        DecamMapper._nbit_tract = 10
        DecamMapper._nbit_patch = 10
        DecamMapper._nbit_filter = 4
        DecamMapper._nbit_id = 64 - (DecamMapper._nbit_tract +
                                     2*DecamMapper._nbit_patch +
                                     DecamMapper._nbit_filter)

    def _extractDetectorName(self, dataId):
        try:
            return DecamMapper.detectorNames[dataId['ccdnum']]
        except KeyError:
            raise RuntimeError("No name found for dataId: %s"%(dataId))

    def bypass_ccdExposureId(self, datasetType, pythonType, location, dataId):
        return self._computeCcdExposureId(dataId)
    def bypass_ccdExposureId_bits(self, datasetType, pythonType, location, dataId):
        return 32 # not really, but this leaves plenty of space for sources
    def _computeCcdExposureId(self, dataId):
        """Compute the 64-bit (long) identifier for a CCD exposure.

        @param dataId (dict) Data identifier with visit, ccd
        """
        visit = dataId['visit']
        ccdnum = dataId['ccdnum']
        return int("%07d%02d" % (visit, ccdnum))

    def _computeCoaddExposureId(self, dataId, singleFilter):
        """Compute the 64-bit (long) identifier for a coadd.

        @param dataId (dict)       Data identifier with tract and patch.
        @param singleFilter (bool) True means the desired ID is for a single-
                                   filter coadd, in which case dataId
                                   must contain filter.
        """
        tract = long(dataId['tract'])
        if tract < 0 or tract >= 2**DecamMapper._nbit_tract:
            raise RuntimeError('tract not in range [0,%d)' % (2**DecamMapper._nbit_tract))
        patchX, patchY = map(int, dataId['patch'].split(','))
        for p in (patchX, patchY):
            if p < 0 or p >= 2**DecamMapper._nbit_patch:
                raise RuntimeError('patch component not in range [0, %d)' % 2**DecamMapper._nbit_patch)
        oid = (((tract << DecamMapper._nbit_patch) + patchX) << DecamMapper._nbit_patch) + patchY
        if singleFilter:
            return (oid << DecamMapper._nbit_filter) + afwImage.Filter(dataId['filter']).getId()
        return oid

    def bypass_deepCoaddId(self, datasetType, pythonType, location, dataId):
        return self._computeCoaddExposureId(dataId, True)

    def bypass_deepCoaddId_bits(self, *args, **kwargs):
        return 64 - DecamMapper._nbit_id

    def bypass_deepMergedCoaddId(self, datasetType, pythonType, location, dataId):
        return self._computeCoaddExposureId(dataId, False)

    def bypass_deepMergedCoaddId_bits(self, *args, **kwargs):
        return 64 - DecamMapper._nbit_id

    def translate_dqmask(self, dqmask):
        # TODO: make a class member variable that knows the mappings
        # below instead of hard-coding them
        dqmArr    = dqmask.getArray()
        mask      = afwImage.MaskU(dqmask.getDimensions())
        mArr      = mask.getArray()
        idxBad    = np.where(dqmArr & 1)
        idxSat    = np.where(dqmArr & 2)
        idxIntrp  = np.where(dqmArr & 4)
        idxCr     = np.where(dqmArr & 16)
        idxBleed  = np.where(dqmArr & 64)
        idxEdge   = np.where(dqmArr & 512)
        mArr[idxBad]   |= mask.getPlaneBitMask("BAD")
        mArr[idxSat]   |= mask.getPlaneBitMask("SAT")
        mArr[idxIntrp] |= mask.getPlaneBitMask("INTRP")
        mArr[idxCr]    |= mask.getPlaneBitMask("CR")
        mArr[idxBleed] |= mask.getPlaneBitMask("SAT")
        mArr[idxEdge] |= mask.getPlaneBitMask("EDGE")
        return mask

    def translate_wtmap(self, wtmap):
        wtmArr = wtmap.getArray()
        idxUndefWeight = np.where(wtmArr <= 0)
        #Reassign weights to be finite but small:
        wtmArr[idxUndefWeight] = min(1e-14, np.min(wtmArr[np.where(wtmArr>0)]))
        var   = 1.0 / wtmArr
        varim = afwImage.ImageF(var)
        return varim
        
    def bypass_instcal(self, datasetType, pythonType, butlerLocation, dataId):
        # Workaround until I can access the butler
        instcalMap  = self.map_instcal(dataId)
        dqmaskMap   = self.map_dqmask(dataId)
        wtmapMap    = self.map_wtmap(dataId)
        instcalType = getattr(afwImage, instcalMap.getPythonType().split(".")[-1])
        dqmaskType  = getattr(afwImage, dqmaskMap.getPythonType().split(".")[-1])
        wtmapType   = getattr(afwImage, wtmapMap.getPythonType().split(".")[-1])
        instcal     = instcalType(instcalMap.getLocations()[0])
        dqmask      = dqmaskType(dqmaskMap.getLocations()[0])
        wtmap       = wtmapType(wtmapMap.getLocations()[0])

        mask        = self.translate_dqmask(dqmask)
        variance    = self.translate_wtmap(wtmap)

        mi          = afwImage.MaskedImageF(afwImage.ImageF(instcal.getImage()), mask, variance)
        md          = instcal.getMetadata()
        wcs         = afwImage.makeWcs(md)
        exp         = afwImage.ExposureF(mi, wcs)

        # Set the calib by hand; need to grab the zeroth extension
        header = re.sub(r'[\[](\d+)[\]]$', "[0]", instcalMap.getLocations()[0])
        md0 = afwImage.readMetadata(header)
        calib = afwImage.Calib()
        calib.setExptime(md0.get("EXPTIME"))
        calib.setFluxMag0(10**(0.4 * md0.get("MAGZERO")))
        exp.setCalib(calib)
        
        exp.setMetadata(md) # Do we need to remove WCS/calib info?
        return exp

    def std_raw(self, item, dataId):
        """Standardize a raw dataset by converting it to an Exposure.

        Raw images are MEF files with one HDU for each detector.
        Header keywords EXPTIME and MJD-OBS exist only in the zeroth
        extension and are copied to metadata.

        @param item: The image read by the butler
        @param dataId: Data identifier
        @return (lsst.afw.image.Exposure) the standardized Exposure
        """
        # Convert the raw DecoratedImage to an Exposure, set metadata and wcs.
        exp = exposureFromImage(item)
        md = exp.getMetadata()
        rawPath = self.map_raw(dataId).getLocations()[0]
        headerPath = re.sub(r'[\[](\d+)[\]]$', "[0]", rawPath)
        md0 = afwImage.readMetadata(headerPath)
        # Keywords EXPTIME and MJD-OBS are used to set the calib object.
        for kw in ('EXPTIME', 'MJD-OBS'):
            if kw in md0.paramNames() and kw not in md.paramNames():
                md.add(kw, md0.get(kw))
        # As TPV is not supported yet, the wcs keywords are not pruned
        # from the metadata. Once TPV is supported, the following keyword
        # removal may not be necessary here and would probably be done at
        # makeWcs() when the raw image is converted to an Exposure.
        for kw in exp.getWcs().getFitsMetadata().paramNames():
            md.remove(kw)
        for kw in ('LTV1', 'LTV2'):
            md.remove(kw)
        # Currently the existence of some PV cards in the metadata combined
        # with a CTYPE of TAN is interpreted as TPV (DM-2883).
        for kw in md.paramNames():
            if re.match(r'PV\d_\d', kw):
                md.remove(kw)
        # Standardize an Exposure, including setting the calib object
        return self._standardizeExposure(self.exposures['raw'], exp, dataId,
                                         trimmed=False)

    def _standardizeCpMasterCal(self, datasetType, item, dataId, setFilter=False):
        """Standardize a MasterCal image obtained from NOAO archive into Exposure

        These MasterCal images are MEF files with one HDU for each detector.
        Some WCS header, eg CTYPE1, exists only in the zeroth extensionr,
        so info in the zeroth header need to be copied over to metadata.

        @param datasetType: Dataset type ("bias" or "flat")
        @param item: The image read by the butler
        @param dataId: Data identifier
        @param setFilter: Whether to set the filter in the Exposure
        @return (lsst.afw.image.Exposure) the standardized Exposure
        """
        mi = afwImage.makeMaskedImage(item.getImage())
        md = item.getMetadata()
        masterCalMap = getattr(self, "map_" + datasetType)
        masterCalPath = masterCalMap(dataId).getLocations()[0]
        headerPath = re.sub(r'[\[](\d+)[\]]$', "[0]", masterCalPath)
        md0 = afwImage.readMetadata(headerPath)
        for kw in ('CTYPE1', 'CTYPE2', 'CRVAL1', 'CRVAL2', 'CUNIT1', 'CUNIT2',
                   'CD1_1', 'CD1_2', 'CD2_1', 'CD2_2'):
            if kw in md0.paramNames() and kw not in md.paramNames():
                md.add(kw, md0.get(kw))
        wcs = afwImage.makeWcs(md, True)
        exp = afwImage.makeExposure(mi, wcs)
        exp.setMetadata(md)
        return self._standardizeExposure(self.calibrations[datasetType], exp, dataId, filter=setFilter)

    def std_cpBias(self, item, dataId):
        return self._standardizeCpMasterCal("cpBias", item, dataId, setFilter=False)

    def std_cpFlat(self, item, dataId):
        return self._standardizeCpMasterCal("cpFlat", item, dataId, setFilter=True)

    def std_fringe(self, item, dataId):
        exp = afwImage.makeExposure(afwImage.makeMaskedImage(item))
        return self._standardizeExposure(self.calibrations["fringe"], exp, dataId)

    def map_defects(self, dataId, write=False):
        """Map defects dataset with the calibration registry.

        Overriding the method so to use CalibrationMapping policy,
        instead of looking up the path in defectRegistry as currently
        implemented in CameraMapper.

        @param dataId (dict) Dataset identifier
        @return daf.persistence.ButlerLocation
        """
        return self.mappings["defects"].map(self, dataId=dataId, write=write)

    def bypass_defects(self, datasetType, pythonType, butlerLocation, dataId):
        """Return a defect list based on butlerLocation returned by map_defects.

        Use all nonzero pixels in the Community Pipeline Bad Pixel Masks.

        @param[in] butlerLocation: Butler Location with path to defects FITS
        @param[in] dataId: data identifier
        @return meas.algorithms.DefectListT
        """
        bpmFitsPath = butlerLocation.locationList[0]
        bpmImg = afwImage.ImageU(bpmFitsPath)
        idxBad = np.nonzero(bpmImg.getArray())
        mim = afwImage.MaskedImageU(bpmImg.getDimensions())
        mim.getMask().getArray()[idxBad] |= mim.getMask().getPlaneBitMask("BAD")
        return isr.getDefectListFromMask(mim, "BAD", growFootprints=0)

    def std_defects(self, item, dataId):
        """Return the defect list as it is.

        Do not standardize it to Exposure.
        """
        return item

    @classmethod
    def getLinearizerDir(cls):
        """Directory containing linearizers"""
        packageName = cls.getPackageName()
        packageDir = getPackageDir(packageName)
        return os.path.join(packageDir, "decam", "linearizer")

    def map_linearizer(self, dataId, write=False):
        """Map a linearizer"""
        actualId = self._transformId(dataId)
        location = os.path.join(self.getLinearizerDir(), "%02d.fits" % (dataId["ccdnum"]),)
        return ButlerLocation(
            pythonType = "lsst.ip.isr.LinearizeSquared",
            cppType = "Config",
            storageName = "PickleStorage",
            locationList = [location],
            dataId = actualId,
            mapper = self,
        )
