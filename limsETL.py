from conf import settings
import requests
import os
import urllib3
urllib3.disable_warnings()

class ETLExceptions(Exception):
    code = None

class LIMSRequestException(ETLExceptions):
    """
    Failed to get response from LIMS or data not in the right format
    """
    code = 101

class Sample:
    # 'investigatorSampleId',
    # 'igoSampleId',
    # 'igocomplete',
    #
    def __init__(self,sampleJson):
        self.__dict__=sampleJson

class RequestSamples:
    # 'dataAccessEmails',
    # 'dataAnalystEmail',
    # 'dataAnalystName',
    # 'investigatorEmail',
    # 'investigatorName',
    # 'labHeadEmail',
    # 'labHeadName',
    # 'otherContactEmails',
    # 'piEmail',
    # 'pooledNormals',
    # 'projectManagerName',
    # 'qcAccessEmails',
    # 'recipe',
    # 'requestId',
    # 'samples',
    # 'strand'
    #
    def __init__(self,reqSampsJson):
        self.__dict__=reqSampsJson
        self.samples=[Sample(x) for x in self.samples]

class Run:
    # 'fastqs',
    # 'flowCellId',
    # 'flowCellLanes',
    # 'readLength',
    # 'runDate',
    # 'runId',
    # 'runMode'
    #
    def __init__(self,runJson):
        self.__dict__=runJson
        self.runType=self.getRunType()
        self.runId=self.getRunId()
        self.fastqDir=os.path.dirname(self.fastqs[0])


    def getRunType(self):
        hasR2File=len([x for x in self.fastqs if x.find("_R2_")>-1])==1
        if hasR2File:
            return("PE")
        else:
            return("SE")

    def getRunId(self):
        pp=self.fastqs[0].find("/FASTQ/")
        return self.fastqs[0][pp:].split("/")[2]



class Library:
    # 'barcodeId',
    # 'barcodeIndex',
    # 'captureConcentrationNm',
    # 'captureInputNg',
    # 'captureName',
    # 'dnaInputNg',
    # 'libraryConcentrationNgul',
    # 'libraryIgoId',
    # 'libraryVolume',
    # 'runs'
    #
    def __init__(self,libraryJson):
        self.__dict__=libraryJson
        self.runs=[Run(x) for x in self.runs]

class SampleManifest:
    # 'baitSet',
    # 'cfDNA2dBarcode',
    # 'cmoPatientId',
    # 'cmoSampleClass',
    # 'cmoSampleName',
    # 'collectionYear',
    # 'igoId',
    # 'investigatorSampleId',
    # 'libraries',
    # 'oncoTreeCode',
    # 'preservation',
    # 'qcReports',
    # 'sampleName',
    # 'sampleOrigin',
    # 'sex',
    # 'species',
    # 'specimenType',
    # 'tissueLocation',
    # 'tumorOrNormal'
    #
    def __init__(self,sampMetaDataJson):
        self.__dict__=sampMetaDataJson
        self.libraries=[Library(x) for x in self.libraries]


def getDeliveries(timestamp):
    requestIds = requests.get('%s/getDeliveries' % settings.LIMS_ROOT_URL,
                              params={"timestamp": timestamp},
                              auth=(settings.LIMS_USERNAME, settings.LIMS_PASSWORD), verify=False)
    if requestIds.status_code != 200:
        raise LIMSRequestException("Failed to fetch new requests")
    if not requestIds.json():
        logger.info("There is no new RequestIDs")
        return []
    else:
        return requestIds.json()

def getRequestSamples(request_id):
    limsRequest = requests.get('%s/getRequestSamples' % settings.LIMS_ROOT_URL,
                            params={"request": request_id},
                            auth=(settings.LIMS_USERNAME, settings.LIMS_PASSWORD), verify=False)
    if limsRequest.status_code != 200:
        raise LIMSRequestException("Failed to fetch request_id %s" % request_id)
    if limsRequest.json()['requestId']!=request_id:
        raise LIMSRequestException("Invalid LIMS record requestId!=request_id [%s,%s]" % (limsRequest.json()['requestId'],request_id))
    else:
        return RequestSamples(limsRequest.json())

def getSampleManifest(sample_id):
    sampleMetadata = requests.get('%s/getSampleManifest' % settings.LIMS_ROOT_URL,
                            params={"igoSampleId": sample_id},
                            auth=(settings.LIMS_USERNAME, settings.LIMS_PASSWORD), verify=False)

    if sampleMetadata.status_code != 200:
        raise LIMSRequestException("Failed to fetch SampleManifest for sampleId:%s" % sample_id)
    try:
        data = sampleMetadata.json()[0]
    except Exception as e:
        raise LIMSRequestException(
            "Failed to fetch SampleManifest for sampleId:%s. Invalid response" % sample_id)
    if data['igoId'] != sample_id:
        raise LIMSRequestException(
            "Failed to fetch SampleManifest for sampleId:%s. LIMS returned %s " % (sample_id, data['igoId']))
    else:
        return SampleManifest(sampleMetadata.json()[0])
