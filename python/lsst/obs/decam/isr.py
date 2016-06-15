#
# LSST Data Management System
# Copyright 2012-2015 LSST Corporation.
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

import lsst.afw.geom as afwGeom
import lsst.afw.table as afwTable
import lsst.pex.config as pexConfig
from lsst.ip.isr import IsrTask, overscanCorrection
from lsst.meas.algorithms.detection import SourceDetectionTask


class DecamIsrConfig(IsrTask.ConfigClass):
    overscanBiasJumpBKP = pexConfig.ListField(
        dtype = str,
        doc = "Names of the backplanes for CCDs showing bias jump due to " +
              "the simultaneous readout of the smaller ancillary CCDs.",
        default = ['DECAM_BKP3', 'DECAM_BKP5', 'DECAM_BKP1', 'DECAM_BKP4'],
    )
    overscanBiasJumpLocation = pexConfig.Field(
        dtype = int,
        doc = "The y distance of the bias jump location measured in units " +
              "of pixels from the readout corner; this should be the y " +
              "dimension of the smaller ancillary CCDs.",
        default = 2098,
    )
    numEdgeSuspect = pexConfig.Field(
        dtype = int,
        doc = "Number of edge pixels to be flagged as untrustworthy.",
        default = 35,
    )


class DecamIsrTask(IsrTask):
    ConfigClass = DecamIsrConfig

    def convertIntToFloat(self, exp):
        """No conversion necessary."""
        return exp

    def maskAndInterpDefect(self, ccdExposure, defectBaseList):
        """Mask defects and edges, interpolate over defects in place

        Mask defect pixels using mask plane BAD and interpolate over them.
        Mask the potentially problematic glowing edges as SUSPECT.

        @param[in,out] ccdExposure: exposure to process
        @param[in] defectBaseList: a list of defects to mask and interpolate
        """
        IsrTask.maskAndInterpDefect(self, ccdExposure, defectBaseList)
        maskedImage = ccdExposure.getMaskedImage()
        goodBBox = maskedImage.getBBox()
        # This makes a bbox numEdgeSuspect pixels smaller than the image on each side
        goodBBox.grow(-self.config.numEdgeSuspect)
        # Mask pixels outside goodBBox as SUSPECT
        SourceDetectionTask.setEdgeBits(
            maskedImage,
            goodBBox,
            maskedImage.getMask().getPlaneBitMask("SUSPECT")
        )

    def overscanCorrection(self, exposure, amp):
        """Apply overscan correction in place

        If the input exposure is on the readout backplanes listed in
        config.overscanBiasJumpBKP, cut the amplifier in two vertically
        and correct each piece separately.

        @param[in,out] exposure: exposure to process; must include both
                                 DataSec and BiasSec pixels
        @param[in] amp: amplifier device data
        """
        if not (exposure.getMetadata().exists('FPA') and
                exposure.getMetadata().get('FPA') in self.config.overscanBiasJumpBKP):
            IsrTask.overscanCorrection(self, exposure, amp)
            return

        dataBox = amp.getRawDataBBox()
        overscanBox = amp.getRawHorizontalOverscanBBox()

        if amp.getReadoutCorner() in (afwTable.LL, afwTable.LR):
            yLower = self.config.overscanBiasJumpLocation
            yUpper = dataBox.getHeight() - yLower
        else:
            yUpper = self.config.overscanBiasJumpLocation
            yLower = dataBox.getHeight() - yUpper

        lowerDataBBox = afwGeom.Box2I(dataBox.getBegin(),
                                      afwGeom.Extent2I(dataBox.getWidth(), yLower))
        upperDataBBox = afwGeom.Box2I(dataBox.getBegin() + afwGeom.Extent2I(0, yLower),
                                      afwGeom.Extent2I(dataBox.getWidth(), yUpper))
        lowerOverscanBBox = afwGeom.Box2I(overscanBox.getBegin(),
                                          afwGeom.Extent2I(overscanBox.getWidth(), yLower))
        upperOverscanBBox = afwGeom.Box2I(overscanBox.getBegin() + afwGeom.Extent2I(0, yLower),
                                          afwGeom.Extent2I(overscanBox.getWidth(), yUpper))

        maskedImage = exposure.getMaskedImage()
        lowerDataView = maskedImage.Factory(maskedImage, lowerDataBBox)
        upperDataView = maskedImage.Factory(maskedImage, upperDataBBox)

        expImage = exposure.getMaskedImage().getImage()
        lowerOverscanImage = expImage.Factory(expImage, lowerOverscanBBox)
        upperOverscanImage = expImage.Factory(expImage, upperOverscanBBox)

        overscanCorrection(
            ampMaskedImage = lowerDataView,
            overscanImage = lowerOverscanImage,
            fitType = self.config.overscanFitType,
            order = self.config.overscanOrder,
            collapseRej = self.config.overscanRej,
        )
        overscanCorrection(
            ampMaskedImage = upperDataView,
            overscanImage = upperOverscanImage,
            fitType = self.config.overscanFitType,
            order = self.config.overscanOrder,
            collapseRej = self.config.overscanRej,
        )
