#!/usr/bin/env python3

import limsETL

def getSampleMappingData(sampleObj):
    sampleMappingData=[]
    for lib in sampleObj.libraries:
        for runs in lib.runs:
            sampleMappingData.append([runs.runId,runs.fastqDir,runs.runType])

    return(sampleMappingData)

if __name__ == "__main__":

    import sys

    projectNo=sys.argv[1]
    print("\n  Project No = %s\n" % projectNo)

    requestData=limsETL.getRequestSamples(projectNo)
    samples=[limsETL.getSampleManifest(xx.igoSampleId) for xx in requestData.samples]

    #
    # Dump request file
    #

    requestFieldsToIgnore=set(("samples","pooledNormals"))

    requestFile="Proj_%s_request.txt" % projectNo
    mappingFile="Proj_%s_sample_mapping.txt" % projectNo

    with open(requestFile,"w") as fp:
        for rField in requestData.__dict__:
            if rField not in requestFieldsToIgnore:
                fp.write("%s: %s\n" % (rField,getattr(requestData,rField)))

    with open(mappingFile,"w") as fp:
        for sample in samples:
            out0=["_1","s_"+sample.investigatorSampleId]
            for ri in getSampleMappingData(sample):
                out=out0+ri
                fp.write(("\t".join(out)+"\n"))
