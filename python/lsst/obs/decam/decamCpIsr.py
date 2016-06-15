#
# LSST Data Management System
#
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <https://www.lsstcorp.org/LegalNotices/>.
#

from lsst.ip.isr import biasCorrection, flatCorrection
from lsst.meas.algorithms.detection import SourceDetectionTask
import lsst.pipe.base as pipeBase
from .isr import DecamIsrTask


def _computeEdgeSize(rawExposure, calibExposure):
    """Compute the number of edge trim pixels of the calibration product.

    Some Community Pipeline Calibration products are trimmed on their edges
    and are smaller than the raw data. Use the dimension difference between
    raw exposure and the calibration product to compute the edge trim pixels.
    @param[in] rawExposure: the data section of a raw exposure
    @param[in] calibExposure: calibration bias or flat exposure,
                              known to be smaller than raw data
    @return an integer as the number of trimmed pixels on each edge
    """
    nx, ny = rawExposure.getBBox().getDimensions() - calibExposure.getBBox().getDimensions()
    assert nx == ny, "Exposure is trimmed differently in X and Y"
    assert nx%2 == 0, "Exposure is trimmed unevenly in X"
    assert nx >= 0, "Calibration image is larger than raw data"
    return nx/2


class DecamCpIsrTask(DecamIsrTask):
    """Perform ISR task using Community Pipeline Calibration Products MasterCal

    The CP MasterCal products have butler dataset types cpBias and cpFlat,
    different from the LSST-generated calibration products (bias/flat).
    """
    def readIsrData(self, dataRef, rawExposure):
        """Retrieve necessary frames for instrument signature removal

        This is identical to IsrTask.readIsrData except the names of the
        bias/flat dataset types are cpBias/cpFlat instead.

        \param[in] dataRef -- a daf.persistence.butlerSubset.ButlerDataRef
                              of the detector data to be processed
        \param[in] rawExposure -- a reference raw exposure that will later be
                                  corrected with the retrieved calibration data;
                                  should not be modified in this method.
        \return a pipeBase.Struct with fields containing kwargs expected by run()
         - bias: exposure of bias frame
         - dark: exposure of dark frame
         - flat: exposure of flat field
         - defects: list of detects
         - fringeStruct: a pipeBase.Struct with field fringes containing
                         exposure of fringe frame or list of fringe exposure
        """
        ccd = rawExposure.getDetector()

        biasExposure = self.getIsrExposure(dataRef, "cpBias") if self.config.doBias else None
        # immediate=True required for functors and linearizers are functors; see ticket DM-6515
        linearizer = dataRef.get("linearizer", immediate=True) if self.doLinearize(ccd) else None
        darkExposure = self.getIsrExposure(dataRef, "dark") if self.config.doDark else None
        flatExposure = self.getIsrExposure(dataRef, "cpFlat") if self.config.doFlat else None
        brighterFatterKernel = dataRef.get("brighterFatterKernel") if self.config.doBrighterFatter else None

        defectList = dataRef.get("defects")

        if self.config.doFringe and self.fringe.checkFilter(rawExposure):
            fringeStruct = self.fringe.readFringes(dataRef, assembler=self.assembleCcd \
                                              if self.config.doAssembleIsrExposures else None)
        else:
            fringeStruct = pipeBase.Struct(fringes = None)

        return pipeBase.Struct(bias = biasExposure,
                               linearizer = linearizer,
                               dark = darkExposure,
                               flat = flatExposure,
                               defects = defectList,
                               fringes = fringeStruct,
                               bfKernel = brighterFatterKernel
                               )

    def biasCorrection(self, exposure, biasExposure):
        """Apply bias correction in place

        DECam bias products have been trimmed and are smaller than
        the raw exposure.  The size of edge trim is computed based
        on the dimensions of the input data.  Only process the inner
        part of the raw exposure, and mask the outer pixels as EDGE.

        @param[in,out] exposure: exposure to process
        @param[in] biasExposure: bias exposure
        """
        nEdge = _computeEdgeSize(exposure, biasExposure)
        if nEdge > 0:
            rawMaskedImage = exposure.getMaskedImage()[nEdge:-nEdge,
                                                       nEdge:-nEdge]
        else:
            rawMaskedImage = exposure.getMaskedImage()
        biasCorrection(rawMaskedImage, biasExposure.getMaskedImage())
        # Mask the unprocessed edge pixels as EDGE
        SourceDetectionTask.setEdgeBits(
            exposure.getMaskedImage(),
            rawMaskedImage.getBBox(),
            exposure.getMaskedImage().getMask().getPlaneBitMask("EDGE")
        )

    def flatCorrection(self, exposure, flatExposure):
        """Apply flat correction in place

        DECam flat products have been trimmed and are smaller than
        the raw exposure.  The size of edge trim is computed based
        on the dimensions of the input data.  Only process the inner
        part of the raw exposure, and mask the outer pixels as EDGE.

        @param[in,out] exposure: exposure to process
        @param[in] flatExposure: flatfield exposure
        """
        nEdge = _computeEdgeSize(exposure, flatExposure)
        if nEdge > 0:
            rawMaskedImage = exposure.getMaskedImage()[nEdge:-nEdge,
                                                       nEdge:-nEdge]
        else:
            rawMaskedImage = exposure.getMaskedImage()
        flatCorrection(
            rawMaskedImage,
            flatExposure.getMaskedImage(),
            self.config.flatScalingType,
            self.config.flatUserScale
        )
        # Mask the unprocessed edge pixels as EDGE
        SourceDetectionTask.setEdgeBits(
            exposure.getMaskedImage(),
            rawMaskedImage.getBBox(),
            exposure.getMaskedImage().getMask().getPlaneBitMask("EDGE")
        )
