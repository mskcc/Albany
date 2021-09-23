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
        self.json=sampleJson
    def __str__(self):
        try:
            return "<limsETL.Sample %s %s %s>" % (
                self.investigatorSampleId,
                self.igoSampleId,
                self.igoComplete
                )
        except AttributeError as e:
            print("\n\n",self.json,"\n\n")
            raise e

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

def getRunId(fastqPath):
    pp=fastqPath.find("/FASTQ/")
    return fastqPath[pp:].split("/")[2]

class MachineRuns:
    def __init__(self,fastqi):
        self.fastqDir=os.path.dirname(fastqi)
        self.runId=getRunId(fastqi)
        self.runType="SE"

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
        machineRuns=dict()
        if len(self.fastqs)>0:
            for fastqi in self.fastqs:
                if getRunId(fastqi) not in machineRuns:
                    machineRuns[getRunId(fastqi)]=MachineRuns(fastqi)
                if fastqi.find("_R2_")>-1:
                    machineRuns[getRunId(fastqi)].runType="PE"

            self.machineRuns=machineRuns

        else:
            self.machineRuns=None



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
